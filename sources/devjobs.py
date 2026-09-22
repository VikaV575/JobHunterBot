import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


DEVJOBS_BASE = "https://devjobs.co.il"

DEVJOBS_LIST_URLS = [
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Software",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Backend",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Embedded",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Cloud%2FDevOps",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=AI%2FML",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Mobile",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Full+Stack",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Frontend",
    f"{DEVJOBS_BASE}/jobs-grid?developerTypes=Data+%26+Analytics",
]

STUDENT_TITLE_SIGNALS = [
    "student",
    "intern",
    "entry level",
    "entry-level",
    "סטודנט",
    "מתמחה",
]

ISRAEL_LOCATION_PATTERNS = [
    ("Tel Aviv", r"\bTel[- ]Aviv(?:-Yafo)?\b"),
    ("Haifa", r"\bHaifa\b"),
    ("Yokneam", r"\bYokneam\b|\bYoqneam\b"),
    ("Herzliya", r"\bHerzliya\b"),
    ("Raanana", r"\bRa['’]?anana\b|\bRaanana\b"),
    ("Petah Tikva", r"\bPet(?:ah|ach)[- ]Tikva\b"),
    ("Netanya", r"\bNetanya\b"),
    ("Ness Ziona", r"\bNess[- ]Ziona\b"),
    ("Rehovot", r"\bRehovot\b"),
    ("Jerusalem", r"\bJerusalem\b"),
    ("Ramat Gan", r"\bRamat[- ]Gan\b"),
    ("Holon", r"\bHolon\b"),
    ("Ashdod", r"\bAshdod\b"),
    ("Beer Sheva", r"\bBe['’]?er[- ]Sheva\b|\bBeer[- ]Sheva\b"),
    ("Israel", r"\bIsrael\b"),
]

DETAIL_CONCURRENCY = 6


def _looks_student_title(title):
    lowered = title.lower()

    return any(
        signal in lowered
        for signal in STUDENT_TITLE_SIGNALS
    )


def _nearest_card(link):
    fallback = link.parent

    for parent in link.parents:
        if getattr(parent, "name", None) not in {
            "article",
            "li",
            "section",
            "div",
        }:
            continue

        text = parent.get_text(" ", strip=True)

        if not text:
            continue

        if len(text) <= 1800:
            fallback = parent

        if (
            "years" in text.lower()
            or "year" in text.lower()
            or "hybrid" in text.lower()
            or "on-site" in text.lower()
            or "remote" in text.lower()
        ):
            return parent

    return fallback


def _company_from_card(card, title_link):
    if card is None:
        return ""

    anchors = card.find_all("a", href=True)

    try:
        title_index = anchors.index(title_link)
    except ValueError:
        title_index = len(anchors)

    for anchor in reversed(anchors[:title_index]):
        text = anchor.get_text(" ", strip=True)
        href = anchor.get("href", "")

        if (
            text
            and len(text) <= 120
            and "/job-details/" not in href
            and "/public/job-details/" not in href
        ):
            return text

    # Some cards put the company link after the title.
    for anchor in anchors[title_index + 1:]:
        text = anchor.get_text(" ", strip=True)
        href = anchor.get("href", "")

        if (
            text
            and len(text) <= 120
            and "/job-details/" not in href
            and "/public/job-details/" not in href
        ):
            return text

    return ""


def _extract_location(text):
    locations = []

    for label, pattern in ISRAEL_LOCATION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            locations.append(label)

    if locations:
        return ", ".join(dict.fromkeys(locations))

    # DevJobs is Israel-specific. Keep a generic country location if the
    # card does not expose a city in a format we recognize.
    return "Israel"


def _parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if (
            "/job-details/" not in href
            and "/public/job-details/" not in href
        ):
            continue

        title = link.get_text(" ", strip=True)

        if not title or not _looks_student_title(title):
            continue

        url = urljoin(DEVJOBS_BASE, href)
        card = _nearest_card(link)
        context = (
            card.get_text(" ", strip=True)
            if card is not None
            else title
        )
        company = _company_from_card(card, link)

        candidates[url] = {
            "title": title,
            "company_name": company or "Unknown company",
            "location": _extract_location(context),
            "url": url,
            "description": context,
            "source": "DevJobs",
        }

    return list(candidates.values())


def _detail_text_and_status(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    is_closed = (
        "no longer accepting applications" in text.lower()
    )

    return text[:20000], is_closed


async def _enrich_candidate(
    semaphore,
    client,
    candidate,
):
    async with semaphore:
        try:
            response = await client.get(candidate["url"])
            response.raise_for_status()

        except httpx.HTTPError:
            # The listing still contains enough information to score it.
            return candidate

        description, is_closed = _detail_text_and_status(
            response.text
        )

        if is_closed:
            return None

        if description:
            candidate["description"] = description

        return candidate


async def get_devjobs_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    timeout = httpx.Timeout(20.0, connect=10.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    ) as client:
        listing_responses = await asyncio.gather(
            *(
                client.get(url)
                for url in DEVJOBS_LIST_URLS
            ),
            return_exceptions=True,
        )

        candidates = {}

        for response in listing_responses:
            if isinstance(response, Exception):
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPError:
                continue

            for job in _parse_listing(response.text):
                candidates[job["url"]] = job

        semaphore = asyncio.Semaphore(
            DETAIL_CONCURRENCY
        )

        enriched = await asyncio.gather(
            *(
                _enrich_candidate(
                    semaphore,
                    client,
                    candidate,
                )
                for candidate in candidates.values()
            )
        )

    jobs = [
        job
        for job in enriched
        if job is not None
    ]

    print(
        f"DevJobs: {len(jobs)} open student/entry-level "
        "tech candidates"
    )

    return jobs
