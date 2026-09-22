from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


JOBNET_STUDENT_SOFTWARE_URL = (
    "https://www.jobs-israel.com/jobs?subprofid=1079"
)

AREA_LINK_TEXT = {
    "מרכז",
    "שרון",
    "ירושלים",
    "צפון",
    "דרום",
    "השפלה",
    "אילת",
    'חו"ל',
    "קרא עוד",
    "למשרות נוספות בתחום",
}


def _nearest_job_card(link):
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

        if len(text) <= 7000:
            fallback = parent

        if (
            "תיאור תפקיד" in text
            and (
                "קוד משרה" in text
                or "היקף משרה" in text
            )
        ):
            return parent

    return fallback


def _company_from_card(card, title_link):
    if card is None:
        return "Jobnet listing"

    anchors = card.find_all("a", href=True)

    try:
        title_index = anchors.index(title_link)
    except ValueError:
        title_index = -1

    for anchor in anchors[title_index + 1:]:
        text = anchor.get_text(" ", strip=True)

        if (
            text
            and text not in AREA_LINK_TEXT
            and "משרות נוספות" not in text
            and len(text) <= 120
        ):
            return text

    return "Jobnet listing"


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if "positionid=" not in href.lower():
            continue

        title = link.get_text(" ", strip=True)

        if not title or len(title) > 220:
            continue

        card = _nearest_job_card(link)

        if card is None:
            continue

        context = card.get_text(" ", strip=True)

        # The page is already the dedicated Computer Science / Software
        # Engineering students category. Avoid navigation links that happen
        # to contain positionid.
        if (
            "תיאור תפקיד" not in context
            and "job" not in context.lower()
        ):
            continue

        url = urljoin(
            "https://www.jobs-israel.com",
            href,
        )

        jobs[url] = {
            "title": title,
            "company_name": _company_from_card(
                card,
                link,
            ),
            "location": "Israel",
            "url": url,
            "description": context[:20000],
            "source": "Jobnet / Jobs-Israel",
        }

    return list(jobs.values())


async def get_jobnet_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                JOBNET_STUDENT_SOFTWARE_URL
            )
            response.raise_for_status()

    except httpx.HTTPError as error:
        print(
            "Failed getting Jobnet student jobs: "
            f"{type(error).__name__}: {error}"
        )
        return []

    jobs = _parse_page(response.text)

    print(
        f"Jobnet: {len(jobs)} computer-science "
        "student jobs"
    )

    return jobs
