import httpx


LEVER_COMPANIES = {
    "WalkMe": {
        "site": "walkme",
        "region": "global",
    },
    "Palantir": {
        "site": "palantir",
        "region": "global",
    },
    "Zadara": {
        "site": "Zadara",
        "region": "global",
    },
    "Tonkean": {
        "site": "tonkean",
        "region": "global",
    },
    "TRAILD": {
        "site": "traildsoftware",
        "region": "global",
    },
    "Houzz": {
        "site": "houzz",
        "region": "global",
    },
    "Mobileye": {
        "site": "mobileye",
        "region": "eu",
    },
}


def _api_base(region):
    if region == "eu":
        return "https://api.eu.lever.co/v0/postings"

    return "https://api.lever.co/v0/postings"


async def get_lever_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, config in LEVER_COMPANIES.items():
            site_name = config["site"]
            base_url = _api_base(
                config.get("region", "global")
            )

            url = (
                f"{base_url}/{site_name}"
                "?mode=json"
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
                        "source": (
                            "Lever EU"
                            if config.get("region") == "eu"
                            else "Lever"
                        ),
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Lever jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
