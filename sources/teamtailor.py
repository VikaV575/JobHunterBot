import xml.etree.ElementTree as ET

import httpx


TEAMTAILOR_COMPANIES = {
    "Moburst": "moburst",
}


def _local_name(tag):
    return tag.split("}")[-1].split(":")[-1].lower()


def _child_text(element, names):
    wanted = {name.lower() for name in names}

    for child in element:
        if _local_name(child.tag) in wanted and child.text:
            text = child.text.strip()
            if text:
                return text

    return ""


async def get_teamtailor_jobs():
    jobs = []

    headers = {
        "Accept": "application/rss+xml, application/xml, text/xml",
        "User-Agent": "JobHunterBot/1.0",
    }

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        for company_name, slug in TEAMTAILOR_COMPANIES.items():
            url = f"https://{slug}.teamtailor.com/jobs.rss?per_page=200"

            try:
                response = await client.get(url)
                response.raise_for_status()

                root = ET.fromstring(response.text)

                for item in root.findall(".//item"):
                    title = item.findtext("title", default="").strip()
                    link = item.findtext("link", default="").strip()
                    description = item.findtext(
                        "description",
                        default=""
                    ).strip()

                    city = _child_text(item, {"city"})
                    country = _child_text(item, {"country"})
                    location = _child_text(
                        item,
                        {"location", "locations", "joblocation"}
                    )

                    if not location:
                        location = ", ".join(
                            part for part in [city, country] if part
                        )

                    remote_status = _child_text(
                        item,
                        {"remotestatus", "remote_status"}
                    )
                    if not location and remote_status.lower() in {
                        "fully",
                        "temporary",
                        "remote",
                    }:
                        location = "Remote"

                    jobs.append({
                        "title": title,
                        "company_name": company_name,
                        "location": location,
                        "url": link,
                        "description": description,
                        "source": "Teamtailor",
                    })

            except (httpx.HTTPError, ET.ParseError) as error:
                print(
                    f"Failed getting Teamtailor jobs "
                    f"for {company_name}: {error}"
                )

    return jobs
