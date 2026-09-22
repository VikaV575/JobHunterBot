import httpx


# Add a Pinpoint tenant subdomain here when you find one.
# Public feed pattern: https://company.pinpointhq.com/postings.json
PINPOINT_COMPANIES = {
}


def _location_text(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        return str(
            value.get("name")
            or value.get("city")
            or ""
        ).strip()

    return ""


async def get_pinpoint_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, slug in PINPOINT_COMPANIES.items():
            url = f"https://{slug}.pinpointhq.com/postings.json"

            try:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                if isinstance(data, list):
                    postings = data
                elif isinstance(data, dict):
                    postings = data.get("data", [])
                else:
                    postings = []

                for job in postings:
                    jobs.append({
                        "title": job.get("title", ""),
                        "company_name": company_name,
                        "location": _location_text(
                            job.get("location")
                        ),
                        "url": (
                            job.get("url")
                            or job.get("apply_url", "")
                        ),
                        "description": (
                            job.get("description")
                            or job.get("skills", "")
                        ),
                        "source": "Pinpoint",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Pinpoint jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
