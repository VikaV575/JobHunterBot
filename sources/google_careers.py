from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


GOOGLE_SEARCH_URL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
)

MAX_PAGES = 8

ISRAEL_LOCATION_HINTS = [
    "Tel Aviv",
    "Tel-Aviv",
    "Haifa",
    "Herzliya",
    "Jerusalem",
    "Petah Tikva",
    "Petah-Tikva",
    "Ramat Gan",
    "Caesarea",
    "Yokneam",
    "Ra'anana",
    "Raanana",
    "Rehovot",
    "Israel",
]


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

        if 20 <= len(text) <= 4500:
            fallback = text

        if any(
            marker.lower() in text.lower()
            for marker in ISRAEL_LOCATION_HINTS
        ):
            return text

    return fallback


def _extract_title(link, context):
    for parent in [link, *list(link.parents)[:4]]:
        heading = parent.find(["h2", "h3", "h4"])
        if heading:
            title = heading.get_text(" ", strip=True)
            if title:
                return title

    title = link.get_text(" ", strip=True)

    if title and len(title) < 180:
        return title

    path = link.get("href", "").rstrip("/").split("/")[-1]
    slug = path.split("-", 1)[-1]
    return slug.replace("-", " ").strip().title()


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

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if "/about/careers/applications/jobs/results/" not in href:
            continue

        url = urljoin("https://www.google.com", href)
        context = _nearest_context(link)
        title = _extract_title(link, context)

        if not title:
            continue

        jobs[url] = {
            "title": title,
            "company_name": "Google",
            "location": _extract_location(context),
            "url": url,
            "description": context,
            "source": "Google Careers",
        }

    return list(jobs.values())


async def get_google_careers_jobs():
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
                "location": "Israel",
                "page": page,
                "sort_by": "date",
            }

            try:
                response = await client.get(
                    GOOGLE_SEARCH_URL,
                    params=params,
                )
                response.raise_for_status()

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Google Careers page "
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
                break

            for job in new_jobs:
                seen_urls.add(job["url"])
                jobs.append(job)

    return jobs
