import httpx


# Add a company's Breezy subdomain here when you find one.
# Example career site: https://company.breezy.hr/
BREEZY_COMPANIES = {
}


def _location_text(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        country = value.get("country")
        if isinstance(country, dict):
            country = country.get("name")

        parts = [
            value.get("name"),
            value.get("city"),
            value.get("state"),
            country,
        ]
        return ", ".join(
            dict.fromkeys(str(part).strip() for part in parts if part)
        )

    return ""


async def get_breezy_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, slug in BREEZY_COMPANIES.items():
            url = f"https://{slug}.breezy.hr/json"

            try:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()
                postings = data if isinstance(data, list) else []

                for job in postings:
                    jobs.append({
                        "title": job.get("name", ""),
                        "company_name": company_name,
                        "location": _location_text(
                            job.get("location")
                        ),
                        "url": (
                            job.get("url")
                            or job.get("friendly_url", "")
                        ),
                        "description": (
                            job.get("description")
                            or job.get("description_html", "")
                        ),
                        "source": "Breezy HR",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Breezy jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
