ATS_VERSION = "v1"
# Track scoring algorithm version for debugging
# and future comparison when scoring logic changes

SCORE_WEIGHTS = {
    "contact": 10,
    "skills": 25,
    "education": 15,
    "experience": 25,
    "projects": 15,
    "certifications": 10
}
# Must sum to exactly 100 — verify with assert at module load:
assert sum(SCORE_WEIGHTS.values()) == 100, \
    "SCORE_WEIGHTS must sum to 100"

ACTION_VERBS = [
    "achieved", "built", "created", "designed", "developed",
    "engineered", "established", "executed", "implemented",
    "improved", "increased", "initiated", "launched", "led",
    "managed", "optimized", "reduced", "resolved", "spearheaded",
    "streamlined", "transformed", "delivered", "architected",
    "automated", "deployed", "integrated", "scaled", "mentored"
]

WEAK_PHRASES = [
    "responsible for", "worked on", "helped with",
    "assisted in", "involved in", "participated in",
    "duties included", "in charge of"
]

GRADE_THRESHOLDS = {
    "Excellent": 90,
    "Good": 70,
    "Fair": 50,
    "Needs Improvement": 0
}

RECOMMENDATION_CATEGORIES = [
    "contact", "skills", "education", "experience",
    "projects", "certifications", "formatting"
]

RECOMMENDATION_PRIORITIES = ["high", "medium", "low"]
