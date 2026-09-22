import re


STUDENT_SCORE_RULES = {
    "working student": 60,
    "student software": 60,
    "student developer": 60,
    "student engineer": 60,
    "student position": 58,
    "student role": 58,
    "internship": 58,
    "intern": 56,
    "student": 55,
    "co-op": 52,
    "coop": 52,
    "new college grad": 45,
    "new grad": 42,
    "graduate software": 40,
    "graduate engineer": 38,
    "junior": 28,
    "entry level": 25,
    "entry-level": 25,
    "undergraduate": 22,
    "part time": 15,
    "part-time": 15,
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


def _contains_keyword(text, keyword):
    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(keyword.lower())
        + r"(?![a-z0-9])"
    )

    return re.search(pattern, text.lower()) is not None


def _matching_rules(text, rules):
    return [
        (keyword, points)
        for keyword, points in rules.items()
        if _contains_keyword(text, keyword)
    ]


def _best_student_score(title, description):
    title_matches = _matching_rules(
        title,
        STUDENT_SCORE_RULES,
    )

    if title_matches:
        return max(points for _, points in title_matches)

    description_matches = _matching_rules(
        description,
        STUDENT_SCORE_RULES,
    )

    if description_matches:
        # A student/intern signal in the description matters, but it is
        # weaker than having it explicitly in the job title.
        return min(
            28,
            round(
                max(points for _, points in description_matches)
                * 0.5
            ),
        )

    return 0


def _role_score(title):
    matches = sorted(
        _matching_rules(title, ROLE_SCORE_RULES),
        key=lambda item: item[1],
        reverse=True,
    )

    if not matches:
        return 0

    score = matches[0][1]

    # A second distinct role signal is useful, but should not double-count.
    if len(matches) > 1:
        score += round(matches[1][1] * 0.25)

    return min(score, 32)


def _skill_score(title, description):
    text = f"{title} {description}"

    matched_points = [
        points
        for _, points in _matching_rules(
            text,
            SKILL_SCORE_RULES,
        )
    ]

    return min(sum(matched_points), 12)


def _experience_penalty(description):
    description = description.lower()

    years = [
        int(match)
        for match in re.findall(
            r"\b(\d{1,2})\+?\s*(?:years|yrs)\b",
            description,
        )
    ]

    if not years:
        return 0

    required_years = max(years)

    if required_years >= 5:
        return 25

    if required_years >= 3:
        return 12

    return 0


def _match_labels(title, description):
    labels = []

    student_matches = sorted(
        _matching_rules(title, STUDENT_SCORE_RULES),
        key=lambda item: item[1],
        reverse=True,
    )

    if student_matches:
        labels.append(student_matches[0][0])
    else:
        description_student_matches = sorted(
            _matching_rules(
                description,
                STUDENT_SCORE_RULES,
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        if description_student_matches:
            labels.append(
                f"{description_student_matches[0][0]} in description"
            )

    role_matches = sorted(
        _matching_rules(title, ROLE_SCORE_RULES),
        key=lambda item: item[1],
        reverse=True,
    )

    for keyword, _ in role_matches:
        if keyword not in labels:
            labels.append(keyword)

        if len(labels) >= 4:
            break

    return labels[:4]


def score_job(job):
    title = str(job.get("title", "")).lower()
    description = str(job.get("description", "")).lower()

    student_score = _best_student_score(
        title,
        description,
    )

    role_score = _role_score(title)
    skill_score = _skill_score(
        title,
        description,
    )

    penalty = _experience_penalty(description)

    score = (
        student_score
        + role_score
        + skill_score
        - penalty
    )

    # Relevant non-student roles should still get a useful score, while
    # explicit student/intern roles naturally rise to the top.
    score = max(0, min(round(score), 100))

    return score


def score_jobs(jobs):
    for job in jobs:
        title = str(job.get("title", "")).lower()
        description = str(
            job.get("description", "")
        ).lower()

        job["score"] = score_job(job)
        job["matches"] = _match_labels(
            title,
            description,
        )

    return sorted(
        jobs,
        key=lambda job: (
            job["score"],
            "student" in job.get("title", "").lower()
            or "intern" in job.get("title", "").lower(),
        ),
        reverse=True,
    )
