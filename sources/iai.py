import asyncio
from datetime import date, datetime, timedelta
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


IAI_BASE = "https://jobs.iai.co.il"
IAI_STUDENT_JOBS_URL = (
    f"{IAI_BASE}/jobs/?tp="
    "%D7%9E%D7%A9%D7%A8%D7%AA+"
    "%D7%A1%D7%98%D7%95%D7%93%D7%A0%D7%98"
)

MAX_JOB_AGE_DAYS = 180
MAX_JOB_PAGES = 220
DETAIL_CONCURRENCY = 6

STUDENT_MARKERS = [
    "סטודנט",
    "student",
    "intern",
]

TECH_MARKERS = [
    "תוכנה",
    "פיתוח",
    "python",
    "c++",
    "c#",
    "java",
    "אלגורית",
    "וריפיק",
    "וליד",
    "אימות",
    "קושחה",
    "firmware",
    "software",
    "validation",
    "verification",
    "embedded",
    "סייבר",
    "cyber",
    "מערכות מידע",
    "data",
    "ai",
    "machine learning",
]

LOCATION_MARKERS = [
    "באר יעקב",
    "יהוד",
    "אשדוד",
    'נתב"ג',
    "לוד",
    "תל אביב",
    "חיפה",
    "ירושלים",
    "באר שבע",
]


def _xml_locs(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []

    for element in root.iter():
        if element.tag.endswith("url"):
            loc = ""
            lastmod = ""

            for child in element:
                if child.tag.endswith("loc"):
                    loc = (child.text or "").strip()
                elif child.tag.endswith("lastmod"):
                    lastmod = (child.text or "").strip()

            if loc:
                items.append(("url", loc, lastmod))

        elif element.tag.endswith("sitemap"):
            loc = ""

            for child in element:
                if child.tag.endswith("loc"):
                    loc = (child.text or "").strip()

            if loc:
                items.append(("sitemap", loc, ""))

    return items


def _parse_lastmod(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except ValueError:
        try:
            return datetime.strptime(
                value[:10],
                "%Y-%m-%d",
            ).date()
        except ValueError:
            return None


def _is_recent(lastmod):
    parsed = _parse_lastmod(lastmod)

    if parsed is None:
        return True

    cutoff = date.today() - timedelta(
        days=MAX_JOB_AGE_DAYS
    )

    return parsed >= cutoff


def _extract_location(text):
    for marker in LOCATION_MARKERS:
        if marker in text:
            return f"{marker}, Israel"

    return "Israel"


def _parse_job_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    lowered = text.lower()

    if not any(
        marker.lower() in lowered
        for marker in STUDENT_MARKERS
    ):
        return None

    if not any(
        marker.lower() in lowered
        for marker in TECH_MARKERS
    ):
        return None

    title = ""

    title_node = soup.find("h1")

    if title_node:
        title = title_node.get_text(" ", strip=True)

    if not title:
        title_node = soup.find(
            ["h2", "h3"],
            string=re.compile(
                "סטודנט|student",
                re.IGNORECASE,
            ),
        )

        if title_node:
            title = title_node.get_text(" ", strip=True)

    if not title:
        return None

    return {
        "title": title,
        "company_name": "IAI",
        "location": _extract_location(text),
        "url": url,
        "description": text[:20000],
        "source": "IAI Careers",
    }


async def _fetch_job(
    semaphore,
    client,
    url,
):
    async with semaphore:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        return _parse_job_page(
            response.text,
            url,
        )


def _job_urls_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        absolute_url = urljoin(IAI_BASE, href)

        if re.search(
            r"https://jobs\.iai\.co\.il/job/\d+/?$",
            absolute_url,
        ):
            urls.append(absolute_url.rstrip("/") + "/")

    return urls


async def _discover_from_student_page(client):
    try:
        response = await client.get(
            IAI_STUDENT_JOBS_URL
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return []

    return _job_urls_from_html(response.text)



async def _discover_from_wp_types(client):
    urls = []

    try:
        types_response = await client.get(
            f"{IAI_BASE}/wp-json/wp/v2/types",
            headers={"Accept": "application/json"},
        )
        types_response.raise_for_status()
        types_data = types_response.json()
    except (
        httpx.HTTPError,
        ValueError,
    ):
        return []

    if not isinstance(types_data, dict):
        return []

    candidate_bases = []

    for type_name, info in types_data.items():
        if not isinstance(info, dict):
            continue

        rest_base = str(
            info.get("rest_base")
            or ""
        ).strip()

        labels = info.get("labels") or {}

        if isinstance(labels, dict):
            label_text = " ".join(
                str(value)
                for value in labels.values()
                if value
            )
        else:
            label_text = ""

        haystack = (
            f"{type_name} {rest_base} "
            f"{info.get('name', '')} "
            f"{label_text}"
        ).lower()

        if any(
            marker in haystack
            for marker in [
                "job",
                "jobs",
                "career",
                "position",
                "משרה",
                "משרות",
            ]
        ):
            if rest_base:
                candidate_bases.append(rest_base)

    for rest_base in dict.fromkeys(candidate_bases):
        endpoint = (
            f"{IAI_BASE}/wp-json/wp/v2/"
            f"{rest_base}"
        )

        for search_term in ["סטודנט", "student"]:
            try:
                response = await client.get(
                    endpoint,
                    params={
                        "search": search_term,
                        "per_page": 100,
                        "orderby": "date",
                        "order": "desc",
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
            except (
                httpx.HTTPError,
                ValueError,
            ):
                continue

            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue

                url = str(
                    item.get("link")
                    or ""
                ).strip()

                if "/job/" in url:
                    urls.append(url)

    return urls


async def _discover_from_wordpress_search(client):
    urls = []

    for term in ["סטודנט", "student"]:
        try:
            response = await client.get(
                IAI_BASE + "/",
                params={"s": term},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            continue

        urls.extend(
            _job_urls_from_html(response.text)
        )

    return urls


async def _discover_from_rest_search(client):
    urls = []

    endpoints = [
        (
            f"{IAI_BASE}/wp-json/wp/v2/search",
            {
                "search": "סטודנט",
                "per_page": 100,
                "page": 1,
            },
        ),
        (
            f"{IAI_BASE}/wp-json/wp/v2/search",
            {
                "search": "student",
                "per_page": 100,
                "page": 1,
            },
        ),
    ]

    for endpoint, params in endpoints:
        try:
            response = await client.get(
                endpoint,
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        except (
            httpx.HTTPError,
            ValueError,
        ):
            continue

        if not isinstance(data, list):
            continue

        for item in data:
            url = str(
                item.get("url")
                or item.get("link")
                or ""
            )

            if "/job/" in url:
                urls.append(url)

    return urls


async def _discover_from_sitemaps(client):
    urls = []
    sitemap_queue = [
        f"{IAI_BASE}/wp-sitemap.xml",
        f"{IAI_BASE}/sitemap_index.xml",
        f"{IAI_BASE}/sitemap.xml",
        f"{IAI_BASE}/job-sitemap.xml",
        f"{IAI_BASE}/wp-sitemap-posts-job-1.xml",
        f"{IAI_BASE}/wp-sitemap-posts-jobs-1.xml",
        f"{IAI_BASE}/wp-sitemap-posts-ext_job-1.xml",
    ]

    seen_sitemaps = set()

    while (
        sitemap_queue
        and len(seen_sitemaps) < 30
        and len(urls) < MAX_JOB_PAGES
    ):
        sitemap_url = sitemap_queue.pop(0)

        if sitemap_url in seen_sitemaps:
            continue

        seen_sitemaps.add(sitemap_url)

        try:
            response = await client.get(sitemap_url)
            response.raise_for_status()
        except httpx.HTTPError:
            continue

        items = _xml_locs(response.text)

        for item_type, loc, lastmod in items:
            if item_type == "sitemap":
                if (
                    loc.startswith(IAI_BASE)
                    and loc not in seen_sitemaps
                ):
                    sitemap_queue.append(loc)

                continue

            if "/job/" not in loc:
                continue

            if not _is_recent(lastmod):
                continue

            urls.append(loc)

    return urls


async def _discover_job_urls(client):
    (
        page_urls,
        rest_urls,
        type_urls,
        wp_search_urls,
        sitemap_urls,
    ) = await asyncio.gather(
        _discover_from_student_page(client),
        _discover_from_rest_search(client),
        _discover_from_wp_types(client),
        _discover_from_wordpress_search(client),
        _discover_from_sitemaps(client),
    )

    # Keep one currently verified technical-student posting as a final
    # fallback. If it closes, _fetch_job will simply ignore its 404/closed
    # page; the dynamic discovery methods above remain the primary path.
    verified_fallback_urls = [
        f"{IAI_BASE}/job/76048241/",
    ]

    urls = [
        *page_urls,
        *rest_urls,
        *type_urls,
        *wp_search_urls,
        *sitemap_urls,
        *verified_fallback_urls,
    ]

    return list(dict.fromkeys(urls))[
        :MAX_JOB_PAGES
    ]


async def get_iai_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml,application/json"
        ),
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        urls = await _discover_job_urls(client)

        print(
            f"IAI Careers: discovered "
            f"{len(urls)} candidate job URLs"
        )

        if not urls:
            return []

        semaphore = asyncio.Semaphore(
            DETAIL_CONCURRENCY
        )

        results = await asyncio.gather(
            *(
                _fetch_job(
                    semaphore,
                    client,
                    url,
                )
                for url in urls
            )
        )

    jobs = [
        job
        for job in results
        if job is not None
    ]

    print(
        f"IAI Careers: {len(jobs)} "
        "technical student jobs"
    )

    return jobs
