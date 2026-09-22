import asyncio
import re
import time
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


IAI_BASE = "https://jobs.iai.co.il"
IAI_STUDENT_JOBS_URL = (
    f"{IAI_BASE}/jobs/?tp="
    "%D7%9E%D7%A9%D7%A8%D7%AA+"
    "%D7%A1%D7%98%D7%95%D7%93%D7%A0%D7%98"
)

DETAIL_CONCURRENCY = 6
BROWSER_MAX_PAGES = 30
BROWSER_WAIT_SECONDS = 12

STUDENT_MARKERS = [
    "סטודנט",
    "student",
    "intern",
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
    "פתח תקווה",
    "הרצליה",
]


def _extract_location(text):
    for marker in LOCATION_MARKERS:
        if marker in text:
            return f"{marker}, Israel"

    return "Israel"


def _parse_job_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    lowered = text.lower()

    # The browser discovery starts from IAI's student-only jobs page,
    # but keep this guard so stale/non-student links are not returned.
    if not any(
        marker.lower() in lowered
        for marker in STUDENT_MARKERS
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
        # Do not pre-filter IAI by our own small keyword list here.
        # The global filters.py already decides whether a student role
        # is software / validation / security / engineering relevant.
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


def _job_urls_from_driver(driver):
    urls = set()

    for link in driver.find_elements(
        By.CSS_SELECTOR,
        'a[href*="/job/"]',
    ):
        href = link.get_attribute("href") or ""

        if re.search(
            r"https://jobs\.iai\.co\.il/job/\d+/?$",
            href,
        ):
            urls.add(href.rstrip("/") + "/")

    return urls


def _visible_clickables(driver):
    return [
        element
        for element in driver.find_elements(
            By.CSS_SELECTOR,
            "a, button",
        )
        if element.is_displayed()
        and element.is_enabled()
    ]


def _next_page_element(driver, current_page):
    clickables = _visible_clickables(driver)

    # Prefer an explicit "next" control when the site exposes one.
    for element in clickables:
        text = (element.text or "").strip()
        aria = (
            element.get_attribute("aria-label")
            or ""
        ).strip().lower()
        title = (
            element.get_attribute("title")
            or ""
        ).strip().lower()

        if (
            text in {"הבא", "›", "»", ">"}
            or "next" in aria
            or "הבא" in aria
            or "next" in title
            or "הבא" in title
        ):
            return element

    # IAI's Angular pagination can render only numbered controls.
    # In that case move to current_page + 1.
    wanted = str(current_page + 1)

    for element in clickables:
        if (element.text or "").strip() == wanted:
            return element

    return None


def _discover_with_browser():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1440,1100")
    options.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
        },
    )

    driver = None

    try:
        # Selenium Manager automatically uses the installed Chrome and
        # resolves a matching driver, so no chromedriver path is needed.
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(35)
        driver.get(IAI_STUDENT_JOBS_URL)

        wait = WebDriverWait(
            driver,
            BROWSER_WAIT_SECONDS,
        )

        try:
            wait.until(
                lambda d: (
                    len(_job_urls_from_driver(d)) > 0
                    or "{{filtered.length}}"
                    not in d.page_source
                )
            )
        except TimeoutException:
            # Still inspect the rendered DOM; some IAI pages finish
            # rendering after Angular's placeholder disappears slowly.
            pass

        all_urls = set()
        current_page = 1

        for _ in range(BROWSER_MAX_PAGES):
            page_urls = _job_urls_from_driver(
                driver
            )
            before = set(page_urls)
            all_urls.update(page_urls)

            next_element = _next_page_element(
                driver,
                current_page,
            )

            if next_element is None:
                break

            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView("
                    "{block: 'center'});",
                    next_element,
                )
                driver.execute_script(
                    "arguments[0].click();",
                    next_element,
                )
            except WebDriverException:
                break

            changed = False

            for _ in range(20):
                time.sleep(0.25)
                after = _job_urls_from_driver(
                    driver
                )

                if after and after != before:
                    changed = True
                    break

            if not changed:
                break

            current_page += 1

        print(
            "IAI browser discovery: "
            f"{len(all_urls)} student job URLs"
        )

        return sorted(all_urls)

    except WebDriverException as error:
        print(
            "IAI browser discovery failed: "
            f"{type(error).__name__}: {error}"
        )
        return []

    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                pass


def _job_urls_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    for link in soup.find_all("a", href=True):
        absolute_url = urljoin(
            IAI_BASE,
            link.get("href", ""),
        )

        if re.search(
            r"https://jobs\.iai\.co\.il/job/\d+/?$",
            absolute_url,
        ):
            urls.append(
                absolute_url.rstrip("/") + "/"
            )

    return urls


async def _discover_http_fallback(client):
    # Keep a lightweight fallback for machines without Chrome. The IAI
    # jobs page is Angular-rendered, so this usually finds fewer links
    # than Selenium, but it is still useful if the site changes.
    urls = []

    try:
        response = await client.get(
            IAI_STUDENT_JOBS_URL
        )
        response.raise_for_status()
        urls.extend(
            _job_urls_from_html(response.text)
        )
    except httpx.HTTPError:
        pass

    # Currently verified live student job. It prevents a total source
    # outage if IAI temporarily changes the listing page.
    urls.append(
        f"{IAI_BASE}/job/76048241/"
    )

    return list(dict.fromkeys(urls))


async def get_iai_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }

    browser_urls = await asyncio.to_thread(
        _discover_with_browser
    )

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        fallback_urls = await _discover_http_fallback(
            client
        )

        urls = list(
            dict.fromkeys(
                [*browser_urls, *fallback_urls]
            )
        )

        print(
            f"IAI Careers: discovered "
            f"{len(urls)} student job URLs"
        )

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
        "student jobs loaded"
    )

    return jobs
