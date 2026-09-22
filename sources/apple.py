import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


APPLE_SEARCH_URL = "https://jobs.apple.com/en-il/search"

# Apple keeps stale roles around for a long time. For this bot, freshness is
# more important than completeness, so undated/old roles are excluded.
MAX_JOB_AGE_DAYS = 60

ISRAEL_LOCATION_HINTS = [
    "Herzliya",
    "Haifa",
    "Tel Aviv",
    "Tel-Aviv",
    "Jerusalem",
    "Ramat Gan",
    "Israel",
]

DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\s+(\d{4})\b",
    re.IGNORECASE,
)


def _extract_posted_date(text):
    match = DATE_PATTERN.search(text)

    if not match:
        return None

    day, month, year = match.groups()

    if month.lower() == "sept":
        month = "Sep"

    try:
        return datetime.strptime(
            f"{day} {month} {year}",
            "%d %b %Y",
        ).date()
    except ValueError:
        return None


def _job_context(link):
    """
    Find the Apple result card that contains both the role details and
    posting date. The previous implementation stopped too early at a
    smaller parent that contained the role number but not the date.
    """
    fallback = link.get_text(" ", strip=True)

    for parent in link.parents:
        if getattr(parent, "name", None) not in {
            "li",
            "article",
            "section",
            "div",
        }:
            continue

        text = parent.get_text(" ", strip=True)

        if 20 <= len(text) <= 5000:
            fallback = text

        if (
            "role number" in text.lower()
            and _extract_posted_date(text) is not None
        ):
            return text

    return fallback


def _extract_title(link):
    for parent in [link, *list(link.parents)[:5]]:
        if not hasattr(parent, "find"):
            continue

        heading = parent.find(["h2", "h3", "h4"])

        if heading:
            title = heading.get_text(" ", strip=True)

            if title:
                return title

    title = link.get_text(" ", strip=True)

    if title and "full role description" not in title.lower():
        return title

    path = link.get("href", "").rstrip("/").split("/")[-1]
    return path.replace("-", " ").strip().title()


def _extract_location(context):
    matches = [
        marker
        for marker in ISRAEL_LOCATION_HINTS
        if marker.lower() in context.lower()
    ]

    if matches:
        return ", ".join(dict.fromkeys(matches))

    return "Israel"


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}

    cutoff = date.today() - timedelta(
        days=MAX_JOB_AGE_DAYS
    )

    skipped_old = 0
    skipped_undated = 0

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if "/en-il/details/" not in href:
            continue

        url = urljoin("https://jobs.apple.com", href)

        if url in jobs:
            continue

        context = _job_context(link)
        title = _extract_title(link)
        posted_date = _extract_posted_date(context)

        if not title:
            continue

        # Important: do NOT keep undated Apple roles. That fallback was the
        # reason stale 2024/2025 positions were still getting through.
        if posted_date is None:
            skipped_undated += 1
            continue

        if posted_date < cutoff:
            skipped_old += 1
            continue

        jobs[url] = {
            "title": title,
            "company_name": "Apple",
            "location": _extract_location(context),
            "url": url,
            "description": context,
            "source": "Apple Careers",
            "posted_date": posted_date.isoformat(),
        }

    print(
        "Apple freshness filter: "
        f"{len(jobs)} kept, "
        f"{skipped_old} old skipped, "
        f"{skipped_undated} undated skipped"
    )

    return list(jobs.values())


async def get_apple_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    params = {
        "location": "israel-ISR",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                APPLE_SEARCH_URL,
                params=params,
            )
            response.raise_for_status()

    except httpx.HTTPError as error:
        print(f"Failed getting Apple Careers: {error}")
        return []

    jobs = _parse_page(response.text)

    print(
        f"Apple Careers: {len(jobs)} fresh roles "
        f"(last {MAX_JOB_AGE_DAYS} days)"
    )

    return jobs
