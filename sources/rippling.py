import httpx


RIPPLING_COMPANIES = {
    "Wenrix": "wenrix",
    "Prime Security": "primesecurity",
}


def _location_text(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        parts = [
            value.get("label"),
            value.get("name"),
            value.get("city"),
            value.get("state"),
            value.get("country"),
        ]
        return ", ".join(
            dict.fromkeys(str(part).strip() for part in parts if part)
        )

    if isinstance(value, list):
        locations = [_location_text(item) for item in value]
        return " / ".join(
            dict.fromkeys(location for location in locations if location)
        )

    return ""


async def get_rippling_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, slug in RIPPLING_COMPANIES.items():
            url = (
                "https://api.rippling.com/platform/api/ats/v1/"
                f"board/{slug}/jobs"
            )

            try:
                response = await client.get(
                    url,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()

                data = response.json()

                if isinstance(data, list):
                    postings = data
                elif isinstance(data, dict):
                    postings = (
                        data.get("jobs")
                        or data.get("result")
                        or data.get("data")
                        or []
                    )
                    if isinstance(postings, dict):
                        postings = (
                            postings.get("jobs")
                            or postings.get("data")
                            or []
                        )
                else:
                    postings = []

                for job in postings:
                    job_id = (
                        job.get("uuid")
                        or job.get("id")
                        or job.get("jobId")
                    )

                    location = (
                        _location_text(job.get("workLocation"))
                        or _location_text(job.get("locations"))
                        or _location_text(job.get("location"))
                    )

                    job_url = (
                        job.get("url")
                        or job.get("jobUrl")
                        or (
                            f"https://ats.rippling.com/{slug}/jobs/{job_id}"
                            if job_id
                            else ""
                        )
                    )

                    jobs.append({
                        "title": (
                            job.get("name")
                            or job.get("title", "")
                        ),
                        "company_name": company_name,
                        "location": location,
                        "url": job_url,
                        "description": (
                            job.get("description")
                            or job.get("descriptionHtml", "")
                        ),
                        "source": "Rippling",
                    })

            except httpx.HTTPError as error:
                print(
                    f"Failed getting Rippling jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
