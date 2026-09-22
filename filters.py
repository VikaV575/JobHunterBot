from config import (
    TECH_KEYWORDS,
    EXCLUDE_KEYWORDS,
    ISRAEL_LOCATIONS
)


def is_in_israel(job):
    location = job.get("location", "").lower()

    return any(
        place in location
        for place in ISRAEL_LOCATIONS
    )


def filter_jobs(jobs):
    relevant_jobs = []

    for job in jobs:
        title = job.get("title", "").lower()

        is_tech = any(
            keyword in title
            for keyword in TECH_KEYWORDS
        )

        is_excluded = any(
            keyword in title
            for keyword in EXCLUDE_KEYWORDS
        )

        in_israel = is_in_israel(job)

        if is_tech and in_israel and not is_excluded:
            relevant_jobs.append(job)

    print("relevant_jobs: ", len(relevant_jobs))
    return relevant_jobs