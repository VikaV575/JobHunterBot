SCORE_RULES = {
    "student": 50,
    "intern": 50,
    "validation": 25,
    "verification": 25,
    "backend": 20,
    "embedded": 30,
    "software": 30,
    "developer": 30,
    "engineer:": 20,
}


def score_job(job):
    title = job.get("title", "").lower()

    score = 0

    for keyword, points in SCORE_RULES.items():
        if keyword in title:
            score += points

    return min(score, 100)


def score_jobs(jobs):
    for job in jobs:
        job["score"] = score_job(job)

    return sorted(
        jobs,
        key=lambda job: job["score"],
        reverse=True
    )