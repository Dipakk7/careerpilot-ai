import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.models.resume import Resume
from app.schemas.job_match import JobDescription
from app.schemas.job_gap import GapAnalysisResponse
from app.services.job_match.gap_analysis import (
    analyze_skill_gaps,
    analyze_experience_gap,
    analyze_education_gap,
    analyze_certification_gap,
    analyze_keyword_gap
)
from app.services.job_match.prioritizer import prioritize_gaps
from app.services.job_match.job_match_service import analyze_resume_gap

class TestGapAnalysisEngine(unittest.TestCase):

    # --- Skill Gap Tests (7 Tests) ---

    def test_01_skills_perfect_match(self):
        resume_skills = ["Python", "FastAPI", "Docker"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        res = analyze_skill_gaps(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["matched"], ["Docker", "FastAPI", "Python"])
        self.assertEqual(res["missing_required"], [])
        self.assertEqual(res["missing_preferred"], [])
        self.assertEqual(res["extra_resume_skills"], [])

    def test_02_skills_missing_required(self):
        resume_skills = ["FastAPI", "Docker"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        res = analyze_skill_gaps(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["matched"], ["Docker", "FastAPI"])
        self.assertEqual(res["missing_required"], ["Python"])
        self.assertEqual(res["missing_preferred"], [])
        self.assertEqual(res["extra_resume_skills"], [])

    def test_03_skills_missing_preferred(self):
        resume_skills = ["Python", "FastAPI"]
        required_skills = ["Python", "FastAPI"]
        preferred_skills = ["Docker"]
        res = analyze_skill_gaps(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["matched"], ["FastAPI", "Python"])
        self.assertEqual(res["missing_required"], [])
        self.assertEqual(res["missing_preferred"], ["Docker"])
        self.assertEqual(res["extra_resume_skills"], [])

    def test_04_skills_extra_only(self):
        resume_skills = ["Python", "FastAPI", "AWS", "Kubernetes"]
        required_skills = ["Python"]
        preferred_skills = ["FastAPI"]
        res = analyze_skill_gaps(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["matched"], ["FastAPI", "Python"])
        self.assertEqual(res["missing_required"], [])
        self.assertEqual(res["missing_preferred"], [])
        self.assertEqual(res["extra_resume_skills"], ["AWS", "Kubernetes"])

    def test_05_skills_case_insensitive(self):
        resume_skills = ["python", "FASTAPI"]
        required_skills = ["Python", "fastapi"]
        preferred_skills = []
        res = analyze_skill_gaps(resume_skills, required_skills, preferred_skills)
        # Should preserve the job/resume casing using casing map
        self.assertEqual(len(res["matched"]), 2)
        self.assertEqual(res["missing_required"], [])

    def test_06_skills_duplicates_removed(self):
        resume_skills = ["Python", "Python", "Python", "FastAPI"]
        required_skills = ["Python", "FastAPI", "FastAPI"]
        preferred_skills = []
        res = analyze_skill_gaps(resume_skills, required_skills, preferred_skills)
        self.assertEqual(res["matched"], ["FastAPI", "Python"])
        self.assertEqual(res["missing_required"], [])
        self.assertEqual(res["missing_preferred"], [])

    def test_07_skills_empty_inputs(self):
        res = analyze_skill_gaps([], [], [])
        self.assertEqual(res["matched"], [])
        self.assertEqual(res["missing_required"], [])
        self.assertEqual(res["missing_preferred"], [])
        self.assertEqual(res["extra_resume_skills"], [])


    # --- Experience Gap Tests (6 Tests) ---

    def test_08_experience_perfect_match(self):
        resume_exp = [{"duration": "3 years"}]
        job_exp = ["3 years"]
        res = analyze_experience_gap(resume_exp, job_exp)
        self.assertTrue(res["matched"])
        self.assertEqual(res["required"], "3.0 years")
        self.assertEqual(res["resume"], "3.0 years")
        self.assertEqual(res["gap"], "0.0 years")

    def test_09_experience_exceeds_requirement(self):
        resume_exp = [{"duration": "5 years"}]
        job_exp = ["3 years"]
        res = analyze_experience_gap(resume_exp, job_exp)
        self.assertTrue(res["matched"])
        self.assertEqual(res["required"], "3.0 years")
        self.assertEqual(res["resume"], "5.0 years")
        self.assertEqual(res["gap"], "0.0 years")

    def test_10_experience_under_requirement(self):
        resume_exp = [{"duration": "2 years"}]
        job_exp = ["5 years"]
        res = analyze_experience_gap(resume_exp, job_exp)
        self.assertFalse(res["matched"])
        self.assertEqual(res["required"], "5.0 years")
        self.assertEqual(res["resume"], "2.0 years")
        self.assertEqual(res["gap"], "3.0 years")

    def test_11_experience_no_requirement(self):
        resume_exp = [{"duration": "2 years"}]
        job_exp = []
        res = analyze_experience_gap(resume_exp, job_exp)
        self.assertTrue(res["matched"])
        self.assertEqual(res["required"], "0.0 years")
        self.assertEqual(res["resume"], "2.0 years")
        self.assertEqual(res["gap"], "0.0 years")

    def test_12_experience_no_resume_experience(self):
        resume_exp = []
        job_exp = ["3 years"]
        res = analyze_experience_gap(resume_exp, job_exp)
        self.assertFalse(res["matched"])
        self.assertEqual(res["required"], "3.0 years")
        self.assertEqual(res["resume"], "0.0 years")
        self.assertEqual(res["gap"], "3.0 years")

    def test_13_experience_complex_formats(self):
        resume_exp = [{"duration": "Jan 2020 - Dec 2022"}]  # 3.0 years
        job_exp = ["Minimum of 4 years"]
        res = analyze_experience_gap(resume_exp, job_exp)
        self.assertFalse(res["matched"])
        self.assertEqual(res["required"], "4.0 years")
        self.assertAlmostEqual(float(res["resume"].split()[0]), 3.0, places=1)
        self.assertAlmostEqual(float(res["gap"].split()[0]), 1.0, places=1)


    # --- Education Gap Tests (7 Tests) ---

    def test_14_education_perfect_match_same_rank(self):
        resume_edu = [{"degree": "Bachelor of Science"}]
        job_edu = ["Bachelor"]
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertTrue(res["matched"])
        self.assertEqual(res["required"], "Bachelor")
        self.assertEqual(res["resume"], "Bachelor of Science")
        self.assertEqual(res["gap"], "None")

    def test_15_education_perfect_match_higher_rank(self):
        resume_edu = [{"degree": "Master of Science"}]
        job_edu = ["Bachelor"]
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertTrue(res["matched"])
        self.assertEqual(res["required"], "Bachelor")
        self.assertEqual(res["resume"], "Master of Science")
        self.assertEqual(res["gap"], "None")

    def test_16_education_missing_degree_rank(self):
        resume_edu = [{"degree": "Bachelor of Science"}]
        job_edu = ["Master"]
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertFalse(res["matched"])
        self.assertEqual(res["required"], "Master")
        self.assertEqual(res["resume"], "Bachelor of Science")
        self.assertIn("Missing required degree level", res["gap"])

    def test_17_education_no_requirement(self):
        resume_edu = [{"degree": "Bachelor of Science"}]
        job_edu = []
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertTrue(res["matched"])
        self.assertEqual(res["required"], "None")
        self.assertEqual(res["resume"], "Bachelor of Science")
        self.assertEqual(res["gap"], "None")

    def test_18_education_no_resume_education(self):
        resume_edu = []
        job_edu = ["Master"]
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertFalse(res["matched"])
        self.assertEqual(res["required"], "Master")
        self.assertEqual(res["resume"], "None")
        self.assertIn("Missing required degree level", res["gap"])

    def test_19_education_case_insensitive_ranks(self):
        resume_edu = [{"degree": "mba"}]  # mba ranks 2 (master level)
        job_edu = ["Master"]
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertTrue(res["matched"])

    def test_20_education_duplicates_removed(self):
        resume_edu = [{"degree": "Bachelor"}, {"degree": "Bachelor"}]
        job_edu = ["Bachelor"]
        res = analyze_education_gap(resume_edu, job_edu)
        self.assertEqual(res["resume"], "Bachelor")


    # --- Certification Gap Tests (5 Tests) ---

    def test_21_certifications_perfect_match(self):
        resume_certs = ["AWS Certified Solutions Architect"]
        job_certs = ["AWS"]
        res = analyze_certification_gap(resume_certs, job_certs)
        self.assertEqual(res["matched"], ["AWS Certified Solutions Architect"])
        self.assertEqual(res["missing"], [])

    def test_22_certifications_missing_certs(self):
        resume_certs = ["Certified Scrum Master"]
        job_certs = ["PMP", "AWS Certified Solutions Architect"]
        res = analyze_certification_gap(resume_certs, job_certs)
        self.assertEqual(res["matched"], [])
        self.assertEqual(res["missing"], ["AWS Certified Solutions Architect", "PMP"])

    def test_23_certifications_substring_match(self):
        resume_certs = ["AWS Cloud Practitioner"]
        job_certs = ["AWS Cloud Practitioner Associate"]
        res = analyze_certification_gap(resume_certs, job_certs)
        self.assertEqual(res["matched"], ["AWS Cloud Practitioner"])
        self.assertEqual(res["missing"], [])

    def test_24_certifications_no_requirement(self):
        resume_certs = ["AWS Cloud Practitioner"]
        job_certs = []
        res = analyze_certification_gap(resume_certs, job_certs)
        self.assertEqual(res["matched"], [])
        self.assertEqual(res["missing"], [])

    def test_25_certifications_case_insensitive(self):
        resume_certs = ["aws certified"]
        job_certs = ["AWS CERTIFIED"]
        res = analyze_certification_gap(resume_certs, job_certs)
        self.assertEqual(len(res["matched"]), 1)
        self.assertEqual(res["missing"], [])


    # --- Keyword Gap Tests (4 Tests) ---

    def test_26_keywords_perfect_match(self):
        resume_keywords = ["Microservices", "REST API"]
        job_keywords = ["microservices", "rest api"]
        res = analyze_keyword_gap(resume_keywords, job_keywords)
        self.assertEqual([k.lower() for k in res["matched"]], ["microservices", "rest api"])
        self.assertEqual(res["missing"], [])

    def test_27_keywords_missing_keywords(self):
        resume_keywords = ["Microservices"]
        job_keywords = ["Microservices", "GraphQL", "gRPC"]
        res = analyze_keyword_gap(resume_keywords, job_keywords)
        self.assertEqual(res["matched"], ["Microservices"])
        self.assertEqual(res["missing"], ["GraphQL", "gRPC"])

    def test_28_keywords_no_requirement(self):
        resume_keywords = ["Microservices"]
        job_keywords = []
        res = analyze_keyword_gap(resume_keywords, job_keywords)
        self.assertEqual(res["matched"], [])
        self.assertEqual(res["missing"], [])

    def test_29_keywords_case_insensitive(self):
        resume_keywords = ["graphql"]
        job_keywords = ["GraphQL"]
        res = analyze_keyword_gap(resume_keywords, job_keywords)
        self.assertEqual([k.lower() for k in res["matched"]], ["graphql"])
        self.assertEqual(res["missing"], [])


    # --- Prioritizer Tests (2 Tests) ---

    def test_30_prioritizer_ordering(self):
        skill_gap = {"missing_required": ["Python"], "missing_preferred": ["Docker"]}
        experience_gap = {"matched": False, "required": "5.0 years", "resume": "3.0 years"}
        education_gap = {"matched": False, "required": "Master"}
        certification_gap = {"missing": ["AWS Solutions Architect"]}
        keyword_gap = {"missing": ["GraphQL"]}
        
        res = prioritize_gaps(
            skill_gap=skill_gap,
            experience_gap=experience_gap,
            education_gap=education_gap,
            certification_gap=certification_gap,
            keyword_gap=keyword_gap
        )
        
        # Verify HIGH priority elements are first
        self.assertEqual(res[0]["priority"], "HIGH")
        # Ensure we have skills, experience, and education under HIGH
        high_categories = {item["category"] for item in res if item["priority"] == "HIGH"}
        self.assertEqual(high_categories, {"skills", "experience", "education"})
        
        # Ensure ordering: HIGH -> MEDIUM -> LOW
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        priorities = [item["priority"] for item in res]
        sorted_priorities = sorted(priorities, key=lambda x: priority_order[x])
        self.assertEqual(priorities, sorted_priorities)

    def test_31_prioritizer_formatting_checks(self):
        # Test formatting check triggered by raw text and missing links
        resume = Resume(
            id=uuid.uuid4(),
            raw_text="Some text with   extra   spaces\tAnd tabs.",
            parsed_data={"data": {"links": []}}
        )
        res = prioritize_gaps(
            skill_gap={}, experience_gap={}, education_gap={}, certification_gap={}, keyword_gap={},
            resume=resume
        )
        categories = {item["category"] for item in res}
        self.assertIn("formatting", categories)
        messages = [item["message"] for item in res if item["category"] == "formatting"]
        # Should have layout/spacing warning and links warning
        self.assertTrue(any("links" in msg for msg in messages))
        self.assertTrue(any("spacing" in msg or "margins" in msg or "margins" in msg or "formatting" in msg for msg in messages))


    # --- Pipeline / Service Tests (2 Tests) ---

    def test_32_analyze_resume_gap_pipeline_perfect(self):
        resume = Resume(
            id=uuid.uuid4(),
            raw_text="Python Developer",
            parsed_data={
                "data": {
                    "skills": {"value": ["Python", "FastAPI"]},
                    "experience": {"value": [{"duration": "3 years", "title": "SE"}]},
                    "education": {"value": [{"degree": "Bachelor of Science"}]},
                    "certifications": {"value": []}
                }
            }
        )
        jd = JobDescription(
            required_skills=["Python"],
            preferred_skills=[],
            education=["Bachelor"],
            experience=["3 years"],
            certifications=[],
            responsibilities=[],
            keywords=[],
            raw_text=""
        )
        res = analyze_resume_gap(resume, jd)
        self.assertTrue(isinstance(res, GapAnalysisResponse))
        self.assertTrue(res.overall_match)
        self.assertEqual(res.skill_gap.missing_required, [])
        self.assertTrue(res.experience_gap.matched)
        self.assertTrue(res.education_gap.matched)

    def test_33_analyze_resume_gap_pipeline_poor(self):
        resume = Resume(
            id=uuid.uuid4(),
            raw_text="Junior Dev",
            parsed_data={
                "data": {
                    "skills": {"value": ["HTML"]},
                    "experience": {"value": []},
                    "education": {"value": []},
                    "certifications": {"value": []}
                }
            }
        )
        jd = JobDescription(
            required_skills=["Python", "FastAPI"],
            preferred_skills=["Docker"],
            education=["Master"],
            experience=["5 years"],
            certifications=["AWS Architect"],
            responsibilities=[],
            keywords=["Microservices"],
            raw_text=""
        )
        res = analyze_resume_gap(resume, jd)
        self.assertTrue(isinstance(res, GapAnalysisResponse))
        self.assertFalse(res.overall_match)
        self.assertEqual(res.skill_gap.missing_required, ["FastAPI", "Python"])
        self.assertEqual(res.skill_gap.missing_preferred, ["Docker"])
        self.assertFalse(res.experience_gap.matched)
        self.assertFalse(res.education_gap.matched)
        self.assertEqual(res.certification_gap.missing, ["AWS Architect"])
        self.assertEqual(res.keyword_gap.missing, ["Microservices"])
        # Should have HIGH priority gaps in priority_improvements
        high_improvements = [item for item in res.priority_improvements if item["priority"] == "HIGH"]
        self.assertGreater(len(high_improvements), 0)

if __name__ == "__main__":
    unittest.main()
