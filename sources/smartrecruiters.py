import httpx


SMARTRECRUITERS_COMPANIES = {
    "Nexar": "NexarInc",
    "Renesas": "RenesasElectronics",
    "Western Digital": "WesternDigital",
    "Wix": "Wix2",
}


def _description_from_details(details):
    job_ad = details.get("jobAd", {})
    sections = job_ad.get("sections", {})

    parts = []

    for section in sections.values():
        if not isinstance(section, dict):
            continue

        text = section.get("text", "")
        if text:
            parts.append(str(text))

    return "\n".join(parts)


async def get_smartrecruiters_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
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

                    details_url = (
                        "https://api.smartrecruiters.com/v1/companies/"
                        f"{company_id}/postings/{job_id}"
                    )

                    details_response = await client.get(details_url)
                    details_response.raise_for_status()
                    details = details_response.json()

                    location = job.get("location", {})
                    city = location.get("city", "")
                    region = location.get("region", "")
                    country = location.get("country", "")

                    location_text = ", ".join(
                        part
                        for part in [city, region, country]
                        if part
                    )

                    jobs.append({
                        "title": job.get("name", ""),
                        "company_name": company_name,
                        "location": location_text,
                        "url": (
                            details.get("postingUrl")
                            or details.get("applyUrl", "")
                        ),
                        "description": _description_from_details(
                            details
                        ),
                        "source": "SmartRecruiters",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting SmartRecruiters jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
