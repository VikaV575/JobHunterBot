import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


SAP_ISRAEL_URL = (
    "https://jobs.sap.com/go/Israel/8807501/"
    "?q=&sortColumn=sort_title&sortDirection=desc"
)

JOB_LINK_PATTERN = re.compile(
    r"/job/.+/\d+/?$",
    re.IGNORECASE,
)

ISRAEL_LOCATION_HINTS = [
    "Israel",
    "IL",
    "Ra'anana",
    "Raanana",
    "Tel Aviv",
    "Herzliya",
    "Haifa",
]


def _nearest_context(link):
    fallback = link.get_text(" ", strip=True)

    for parent in link.parents:
        if getattr(parent, "name", None) not in {
            "tr",
            "li",
            "article",
            "section",
            "div",
        }:
            continue

        text = parent.get_text(" ", strip=True)

        if not text:
            continue

        if len(text) <= 2000:
            fallback = text

        lowered = text.lower()

        if (
            " il" in lowered
            or "israel" in lowered
            or "ra'anana" in lowered
            or "raanana" in lowered
        ):
            return text

    return fallback


def _extract_location(context):
    lowered = context.lower()

    if "ra'anana" in lowered or "raanana" in lowered:
        return "Ra'anana, Israel"

    if "tel aviv" in lowered:
        return "Tel Aviv, Israel"

    if "herzliya" in lowered:
        return "Herzliya, Israel"

    if "haifa" in lowered:
        return "Haifa, Israel"

    if " israel" in f" {lowered}" or " il" in f" {lowered}":
        return "Israel"

    return ""


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if not JOB_LINK_PATTERN.search(href):
            continue

        title = link.get_text(" ", strip=True)

        if not title or len(title) > 220:
            continue

        url = urljoin("https://jobs.sap.com", href)
        context = _nearest_context(link)
        location = _extract_location(context)

        if not location:
            continue

        jobs[url] = {
            "title": title,
            "company_name": "SAP",
            "location": location,
            "url": url,
            "description": context,
            "source": "SAP Careers",
        }

    return list(jobs.values())


async def get_sap_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(SAP_ISRAEL_URL)
            response.raise_for_status()

    except httpx.HTTPError as error:
        print(
            "Failed getting SAP Careers: "
            f"{type(error).__name__}: {error}"
        )
        return []

    jobs = _parse_page(response.text)
    print(f"SAP Careers: {len(jobs)} Israel jobs")
    return jobs
