import httpx


GREENHOUSE_COMPANIES = {
    "Gong": "gongio",
}


async def get_greenhouse_jobs():
    jobs = []

    async with httpx.AsyncClient() as client:
        for company_name, board_token in GREENHOUSE_COMPANIES.items():

            url = (
                f"https://boards-api.greenhouse.io/v1/boards/"
                f"{board_token}/jobs?content=true"
            )

            response = await client.get(url)
            response.raise_for_status()

            data = response.json()

            for job in data["jobs"]:
                jobs.append({
                    "title": job.get("title", ""),
                    "company_name": company_name,
                    "location": job.get("location", {}).get("name", ""),
                    "url": job.get("absolute_url", ""),
                    "description": job.get("content", ""),
                    "source": "Greenhouse"
                })

    return jobs