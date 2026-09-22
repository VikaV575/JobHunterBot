import asyncio

import httpx

from config import ISRAEL_LOCATIONS


WORKDAY_COMPANIES = {
    "Intel": {
        "host": "intel.wd1.myworkdayjobs.com",
        "tenant": "intel",
        "site": "External",
    },
    "NVIDIA": {
        "host": "nvidia.wd5.myworkdayjobs.com",
        "tenant": "nvidia",
        "site": "NVIDIAExternalCareerSite",
    },
    "HP": {
        "host": "hp.wd5.myworkdayjobs.com",
        "tenant": "hp",
        "site": "ExternalCareerSite",
    },
    "Motorola Solutions": {
        "host": "motorolasolutions.wd5.myworkdayjobs.com",
        "tenant": "motorolasolutions",
        "site": "Careers",
    },
    "HPE": {
        "host": "hpe.wd5.myworkdayjobs.com",
        "tenant": "hpe",
        "site": "ACJobSite",
    },
    "Marvell": {
        "host": "marvell.wd1.myworkdayjobs.com",
        "tenant": "marvell",
        "site": "MarvellCareers",
    },
    "KLA": {
        "host": "kla.wd1.myworkdayjobs.com",
        "tenant": "kla",
        "site": "Search",
    },
    "Applied Materials": {
        "host": "amat.wd1.myworkdayjobs.com",
        "tenant": "amat",
        "site": "External",
    },
    "Micron": {
        "host": "micron.wd1.myworkdayjobs.com",
        "tenant": "micron",
        "site": "External",
        "search_text": "Israel",
    },
    "Workday / HiredScore": {
        "host": "workday.wd5.myworkdayjobs.com",
        "tenant": "workday",
        "site": "Workday",
    },
    "Cisco": {
        "host": "cisco.wd5.myworkdayjobs.com",
        "tenant": "cisco",
        "site": "Cisco_Careers",
        "search_text": "Israel",
    },
    "Altera": {
        "host": "altera.wd1.myworkdayjobs.com",
        "tenant": "altera",
        "site": "Altera",
    },
    "Broadcom": {
        "host": "broadcom.wd1.myworkdayjobs.com",
        "tenant": "broadcom",
        "site": "External_Career",
        "search_text": "Israel",
    },
    "Cadence": {
        "host": "cadence.wd1.myworkdayjobs.com",
        "tenant": "cadence",
        "site": "External_Careers",
    },
    "Cadence University": {
        "host": "cadence.wd1.myworkdayjobs.com",
        "tenant": "cadence",
        "site": "Univ_Careers",
    },
}


WORKDAY_ISRAEL_MARKERS = [
    *ISRAEL_LOCATIONS,
    "petah-tikva",
    "migdal ha'emek",
    "migdal haemek",
    "hadera",
    "yavne",
    "glil yam",
    ",isr",
    "il - ",
]

COMPANY_TIMEOUT_SECONDS = 35
WORKDAY_CONCURRENCY = 5
REQUEST_RETRIES = 3


def _is_israel_location(location):
    location = location.lower()

    return any(
        marker in location
        for marker in WORKDAY_ISRAEL_MARKERS
    )


async def _request_with_retry(
    client,
    method,
    url,
    **kwargs,
):
    retryable_errors = (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
    )

    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            response = await client.request(
                method,
                url,
                **kwargs,
            )
            response.raise_for_status()
            return response

        except retryable_errors as error:
            if attempt == REQUEST_RETRIES:
                raise

            print(
                f"Temporary Workday network error "
                f"(attempt {attempt}/{REQUEST_RETRIES}): {error}"
            )

            await asyncio.sleep(attempt)

    raise RuntimeError("unreachable")


async def get_workday_job_details(
    client,
    host,
    tenant,
    site,
    external_path,
):
    url = (
        f"https://{host}/wday/cxs/"
        f"{tenant}/{site}{external_path}"
    )

    response = await _request_with_retry(
        client,
        "GET",
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-US",
            "Referer": f"https://{host}/{site}",
        },
    )
    data = response.json()

    return data.get("jobPostingInfo", {})


async def _get_company_jobs(
    client,
    company_name,
    config,
):
    jobs = []

    host = config["host"]
    tenant = config["tenant"]
    site = config["site"]

    api_url = (
        f"https://{host}/wday/cxs/"
        f"{tenant}/{site}/jobs"
    )

    offset = 0
    limit = 20

    print(f"Fetching Workday jobs from {company_name}...")

    while True:
        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": config.get("search_text", ""),
        }

        try:
            response = await _request_with_retry(
                client,
                "POST",
                api_url,
                json=payload,
                headers={
                    "Origin": f"https://{host}",
                    "Referer": f"https://{host}/{site}",
                },
            )
            data = response.json()

        except httpx.HTTPError as error:
            print(
                f"Failed getting Workday jobs "
                f"for {company_name}: {error}"
            )
            break

        postings = data.get("jobPostings", [])

        if not postings:
            break

        for job in postings:
            title = job.get("title", "")
            location = job.get("locationsText", "")
            external_path = job.get("externalPath", "")

            if not external_path:
                continue

            description = ""

            needs_details = (
                "locations" in location.lower()
                or not location
            )

            if needs_details:
                try:
                    details = await get_workday_job_details(
                        client,
                        host,
                        tenant,
                        site,
                        external_path,
                    )

                    primary_location = details.get(
                        "location",
                        "",
                    )

                    additional_locations = details.get(
                        "additionalLocations",
                        [],
                    )

                    all_locations = []

                    if primary_location:
                        all_locations.append(primary_location)

                    if isinstance(additional_locations, list):
                        all_locations.extend(
                            additional_locations
                        )

                    location = ", ".join(
                        item
                        for item in all_locations
                        if item
                    )

                    description = details.get(
                        "jobDescription",
                        "",
                    )

                except httpx.HTTPError as error:
                    print(
                        f"Failed getting details "
                        f"for {company_name} - "
                        f"{title}: {error}"
                    )

            if not _is_israel_location(location):
                continue

            job_url = (
                f"https://{host}/en-US/"
                f"{site}{external_path}"
            )

            jobs.append({
                "title": title,
                "company_name": company_name,
                "location": location,
                "url": job_url,
                "description": description,
                "source": "Workday",
            })

        offset += limit

        total = data.get("total", 0)

        if offset >= total:
            break

    print(
        f"Workday {company_name}: "
        f"{len(jobs)} Israel jobs"
    )

    return jobs


async def _get_company_jobs_with_timeout(
    semaphore,
    client,
    company_name,
    config,
):
    async with semaphore:
        try:
            return await asyncio.wait_for(
                _get_company_jobs(
                    client,
                    company_name,
                    config,
                ),
                timeout=COMPANY_TIMEOUT_SECONDS,
            )

        except asyncio.TimeoutError:
            print(
                f"Workday {company_name}: timed out after "
                f"{COMPANY_TIMEOUT_SECONDS}s, skipping it"
            )
            return []

        except Exception as error:
            print(
                f"Workday {company_name}: failed with "
                f"{type(error).__name__}: {error}"
            )
            return []


async def get_workday_jobs():
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/152 Safari/537.36"
        ),
    }

    semaphore = asyncio.Semaphore(WORKDAY_CONCURRENCY)

    timeout = httpx.Timeout(
        20.0,
        connect=10.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
    ) as client:
        company_results = await asyncio.gather(
            *(
                _get_company_jobs_with_timeout(
                    semaphore,
                    client,
                    company_name,
                    config,
                )
                for company_name, config
                in WORKDAY_COMPANIES.items()
            )
        )

    return [
        job
        for company_jobs in company_results
        for job in company_jobs
    ]
