import html

import httpx


ORACLE_HCM_SITES = {
    "Texas Instruments": {
        "host": "edbz.fa.us2.oraclecloud.com",
        "site": "CX",
        "source": "Texas Instruments Careers",
        "country_code": "IL",
    },
}

PAGE_SIZE = 100
MAX_PAGES = 5


def _clean_text(value):
    if value is None:
        return ""

    text = html.unescape(str(value))
    return (
        text.replace("<br>", " ")
        .replace("<br/>", " ")
        .replace("<br />", " ")
    )


def _request_items(data):
    if not isinstance(data, dict):
        return []

    items = data.get("items", [])

    if not isinstance(items, list):
        return []

    return items


def _requisition_rows(data):
    rows = []

    for item in _request_items(data):
        if not isinstance(item, dict):
            continue

        requisitions = item.get(
            "requisitionList",
            [],
        )

        if isinstance(requisitions, list):
            rows.extend(
                row
                for row in requisitions
                if isinstance(row, dict)
            )

    return rows


def _location_text(row):
    primary = str(
        row.get("PrimaryLocation")
        or ""
    ).strip()

    country = str(
        row.get("PrimaryLocationCountry")
        or ""
    ).strip()

    if primary:
        return primary

    if country.upper() == "IL":
        return "Israel"

    return ""


def _is_israel_row(row):
    country = str(
        row.get("PrimaryLocationCountry")
        or ""
    ).upper()

    location = _location_text(row).lower()

    return (
        country in {"IL", "ISR"}
        or "israel" in location
        or "ra'anana" in location
        or "raanana" in location
    )


def _description(row):
    parts = [
        row.get("ShortDescriptionStr"),
        row.get("ExternalResponsibilitiesStr"),
        row.get("ExternalQualificationsStr"),
        row.get("JobFamily"),
        row.get("JobFunction"),
        row.get("StudyLevel"),
    ]

    return "\n".join(
        _clean_text(part)
        for part in parts
        if part
    )


async def _get_company_jobs(
    client,
    company_name,
    config,
):
    host = config["host"]
    site = config["site"]
    country_code = config.get(
        "country_code",
        "IL",
    )

    endpoint = (
        f"https://{host}/hcmRestApi/resources/latest/"
        "recruitingCEJobRequisitions"
    )

    jobs = []
    seen_ids = set()

    for page in range(MAX_PAGES):
        offset = page * PAGE_SIZE

        finder = (
            "findReqs;"
            f"workLocationCountryCode={country_code}"
        )

        params = {
            "onlyData": "true",
            "expand": "requisitionList",
            "finder": finder,
            "limit": PAGE_SIZE,
            "offset": offset,
            "q": f"SiteNumber='{site}'",
        }

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers={
                    "Accept": (
                        "application/vnd.oracle.adf."
                        "resourcecollection+json"
                    ),
                    "REST-Framework-Version": "4",
                    "Ora-Irc-Language": "en",
                },
            )
            response.raise_for_status()
            data = response.json()

        except (
            httpx.HTTPError,
            ValueError,
        ) as error:
            print(
                f"Failed getting Oracle HCM jobs "
                f"for {company_name}: "
                f"{type(error).__name__}: {error}"
            )
            break

        rows = _requisition_rows(data)

        if not rows:
            break

        new_rows = 0

        for row in rows:
            if not _is_israel_row(row):
                continue

            job_id = str(
                row.get("Id")
                or row.get("RequisitionId")
                or ""
            ).strip()

            title = str(
                row.get("Title")
                or ""
            ).strip()

            if (
                not job_id
                or not title
                or job_id in seen_ids
            ):
                continue

            seen_ids.add(job_id)
            new_rows += 1

            jobs.append({
                "title": title,
                "company_name": company_name,
                "location": _location_text(row),
                "url": (
                    f"https://{host}/hcmUI/"
                    "CandidateExperience/en/sites/"
                    f"{site}/job/{job_id}"
                ),
                "description": _description(row),
                "source": config["source"],
                "posted_date": str(
                    row.get("PostedDate")
                    or ""
                ),
            })

        if len(rows) < PAGE_SIZE:
            break

        if new_rows == 0 and page > 0:
            break

    if jobs:
        print(
            f"Oracle HCM {company_name}: "
            f"{len(jobs)} Israel jobs"
        )
    else:
        print(
            f"Oracle HCM {company_name}: "
            "source responded successfully; "
            "0 currently open Israel jobs"
        )

    return jobs


async def get_oracle_hcm_jobs():
    jobs = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=25.0,
        headers=headers,
        follow_redirects=True,
    ) as client:
        for company_name, config in (
            ORACLE_HCM_SITES.items()
        ):
            jobs.extend(
                await _get_company_jobs(
                    client,
                    company_name,
                    config,
                )
            )

    return jobs
