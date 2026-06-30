import os
import sys
import unittest
import uuid
from unittest.mock import patch

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.schemas.ats import ATSBreakdown, ATSRecommendation
from app.services.ats.recommendations import (
    generate_strengths,
    generate_weaknesses,
    generate_recommendations,
)
from app.services.ats.ats_service import calculate_ats_score
from app.models.resume import Resume
from app.core.config import settings

class TestATSRecommendations(unittest.TestCase):
    def setUp(self):
        # Sample empty resume data structure
        self.empty_parsed_data = {
            "parser_version": "v2",
            "data": {
                "name": {"value": ""},
                "email": {"value": ""},
                "phone": {"value": ""},
                "links": {"value": []},
                "skills": {"value": []},
                "education": {"value": []},
                "experience": {"value": []},
                "projects": {"value": []},
                "certifications": {"value": []},
            }
        }
        self.empty_breakdown = {
            "contact": 0,
            "skills": 0,
            "education": 0,
            "experience": 0,
            "projects": 0,
            "certifications": 0,
        }

        # Sample complete resume data structure
        self.complete_parsed_data = {
            "parser_version": "v2",
            "data": {
                "name": {"value": "Jane Doe"},
                "email": {"value": "jane@doe.com"},
                "phone": {"value": "+1-555-0199"},
                "links": {"value": ["https://linkedin.com/in/janedoe"]},
                "skills": {"value": ["Python", "Django", "FastAPI", "Go", "Docker", "Kubernetes", "AWS", "SQL"]},
                "education": {"value": [
                    {"degree": "Bachelor of Science", "institution": "Stanford University"},
                    {"degree": "Master of Science", "institution": "Massachusetts Institute of Technology"}
                ]},
                "experience": {"value": [
                    {
                        "title": "Senior Engineer",
                        "company": "Google",
                        "duration": "3 years",
                        "description": "Led a team of engineers to build high-performance APIs and architected scalable backend systems.",
                    },
                    {
                        "title": "Engineer",
                        "company": "Meta",
                        "duration": "2 years",
                        "description": "Developed and deployed key microservices using Python and integrated them with cloud services.",
                    }
                ]},
                "projects": {"value": [
                    {
                        "name": "Project Alpha",
                        "description": "A cloud monitoring system built from scratch.",
                        "technologies": ["Go", "AWS", "Docker"],
                    },
                    {
                        "name": "Project Beta",
                        "description": "An AI-powered document scanner and parser.",
                        "technologies": ["Python", "FastAPI"],
                    }
                ]},
                "certifications": {"value": ["AWS Solutions Architect", "Certified Kubernetes Administrator"]},
            }
        }
        self.complete_breakdown = {
            "contact": 10,
            "skills": 25,
            "education": 15,
            "experience": 25,
            "projects": 15,
            "certifications": 10,
        }

    def test_strengths_generation_empty(self):
        # Empty parsed data should return no strengths
        strengths = generate_strengths(self.empty_parsed_data, self.empty_breakdown)
        self.assertEqual(strengths, [])

    def test_strengths_generation_complete(self):
        # Complete parsed data should return strengths
        strengths = generate_strengths(self.complete_parsed_data, self.complete_breakdown)
        expected_strengths = [
            "Complete contact information",
            "Strong technical skills",
            "Multiple projects",
            "Experience section complete",
            "Certifications present",
            "Well structured education",
            "Professional portfolio links",
        ]
        for expected in expected_strengths:
            self.assertIn(expected, strengths)

        # Maximum 10 strengths limit and no duplicates
        self.assertLessEqual(len(strengths), 10)
        self.assertEqual(len(strengths), len(set(strengths)))

    def test_weaknesses_generation_empty(self):
        # Empty parsed data should return weaknesses
        weaknesses = generate_weaknesses(self.empty_parsed_data, self.empty_breakdown)
        expected_weaknesses = [
            "Missing phone number",
            "Missing email address",
            "No technical skills listed",
            "No certifications",
            "No projects listed",
            "No work experience listed",
            "No education history listed",
            "No action verbs",
        ]
        for expected in expected_weaknesses:
            self.assertIn(expected, weaknesses)

        self.assertLessEqual(len(weaknesses), 10)
        self.assertEqual(len(weaknesses), len(set(weaknesses)))

    def test_weaknesses_generation_complete(self):
        # Complete parsed data should return no weaknesses
        weaknesses = generate_weaknesses(self.complete_parsed_data, self.complete_breakdown)
        self.assertEqual(weaknesses, [])

    def test_recommendation_priorities_correct(self):
        # Define test case with mixed score percentages
        # contact: 0/10 (0% -> High)
        # skills: 10/25 (40% -> High)
        # education: 11/15 (73.3% -> Medium)
        # experience: 20/25 (80% -> Medium)
        # projects: 13/15 (86.7% -> Low)
        # certifications: 5/10 (50% -> Medium)
        mixed_breakdown = {
            "contact": 0,
            "skills": 10,
            "education": 11,
            "experience": 20,
            "projects": 13,
            "certifications": 5,
        }
        recs = generate_recommendations(self.complete_parsed_data, mixed_breakdown)
        
        # Verify recommendation fields and types
        for r in recs:
            self.assertIsInstance(r, ATSRecommendation)
            self.assertIn(r.category, ["contact", "skills", "education", "experience", "projects", "certifications"])
            self.assertIn(r.priority, ["high", "medium", "low"])

        # Check mapping priorities
        priority_map = {r.category: r.priority for r in recs}
        self.assertEqual(priority_map["contact"], "high")
        self.assertEqual(priority_map["skills"], "high")
        self.assertEqual(priority_map["education"], "medium")
        self.assertEqual(priority_map["experience"], "medium")
        self.assertEqual(priority_map["certifications"], "medium")
        self.assertEqual(priority_map["projects"], "low")

        # Verify priority sorting: high first, then medium, then low
        priority_levels = [r.priority for r in recs]
        # Sort priority level list using standard custom order mapping: {"high": 0, "medium": 1, "low": 2}
        order = {"high": 0, "medium": 1, "low": 2}
        sorted_priorities = sorted(priority_levels, key=lambda p: order[p])
        self.assertEqual(priority_levels, sorted_priorities)

    def test_recommendation_limit_respected(self):
        # Setup mock limit to 3 recommendations
        with patch.object(settings, "ATS_RECOMMENDATION_LIMIT", 3):
            recs = generate_recommendations(self.empty_parsed_data, self.empty_breakdown)
            self.assertEqual(len(recs), 3)

    def test_duplicate_removal(self):
        # Test strength duplicate removal
        # Since our generate_strengths logic appends dynamically check-based lists,
        # we can verify that the list returns unique strengths.
        strengths = generate_strengths(self.complete_parsed_data, self.complete_breakdown)
        self.assertEqual(len(strengths), len(set(strengths)))

        # Test weakness duplicate removal
        weaknesses = generate_weaknesses(self.empty_parsed_data, self.empty_breakdown)
        self.assertEqual(len(weaknesses), len(set(weaknesses)))

    def test_empty_resume_orchestration(self):
        resume = Resume(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            original_filename="resume_empty.pdf",
            stored_filename="resume_empty_stored.pdf",
            file_path="storage/resumes/resume_empty_stored.pdf",
            file_size=1024,
            file_type="pdf",
            mime_type="application/pdf",
            parsed_data=self.empty_parsed_data
        )

        response = calculate_ats_score(resume)
        
        self.assertEqual(response.overall_score, 0)
        self.assertEqual(response.grade, "Needs Improvement")
        self.assertEqual(response.grade_summary, "Resume requires significant improvements.")
        self.assertEqual(response.strengths, [])
        self.assertGreater(len(response.weaknesses), 0)
        self.assertGreater(len(response.recommendations), 0)

        # Check recommendations are high priority
        for rec in response.recommendations:
            self.assertEqual(rec.priority, "high")

    def test_complete_resume_orchestration(self):
        resume = Resume(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            original_filename="resume_complete.pdf",
            stored_filename="resume_complete_stored.pdf",
            file_path="storage/resumes/resume_complete_stored.pdf",
            file_size=2048,
            file_type="pdf",
            mime_type="application/pdf",
            parsed_data=self.complete_parsed_data
        )

        response = calculate_ats_score(resume)
        
        self.assertEqual(response.overall_score, 100)
        self.assertEqual(response.grade, "Excellent")
        self.assertEqual(response.grade_summary, "Resume is ATS optimized.")
        self.assertGreater(len(response.strengths), 0)
        self.assertEqual(response.weaknesses, [])
        self.assertEqual(response.recommendations, [])

if __name__ == "__main__":
    unittest.main()
