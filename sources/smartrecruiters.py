import httpx


SMARTRECRUITERS_COMPANIES = {
    "Nexar": "NexarInc",
    "Renesas": "RenesasElectronics",
}


async def get_smartrecruiters_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=10.0) as client:

        for company_name, company_id in SMARTRECRUITERS_COMPANIES.items():

            url = (
                "https://api.smartrecruiters.com/v1/companies/"
                f"{company_id}/postings"
            )

            params = {
                "country": "il",
                "limit": 100,
            }

            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                for job in data.get("content", []):

                    job_id = job.get("id")

                    # Get the full information for this job
                    details_url = (
                        "https://api.smartrecruiters.com/v1/companies/"
                        f"{company_id}/postings/{job_id}"
                    )

                    details_response = await client.get(details_url)
                    details_response.raise_for_status()

                    details = details_response.json()

                    location = job.get("location", {})

                    city = location.get("city", "")
                    country = location.get("country", "")

                    location_text = ", ".join(
                        part for part in [city, country] if part
                    )

                    jobs.append({
                        "title": job.get("name", ""),
                        "company_name": company_name,
                        "location": location_text,
                        "url": details.get("postingUrl", ""),
                        "description": "",
                        "source": "SmartRecruiters",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting SmartRecruiters jobs "
                    f"for {company_name}: {error}"
                )

    return jobs