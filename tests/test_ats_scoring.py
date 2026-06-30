import os
import sys
import unittest
import uuid
from datetime import datetime

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.ats_constants import SCORE_WEIGHTS
from app.services.ats.scoring import (
    score_contact,
    score_skills,
    score_education,
    score_experience,
    score_projects,
    score_certifications,
)
from app.services.ats.grading import determine_grade
from app.services.ats.ats_service import calculate_ats_score
from app.models.resume import Resume


class TestATSScoringEngine(unittest.TestCase):
    def test_contact_scoring(self):
        # 1. Empty data
        self.assertEqual(score_contact({}), 0)
        self.assertEqual(score_contact(None), 0)

        # 2. 1 field present (Email only)
        data_1 = {"data": {"email": {"value": "test@example.com"}}}
        # Max is 10. 1/3 present -> round(1/3 * 10) = 3
        self.assertEqual(score_contact(data_1), 3)

        # 3. 2 fields present (Email, Phone)
        data_2 = {"data": {"email": "test@example.com", "phone": {"value": "12345"}}}
        # 2/3 present -> round(2/3 * 10) = 7
        self.assertEqual(score_contact(data_2), 7)

        # 4. 3 fields present (Name, Email, Phone)
        data_3 = {
            "data": {
                "name": {"value": "John"},
                "email": {"value": "test@example.com"},
                "phone": {"value": "12345"},
            }
        }
        # 3/3 present -> 10
        self.assertEqual(score_contact(data_3), 10)

    def test_skills_scoring(self):
        # 1. Empty data
        self.assertEqual(score_skills({}), 0)
        self.assertEqual(score_skills(None), 0)

        # 2. Duplicate skills and empty strings
        data_skills = {
            "data": {
                "skills": {
                    "value": ["Python", "python", "", "  ", "Go", "Python", None]
                }
            }
        }
        # Unique skills list: {"python", "go"}. Length = 2.
        # Min skills for full score is 8 (from settings/default).
        # Score: round(2/8 * 25) = 6
        self.assertEqual(score_skills(data_skills), 6)

        # 3. Full score (8+ skills)
        data_full = {
            "data": {
                "skills": {
                    "value": [
                        "Python",
                        "Go",
                        "JavaScript",
                        "SQL",
                        "Docker",
                        "AWS",
                        "FastAPI",
                        "Git",
                    ]
                }
            }
        }
        self.assertEqual(score_skills(data_full), 25)

        # 4. Overflow skills (> 8)
        data_overflow = {
            "data": {
                "skills": {
                    "value": [
                        "Python",
                        "Go",
                        "JavaScript",
                        "SQL",
                        "Docker",
                        "AWS",
                        "FastAPI",
                        "Git",
                        "HTML",
                        "CSS",
                    ]
                }
            }
        }
        self.assertEqual(score_skills(data_overflow), 25)

    def test_education_scoring(self):
        # Max score: 15
        # 1. Empty education
        self.assertEqual(score_education({}), 0)
        self.assertEqual(score_education(None), 0)

        # 2. 1 entry - both institution and degree present
        # Quality: 1.0. Score: round(0.7 * 15 * 1.0) = 11
        data_1_full = {
            "data": {
                "education": {
                    "value": [
                        {"degree": "Bachelor of Science", "institution": "Stanford University"}
                    ]
                }
            }
        }
        self.assertEqual(score_education(data_1_full), 11)

        # 3. 1 entry - institution present, degree missing
        # Quality: 0.7. Score: round(0.7 * 15 * 0.7) = 7
        data_1_inst = {
            "data": {
                "education": {
                    "value": [{"degree": "", "institution": "Stanford University"}]
                }
            }
        }
        self.assertEqual(score_education(data_1_inst), 7)

        # 4. 1 entry - degree present, institution missing
        # Quality: 0.5. Score: round(0.7 * 15 * 0.5) = 5
        data_1_deg = {
            "data": {
                "education": {
                    "value": [{"degree": "Bachelor of Science", "institution": ""}]
                }
            }
        }
        self.assertEqual(score_education(data_1_deg), 5)

        # 5. 2+ entries - both complete
        # Avg quality: 1.0. Score: 15
        data_2_full = {
            "data": {
                "education": {
                    "value": [
                        {"degree": "BS", "institution": "Stanford"},
                        {"degree": "MS", "institution": "MIT"},
                    ]
                }
            }
        }
        self.assertEqual(score_education(data_2_full), 15)

        # 6. 2+ entries - one missing institution
        # Entry 1 quality: 1.0, Entry 2 quality: 0.5
        # Avg quality: 0.75. Score: round(15 * 0.75) = 11
        data_2_mixed = {
            "data": {
                "education": {
                    "value": [
                        {"degree": "BS", "institution": "Stanford"},
                        {"degree": "MS", "institution": ""},
                    ]
                }
            }
        }
        self.assertEqual(score_education(data_2_mixed), 11)

    def test_experience_scoring(self):
        # Max score: 25. Min experience entries target: 2
        # 1. Empty experience
        self.assertEqual(score_experience({}), 0)
        self.assertEqual(score_experience(None), 0)

        # 2. 1 entry - all 4 fields present
        # Quality: 1.0. Since min entries is 2, quantity factor is 0.5
        # Score: round(25 * (1.0 / 2)) = 13
        data_1_full = {
            "data": {
                "experience": {
                    "value": [
                        {
                            "title": "Engineer",
                            "company": "Google",
                            "duration": "2 years",
                            "description": "Built search engine stuff",
                        }
                    ]
                }
            }
        }
        self.assertEqual(score_experience(data_1_full), 13)

        # 3. 2 entries - all 4 fields present
        # Score: 25
        data_2_full = {
            "data": {
                "experience": {
                    "value": [
                        {
                            "title": "Engineer",
                            "company": "Google",
                            "duration": "2 years",
                            "description": "Built stuff",
                        },
                        {
                            "title": "Intern",
                            "company": "Meta",
                            "duration": "3 months",
                            "description": "Learnt stuff",
                        },
                    ]
                }
            }
        }
        self.assertEqual(score_experience(data_2_full), 25)

        # 4. 2 entries - mixed completeness
        # Entry 1: 4 fields (quality 1.0)
        # Entry 2: 2 fields (quality 0.5)
        # Avg quality of top 2: 0.75
        # Score: round(25 * 0.75) = 19
        data_2_mixed = {
            "data": {
                "experience": {
                    "value": [
                        {
                            "title": "Engineer",
                            "company": "Google",
                            "duration": "2 years",
                            "description": "Built stuff",
                        },
                        {
                            "title": "Intern",
                            "company": "Meta",
                        },
                    ]
                }
            }
        }
        self.assertEqual(score_experience(data_2_mixed), 19)

    def test_projects_scoring(self):
        # Max score: 15
        # 1. Empty projects
        self.assertEqual(score_projects({}), 0)
        self.assertEqual(score_projects(None), 0)

        # 2. 1 project - all 3 fields (name, description, technologies) present
        # Quality: 1.0. Target: 2. Score: round(15 * (1.0 / 2)) = 8
        data_1_full = {
            "data": {
                "projects": {
                    "value": [
                        {
                            "name": "Project A",
                            "description": "Awesome project",
                            "technologies": ["Python", "FastAPI"],
                        }
                    ]
                }
            }
        }
        self.assertEqual(score_projects(data_1_full), 8)

        # 3. 2 projects - all fields present
        # Score: 15
        data_2_full = {
            "data": {
                "projects": {
                    "value": [
                        {
                            "name": "Project A",
                            "description": "Awesome project",
                            "technologies": ["Python"],
                        },
                        {
                            "name": "Project B",
                            "description": "Another project",
                            "technologies": ["Go"],
                        },
                    ]
                }
            }
        }
        self.assertEqual(score_projects(data_2_full), 15)

    def test_certifications_scoring(self):
        # Max score: 10
        # 1. Empty certifications
        self.assertEqual(score_certifications({}), 0)
        self.assertEqual(score_certifications(None), 0)

        # 2. 1 certification -> half score (5)
        data_1 = {"data": {"certifications": {"value": ["AWS Certified Solutions Architect"]}}}
        self.assertEqual(score_certifications(data_1), 5)

        # 3. 2+ certifications -> full score (10)
        data_2 = {
            "data": {
                "certifications": {
                    "value": ["AWS Certified CSA", "Certified Scrum Master", "  "]
                }
            }
        }
        self.assertEqual(score_certifications(data_2), 10)

    def test_grade_calculation(self):
        # Thresholds: Excellent (90+), Good (70+), Fair (50+), Needs Improvement (under 50)
        self.assertEqual(determine_grade(95), "Excellent")
        self.assertEqual(determine_grade(90), "Excellent")
        self.assertEqual(determine_grade(89), "Good")
        self.assertEqual(determine_grade(70), "Good")
        self.assertEqual(determine_grade(69), "Fair")
        self.assertEqual(determine_grade(50), "Fair")
        self.assertEqual(determine_grade(49), "Needs Improvement")
        self.assertEqual(determine_grade(0), "Needs Improvement")

    def test_score_aggregation_and_limits(self):
        # Create a mock Resume model
        resume = Resume(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            original_filename="resume.pdf",
            stored_filename="resume_stored.pdf",
            file_path="storage/resumes/resume_stored.pdf",
            file_size=1024,
            file_type="pdf",
            mime_type="application/pdf",
        )

        # 1. Empty parsed_data -> score is 0
        resume.parsed_data = {}
        response = calculate_ats_score(resume)
        self.assertEqual(response.overall_score, 0)
        self.assertEqual(resume.ats_score, 0)
        self.assertEqual(response.grade, "Needs Improvement")
        self.assertEqual(response.strengths, [])
        self.assertEqual(response.weaknesses, [])
        self.assertEqual(response.recommendations, [])

        # 2. Full score resume data
        resume.parsed_data = {
            "parser_version": "v2",
            "data": {
                "name": {"value": "John Doe"},
                "email": {"value": "john@doe.com"},
                "phone": {"value": "12345"},
                "skills": {
                    "value": [
                        "Python",
                        "Go",
                        "Javascript",
                        "Docker",
                        "AWS",
                        "FastAPI",
                        "SQL",
                        "Git",
                    ]
                },
                "education": {
                    "value": [
                        {"degree": "BS CS", "institution": "Stanford"},
                        {"degree": "MS CS", "institution": "MIT"},
                    ]
                },
                "experience": {
                    "value": [
                        {
                            "title": "Engineer",
                            "company": "Google",
                            "duration": "2 years",
                            "description": "High performance APIs",
                        },
                        {
                            "title": "Lead Architect",
                            "company": "Netflix",
                            "duration": "3 years",
                            "description": "Distributed systems orchestration",
                        },
                    ]
                },
                "projects": {
                    "value": [
                        {
                            "name": "Project A",
                            "description": "A startup idea",
                            "technologies": ["Python", "Vue"],
                        },
                        {
                            "name": "Project B",
                            "description": "An open source project",
                            "technologies": ["Go", "Kubernetes"],
                        },
                    ]
                },
                "certifications": {
                    "value": ["AWS Solutions Architect", "Google Cloud Professional Architect"]
                },
            },
        }
        response = calculate_ats_score(resume)
        self.assertEqual(response.overall_score, 100)
        self.assertEqual(resume.ats_score, 100)
        self.assertEqual(response.grade, "Excellent")
        self.assertEqual(response.parser_version, "v2")

        # 3. Ensure score does not exceed 100 and handles invalid/garbage types gracefully
        # By giving large structures and weird types
        resume.parsed_data = {
            "data": {
                "name": "garbage name string but no dict",  # Invalid type (expects dict or has value attribute)
                "email": None,
                "skills": {"value": ["A"] * 100},  # All duplicates of "A"
                "education": "invalid type",
                "experience": [{"title": 12345}],  # Invalid inner type (ints instead of strings)
            }
        }
        # Let's verify it evaluates and aggregates without crash
        response = calculate_ats_score(resume)
        self.assertLessEqual(response.overall_score, 100)
        self.assertGreaterEqual(response.overall_score, 0)
        self.assertIn(response.grade, ["Excellent", "Good", "Fair", "Needs Improvement"])


if __name__ == "__main__":
    unittest.main()
