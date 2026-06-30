import os
import sys
import unittest
import uuid
from datetime import datetime, timezone
import structlog

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.models.resume import Resume
from app.schemas.job_match import JobDescription, JobMatchResponse, MatchBreakdown, MatchRecommendation
from app.services.job_match.matcher import (
    match_skills,
    match_experience,
    match_education,
    match_certifications,
    match_keywords,
    calculate_experience_years,
    get_degree_rank
)
from app.services.job_match.analyzer import (
    calculate_match_breakdown,
    calculate_match_score,
    find_missing_items,
    find_extra_items
)
from app.services.job_match.recommendations import generate_job_recommendations
from app.services.job_match.job_match_service import calculate_job_match

class TestJobMatchingEngine(unittest.TestCase):

    # --- Matcher Tests ---

    def test_skills_perfect_match(self):
        resume_skills = ["Python", "FastAPI", "Docker"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        res = match_skills(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["score"], 100)
        self.assertEqual(res["matched_required"], ["FastAPI", "Python"])
        self.assertEqual(res["matched_preferred"], ["Docker"])
        self.assertEqual(res["missing_required"], [])
        self.assertEqual(res["missing_preferred"], [])

    def test_skills_missing_required(self):
        resume_skills = ["FastAPI", "Docker"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        # Required skills are missing 1 of 2 -> 50% matched.
        # Base req score: 0.5 * 80 = 40. Pref score: 1.0 * 20 = 20.
        # Penalty for 1 missing required skill: 10.
        # Score = max(0, 40 + 20 - 10) = 50.
        res = match_skills(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["score"], 50)
        self.assertIn("Python", res["missing_required"])

    def test_skills_missing_preferred(self):
        resume_skills = ["Python", "FastAPI"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        # All required match (80). Preferred is missing (0).
        # Penalty: 0 (no required skills missing).
        # Score = 80 + 0 = 80.
        res = match_skills(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["score"], 80)
        self.assertIn("Docker", res["missing_preferred"])

    def test_skills_extra_skills(self):
        resume_skills = ["Python", "FastAPI", "Docker", "Kubernetes", "AWS"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        res = match_skills(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["score"], 100)
        self.assertEqual(res["extra_skills"], ["AWS", "Kubernetes"])

    def test_skills_normalization(self):
        resume_skills = ["  python ", "FASTAPI", "Python"]
        required_skills = ["Python", "fastapi"]
        preferred_skills = []
        res = match_skills(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["score"], 100)
        self.assertCountEqual([s.lower() for s in res["matched_required"]], ["fastapi", "python"])

    def test_experience_exact_match(self):
        resume_exp = [{"duration": "3 years", "title": "SE"}]
        job_exp = ["3+ years of experience"]
        res = match_experience(resume_exp, job_exp)
        self.assertEqual(res["experience_score"], 100)
        self.assertTrue(res["matched"])
        self.assertEqual(res["missing"], [])

    def test_experience_more_than_required(self):
        resume_exp = [{"duration": "5 years", "title": "SE"}]
        job_exp = ["3 years"]
        res = match_experience(resume_exp, job_exp)
        self.assertEqual(res["experience_score"], 100)
        self.assertTrue(res["matched"])

    def test_experience_less_than_required(self):
        resume_exp = [{"duration": "2 years", "title": "SE"}]
        job_exp = ["Minimum 5 years"]
        res = match_experience(resume_exp, job_exp)
        # Score should be proportional (2/5 * 100) = 40.
        self.assertEqual(res["experience_score"], 40)
        self.assertFalse(res["matched"])
        self.assertIn("Requires 5.0 years", res["missing"][0])

    def test_experience_no_requirement(self):
        resume_exp = [{"duration": "2 years", "title": "SE"}]
        job_exp = []
        res = match_experience(resume_exp, job_exp)
        self.assertEqual(res["experience_score"], 100)
        self.assertTrue(res["matched"])
        self.assertEqual(res["missing"], [])

    def test_experience_duration_parsing_yrs(self):
        self.assertEqual(calculate_experience_years("3 years"), 3.0)
        self.assertEqual(calculate_experience_years("2.5 yrs"), 2.5)

    def test_experience_duration_parsing_range(self):
        # Jan 2020 - Dec 2022 -> (2022-2020)*12 + (12-1) = 35 months.
        # (35 + 1)/12 = 3.0 years
        self.assertEqual(calculate_experience_years("Jan 2020 - Dec 2022"), 3.0)

    def test_experience_duration_parsing_present(self):
        # Assuming current mock year is 2026/06.
        # "2024 - Present" -> (2026 - 2024)*12 + (6 - 1) = 29 months. (29+1)/12 = 2.5 years.
        # We test that it successfully extracts a float value.
        val = calculate_experience_years("2024 - Present")
        self.assertGreater(val, 0.0)

    def test_experience_duration_parsing_months(self):
        self.assertEqual(calculate_experience_years("6 months"), 0.5)

    def test_education_perfect_match_same_rank(self):
        resume_edu = [{"degree": "Bachelor of Technology"}]
        job_edu = ["B.Tech"]
        res = match_education(resume_edu, job_edu)
        self.assertEqual(res["score"], 100)
        self.assertTrue(res["matched"])

    def test_education_higher_rank_match(self):
        resume_edu = [{"degree": "MS in CS"}]
        job_edu = ["Bachelor"]
        res = match_education(resume_edu, job_edu)
        self.assertEqual(res["score"], 100)
        self.assertTrue(res["matched"])

    def test_education_lower_rank_partial_match(self):
        resume_edu = [{"degree": "BS in CS"}]
        job_edu = ["Master"]
        # Required is Master (rank 2), candidate has Bachelor (rank 1).
        # Score = (1/2)*100 = 50.
        res = match_education(resume_edu, job_edu)
        self.assertEqual(res["score"], 50)
        self.assertFalse(res["matched"])
        self.assertEqual(res["missing"], job_edu)

    def test_education_no_match(self):
        resume_edu = []
        job_edu = ["PhD"]
        res = match_education(resume_edu, job_edu)
        self.assertEqual(res["score"], 0)
        self.assertFalse(res["matched"])

    def test_education_no_requirement(self):
        resume_edu = [{"degree": "Bachelor"}]
        job_edu = []
        res = match_education(resume_edu, job_edu)
        self.assertEqual(res["score"], 100)
        self.assertTrue(res["matched"])

    def test_certifications_perfect_match(self):
        resume_certs = ["AWS Certified Solutions Architect", "Kubernetes Administrator"]
        job_certs = ["AWS", "Kubernetes"]
        res = match_certifications(resume_certs, job_certs)
        self.assertEqual(res["score"], 100)
        self.assertEqual(res["matched"], ["AWS Certified Solutions Architect", "Kubernetes Administrator"])
        self.assertEqual(res["missing"], [])

    def test_certifications_partial_match(self):
        resume_certs = ["AWS Certified Solutions Architect"]
        job_certs = ["AWS", "Kubernetes"]
        # Matched 1 of 2 -> 50%
        res = match_certifications(resume_certs, job_certs)
        self.assertEqual(res["score"], 50)
        self.assertIn("Kubernetes", res["missing"])

    def test_certifications_no_requirement(self):
        resume_certs = ["AWS"]
        job_certs = []
        res = match_certifications(resume_certs, job_certs)
        self.assertEqual(res["score"], 100)
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["extra"], ["AWS"])

    def test_keywords_perfect_match(self):
        resume_kw = ["python", "fastapi", "docker"]
        job_kw = ["python", "fastapi"]
        res = match_keywords(resume_kw, job_kw)
        self.assertEqual(res["keyword_score"], 100)
        self.assertEqual(res["matched_keywords"], ["fastapi", "python"])
        self.assertEqual(res["missing_keywords"], [])

    def test_keywords_partial_match(self):
        resume_kw = ["python"]
        job_kw = ["python", "fastapi"]
        res = match_keywords(resume_kw, job_kw)
        self.assertEqual(res["keyword_score"], 50)
        self.assertEqual(res["missing_keywords"], ["fastapi"])

    def test_keywords_no_requirement(self):
        resume_kw = ["python"]
        job_kw = []
        res = match_keywords(resume_kw, job_kw)
        self.assertEqual(res["keyword_score"], 100)

    # --- Analyzer Tests ---

    def test_breakdown_calculation(self):
        bd = calculate_match_breakdown(100, 80, 50, 0, 90)
        self.assertEqual(bd.skills, 100)
        self.assertEqual(bd.experience, 80)
        self.assertEqual(bd.education, 50)
        self.assertEqual(bd.certifications, 0)
        self.assertEqual(bd.keywords, 90)

    def test_overall_score_calculation(self):
        # Weights: skills (40%), experience (25%), education (15%), certifications (10%), keywords (10%)
        # 100*0.40 + 80*0.25 + 60*0.15 + 50*0.10 + 90*0.10
        # = 40 + 20 + 9 + 5 + 9 = 83
        bd = MatchBreakdown(skills=100, experience=80, education=60, certifications=50, keywords=90)
        self.assertEqual(calculate_match_score(bd), 83)

    def test_overall_score_clamping(self):
        bd_low = MatchBreakdown(skills=0, experience=0, education=0, certifications=0, keywords=0)
        self.assertEqual(calculate_match_score(bd_low), 0)
        bd_high = MatchBreakdown(skills=100, experience=100, education=100, certifications=100, keywords=100)
        self.assertEqual(calculate_match_score(bd_high), 100)

    def test_grade_excellent(self):
        # Score >= 90 is Excellent
        self.assertEqual(calculate_job_match_mock_grade(95), "Excellent")
        self.assertEqual(calculate_job_match_mock_grade(90), "Excellent")

    def test_grade_good(self):
        # Score >= 75 and < 90 is Good
        self.assertEqual(calculate_job_match_mock_grade(85), "Good")
        self.assertEqual(calculate_job_match_mock_grade(75), "Good")

    def test_grade_fair(self):
        # Score >= 50 and < 75 is Fair
        self.assertEqual(calculate_job_match_mock_grade(65), "Fair")
        self.assertEqual(calculate_job_match_mock_grade(50), "Fair")

    def test_grade_poor(self):
        # Score < 50 is Poor
        self.assertEqual(calculate_job_match_mock_grade(45), "Poor")
        self.assertEqual(calculate_job_match_mock_grade(0), "Poor")

    # --- Recommendations Tests ---

    def test_recommendation_priorities_sorting(self):
        recs = generate_job_recommendations(
            missing_skills=["Python"],
            missing_education=["Master"],
            missing_certifications=["AWS"],
            missing_experience=["Requires 3.0 years of experience"],
            missing_keywords=["FastAPI"]
        )
        # Skills and Experience are HIGH.
        # Education and Certifications are MEDIUM.
        # Keywords are LOW.
        # We verify ordering is HIGH -> MEDIUM -> LOW
        priorities = [r.priority for r in recs]
        self.assertEqual(priorities[0], "high")
        self.assertEqual(priorities[1], "high")
        self.assertEqual(priorities[2], "medium")
        self.assertEqual(priorities[3], "medium")
        self.assertEqual(priorities[4], "low")

    def test_recommendation_deduplication(self):
        recs = generate_job_recommendations(
            missing_skills=["Python", "Python"],
            missing_education=["Bachelor"],
            missing_certifications=[],
            missing_experience=[],
            missing_keywords=[]
        )
        self.assertEqual(len(recs), 2)  # 1 for Python, 1 for Bachelor

    def test_recommendation_limit(self):
        # Generate 15 items
        recs = generate_job_recommendations(
            missing_skills=[f"Skill{i}" for i in range(15)],
            missing_education=[],
            missing_certifications=[],
            missing_experience=[],
            missing_keywords=[]
        )
        # Should be limited to JOB_MATCH_MAX_RECOMMENDATIONS (default 10)
        self.assertLessEqual(len(recs), 10)

    def test_missing_items_gathering(self):
        res = find_missing_items(["Python"], ["Master"], ["AWS"], ["2 yrs"], ["FastAPI"])
        self.assertEqual(res["skills"], ["Python"])
        self.assertEqual(res["education"], ["Master"])
        self.assertEqual(res["certifications"], ["AWS"])
        self.assertEqual(res["experience"], ["2 yrs"])
        self.assertEqual(res["keywords"], ["FastAPI"])

    def test_extra_items_gathering(self):
        res = find_extra_items(["Java"], ["PMP"])
        self.assertEqual(res["skills"], ["Java"])
        self.assertEqual(res["certifications"], ["PMP"])

    # --- Pipeline Tests ---

    def test_job_match_service_perfect_match(self):
        resume = Resume(
            id=uuid.uuid4(),
            raw_text="Python FastAPI Developer with AWS Certified Solutions Architect and Bachelor's. 3 years experience.",
            parsed_data={
                "parser_version": "v2",
                "data": {
                    "skills": {"value": ["Python", "FastAPI"]},
                    "education": {"value": [{"degree": "Bachelor of Technology"}]},
                    "experience": {"value": [{"duration": "3 years", "title": "Developer", "description": "Python FastAPI development"}]},
                    "certifications": {"value": ["AWS"]}
                }
            }
        )
        jd = JobDescription(
            title="Python Developer",
            company="TechCorp",
            required_skills=["Python"],
            preferred_skills=["FastAPI"],
            education=["Bachelor"],
            experience=["3 years"],
            certifications=["AWS"],
            responsibilities=["Develop backend APIs"],
            keywords=["Python", "FastAPI"],
            raw_text="Python FastAPI Developer with AWS. Bachelor's and 3 years experience required."
        )
        res = calculate_job_match(resume, jd)
        self.assertEqual(res.match_score, 100)
        self.assertEqual(res.grade, "Excellent")
        self.assertEqual(res.recommendations, [])

    def test_job_match_service_poor_match(self):
        resume = Resume(
            id=uuid.uuid4(),
            raw_text="Junior programmer with some HTML knowledge.",
            parsed_data={
                "parser_version": "v2",
                "data": {
                    "skills": {"value": ["HTML"]},
                    "education": {"value": []},
                    "experience": {"value": []},
                    "certifications": {"value": []}
                }
            }
        )
        jd = JobDescription(
            title="Senior backend engineer",
            company="Google",
            required_skills=["Python", "FastAPI"],
            preferred_skills=["Kubernetes"],
            education=["PhD"],
            experience=["5 years"],
            certifications=["AWS"],
            responsibilities=["Lead team"],
            keywords=["Python", "FastAPI", "Kubernetes"],
            raw_text="Looking for PhD with 5 years experience in Python and FastAPI."
        )
        res = calculate_job_match(resume, jd)
        # Verify score is low, grade is poor, recommendations are present.
        self.assertLess(res.match_score, 40)
        self.assertEqual(res.grade, "Poor")
        self.assertGreater(len(res.recommendations), 0)

    def test_job_match_service_validation_missing_parsed_data(self):
        resume = Resume(id=uuid.uuid4(), parsed_data=None)
        jd = JobDescription(
            required_skills=[], preferred_skills=[], education=[], experience=[],
            certifications=[], responsibilities=[], keywords=[], raw_text=""
        )
        with self.assertRaises(ValueError):
            calculate_job_match(resume, jd)

    def test_job_match_service_validation_missing_job_desc(self):
        resume = Resume(
            id=uuid.uuid4(),
            parsed_data={"data": {}}
        )
        with self.assertRaises(ValueError):
            calculate_job_match(resume, None)

    def test_job_match_service_logging(self):
        resume = Resume(
            id=uuid.uuid4(),
            parsed_data={
                "data": {
                    "skills": {"value": ["Python"]},
                    "experience": {"value": []},
                    "education": {"value": []},
                    "certifications": {"value": []}
                }
            }
        )
        jd = JobDescription(
            required_skills=["Python"], preferred_skills=[], education=[], experience=[],
            certifications=[], responsibilities=[], keywords=[], raw_text=""
        )
        res = calculate_job_match(resume, jd)
        self.assertEqual(res.match_score, 100)

# Helper function to mock grading logic for test assertion
def calculate_job_match_mock_grade(score: int) -> str:
    from app.core.job_match_constants import MATCH_GRADES
    sorted_grades = sorted(MATCH_GRADES.items(), key=lambda x: x[1], reverse=True)
    for gr, threshold in sorted_grades:
        if score >= threshold:
            return gr
    return "Poor"

if __name__ == "__main__":
    unittest.main()
