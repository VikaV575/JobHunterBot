import asyncio

import httpx


ASHBY_COMPANIES = {
    "Viz.ai": "Viz.ai",
    "HUMAN": "HUMAN",
    "Finout": "finout",
    "Nexxen": "nexxen",
    "Chamelio": "chamelio",

    # Smaller / fast-growing companies with Tel Aviv or Israel teams.
    "Semperis": "semperis",
    "PointFive": "pointfive",
    "Irregular": "Irregular",
    "Maxima": "Maxima",
    "Strix": "strix",
    "Reindeer": "reindeer-ai",
    "Shapes": "shapes",
    "Echo": "echo.ai",
    "Tavily": "tavily",
    "Matia": "matia",
    "Act Security": "act",
    "Loora": "loora",
    "Oak": "oak",
}


ASHBY_CONCURRENCY = 8


async def _get_company_jobs(
    semaphore,
    client,
    company_name,
    board_name,
):
    async with semaphore:
        url = (
            "https://api.ashbyhq.com/"
            f"posting-api/job-board/{board_name}"
        )

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPError as error:
            print(
                f"Failed getting Ashby jobs "
                f"for {company_name}: {error}"
            )
            return []

        jobs = []

        for job in data.get("jobs", []):
            jobs.append({
                "title": job.get("title", ""),
                "company_name": company_name,
                "location": job.get("location", ""),
                "url": job.get("jobUrl", ""),
                "description": job.get(
                    "descriptionPlain",
                    "",
                ),
                "source": "Ashby",
            })

        return jobs


async def get_ashby_jobs():
    semaphore = asyncio.Semaphore(
        ASHBY_CONCURRENCY
    )

    async with httpx.AsyncClient(
        timeout=20.0,
    ) as client:
        results = await asyncio.gather(
            *(
                _get_company_jobs(
                    semaphore,
                    client,
                    company_name,
                    board_name,
                )
                for company_name, board_name
                in ASHBY_COMPANIES.items()
            )
        )

    return [
        job
        for company_jobs in results
        for job in company_jobs
    ]
