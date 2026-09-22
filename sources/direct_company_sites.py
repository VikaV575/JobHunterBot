import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


DIRECT_COMPANIES = {
    "monday.com": {
        "urls": [
            "https://monday.com/careers",
        ],
        "job_pattern": r"/careers/[0-9a-fA-F-]{30,}$",
        "prefiltered_israel": False,
    },
    "Palo Alto Networks": {
        "urls": [
            (
                "https://jobs.paloaltonetworks.com/en/location/"
                "israel-jobs/47263/294640/2"
            ),
            (
                "https://jobs.paloaltonetworks.com/en/location/"
                "israel-jobs/47263/294640/2/2"
            ),
            (
                "https://jobs.paloaltonetworks.com/en/location/"
                "israel-jobs/47263/294640/2/3"
            ),
            (
                "https://jobs.paloaltonetworks.com/en/location/"
                "israel-jobs/47263/294640/2/4"
            ),
            (
                "https://jobs.paloaltonetworks.com/en/location/"
                "israel-jobs/47263/294640/2/5"
            ),
            (
                "https://jobs.paloaltonetworks.com/en/location/"
                "israel-jobs/47263/294640/2/6"
            ),
        ],
        "job_pattern": r"/en/job/",
        "prefiltered_israel": True,
    },
    "Qualcomm": {
        "urls": [
            (
                "https://careers.qualcomm.com/careers"
                "?query=&location=Israel&domain=qualcomm.com"
            ),
        ],
        "job_pattern": r"/careers/job/\d+",
        "prefiltered_israel": False,
    },
}

# These sites currently block automated requests with HTTP 403.
# Repeated requests only add noise and contribute no jobs.
BLOCKED_DIRECT_COMPANIES = {
    "Check Point": "HTTP 403",
    "CyberArk": "HTTP 403",
}


ISRAEL_LOCATION_PATTERNS = [
    ("Tel Aviv", r"\bTel[- ]Aviv(?:-Yafo)?\b"),
    ("Petah Tikva", r"\bPet(?:ah|ach)[- ]Tikva\b"),
    ("Herzliya", r"\bHerzliya\b"),
    ("Haifa", r"\bHaifa\b"),
    ("Jerusalem", r"\bJerusalem\b"),
    ("Raanana", r"\bRa['’]?anana\b|\bRaanana\b"),
    ("Ramat Gan", r"\bRamat Gan\b"),
    ("Bnei Brak", r"\bBnei Brak\b"),
    ("Kfar Saba", r"\bKfar Saba\b"),
    ("Caesarea", r"\bCaesarea\b"),
    ("Yokneam", r"\bYokneam\b|\bYoqneam\b"),
    ("Rehovot", r"\bRehovot\b"),
    ("Ness Ziona", r"\bNess Ziona\b"),
    ("Beer Sheva", r"\bBe['’]?er Sheva\b|\bBeer Sheva\b"),
    ("Holon", r"\bHolon\b"),
    ("Israel", r"\bIsrael\b"),
    ("Israel", r"\bIL\b"),
]


GENERIC_LINK_TEXT = {
    "",
    "apply",
    "apply now",
    "learn more",
    "read more",
    "view job",
    "view position",
    "see details",
    "details",
}


def _extract_location(text, prefiltered_israel=False):
    locations = []

    for label, pattern in ISRAEL_LOCATION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            locations.append(label)

    locations = list(dict.fromkeys(locations))

    if locations:
        return ", ".join(locations)

    if prefiltered_israel:
        return "Israel"

    return ""


def _nearest_context(link):
    fallback = link.get_text(" ", strip=True)

    for parent in link.parents:
        if getattr(parent, "name", None) not in {
            "li",
            "article",
            "section",
            "div",
            "tr",
        }:
            continue

        text = parent.get_text(" ", strip=True)

        if not text:
            continue

        if len(text) <= 4500:
            fallback = text

        if _extract_location(text):
            return text

    return fallback


def _title_from_link(link, context, url):
    title = link.get_text(" ", strip=True)

    if title.lower() not in GENERIC_LINK_TEXT and len(title) <= 180:
        return title

    for parent in [link, *list(link.parents)[:6]]:
        if not hasattr(parent, "find"):
            continue

        heading = parent.find(["h1", "h2", "h3", "h4", "h5"])

        if heading:
            candidate = heading.get_text(" ", strip=True)

            if (
                candidate
                and candidate.lower() not in GENERIC_LINK_TEXT
                and len(candidate) <= 180
            ):
                return candidate

    # Last-resort title from the URL slug.
    path = urlparse(url).path.rstrip("/").split("/")[-1]
    path = re.sub(r"^\d+[-_]*", "", path)
    path = path.replace("-", " ").replace("_", " ").strip()

    if path:
        return path.title()

    # Avoid returning a giant card as a title.
    if context and len(context) <= 180:
        return context

    return ""


def _parse_link_jobs(html, page_url, company_name, config):
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}

    pattern = re.compile(
        config["job_pattern"],
        flags=re.IGNORECASE,
    )

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        absolute_url = urljoin(page_url, href).split("#")[0]

        if not pattern.search(absolute_url):
            continue

        context = _nearest_context(link)
        location = _extract_location(
            context,
            prefiltered_israel=config.get(
                "prefiltered_israel",
                False,
            ),
        )

        if not location:
            continue

        title = _title_from_link(
            link,
            context,
            absolute_url,
        )

        if not title:
            continue

        jobs[absolute_url] = {
            "title": title,
            "company_name": company_name,
            "location": location,
            "url": absolute_url,
            "description": context,
            "source": f"{company_name} Careers",
        }

    return list(jobs.values())


def _parse_playtika(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    open_roles_heading = None

    for heading in soup.find_all(["h2", "h3"]):
        if heading.get_text(" ", strip=True).upper() == "OPEN ROLES":
            open_roles_heading = heading
            break

    if open_roles_heading is None:
        return jobs

    for element in open_roles_heading.find_all_next(
        ["h2", "h3"]
    ):
        text = element.get_text(" ", strip=True)

        if text.upper() == "DEPARTMENTS":
            break

        if element.name != "h3" or not text:
            continue

        location = ""
        sibling = element.find_next_sibling()

        while sibling is not None:
            if sibling.name in {"h2", "h3"}:
                break

            sibling_text = sibling.get_text(
                " ",
                strip=True,
            )

            if sibling_text:
                location = _extract_location(sibling_text)

                if location:
                    break

            sibling = sibling.find_next_sibling()

        if not location:
            # Teamme currently renders the role location immediately
            # after the title. Use the card text as a second attempt.
            parent = element.parent

            if parent:
                location = _extract_location(
                    parent.get_text(" ", strip=True)
                )

        if not location:
            continue

        jobs.append({
            "title": text,
            "company_name": "Playtika",
            "location": location,
            "url": "https://playtika.teamme.link/",
            "description": f"{text} {location}",
            "source": "Playtika Careers",
        })

    return jobs


async def _fetch_url(client, url):
    try:
        response = await client.get(url)
        response.raise_for_status()
        return url, response.text

    except httpx.HTTPError as error:
        print(f"Direct careers page failed {url}: {error}")
        return url, ""


async def _get_company_jobs(client, company_name, config):
    results = await asyncio.gather(
        *(
            _fetch_url(client, url)
            for url in config["urls"]
        )
    )

    jobs = {}

    for page_url, html in results:
        if not html:
            continue

        for job in _parse_link_jobs(
            html,
            page_url,
            company_name,
            config,
        ):
            jobs[
                (
                    job["url"],
                    job["title"].lower(),
                )
            ] = job

    print(
        f"{company_name} direct careers: "
        f"{len(jobs)} jobs"
    )

    return list(jobs.values())


async def get_direct_company_jobs():
    headers = {
        "User-Agent": "Mozilla/5.0 JobHunterBot/1.0",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        company_results = await asyncio.gather(
            *(
                _get_company_jobs(
                    client,
                    company_name,
                    config,
                )
                for company_name, config
                in DIRECT_COMPANIES.items()
            )
        )

        playtika_url = "https://playtika.teamme.link/"
        _, playtika_html = await _fetch_url(
            client,
            playtika_url,
        )

        playtika_jobs = (
            _parse_playtika(playtika_html)
            if playtika_html
            else []
        )

        print(
            "Playtika direct careers: "
            f"{len(playtika_jobs)} jobs"
        )

    jobs = [
        job
        for company_jobs in company_results
        for job in company_jobs
    ]

    jobs.extend(playtika_jobs)

    return jobs
