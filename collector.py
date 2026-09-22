import asyncio

from sources.amazon import get_amazon_jobs
from sources.ashby import get_ashby_jobs
from sources.bamboohr import get_bamboohr_jobs
from sources.breezy import get_breezy_jobs
from sources.comeet import get_comeet_jobs
from sources.greenhouse import get_greenhouse_jobs
from sources.lever import get_lever_jobs
from sources.personio import get_personio_jobs
from sources.pinpoint import get_pinpoint_jobs
from sources.recruitee import get_recruitee_jobs
from sources.rippling import get_rippling_jobs
from sources.smartrecruiters import get_smartrecruiters_jobs
from sources.teamtailor import get_teamtailor_jobs
from sources.workable import get_workable_jobs
from sources.workday import get_workday_jobs


SOURCES = [
    ("Lever", get_lever_jobs),
    ("Greenhouse", get_greenhouse_jobs),
    ("Ashby", get_ashby_jobs),
    ("SmartRecruiters", get_smartrecruiters_jobs),
    ("Workday", get_workday_jobs),
    ("Amazon", get_amazon_jobs),
    ("Workable", get_workable_jobs),
    ("Comeet", get_comeet_jobs),
    ("Recruitee", get_recruitee_jobs),
    ("Teamtailor", get_teamtailor_jobs),
    ("Rippling", get_rippling_jobs),
    ("Personio", get_personio_jobs),
    ("BambooHR", get_bamboohr_jobs),
    ("Breezy HR", get_breezy_jobs),
    ("Pinpoint", get_pinpoint_jobs),
]


async def _collect_source(source_name, source_function):
    try:
        jobs = await source_function()
        print(f"{source_name}: {len(jobs)}")
        return jobs

    except Exception as error:
        print(
            f"{source_name} failed: "
            f"{type(error).__name__}: {error}"
        )
        return []


def _deduplicate_jobs(jobs):
    unique_jobs = []
    seen = set()

    for job in jobs:
        url = str(job.get("url", "")).strip().rstrip("/")

        if url:
            key = ("url", url.lower())
        else:
            key = (
                "job",
                str(job.get("company_name", "")).strip().lower(),
                str(job.get("title", "")).strip().lower(),
                str(job.get("location", "")).strip().lower(),
            )

        if key in seen:
            continue

        seen.add(key)
        unique_jobs.append(job)

    return unique_jobs


async def get_jobs():
    source_results = await asyncio.gather(
        *(
            _collect_source(source_name, source_function)
            for source_name, source_function in SOURCES
        )
    )

    jobs = [
        job
        for source_jobs in source_results
        for job in source_jobs
    ]

    jobs = _deduplicate_jobs(jobs)

    print(f"Total unique jobs: {len(jobs)}")

    return jobs
