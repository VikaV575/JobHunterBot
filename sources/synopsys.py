import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


SYNOPSYS_ISRAEL_URL = "https://careers.synopsys.com/jobs-in-israel"

LOCATION_PATTERN = re.compile(
    r"\b(Raanana|Ra'anana|Haifa|Herzliya|Tel Aviv|Israel)\b",
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

        if 20 <= len(text) <= 2500:
            fallback = text

        if "job id" in text.lower():
            return text

    return fallback


def _clean_title(text):
    text = re.sub(r"^Save\s+", "", text, flags=re.IGNORECASE)

    match = LOCATION_PATTERN.search(text)

    if match:
        text = text[:match.start()]

    return text.strip(" -|")


async def get_synopsys_jobs():
    headers = {
        "User-Agent": "Mozilla/5.0 JobHunterBot/1.0",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(SYNOPSYS_ISRAEL_URL)
            response.raise_for_status()

        except httpx.HTTPError as error:
            print(
                f"Failed getting Synopsys Careers: {error}"
            )
            return []

    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if "/job/" not in href:
            continue

        url = urljoin(SYNOPSYS_ISRAEL_URL, href)

        if url in seen:
            continue

        context = _nearest_context(link)
        title = _clean_title(
            link.get_text(" ", strip=True)
        )

        if not title:
            continue

        locations = LOCATION_PATTERN.findall(context)
        location = ", ".join(dict.fromkeys(locations))

        if "israel" not in context.lower():
            continue

        seen.add(url)

        jobs.append({
            "title": title,
            "company_name": "Synopsys",
            "location": location or "Israel",
            "url": url,
            "description": context,
            "source": "Synopsys Careers",
        })

    return jobs
