import asyncio
import re
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


# Comeet's hosted board (www.comeet.com/jobs/...) is rendered with
# JavaScript, so a plain httpx request only sees Angular placeholders.
# Many Comeet customers also expose the same jobs on a server-rendered
# branded careers page. We collect those branded pages here.
COMEET_BRANDED_SITES = {
    "Samsung R&D Israel": {
        "url": "https://samsung-careers.co.il/careers/",
        "job_pattern": r"/careers/co/.+?/[^/]+/all/?$",
        "title_slug_index": -2,
    },
    "Nuvoton Israel": {
        "url": "https://nuvoton.co.il/careers/",
        "job_pattern": r"/careers/co/.+?/[^/]+/all/?$",
        "title_slug_index": -2,
    },
    "DriveNets": {
        "url": "https://drivenets.com/careers/",
        "job_pattern": r"/career/[A-Za-z0-9.]+/?$",
        "use_heading_title": True,
    },
    "Vega": {
        "url": "https://vega.io/careers",
        "job_pattern": (
            r"comeet\.com/jobs/vega/C9\.009/"
            r"[^/]+/[A-Za-z0-9.]+/?$"
        ),
        "title_slug_index": -2,
    },
    "Navina": {
        "url": "https://www.navina.ai/careers",
        "job_pattern": r"/positions/position-[A-Za-z0-9_-]+/?$",
        "use_heading_title": True,
    },
    "Retym": {
        "url": "https://retym.com/careers-2/",
        "job_pattern": r"/careers-2/co/.+?/[^/]+/all/?$",
        "title_slug_index": -2,
    },
    "Imagene AI": {
        "url": "https://imagene-ai.com/careers/",
        "job_pattern": r"/careers/co/.+?/[^/]+/all/?$",
        "title_slug_index": -2,
    },
    "Qedma": {
        "url": "https://www.qedma.com/careers/",
        "job_pattern": r"/careers/co/.+?/[^/]+/all/?$",
        "title_slug_index": -2,
    },
    "Anecdotes": {
        "url": "https://www.anecdotes.ai/careers",
        "job_pattern": r"(?:comeet\.com/jobs/|/careers/|/positions/).+",
        "use_heading_title": True,
    },
}

COMEET_CONCURRENCY = 6

GENERIC_LINK_TEXT = {
    "",
    "apply",
    "apply now",
    "read more",
    "learn more",
    "view job",
    "view position",
    "details",
    "see details",
}

ISRAEL_LOCATION_PATTERNS = [
    ("Tel Aviv", r"\bTel[- ]Aviv(?:-Yafo)?\b"),
    ("Raanana", r"\bRa['’]?anana\b|\bRaanana\b"),
    ("Ramat Gan", r"\bRamat[- ]Gan\b"),
    ("Herzliya", r"\bHerzliya\b|\bHerzelia\b"),
    ("Haifa", r"\bHaifa\b"),
    ("Yokneam", r"\bYokneam\b|\bYoqneam\b"),
    ("Petah Tikva", r"\bPet(?:ah|ach)[- ]Tikva\b"),
    ("Kfar Saba", r"\bKfar[- ]Saba\b"),
    ("Caesarea", r"\bCaesarea\b"),
    ("Netanya", r"\bNetanya\b"),
    ("Rehovot", r"\bRehovot\b"),
    ("Jerusalem", r"\bJerusalem\b"),
    ("Beer Sheva", r"\bBe['’]?er[- ]Sheva\b|\bBeer[- ]Sheva\b"),
    ("Ness Ziona", r"\bNess[- ]Ziona\b|\bNes[- ]Ziona\b"),
    ("Migdal Haemek", r"\bMigdal[- ]Ha['’]?emek\b"),
    ("Bnei Brak", r"\bBnei[- ]Brak\b"),
    ("Holon", r"\bHolon\b"),
    ("Or Yehuda", r"\bOr[- ]Yehuda\b"),
    ("Israel", r"\bIsrael\b"),
]

FOREIGN_LOCATION_MARKERS = [
    "united states",
    "usa",
    "new york",
    "boston",
    "austin",
    "california",
    "palo alto",
    "london",
    "united kingdom",
    "uk",
    "poland",
    "romania",
    "armenia",
    "japan",
    "taiwan",
    "india",
]


def _extract_israel_location(text, url=""):
    combined = f"{text} {unquote(url)}"
    locations = []

    for label, pattern in ISRAEL_LOCATION_PATTERNS:
        if re.search(
            pattern,
            combined,
            flags=re.IGNORECASE,
        ):
            locations.append(label)

    # Some branded Comeet pages use only the country code "IL".
    if re.search(r"(?<![A-Za-z])IL(?![A-Za-z])", text):
        locations.append("Israel")

    lowered_url = unquote(url).lower()

    if "/israel/" in lowered_url:
        locations.append("Israel")

    if "ramat-gan" in lowered_url:
        locations.append("Ramat Gan")

    if "tel-aviv" in lowered_url:
        locations.append("Tel Aviv")

    return ", ".join(dict.fromkeys(locations))


def _looks_foreign(text):
    lowered = text.lower()

    return any(
        marker in lowered
        for marker in FOREIGN_LOCATION_MARKERS
    )


def _nearest_card_text(link):
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

        # Stop before we accidentally use an entire page containing
        # locations from unrelated jobs.
        if len(text) > 1800:
            break

        fallback = text

        if (
            _extract_israel_location(text)
            or _looks_foreign(text)
        ):
            return text

    return fallback


def _slug_title(url, index):
    parts = [
        part
        for part in urlparse(url).path.rstrip("/").split("/")
        if part
    ]

    if not parts:
        return ""

    try:
        slug = parts[index]
    except IndexError:
        return ""

    slug = unquote(slug)
    slug = re.sub(r"^[A-Za-z0-9.]+$", lambda m: m.group(0), slug)

    return (
        slug
        .replace("-", " ")
        .replace("_", " ")
        .strip()
        .title()
    )


def _heading_title(link):
    for node in [link, *list(link.parents)[:6]]:
        if not hasattr(node, "find"):
            continue

        heading = node.find(
            ["h1", "h2", "h3", "h4", "h5"]
        )

        if heading:
            title = heading.get_text(" ", strip=True)

            if title and len(title) <= 180:
                return title

    return ""


def _extract_title(link, url, config):
    slug_index = config.get("title_slug_index")

    if slug_index is not None:
        title = _slug_title(url, slug_index)

        if title:
            return title

    if config.get("use_heading_title"):
        title = _heading_title(link)

        if title:
            return title

    title = link.get_text(" ", strip=True)

    if (
        title
        and title.lower() not in GENERIC_LINK_TEXT
        and len(title) <= 180
    ):
        return title

    return _heading_title(link)


def _section_location(link):
    # Webflow/WordPress Comeet integrations often group jobs below
    # a location heading such as "IL" or "Ramat-Gan".
    previous = link.find_previous(
        ["h2", "h3", "h4"]
    )

    if previous:
        heading_text = previous.get_text(" ", strip=True)
        location = _extract_israel_location(
            heading_text
        )

        if location:
            return location

        if heading_text.strip().upper() == "IL":
            return "Israel"

    return ""


def _parse_site(html, company_name, config):
    soup = BeautifulSoup(html, "html.parser")
    page_url = config["url"]
    pattern = re.compile(
        config["job_pattern"],
        flags=re.IGNORECASE,
    )
    found = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        absolute_url = urljoin(page_url, href).split("#")[0]

        if not pattern.search(absolute_url):
            continue

        context = _nearest_card_text(link)
        location = (
            _extract_israel_location(
                context,
                absolute_url,
            )
            or _section_location(link)
        )

        if not location:
            continue

        title = _extract_title(
            link,
            absolute_url,
            config,
        )

        if not title:
            continue

        found[absolute_url] = {
            "title": title,
            "company_name": company_name,
            "location": location,
            "url": absolute_url,
            "description": context,
            "source": "Comeet / company careers",
        }

    return list(found.values())


async def _fetch_company(
    semaphore,
    client,
    company_name,
    config,
):
    async with semaphore:
        try:
            response = await client.get(config["url"])
            response.raise_for_status()

        except httpx.HTTPError as error:
            print(
                f"Failed getting Comeet-backed jobs "
                f"for {company_name}: {error}"
            )
            return []

        jobs = _parse_site(
            response.text,
            company_name,
            config,
        )

        print(
            f"Comeet-backed {company_name}: "
            f"{len(jobs)} Israel jobs"
        )

        return jobs


async def get_comeet_jobs():
    semaphore = asyncio.Semaphore(
        COMEET_CONCURRENCY
    )

    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *(
                _fetch_company(
                    semaphore,
                    client,
                    company_name,
                    config,
                )
                for company_name, config
                in COMEET_BRANDED_SITES.items()
            )
        )

    return [
        job
        for company_jobs in results
        for job in company_jobs
    ]
