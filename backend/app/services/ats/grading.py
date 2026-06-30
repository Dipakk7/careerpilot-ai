from app.core.ats_constants import GRADE_THRESHOLDS

def determine_grade(overall_score: int) -> str:
    """Map score to grade using GRADE_THRESHOLDS.
    Implemented in Part 2.
    """
    sorted_thresholds = sorted(GRADE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True)
    for grade, threshold in sorted_thresholds:
        if overall_score >= threshold:
            return grade
    return "Needs Improvement"

def generate_grade_summary(grade: str) -> str:
    """Return a brief user-friendly summary of the grade."""
    summaries = {
        "Excellent": "Resume is ATS optimized.",
        "Good": "Resume is strong but has room for improvement.",
        "Fair": "Several important resume sections need improvement.",
        "Needs Improvement": "Resume requires significant improvements.",
    }
    return summaries.get(grade, "Resume requires significant improvements.")

