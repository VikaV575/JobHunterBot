import httpx


COMEET_COMPANIES = {
    # נוסיף כאן חברות כשיש לנו uid + token
    #
    # "VAST Data": {
    #     "uid": "43.001",
    #     "token": "..."
    # },
}


async def get_comeet_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=60.0) as client:

        for company_name, config in COMEET_COMPANIES.items():

            company_uid = config["uid"]
            token = config["token"]

            url = (
                "https://www.comeet.co/careers-api/2.0/"
                f"company/{company_uid}/positions"
            )

            params = {
                "token": token,
                "details": "true",
            }

            try:
                response = await client.get(
                    url,
                    params=params,
                )

                response.raise_for_status()

                positions = response.json()

                for job in positions:

                    location_data = job.get(
                        "location",
                        {}
                    )

                    location = location_data.get(
                        "name",
                        ""
                    )

                    # Comeet returns description/requirements
                    # inside the details array.
                    description_parts = []

                    for detail in job.get("details", []):
                        value = detail.get("value", "")

                        if value:
                            description_parts.append(
                                value
                            )

                    jobs.append({
                        "title": job.get("name", ""),
                        "company_name": (
                            job.get("company_name")
                            or company_name
                        ),
                        "location": location,
                        "url": (
                            job.get("url_active_page")
                            or job.get(
                                "url_comeet_hosted_page",
                                ""
                            )
                        ),
                        "description": "\n".join(
                            description_parts
                        ),
                        "source": "Comeet",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Comeet jobs "
                    f"for {company_name}: {error}"
                )

    return jobs