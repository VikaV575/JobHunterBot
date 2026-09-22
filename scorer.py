import re


STUDENT_SCORE_RULES = {
    # Only true student/intern signals belong here.
    "working student": 82,
    "student software": 82,
    "student developer": 82,
    "student engineer": 82,
    "software student": 82,
    "engineering student": 82,
    "student position": 80,
    "student role": 80,
    "internship": 80,
    "intern": 79,
    "student": 78,
    "co-op": 76,
    "coop": 76,
    "undergraduate": 74,
}


ROLE_SCORE_RULES = {
    "validation": 30,
    "verification": 30,
    "design verification": 30,
    "silicon validation": 30,
    "post silicon": 30,
    "post-silicon": 30,
    "embedded": 29,
    "firmware": 29,
    "system software": 28,
    "systems software": 28,
    "backend": 27,
    "back-end": 27,
    "software": 26,
    "developer": 24,
    "test automation": 24,
    "automation engineer": 24,
    "sdet": 24,
    "test engineer": 22,
    "qa": 20,
    "quality assurance": 20,
    "security engineer": 23,
    "application security": 23,
    "product security": 23,
    "cybersecurity": 22,
    "cyber security": 22,
    "devops": 21,
    "site reliability": 21,
    "sre": 21,
    "platform engineer": 20,
    "cloud engineer": 20,
    "infrastructure engineer": 20,
    "frontend": 19,
    "front-end": 19,
    "full stack": 20,
    "full-stack": 20,
    "fpga": 24,
    "rtl": 24,
    "data engineer": 18,
    "machine learning": 18,
    "ml engineer": 18,
    "computer vision": 18,
    "algorithm": 18,
}


SKILL_SCORE_RULES = {
    "python": 4,
    "c++": 5,
    " c ": 4,
    "java": 4,
    "linux": 5,
    "git": 2,
    "docker": 3,
    "kubernetes": 3,
    "networking": 4,
    "tcp": 3,
    "systemverilog": 5,
    "verilog": 4,
    "debugging": 3,
    "data structures": 4,
    "algorithms": 4,
    "computer science": 3,
}


MAX_DESCRIPTION_CHARS = 20000
YEARS_PATTERN = re.compile(
    r"\b(\d{1,2})\+?\s*(?:years|yrs)\b",
    re.IGNORECASE,
)


def _compile_rules(rules):
    compiled = []

    for keyword, points in rules.items():
        pattern = re.compile(
            r"(?<![a-z0-9])"
            + re.escape(keyword.lower())
            + r"(?![a-z0-9])",
            re.IGNORECASE,
        )

        compiled.append(
            (keyword, points, pattern)
        )

    return compiled


COMPILED_STUDENT_RULES = _compile_rules(
    STUDENT_SCORE_RULES
)
COMPILED_ROLE_RULES = _compile_rules(
    ROLE_SCORE_RULES
)
COMPILED_SKILL_RULES = _compile_rules(
    SKILL_SCORE_RULES
)


def _matching_rules(text, compiled_rules):
    return [
        (keyword, points)
        for keyword, points, pattern in compiled_rules
        if pattern.search(text)
    ]


def _experience_penalty(description):
    years = [
        int(match)
        for match in YEARS_PATTERN.findall(description)
    ]

    if not years:
        return 0

    required_years = max(years)

    if required_years >= 5:
        return 25

    if required_years >= 3:
        return 12

    return 0


def _score_and_labels(job):
    title = str(
        job.get("title", "")
    ).lower()

    description = str(
        job.get("description", "")
    ).lower()[:MAX_DESCRIPTION_CHARS]

    title_student_matches = _matching_rules(
        title,
        COMPILED_STUDENT_RULES,
    )

    if title_student_matches:
        student_score = max(
            points
            for _, points in title_student_matches
        )
        strongest_student = max(
            title_student_matches,
            key=lambda item: item[1],
        )[0]
    else:
        description_student_matches = _matching_rules(
            description,
            COMPILED_STUDENT_RULES,
        )

        if description_student_matches:
            strongest = max(
                description_student_matches,
                key=lambda item: item[1],
            )

            student_score = min(
                55,
                round(strongest[1] * 0.75),
            )
            strongest_student = (
                f"{strongest[0]} in description"
            )
        else:
            student_score = 0
            strongest_student = None

    role_matches = sorted(
        _matching_rules(
            title,
            COMPILED_ROLE_RULES,
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    role_score = 0

    if role_matches:
        role_score = role_matches[0][1]

        if len(role_matches) > 1:
            role_score += round(
                role_matches[1][1] * 0.25
            )

        role_score = min(role_score, 32)

    skill_matches = _matching_rules(
        f"{title} {description}",
        COMPILED_SKILL_RULES,
    )

    skill_score = min(
        sum(points for _, points in skill_matches),
        12,
    )

    penalty = _experience_penalty(description)

    score = max(
        0,
        min(
            round(
                student_score
                + role_score
                + skill_score
                - penalty
            ),
            100,
        ),
    )

    labels = []

    if strongest_student:
        labels.append(strongest_student)

    for keyword, _ in role_matches:
        if keyword not in labels:
            labels.append(keyword)

        if len(labels) >= 4:
            break

    return score, labels[:4]


def score_job(job):
    score, _ = _score_and_labels(job)
    return score


def score_jobs(jobs):
    print(f"Scoring {len(jobs)} jobs...")

    for job in jobs:
        score, labels = _score_and_labels(job)
        job["score"] = score
        job["matches"] = labels

    ranked_jobs = sorted(
        jobs,
        key=lambda job: (
            job["score"],
            any(
                pattern.search(
                    str(job.get("title", "")).lower()
                )
                for _, _, pattern in COMPILED_STUDENT_RULES
            ),
        ),
        reverse=True,
    )

    print("Scoring complete")

    return ranked_jobs
