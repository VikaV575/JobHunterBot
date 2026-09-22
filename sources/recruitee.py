import os

import httpx


RECRUITEE_COMPANIES = {
    "Aikido Security": {
        "slug": "aikidosecurity",
        "token_env": "AIKIDO_RECRUITEE_TOKEN",
    },
}


def _location_text(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        parts = [_location_text(item) for item in value]
        return " / ".join(dict.fromkeys(part for part in parts if part))

    if isinstance(value, dict):
        parts = [
            value.get("name"),
            value.get("city"),
            value.get("state"),
            value.get("country"),
        ]
        return ", ".join(
            dict.fromkeys(str(part).strip() for part in parts if part)
        )

    return ""


async def get_recruitee_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, config in RECRUITEE_COMPANIES.items():
            slug = config["slug"]
            url = f"https://{slug}.recruitee.com/api/offers/"

            headers = {"Accept": "application/json"}
            token_env = config.get("token_env")
            token = os.getenv(token_env) if token_env else None

            if token:
                headers["X-Careers-Sites-Token"] = token

            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if isinstance(data, list):
                    offers = data
                elif isinstance(data, dict):
                    offers = data.get("offers", [])
                else:
                    offers = []

                for job in offers:
                    location = (
                        _location_text(job.get("locations"))
                        or _location_text(job.get("location"))
                    )

                    description_parts = [
                        job.get("description"),
                        job.get("description_html"),
                        job.get("requirements"),
                        job.get("requirements_html"),
                    ]

                    job_slug = job.get("slug", "")
                    job_url = (
                        job.get("careers_url")
                        or job.get("url")
                        or (
                            f"https://{slug}.recruitee.com/o/{job_slug}"
                            if job_slug
                            else ""
                        )
                    )

                    jobs.append({
                        "title": job.get("title", ""),
                        "company_name": company_name,
                        "location": location,
                        "url": job_url,
                        "description": "\n".join(
                            str(part) for part in description_parts if part
                        ),
                        "source": "Recruitee",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Recruitee jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
