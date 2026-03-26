"""Scheduler — manages recurring content schedules and processes due jobs."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import job_queue
import manager_agent
from config import load_site_config

logger = logging.getLogger(__name__)

SCHEDULES_PATH = Path(__file__).parent / "schedules.json"


def load_schedules() -> list[dict]:
    if SCHEDULES_PATH.exists():
        return json.loads(SCHEDULES_PATH.read_text())
    return []


def save_schedules(schedules: list[dict]):
    SCHEDULES_PATH.write_text(json.dumps(schedules, indent=2))


def add_schedule(brief: str, frequency: str = "weekly", day: str = "monday") -> dict:
    """Add a recurring schedule.

    Args:
        brief: The brief text to send to Max each cycle.
        frequency: 'daily' or 'weekly'.
        day: Day of week for weekly (monday-sunday). Ignored for daily.

    Returns:
        The new schedule dict.
    """
    schedules = load_schedules()
    schedule = {
        "id": len(schedules) + 1,
        "brief": brief,
        "frequency": frequency,
        "day": day.lower(),
        "active": True,
        "last_run": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    schedules.append(schedule)
    save_schedules(schedules)
    logger.info("Schedule added: %s (%s)", brief[:50], frequency)
    return schedule


def remove_schedule(schedule_id: int):
    schedules = load_schedules()
    schedules = [s for s in schedules if s.get("id") != schedule_id]
    save_schedules(schedules)


def check_and_queue():
    """Check all schedules and queue any that are due.

    Call this on a cron or at startup. It's idempotent — won't double-queue.
    """
    schedules = load_schedules()
    now = datetime.now(timezone.utc)
    today = now.strftime("%A").lower()
    today_date = now.strftime("%Y-%m-%d")
    site_config = load_site_config()
    queued = 0

    for schedule in schedules:
        if not schedule.get("active"):
            continue

        # Check if already run today
        if schedule.get("last_run", "").startswith(today_date):
            continue

        should_run = False
        if schedule["frequency"] == "daily":
            should_run = True
        elif schedule["frequency"] == "weekly" and today == schedule.get("day", "monday"):
            should_run = True

        if should_run:
            logger.info("Schedule %d is due: %s", schedule["id"], schedule["brief"][:50])

            # Use Manager to parse the brief into jobs
            result = manager_agent.run(schedule["brief"], site_config)
            jobs = result.get("jobs", [])

            if jobs:
                job_queue.add_batch(jobs)
                logger.info("Queued %d jobs from schedule %d", len(jobs), schedule["id"])
                queued += len(jobs)

            schedule["last_run"] = now.isoformat()

    save_schedules(schedules)
    return queued


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        n = check_and_queue()
        print(f"Queued {n} jobs from schedules")
    else:
        print("Usage:")
        print("  python scheduler.py check  — check schedules and queue due jobs")
        print("\nCurrent schedules:")
        for s in load_schedules():
            print(f"  [{s['id']}] {s['frequency']} ({s.get('day', 'daily')}): {s['brief'][:60]}")
