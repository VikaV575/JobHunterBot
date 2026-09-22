from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


MICROSOFT_ISRAEL_URL = (
    "https://careers.microsoft.com/v2/global/en/locations/israel.html"
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

        if 30 <= len(text) <= 5000:
            fallback = text

        if "qualifications" in text.lower():
            return text

    return fallback


def _extract_title(link):
    for parent in [link, *list(link.parents)[:5]]:
        heading = parent.find(["h2", "h3", "h4"])
        if heading:
            title = heading.get_text(" ", strip=True)
            if title:
                return title

    return link.get_text(" ", strip=True)


async def get_microsoft_jobs():
    jobs = []
    seen = set()

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
            response = await client.get(MICROSOFT_ISRAEL_URL)
            response.raise_for_status()

        except httpx.HTTPError as error:
            print(
                f"Failed getting Microsoft Careers: {error}"
            )
            return []

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        is_job_link = (
            "apply.careers.microsoft.com" in href
            or "jobdetail" in href.lower()
        )

        if not is_job_link:
            continue

        url = urljoin(MICROSOFT_ISRAEL_URL, href)

        if url in seen:
            continue

        context = _nearest_context(link)
        title = _extract_title(link)

        if not title or title.lower() in {
            "see details",
            "apply",
        }:
            heading = None

            for parent in list(link.parents)[:5]:
                heading = parent.find(["h2", "h3", "h4"])

                if heading:
                    break

            if heading:
                title = heading.get_text(" ", strip=True)

        if not title:
            continue

        seen.add(url)

        jobs.append({
            "title": title,
            "company_name": "Microsoft",
            "location": "Israel",
            "url": url,
            "description": context,
            "source": "Microsoft Careers",
        })

    return jobs
