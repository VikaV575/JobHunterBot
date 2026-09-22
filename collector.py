import asyncio

from sources.amazon import get_amazon_jobs
from sources.apple import get_apple_jobs
from sources.ashby import get_ashby_jobs
from sources.comeet import get_comeet_jobs
from sources.direct_company_sites import get_direct_company_jobs
from sources.devjobs import get_devjobs_jobs
from sources.greenhouse import get_greenhouse_jobs
from sources.google_careers import get_google_careers_jobs
from sources.jobnet import get_jobnet_jobs
from sources.lever import get_lever_jobs
from sources.microsoft import get_microsoft_jobs
from sources.personio import get_personio_jobs
from sources.recruitee import get_recruitee_jobs
from sources.rippling import get_rippling_jobs
from sources.sap import get_sap_jobs
from sources.smartrecruiters import get_smartrecruiters_jobs
from sources.synopsys import get_synopsys_jobs
from sources.teamtailor import get_teamtailor_jobs
from sources.workable import get_workable_jobs
from sources.workday import get_workday_jobs


SOURCES = [
    ("Lever", get_lever_jobs),
    ("Google Careers", get_google_careers_jobs),
    ("Apple Careers", get_apple_jobs),
    ("Microsoft Careers", get_microsoft_jobs),
    ("Synopsys Careers", get_synopsys_jobs),
    ("SAP Careers", get_sap_jobs),
    ("DevJobs", get_devjobs_jobs),
    ("Jobnet", get_jobnet_jobs),
    ("Direct company sites", get_direct_company_jobs),
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
]

SOURCE_TIMEOUT_SECONDS = 60
SOURCE_CONCURRENCY = 6

# Workday internally checks many companies, each with its own timeout.
# Giving the whole Workday source only 60 seconds caused us to throw away
# already-collected Workday jobs when a few slow companies were still running.
SOURCE_TIMEOUTS = {
    "Workday": 150,
}


async def _collect_source(
    semaphore,
    source_name,
    source_function,
):
    async with semaphore:
        timeout_seconds = SOURCE_TIMEOUTS.get(
            source_name,
            SOURCE_TIMEOUT_SECONDS,
        )

        try:
            jobs = await asyncio.wait_for(
                source_function(),
                timeout=timeout_seconds,
            )

            print(f"{source_name}: {len(jobs)}")
            return jobs

        except asyncio.TimeoutError:
            print(
                f"{source_name}: timed out after "
                f"{timeout_seconds}s, skipping it"
            )
            return []

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
            key = (
                "url",
                url.lower(),
                str(job.get("title", "")).strip().lower(),
            )
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
    # Do not start every ATS at once. Too much parallel DNS/network traffic
    # caused intermittent macOS resolver errors such as Errno 8.
    semaphore = asyncio.Semaphore(SOURCE_CONCURRENCY)

    source_results = await asyncio.gather(
        *(
            _collect_source(
                semaphore,
                source_name,
                source_function,
            )
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
