import httpx


WORKABLE_COMPANIES = {
    "Nuvei": "nuvei",
    "Autofleet": "autofleet",
}


async def get_workable_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:

        for company_name, subdomain in WORKABLE_COMPANIES.items():

            url = (
                "https://www.workable.com/api/accounts/"
                f"{subdomain}"
            )

            params = {
                "details": "true"
            }

            try:
                response = await client.get(
                    url,
                    params=params
                )

                response.raise_for_status()

                data = response.json()

                for job in data.get("jobs", []):

                    country = job.get("country", "")
                    city = job.get("city", "")
                    state = job.get("state", "")

                    location_parts = [
                        city,
                        state,
                        country
                    ]

                    location = ", ".join(
                        part
                        for part in location_parts
                        if part
                    )

                    jobs.append({
                        "title": job.get("title", ""),
                        "company_name": company_name,
                        "location": location,
                        "url": (
                            job.get("shortlink")
                            or job.get("application_url")
                            or job.get("url", "")
                        ),
                        "description": job.get(
                            "description",
                            ""
                        ),
                        "source": "Workable",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Workable jobs "
                    f"for {company_name}: {error}"
                )

    return jobs