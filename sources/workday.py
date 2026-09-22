import httpx


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
}


async def get_workday_job_details(
    client,
    host,
    tenant,
    site,
    external_path
):
    """
    Fetch full details for a single Workday job.
    """

    url = (
        f"https://{host}/wday/cxs/"
        f"{tenant}/{site}{external_path}"
    )

    response = await client.get(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-US",
        },
    )

    response.raise_for_status()

    data = response.json()

    return data.get("jobPostingInfo", {})


async def get_workday_jobs():
    jobs = []

    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers
    ) as client:

        for company_name, config in WORKDAY_COMPANIES.items():

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
                    "searchText": "",
                }

                try:
                    response = await client.post(
                        api_url,
                        json=payload,
                    )

                    response.raise_for_status()

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

                    # Workday sometimes says "2 Locations",
                    # "5 Locations", etc., instead of listing them.
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
                                ""
                            )

                            additional_locations = details.get(
                                "additionalLocations",
                                []
                            )

                            all_locations = []

                            if primary_location:
                                all_locations.append(
                                    primary_location
                                )

                            if isinstance(
                                additional_locations,
                                list
                            ):
                                all_locations.extend(
                                    additional_locations
                                )

                            location = ", ".join(
                                location
                                for location in all_locations
                                if location
                            )

                            description = details.get(
                                "jobDescription",
                                ""
                            )

                        except httpx.HTTPError as error:
                            print(
                                f"Failed getting details "
                                f"for {company_name} - "
                                f"{title}: {error}"
                            )

                    # We only want sources in Israel.
                    if "israel" not in location.lower():
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

    return jobs