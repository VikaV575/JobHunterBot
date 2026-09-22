import httpx


WORKABLE_COMPANIES = {
    "Nuvei": "nuvei",
    "Autofleet": "autofleet",
}


def _location_text(job):
    locations = job.get("locations")

    if isinstance(locations, list) and locations:
        formatted = []

        for location in locations:
            if not isinstance(location, dict):
                continue

            city = location.get("city", "")
            state = (
                location.get("state")
                or location.get("state_code")
                or ""
            )
            country = (
                location.get("country_name")
                or location.get("country")
                or ""
            )

            text = ", ".join(
                part for part in [city, state, country] if part
            )

            if text:
                formatted.append(text)

        if formatted:
            return " / ".join(dict.fromkeys(formatted))

    country = job.get("country", "")
    city = job.get("city", "")
    state = job.get("state", "")

    return ", ".join(
        part for part in [city, state, country] if part
    )


async def get_workable_jobs():
    jobs = []

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
    ) as client:
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
                    params=params,
                )

                response.raise_for_status()
                data = response.json()

                for job in data.get("jobs", []):
                    jobs.append({
                        "title": job.get("title", ""),
                        "company_name": company_name,
                        "location": _location_text(job),
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
