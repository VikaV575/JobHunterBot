import httpx


LEVER_COMPANIES = {
    "WalkMe": "walkme",
    "Palantir": "palantir",
    "Zadara": "Zadara",
    "Tonkean": "tonkean",
    "TRAILD": "traildsoftware",
    "Houzz": "houzz",
}


async def get_lever_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, site_name in LEVER_COMPANIES.items():
            url = (
                f"https://api.lever.co/v0/postings/"
                f"{site_name}?mode=json"
            )

            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                for job in data:
                    jobs.append({
                        "title": job.get("text", ""),
                        "company_name": company_name,
                        "location": job.get(
                            "categories",
                            {}
                        ).get("location", ""),
                        "url": (
                            job.get("hostedUrl")
                            or job.get("applyUrl", "")
                        ),
                        "description": job.get(
                            "descriptionPlain",
                            ""
                        ),
                        "source": "Lever",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Lever jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
