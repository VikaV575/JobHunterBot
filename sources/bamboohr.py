import httpx


# Add a company's BambooHR subdomain here when you find one.
# Example career site: https://company.bamboohr.com/careers
BAMBOOHR_COMPANIES = {
}


def _location_text(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        parts = [
            value.get("city"),
            value.get("state"),
            value.get("country"),
            value.get("name"),
        ]
        return ", ".join(
            dict.fromkeys(str(part).strip() for part in parts if part)
        )

    return ""


async def get_bamboohr_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, slug in BAMBOOHR_COMPANIES.items():
            url = f"https://{slug}.bamboohr.com/careers/list"

            try:
                response = await client.get(
                    url,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()

                data = response.json()
                postings = data.get("result", [])

                for job in postings:
                    job_id = (
                        job.get("id")
                        or job.get("jobOpeningId")
                    )

                    location = (
                        _location_text(job.get("location"))
                        or _location_text(job.get("jobLocation"))
                    )

                    jobs.append({
                        "title": (
                            job.get("jobOpeningName")
                            or job.get("title", "")
                        ),
                        "company_name": company_name,
                        "location": location,
                        "url": (
                            f"https://{slug}.bamboohr.com/careers/{job_id}"
                            if job_id
                            else f"https://{slug}.bamboohr.com/careers"
                        ),
                        "description": "",
                        "source": "BambooHR",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting BambooHR jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
