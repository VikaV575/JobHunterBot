import asyncio
from datetime import date, datetime, timedelta
import re
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup


IAI_BASE = "https://jobs.iai.co.il"
IAI_SITEMAP = f"{IAI_BASE}/wp-sitemap.xml"

MAX_JOB_AGE_DAYS = 180
MAX_JOB_PAGES = 140
DETAIL_CONCURRENCY = 6

STUDENT_MARKERS = [
    "סטודנט",
    "student",
    "intern",
]

TECH_MARKERS = [
    "תוכנה",
    "פיתוח",
    "python",
    "c++",
    "c#",
    "java",
    "אלגורית",
    "וריפיק",
    "וליד",
    "אימות",
    "קושחה",
    "firmware",
    "software",
    "validation",
    "verification",
    "embedded",
    "סייבר",
    "cyber",
    "מערכות מידע",
    "data",
    "ai",
    "machine learning",
]

LOCATION_MARKERS = [
    "באר יעקב",
    "יהוד",
    "אשדוד",
    'נתב"ג',
    "לוד",
    "תל אביב",
    "חיפה",
    "ירושלים",
    "באר שבע",
]


def _xml_locs(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []

    for element in root.iter():
        if element.tag.endswith("url"):
            loc = ""
            lastmod = ""

            for child in element:
                if child.tag.endswith("loc"):
                    loc = (child.text or "").strip()
                elif child.tag.endswith("lastmod"):
                    lastmod = (child.text or "").strip()

            if loc:
                items.append((loc, lastmod))

        elif element.tag.endswith("sitemap"):
            loc = ""

            for child in element:
                if child.tag.endswith("loc"):
                    loc = (child.text or "").strip()

            if loc:
                items.append((loc, ""))

    return items


def _parse_lastmod(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except ValueError:
        try:
            return datetime.strptime(
                value[:10],
                "%Y-%m-%d",
            ).date()
        except ValueError:
            return None


def _is_recent(lastmod):
    parsed = _parse_lastmod(lastmod)

    if parsed is None:
        return True

    cutoff = date.today() - timedelta(
        days=MAX_JOB_AGE_DAYS
    )

    return parsed >= cutoff


def _extract_location(text):
    for marker in LOCATION_MARKERS:
        if marker in text:
            return marker

    return "Israel"


def _parse_job_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    lowered = text.lower()

    if not any(
        marker.lower() in lowered
        for marker in STUDENT_MARKERS
    ):
        return None

    if not any(
        marker.lower() in lowered
        for marker in TECH_MARKERS
    ):
        return None

    title_node = soup.find("h1")

    if title_node:
        title = title_node.get_text(" ", strip=True)
    else:
        title = ""

    if not title:
        title_node = soup.find(
            ["h2", "h3"],
            string=re.compile("סטודנט|student", re.IGNORECASE),
        )

        if title_node:
            title = title_node.get_text(" ", strip=True)

    if not title:
        return None

    return {
        "title": title,
        "company_name": "IAI",
        "location": _extract_location(text),
        "url": url,
        "description": text[:20000],
        "source": "IAI Careers",
    }


async def _fetch_job(
    semaphore,
    client,
    url,
):
    async with semaphore:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        return _parse_job_page(
            response.text,
            url,
        )


async def _discover_job_urls(client):
    try:
        response = await client.get(IAI_SITEMAP)
        response.raise_for_status()
    except httpx.HTTPError as error:
        print(
            f"Failed getting IAI sitemap: "
            f"{type(error).__name__}: {error}"
        )
        return []

    root_items = _xml_locs(response.text)

    child_sitemaps = [
        loc
        for loc, _ in root_items
        if "job" in loc.lower()
    ]

    # Some WordPress installations do not expose an obvious job-named
    # child sitemap. Try the standard custom-post-type sitemap as fallback.
    if not child_sitemaps:
        child_sitemaps = [
            f"{IAI_BASE}/wp-sitemap-posts-job-1.xml",
            f"{IAI_BASE}/wp-sitemap-posts-jobs-1.xml",
        ]

    candidates = []

    for sitemap_url in child_sitemaps[:4]:
        try:
            sitemap_response = await client.get(
                sitemap_url
            )
            sitemap_response.raise_for_status()
        except httpx.HTTPError:
            continue

        for loc, lastmod in _xml_locs(
            sitemap_response.text
        ):
            if "/job/" not in loc:
                continue

            if not _is_recent(lastmod):
                continue

            candidates.append(loc)

    return list(dict.fromkeys(candidates))[
        :MAX_JOB_PAGES
    ]


async def get_iai_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        urls = await _discover_job_urls(client)

        if not urls:
            print("IAI Careers: 0 discovered job URLs")
            return []

        semaphore = asyncio.Semaphore(
            DETAIL_CONCURRENCY
        )

        results = await asyncio.gather(
            *(
                _fetch_job(
                    semaphore,
                    client,
                    url,
                )
                for url in urls
            )
        )

    jobs = [
        job
        for job in results
        if job is not None
    ]

    print(
        f"IAI Careers: {len(jobs)} "
        "technical student jobs"
    )

    return jobs
