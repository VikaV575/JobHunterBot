import re

from config import (
    EXCLUDE_KEYWORDS,
    ISRAEL_LOCATIONS,
    NON_TECH_TITLE_KEYWORDS,
    STUDENT_KEYWORDS,
    TECH_CONTEXT_KEYWORDS,
    TECH_TITLE_KEYWORDS,
    WEAK_TECH_TITLE_KEYWORDS,
)


def _contains_keyword(text, keyword):
    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(keyword.lower())
        + r"(?![a-z0-9])"
    )

    return re.search(pattern, text.lower()) is not None


def _contains_any(text, keywords):
    return any(
        _contains_keyword(text, keyword)
        for keyword in keywords
    )


def is_in_israel(job):
    location = str(job.get("location", "")).lower()

    return any(
        place in location
        for place in ISRAEL_LOCATIONS
    )


def is_relevant_job(job):
    title = str(job.get("title", ""))
    description = str(job.get("description", ""))

    if _contains_any(title, EXCLUDE_KEYWORDS):
        return False

    if _contains_any(title, NON_TECH_TITLE_KEYWORDS):
        return False

    # This bot is student-first: a role must explicitly look like a
    # student/intern/co-op/undergraduate/entry-level role. Junior and
    # ordinary full-time engineering roles are intentionally excluded.
    student_signal = (
        _contains_any(title, STUDENT_KEYWORDS)
        or _contains_any(description, STUDENT_KEYWORDS)
    )

    if not student_signal:
        return False

    strong_tech_title = _contains_any(
        title,
        TECH_TITLE_KEYWORDS,
    )

    weak_tech_title = _contains_any(
        title,
        WEAK_TECH_TITLE_KEYWORDS,
    )

    technical_context = _contains_any(
        f"{title} {description}",
        TECH_CONTEXT_KEYWORDS,
    )

    # A clear technical title plus a student signal is enough.
    if strong_tech_title:
        return True

    # Broad titles such as "R&D Intern" or "Engineering Student" are kept
    # only when the description is clearly technical.
    if weak_tech_title and technical_context:
        return True

    # Generic "Intern" / "Student" titles must have strong technical context.
    if technical_context:
        return True

    return False


def filter_jobs(jobs):
    relevant_jobs = []

    for job in jobs:
        if not is_in_israel(job):
            continue

        if is_relevant_job(job):
            relevant_jobs.append(job)

    print("relevant_jobs:", len(relevant_jobs))
    return relevant_jobs
