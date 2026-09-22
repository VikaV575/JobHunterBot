import httpx


ASHBY_COMPANIES = {
    "Viz.ai": "Viz.ai",
    "HUMAN": "HUMAN",
    "Finout": "finout",
    "Nexxen": "nexxen",
    "Chamelio": "chamelio",
}


async def get_ashby_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for company_name, board_name in ASHBY_COMPANIES.items():
            url = (
                "https://api.ashbyhq.com/"
                f"posting-api/job-board/{board_name}"
            )

            try:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                for job in data.get("jobs", []):
                    jobs.append({
                        "title": job.get("title", ""),
                        "company_name": company_name,
                        "location": job.get("location", ""),
                        "url": job.get("jobUrl", ""),
                        "description": job.get(
                            "descriptionPlain",
                            ""
                        ),
                        "source": "Ashby",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Ashby jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
