import httpx


AMAZON_API_URL = "https://www.amazon.jobs/en/search.json"
AMAZON_BASE_URL = "https://www.amazon.jobs"


async def get_amazon_jobs():
    jobs = []

    offset = 0
    limit = 100

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=headers
    ) as client:

        while True:

            params = {
                "normalized_country_code[]": "ISR",
                "offset": offset,
                "result_limit": limit,
                "sort": "recent",
            }

            try:
                response = await client.get(
                    AMAZON_API_URL,
                    params=params,
                )

                response.raise_for_status()

                data = response.json()

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Amazon jobs: {error}"
                )
                break

            amazon_jobs = data.get("jobs", [])

            if not amazon_jobs:
                break

            for job in amazon_jobs:

                job_path = job.get("job_path", "")

                if job_path:
                    job_url = AMAZON_BASE_URL + job_path
                else:
                    job_url = ""

                jobs.append({
                    "title": job.get("title", ""),
                    "company_name": (
                        job.get("company_name")
                        or "Amazon"
                    ),
                    "location": (
                        job.get("location")
                        or job.get("normalized_location", "")
                    ),
                    "url": job_url,
                    "description": job.get(
                        "description",
                        ""
                    ),
                    "source": "Amazon Jobs",
                })

            total = data.get("hits", 0)

            offset += limit

            if offset >= total:
                break

    return jobs