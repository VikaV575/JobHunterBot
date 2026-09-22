import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


ORACLE_HCM_SITES = {
    "Texas Instruments": {
        "url": (
            "https://edbz.fa.us2.oraclecloud.com/"
            "hcmUI/CandidateExperience/en/sites/CX/jobs"
        ),
        "source": "Texas Instruments Careers",
    },
}

JOB_HREF_PATTERN = re.compile(
    r"/hcmUI/CandidateExperience/en/sites/CX/job/\d+",
    re.IGNORECASE,
)

ISRAEL_MARKERS = [
    "israel",
    "ra'anana",
    "raanana",
    "tel aviv",
    "herzliya",
    "haifa",
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

        if not text:
            continue

        if len(text) <= 2500:
            fallback = text

        if any(
            marker in text.lower()
            for marker in ISRAEL_MARKERS
        ):
            return text

    return fallback


def _extract_location(text):
    lowered = text.lower()

    if "ra'anana" in lowered or "raanana" in lowered:
        return "Ra'anana, Israel"

    if "tel aviv" in lowered:
        return "Tel Aviv, Israel"

    if "herzliya" in lowered:
        return "Herzliya, Israel"

    if "haifa" in lowered:
        return "Haifa, Israel"

    if "israel" in lowered:
        return "Israel"

    return ""


def _parse_jobs(html, base_url, company_name, source_name):
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if not JOB_HREF_PATTERN.search(href):
            continue

        title = link.get_text(" ", strip=True)

        if not title or len(title) > 220:
            continue

        context = _nearest_context(link)
        location = _extract_location(context)

        if not location:
            continue

        url = urljoin(base_url, href).split("?")[0]

        jobs[url] = {
            "title": title,
            "company_name": company_name,
            "location": location,
            "url": url,
            "description": context,
            "source": source_name,
        }

    return list(jobs.values())


async def get_oracle_hcm_jobs():
    jobs = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=25.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        for company_name, config in ORACLE_HCM_SITES.items():
            try:
                response = await client.get(config["url"])
                response.raise_for_status()

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Oracle HCM jobs "
                    f"for {company_name}: "
                    f"{type(error).__name__}: {error}"
                )
                continue

            company_jobs = _parse_jobs(
                response.text,
                config["url"],
                company_name,
                config["source"],
            )

            print(
                f"Oracle HCM {company_name}: "
                f"{len(company_jobs)} Israel jobs"
            )

            jobs.extend(company_jobs)

    return jobs
