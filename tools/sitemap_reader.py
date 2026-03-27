"""Sitemap Reader Tool — fetches and parses a site's sitemap.xml.

First MCP tool. Used by Sarah (SEO) to check what's already live
before briefing new content. Prevents keyword cannibalization at source.
"""

import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SitemapPage:
    url: str
    slug: str
    section: str  # reviews, guides, bonuses
    last_modified: str | None


def fetch_sitemap(domain: str) -> list[SitemapPage]:
    """Fetch and parse sitemap.xml from a domain.

    Args:
        domain: The site domain including port, e.g. '68.183.44.120:3284'

    Returns:
        List of SitemapPage objects for all content pages.
    """
    url = f"http://{domain}/sitemap.xml"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AffiliateFactory/1.0"})
        response = urllib.request.urlopen(req, timeout=10)
        xml_data = response.read().decode()
    except Exception as e:
        logger.error("Failed to fetch sitemap from %s: %s", url, e)
        return []

    pages = []
    try:
        root = ET.fromstring(xml_data)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_elem in root.findall("sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            lastmod = url_elem.find("sm:lastmod", ns)
            if loc is None:
                continue

            page_url = loc.text.strip()

            # Extract slug and section from URL
            # e.g. http://68.183.44.120:3284/guides/how-uk-casino-bonuses-work/
            path = page_url.split("//", 1)[-1]  # remove scheme
            path = path.split("/", 1)[-1]  # remove domain
            path = path.strip("/")
            parts = path.split("/")

            # Skip index pages and taxonomy pages
            if not parts or parts[0] in ("categories", "tags", "") or len(parts) < 2:
                continue

            section = parts[0]
            slug = parts[-1] if len(parts) > 1 else ""
            if not slug:
                continue

            pages.append(SitemapPage(
                url=page_url,
                slug=slug,
                section=section,
                last_modified=lastmod.text.strip() if lastmod is not None else None,
            ))
    except ET.ParseError as e:
        logger.error("Failed to parse sitemap XML: %s", e)

    logger.info("Sitemap: %d content pages found on %s", len(pages), domain)
    return pages


def get_existing_topics(domain: str) -> str:
    """Get a formatted summary of existing content for an agent's context.

    Returns a string ready to inject into an LLM prompt.
    """
    pages = fetch_sitemap(domain)
    if not pages:
        return "No existing content found on the live site."

    lines = [f"Live content on {domain} ({len(pages)} pages):"]
    for p in pages:
        # Convert slug to readable topic: "how-uk-casino-bonuses-work" → "how uk casino bonuses work"
        topic = p.slug.replace("-", " ")
        lines.append(f"  - [{p.section}] {topic} ({p.url})")

    lines.append("")
    lines.append("DO NOT create briefs that duplicate or heavily overlap with any of the above topics.")
    lines.append("If the requested topic overlaps, find a distinct angle or long-tail variation.")

    return "\n".join(lines)


def check_overlap(domain: str, keyword: str, threshold: float = 0.5) -> list[SitemapPage]:
    """Check if a keyword overlaps with existing content.

    Uses simple word overlap scoring — not semantic, but catches obvious duplicates.

    Returns list of pages that overlap above the threshold.
    """
    pages = fetch_sitemap(domain)
    kw_words = set(keyword.lower().split())
    overlaps = []

    for p in pages:
        slug_words = set(p.slug.replace("-", " ").lower().split())
        if not kw_words or not slug_words:
            continue
        overlap = len(kw_words & slug_words) / len(kw_words)
        if overlap >= threshold:
            overlaps.append(p)

    return overlaps


if __name__ == "__main__":
    import sys
    domain = sys.argv[1] if len(sys.argv) > 1 else "68.183.44.120:3284"
    print(get_existing_topics(domain))

    if len(sys.argv) > 2:
        kw = " ".join(sys.argv[2:])
        overlaps = check_overlap(domain, kw)
        if overlaps:
            print(f"\n⚠ Overlap detected for '{kw}':")
            for p in overlaps:
                print(f"  - {p.slug} ({p.url})")
        else:
            print(f"\n✓ No overlap for '{kw}'")
