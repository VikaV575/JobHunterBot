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
}


GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"


async def get_greenhouse_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, board_token in GREENHOUSE_COMPANIES.items():
            url = (
                f"{GREENHOUSE_API_BASE}/"
                f"{board_token}/jobs?content=true"
            )

            try:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                for job in data.get("jobs", []):
                    jobs.append({
                        "title": job.get("title", ""),
                        "company_name": company_name,
                        "location": job.get(
                            "location",
                            {}
                        ).get("name", ""),
                        "url": job.get("absolute_url", ""),
                        "description": job.get("content", ""),
                        "source": "Greenhouse",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Greenhouse jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
