import xml.etree.ElementTree as ET

import httpx


PERSONIO_COMPANIES = {
    "Package.AI": {
        "slug": "package-ai",
        "domain": "com",
    },
}


def _element_text(element):
    if element is None:
        return ""

    return " ".join(
        text.strip()
        for text in element.itertext()
        if text and text.strip()
    )


async def get_personio_jobs():
    jobs = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for company_name, config in PERSONIO_COMPANIES.items():
            slug = config["slug"]
            domain = config.get("domain", "de")

            base_url = f"https://{slug}.jobs.personio.{domain}"
            feed_url = f"{base_url}/xml?language=en"

            try:
                response = await client.get(feed_url)
                response.raise_for_status()

                root = ET.fromstring(response.text)

                for position in root.findall(".//position"):
                    job_id = position.findtext("id", default="").strip()
                    title = position.findtext(
                        "name",
                        default=""
                    ).strip()
                    office = position.findtext(
                        "office",
                        default=""
                    ).strip()

                    additional_offices = [
                        item.text.strip()
                        for item in position.findall(
                            ".//additionalOffices/*"
                        )
                        if item.text and item.text.strip()
                    ]

                    location = " / ".join(
                        dict.fromkeys(
                            part
                            for part in [office, *additional_offices]
                            if part
                        )
                    )

                    descriptions = []
                    for block in position.findall(
                        ".//jobDescriptions/jobDescription"
                    ):
                        block_name = block.findtext(
                            "name",
                            default=""
                        ).strip()
                        block_value = _element_text(block.find("value"))

                        if block_name or block_value:
                            descriptions.append(
                                f"{block_name}\n{block_value}".strip()
                            )

                    jobs.append({
                        "title": title,
                        "company_name": company_name,
                        "location": location,
                        "url": (
                            f"{base_url}/job/{job_id}?language=en"
                            if job_id
                            else base_url
                        ),
                        "description": "\n\n".join(descriptions),
                        "source": "Personio",
                    })

            except (httpx.HTTPError, ET.ParseError) as error:
                print(
                    f"Failed getting Personio jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
