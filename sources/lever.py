import httpx


LEVER_COMPANIES = {
    "WalkMe": "walkme",
    "Palantir": "palantir",
    "Zadara": "Zadara",
    "Tonkean": "tonkean",
}


async def get_lever_jobs():
    jobs = []

    async with httpx.AsyncClient() as client:
        for company_name, site_name in LEVER_COMPANIES.items():

            url = f"https://api.lever.co/v0/postings/{site_name}?mode=json"

            response = await client.get(url)
            response.raise_for_status()

            data = response.json()

            for job in data:
                jobs.append({
                    "title": job.get("text", ""),
                    "company_name": company_name,
                    "location": job.get("categories", {}).get(
                        "location", ""
                    ),
                    "url": job.get("hostedUrl", ""),
                    "description": job.get("descriptionPlain", ""),
                    "source": "Lever"
                })

    return jobs