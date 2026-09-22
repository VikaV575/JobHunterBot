import asyncio
from urllib.parse import urljoin

import httpx


EIGHTFOLD_COMPANIES = {
    "Qualcomm": {
        "host": "https://qualcomm.eightfold.ai",
        "domain": "qualcomm.com",
        "location": "Israel",
    },
}

PAGE_SIZE = 10
MAX_PAGES = 80


def _location_piece(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        parts = [
            value.get("name"),
            value.get("city"),
            value.get("state"),
            value.get("country"),
        ]

        return ", ".join(
            str(part).strip()
            for part in parts
            if part
        )

    return ""


def _location_text(position):
    candidates = [
        position.get("locations"),
        position.get("standardizedLocations"),
        position.get("primaryLocation"),
        position.get("primary_location"),
        position.get("location"),
    ]

    locations = []

    for value in candidates:
        if isinstance(value, list):
            for item in value:
                text = _location_piece(item)

                if text:
                    locations.append(text)
        else:
            text = _location_piece(value)

            if text:
                locations.append(text)

    return " / ".join(
        dict.fromkeys(locations)
    )


def _is_israel_location(location):
    lowered = location.lower()

    return any(
        marker in lowered
        for marker in [
            "israel",
            "tel aviv",
            "haifa",
            "herzliya",
            "ra'anana",
            "raanana",
            "yokneam",
            "petah tikva",
        ]
    )


def _title(position):
    return str(
        position.get("name")
        or position.get("posting_name")
        or position.get("title")
        or ""
    ).strip()


def _description(position):
    return str(
        position.get("job_description")
        or position.get("jobDescription")
        or position.get("description")
        or ""
    )


def _position_url(
    host,
    domain,
    position,
):
    url = (
        position.get("canonicalPositionUrl")
        or position.get("canonical_position_url")
        or position.get("positionUrl")
        or position.get("position_url")
    )

    if url:
        return urljoin(host, str(url))

    position_id = (
        position.get("id")
        or position.get("displayJobId")
        or position.get("display_job_id")
        or position.get("atsJobId")
        or position.get("ats_job_id")
    )

    if not position_id:
        return host

    return (
        f"{host}/careers/job/{position_id}"
        f"?domain={domain}"
    )


def _response_payload(data):
    if not isinstance(data, dict):
        return {}, []

    nested = data.get("data")

    if isinstance(nested, dict):
        payload = nested
    else:
        payload = data

    positions = payload.get(
        "positions",
        [],
    )

    if not isinstance(positions, list):
        positions = []

    return payload, positions


async def _fetch_page(
    client,
    config,
    start,
):
    host = config["host"]
    domain = config["domain"]

    params = {
        "domain": domain,
        "start": start,
        "num": PAGE_SIZE,
        "query": "",
        "location": config.get(
            "location",
            "Israel",
        ),
    }

    # Qualcomm runs Eightfold PCS-X. Probe the endpoint used by the
    # public careers page first; fall back to classic Smart Apply.
    endpoints = [
        f"{host}/api/pcsx/search",
        f"{host}/api/apply/v2/jobs",
    ]

    last_error = None

    for endpoint in endpoints:
        try:
            response = await client.get(
                endpoint,
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            payload, positions = (
                _response_payload(data)
            )

            return payload, positions

        except (
            httpx.HTTPError,
            ValueError,
        ) as error:
            last_error = error

    raise last_error


async def _get_company_jobs(
    client,
    company_name,
    config,
):
    jobs = []
    seen_urls = set()

    for page in range(MAX_PAGES):
        start = page * PAGE_SIZE

        try:
            payload, positions = await _fetch_page(
                client,
                config,
                start,
            )

        except Exception as error:
            print(
                f"Failed getting Eightfold jobs "
                f"for {company_name}: "
                f"{type(error).__name__}: {error}"
            )
            break

        if not positions:
            break

        for position in positions:
            if not isinstance(position, dict):
                continue

            title = _title(position)
            location = _location_text(position)

            if (
                not title
                or not _is_israel_location(
                    location
                )
            ):
                continue

            url = _position_url(
                config["host"],
                config["domain"],
                position,
            )

            if url in seen_urls:
                continue

            seen_urls.add(url)

            jobs.append({
                "title": title,
                "company_name": company_name,
                "location": location,
                "url": url,
                "description": _description(
                    position
                ),
                "source": "Eightfold",
            })

        count = payload.get("count")

        if (
            isinstance(count, int)
            and start + len(positions) >= count
        ):
            break

        if len(positions) < PAGE_SIZE:
            break

    print(
        f"Eightfold {company_name}: "
        f"{len(jobs)} Israel jobs"
    )

    return jobs


async def get_eightfold_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *(
                _get_company_jobs(
                    client,
                    company_name,
                    config,
                )
                for company_name, config
                in EIGHTFOLD_COMPANIES.items()
            )
        )

    return [
        job
        for company_jobs in results
        for job in company_jobs
    ]
