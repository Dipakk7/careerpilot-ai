JOB_MATCH_VERSION = "v1"

MATCH_WEIGHTS = {
    "skills": 40,
    "experience": 25,
    "education": 15,
    "certifications": 10,
    "keywords": 10
}

assert sum(MATCH_WEIGHTS.values()) == 100, "MATCH_WEIGHTS must sum to 100"

MATCH_GRADES = {
    "Excellent": 90,
    "Good": 75,
    "Fair": 50,
    "Poor": 0
}

MATCH_LEVELS = [
    "matched",
    "missing",
    "extra"
]

RECOMMENDATION_PRIORITY = [
    "high",
    "medium",
    "low"
]
