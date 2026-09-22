import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


COMEET_BOARDS = {
    "DriveNets": "https://www.comeet.com/jobs/drivenets/72.006",
    "VAST Data": "https://www.comeet.com/jobs/vastdata/43.001",
    "Paragon": "https://www.comeet.com/jobs/paragon/76.006",
    "Vega": "https://www.comeet.com/jobs/vega/C9.009",
    "Immunai": "https://www.comeet.com/jobs/immunai/37.009",
    "Retym": "https://www.comeet.com/jobs/retym/C6.003",
    "Foresight Automotive": (
        "https://www.comeet.com/jobs/foresightauto/13.000"
    ),
    "ScyllaDB": "https://www.comeet.com/jobs/scylladb/E4.006",
    "Masterschool": (
        "https://www.comeet.com/jobs/masterschool/57.005"
    ),
    "Qedma": "https://www.comeet.com/jobs/qedma/7A.006",
    "Imagene AI": (
        "https://www.comeet.com/jobs/imagene-ai/D7.000"
    ),
}


GENERIC_LINK_TEXT = {
    "",
    "apply",
    "apply now",
    "view job",
    "view position",
    "learn more",
}

ISRAEL_LOCATION_HINTS = [
    "Tel Aviv",
    "Tel-Aviv",
    "Raanana",
    "Ra'anana",
    "Haifa",
    "Herzliya",
    "Yokneam",
    "Petah Tikva",
    "Kfar Saba",
    "Caesarea",
    "Netanya",
    "Rehovot",
    "Jerusalem",
    "Beer Sheva",
    "Be'er Sheva",
    "Israel",
]


def _is_position_url(url, board_url):
    parsed = urlparse(url)
    board = urlparse(board_url)

    if parsed.netloc != board.netloc:
        return False

    board_path = board.path.rstrip("/")
    if not parsed.path.startswith(board_path + "/"):
        return False

    tail = parsed.path[len(board_path):].strip("/")
    segments = [part for part in tail.split("/") if part]

    if len(segments) < 2:
        return False

    position_id = segments[-1]
    return bool(
        re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z0-9.-]+",
            position_id,
        )
    )


def _extract_location(context):
    matches = []

    for hint in ISRAEL_LOCATION_HINTS:
        if hint.lower() in context.lower():
            matches.append(hint)

    return ", ".join(dict.fromkeys(matches))


def _title_from_url(url):
    path_parts = [
        part for part in urlparse(url).path.split("/") if part
    ]

    if len(path_parts) < 2:
        return ""

    return path_parts[-2].replace("-", " ").strip().title()


def _context_for_link(link):
    fallback = link.get_text(" ", strip=True)

    for parent in link.parents:
        if getattr(parent, "name", None) not in {
            "article",
            "li",
            "section",
            "div",
        }:
            continue

        text = parent.get_text(" ", strip=True)

        if any(
            hint.lower() in text.lower()
            for hint in ISRAEL_LOCATION_HINTS
        ):
            return text

        if len(text) < 500:
            fallback = text

    return fallback


def _parse_board(html, board_url, company_name):
    soup = BeautifulSoup(html, "html.parser")
    found = {}

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        absolute_url = urljoin(board_url + "/", href).split("#")[0]

        if not _is_position_url(absolute_url, board_url):
            continue

        title = link.get_text(" ", strip=True)
        if title.lower() in GENERIC_LINK_TEXT:
            title = ""

        context = _context_for_link(link)
        location = _extract_location(context)

        existing = found.get(absolute_url)
        candidate_title = title or _title_from_url(absolute_url)

        if existing is None:
            found[absolute_url] = {
                "title": candidate_title,
                "company_name": company_name,
                "location": location,
                "url": absolute_url,
                "description": "",
                "source": "Comeet",
            }
        else:
            if len(candidate_title) > len(existing["title"]):
                existing["title"] = candidate_title

            if location and not existing["location"]:
                existing["location"] = location

    return list(found.values())


async def get_comeet_jobs():
    jobs = []

    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "Mozilla/5.0 JobHunterBot/1.0",
    }

    async with httpx.AsyncClient(
        timeout=30.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        for company_name, board_url in COMEET_BOARDS.items():
            try:
                response = await client.get(board_url)
                response.raise_for_status()

                jobs.extend(
                    _parse_board(
                        response.text,
                        board_url,
                        company_name,
                    )
                )

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Comeet jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
