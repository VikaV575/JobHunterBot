import httpx


GREENHOUSE_COMPANIES = {
    "Gong": {
        "token": "gongio",
        "region": "us",
    },
    "At-Bay": {
        "token": "atbayjobs",
        "region": "us",
    },
    "Pagaya": {
        "token": "pagayais",
        "region": "us",
    },
    "Pendo": {
        "token": "pendo",
        "region": "us",
    },
    "DoiT": {
        "token": "doitintl",
        "region": "us",
    },
    "Aidoc": {
        "token": "aidocmedical",
        "region": "eu",
    },
    "accessiBe": {
        "token": "accessibe",
        "region": "eu",
    },
}


def _api_host(region):
    if region == "eu":
        return "https://boards-api.eu.greenhouse.io"

    return "https://boards-api.greenhouse.io"


async def get_greenhouse_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, config in GREENHOUSE_COMPANIES.items():
            board_token = config["token"]
            host = _api_host(config.get("region", "us"))

            url = (
                f"{host}/v1/boards/"
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
