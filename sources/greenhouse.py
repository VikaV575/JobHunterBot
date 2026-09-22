import asyncio

import httpx


GREENHOUSE_COMPANIES = {
    "Gong": "gongio",
    "At-Bay": "atbayjobs",
    "Pagaya": "pagayais",
    "Pendo": "pendo",
    "DoiT": "doitintl",
    "Aidoc": "aidocmedical",
    "accessiBe": "accessibe",
    "Cato Networks": "catonetworks",
    "Similarweb": "similarweb",
    "JFrog": "jfrog",
    "Wiz": "wizinc",
    "AppsFlyer": "appsflyer",
    "Taboola": "taboola",
    "Riskified": "riskified",
    "Fireblocks": "fireblocks",
    "Connecteam": "connecteam",

    # Additional Israeli / Israel-R&D companies.
    "Armis Security": "armissecurity",
    "Melio": "melio",
    "Bringg": "bringg",
    "Torq": "torq",
    "Apiiro": "apiiro",
    "Salt Security": "saltsecurity",
    "BigID": "bigid",
}


GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"
GREENHOUSE_CONCURRENCY = 8


async def _get_company_jobs(
    semaphore,
    client,
    company_name,
    board_token,
):
    async with semaphore:
        url = (
            f"{GREENHOUSE_API_BASE}/"
            f"{board_token}/jobs?content=true"
        )

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPError as error:
            print(
                f"Failed getting Greenhouse jobs "
                f"for {company_name}: {error}"
            )
            return []

        jobs = []

        for job in data.get("jobs", []):
            jobs.append({
                "title": job.get("title", ""),
                "company_name": company_name,
                "location": job.get(
                    "location",
                    {},
                ).get("name", ""),
                "url": job.get("absolute_url", ""),
                "description": job.get("content", ""),
                "source": "Greenhouse",
            })

        return jobs


async def get_greenhouse_jobs():
    semaphore = asyncio.Semaphore(
        GREENHOUSE_CONCURRENCY
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
                    board_token,
                )
                for company_name, board_token
                in GREENHOUSE_COMPANIES.items()
            )
        )

    return [
        job
        for company_jobs in results
        for job in company_jobs
    ]
