import os
import sys
import uuid
import unittest
from fastapi.testclient import TestClient

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.core.db import SessionLocal
from app.models.user import User
from app.models.resume import Resume
from app.core.enums import ResumeStatus, StorageProvider

class TestATSAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test users and obtain authenticated TestClients."""
        db = SessionLocal()
        cls.db = db
        try:
            # Delete any existing test users to clean up state
            for email in ["ats_test@careerpilot.com", "ats_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    resumes = db.query(Resume).filter(Resume.user_id == test_user.id).all()
                    for r in resumes:
                        db.delete(r)
                    db.delete(test_user)
            db.commit()

            # Create primary test user
            from app.services import auth_service
            from app.schemas.user import UserCreate
            
            user_in = UserCreate(
                email="ats_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="ATS Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id

            # Create secondary test user (other user)
            other_user_in = UserCreate(
                email="ats_test_other@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Other Test User"
            )
            cls.other_user = auth_service.register_user(db, user_create=other_user_in)
            cls.other_user_id = cls.other_user.id

            db.commit()
        finally:
            db.close()

        # Primary user client
        cls.client = TestClient(app)
        login_payload = {
            "email": "ats_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Primary login failed: {login_response.text}"

        # Other user client
        cls.other_client = TestClient(app)
        other_login_payload = {
            "email": "ats_test_other@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        other_login_response = cls.other_client.post("/api/v1/auth/login", json=other_login_payload)
        assert other_login_response.status_code == 200, f"Other login failed: {other_login_response.text}"

        # Initialize shared test state
        cls.parsed_resume_id = None
        cls.unparsed_resume_id = None
        cls.other_resume_id = None
        cls.perfect_resume_id = None
        cls.empty_resume_id = None
        cls.shared_score = None

    @classmethod
    def tearDownClass(cls):
        """Clean up database records generated during tests."""
        db = SessionLocal()
        try:
            for email in ["ats_test@careerpilot.com", "ats_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    resumes = db.query(Resume).filter(Resume.user_id == test_user.id).all()
                    for r in resumes:
                        db.delete(r)
                    db.delete(test_user)
            db.commit()
        finally:
            db.close()

    def helper_create_resume(self, user_id, filename, parsed_data=None):
        db = SessionLocal()
        try:
            resume = Resume(
                user_id=user_id,
                original_filename=filename,
                stored_filename=f"{uuid.uuid4()}_{filename}",
                file_path=f"storage/resumes/{uuid.uuid4()}_{filename}",
                storage_provider=StorageProvider.LOCAL,
                file_size=1024,
                file_type="pdf",
                mime_type="application/pdf",
                status=ResumeStatus.PARSED if parsed_data else ResumeStatus.UPLOADED,
                parsed_data=parsed_data
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            return resume.id
        finally:
            db.close()

    def test_01_score_parsed_resume(self):
        print("\n--- Running Test 1: Score parsed resume ---")
        basic_parsed_data = {
            "parser_version": "v1",
            "data": {
                "name": {"value": "Jane Doe"},
                "email": {"value": "jane@doe.com"},
                "phone": {"value": "+1-555-0199"},
                "skills": {"value": ["Python", "FastAPI", "SQL", "Docker", "Git"]},
                "education": {"value": [{"degree": "Bachelor of Science", "institution": "Stanford University"}]},
                "experience": {"value": [{"title": "Senior Engineer", "company": "Google", "duration": "3 years", "description": "some text"}]}
            }
        }
        TestATSAPI.parsed_resume_id = self.helper_create_resume(
            self.user_id, "parsed_resume.pdf", basic_parsed_data
        )

        response = self.client.post(f"/api/v1/resumes/{self.parsed_resume_id}/score")
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}: {response.text}")
        
        data = response.json()
        self.assertIn("overall_score", data)
        self.assertIn("grade", data)
        self.assertIn("recommendations", data)
        
        TestATSAPI.shared_score = data["overall_score"]
        
        # Verify db was updated with score
        db = SessionLocal()
        db_resume = db.query(Resume).filter(Resume.id == self.parsed_resume_id).first()
        self.assertEqual(db_resume.ats_score, data["overall_score"])
        db.close()
        print(f"[SUCCESS] Score parsed resume. Score: {data['overall_score']}, Grade: {data['grade']}")

    def test_02_score_unparsed_resume(self):
        print("\n--- Running Test 2: Score unparsed resume ---")
        TestATSAPI.unparsed_resume_id = self.helper_create_resume(
            self.user_id, "unparsed_resume.pdf", parsed_data=None
        )

        response = self.client.post(f"/api/v1/resumes/{self.unparsed_resume_id}/score")
        self.assertEqual(response.status_code, 400, f"Expected 400, got {response.status_code}")
        data = response.json()
        self.assertEqual(data["message"], "Resume must be parsed before ATS scoring.")
        print("[SUCCESS] Score unparsed resume was correctly rejected with 400.")

    def test_03_resume_not_found(self):
        print("\n--- Running Test 3: Resume not found ---")
        fake_uuid = uuid.uuid4()
        response = self.client.post(f"/api/v1/resumes/{fake_uuid}/score")
        self.assertEqual(response.status_code, 404, f"Expected 404, got {response.status_code}")
        data = response.json()
        self.assertEqual(data["message"], "Resume not found")
        print("[SUCCESS] Score nonexistent resume was correctly rejected with 404.")

    def test_04_unauthorized(self):
        print("\n--- Running Test 4: Unauthorized ---")
        unauth_client = TestClient(app)
        response = unauth_client.post(f"/api/v1/resumes/{self.parsed_resume_id}/score")
        self.assertEqual(response.status_code, 401, f"Expected 401, got {response.status_code}")
        print("[SUCCESS] Score request without auth cookie was correctly rejected with 401.")

    def test_05_other_users_resume(self):
        print("\n--- Running Test 5: Other user's resume ---")
        # Other user's resume has parsed data
        other_parsed_data = {
            "parser_version": "v1",
            "data": {
                "name": {"value": "Other User"}
            }
        }
        TestATSAPI.other_resume_id = self.helper_create_resume(
            self.other_user_id, "other_resume.pdf", other_parsed_data
        )

        # Primary user tries to score other user's resume
        response = self.client.post(f"/api/v1/resumes/{self.other_resume_id}/score")
        self.assertEqual(response.status_code, 404, f"Expected 404, got {response.status_code}")
        data = response.json()
        self.assertEqual(data["message"], "Resume not found")
        print("[SUCCESS] Accessing other user's resume returned 404.")

    def test_06_get_score(self):
        print("\n--- Running Test 6: GET score ---")
        response = self.client.get(f"/api/v1/resumes/{self.parsed_resume_id}/score")
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        
        data = response.json()
        self.assertEqual(data["overall_score"], self.shared_score)
        self.assertIn("grade", data)
        self.assertIn("recommendations", data)
        print(f"[SUCCESS] GET score returned same score: {data['overall_score']}")

    def test_07_perfect_resume(self):
        print("\n--- Running Test 7: Perfect resume ---")
        perfect_parsed_data = {
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
        TestATSAPI.perfect_resume_id = self.helper_create_resume(
            self.user_id, "perfect_resume.pdf", perfect_parsed_data
        )

        response = self.client.post(f"/api/v1/resumes/{self.perfect_resume_id}/score")
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        
        data = response.json()
        self.assertGreaterEqual(data["overall_score"], 90)
        self.assertEqual(data["grade"], "Excellent")
        print(f"[SUCCESS] Perfect resume scored {data['overall_score']} with grade {data['grade']}.")

    def test_08_empty_resume(self):
        print("\n--- Running Test 8: Empty resume ---")
        empty_parsed_data = {
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
        TestATSAPI.empty_resume_id = self.helper_create_resume(
            self.user_id, "empty_resume.pdf", empty_parsed_data
        )

        response = self.client.post(f"/api/v1/resumes/{self.empty_resume_id}/score")
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        
        data = response.json()
        self.assertLess(data["overall_score"], 30)
        self.assertEqual(data["grade"], "Needs Improvement")
        self.assertGreater(len(data["recommendations"]), 0)
        print(f"[SUCCESS] Empty resume scored {data['overall_score']} with grade {data['grade']}. {len(data['recommendations'])} recommendations generated.")

    def test_09_recommendations_returned(self):
        print("\n--- Running Test 9: Recommendations structure ---")
        response = self.client.post(f"/api/v1/resumes/{self.empty_resume_id}/score")
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        
        data = response.json()
        recommendations = data["recommendations"]
        self.assertGreater(len(recommendations), 0)
        for rec in recommendations:
            self.assertIn("category", rec)
            self.assertIn("priority", rec)
            self.assertIn("message", rec)
        print("[SUCCESS] Recommendation structure verified with fields: category, priority, message.")

    def test_10_health(self):
        print("\n--- Running Test 10: Health check ---")
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}")
        
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "healthy")
        print("[SUCCESS] Health check successful. Status healthy.")

if __name__ == "__main__":
    unittest.main()
