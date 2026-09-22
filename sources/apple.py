import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


APPLE_SEARCH_URL = "https://jobs.apple.com/en-il/search"

# Apple keeps some very old roles visible in search results. We only keep
# recently posted roles so stale 2024/2025 listings do not dominate the feed.
MAX_JOB_AGE_DAYS = 90
MAX_PAGES = 8

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


def _nearest_context(link):
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

        if 20 <= len(text) <= 3500:
            fallback = text

        if "role number" in text.lower():
            return text

    return fallback


def _extract_title(link):
    for parent in [link, *list(link.parents)[:4]]:
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


def _extract_posted_date(context):
    match = DATE_PATTERN.search(context)

    if not match:
        return None

    day, month, year = match.groups()

    # Apple sometimes writes September as "Sept" rather than "Sep".
    if month.lower() == "sept":
        month = "Sep"

    try:
        return datetime.strptime(
            f"{day} {month} {year}",
            "%d %b %Y",
        ).date()

    except ValueError:
        return None


def _is_recent(posted_date):
    if posted_date is None:
        # If Apple changes the markup and we cannot find the date,
        # keep the role rather than accidentally losing a new posting.
        return True

    cutoff = date.today() - timedelta(
        days=MAX_JOB_AGE_DAYS
    )

    return posted_date >= cutoff


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if "/en-il/details/" not in href:
            continue

        url = urljoin("https://jobs.apple.com", href)
        context = _nearest_context(link)
        title = _extract_title(link)

        if not title:
            continue

        posted_date = _extract_posted_date(context)

        if not _is_recent(posted_date):
            continue

        jobs[url] = {
            "title": title,
            "company_name": "Apple",
            "location": _extract_location(context),
            "url": url,
            "description": context,
            "source": "Apple Careers",
            "posted_date": (
                posted_date.isoformat()
                if posted_date
                else ""
            ),
        }

    return list(jobs.values())


async def get_apple_jobs():
    jobs = []
    seen_urls = set()

    headers = {
        "User-Agent": "Mozilla/5.0 JobHunterBot/1.0",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        for page in range(1, MAX_PAGES + 1):
            params = {
                "location": "israel-ISR",
                "page": page,
            }

            try:
                response = await client.get(
                    APPLE_SEARCH_URL,
                    params=params,
                )
                response.raise_for_status()

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Apple Careers page "
                    f"{page}: {error}"
                )
                break

            page_jobs = _parse_page(response.text)
            new_jobs = [
                job
                for job in page_jobs
                if job["url"] not in seen_urls
            ]

            if not new_jobs:
                # Apple sorts this search by newest. Once a page contains
                # no recent roles, later pages are normally older as well.
                break

            for job in new_jobs:
                seen_urls.add(job["url"])
                jobs.append(job)

    print(
        f"Apple Careers: keeping {len(jobs)} roles "
        f"posted in the last {MAX_JOB_AGE_DAYS} days"
    )

    return jobs
