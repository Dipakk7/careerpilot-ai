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

class TestJobMatchAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test users and obtain authenticated TestClients."""
        db = SessionLocal()
        cls.db = db
        try:
            # Delete any existing test users to clean up state
            for email in ["job_match_test@careerpilot.com", "job_match_test_other@careerpilot.com"]:
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
                email="job_match_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Job Match Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id

            # Create secondary test user (other user)
            other_user_in = UserCreate(
                email="job_match_test_other@careerpilot.com",
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
            "email": "job_match_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Primary login failed: {login_response.text}"

        # Other user client
        cls.other_client = TestClient(app)
        other_login_payload = {
            "email": "job_match_test_other@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        other_login_response = cls.other_client.post("/api/v1/auth/login", json=other_login_payload)
        assert other_login_response.status_code == 200, f"Other login failed: {other_login_response.text}"

        # Setup test resume IDs
        cls.perfect_resume_id = None
        cls.partial_resume_id = None
        cls.poor_resume_id = None
        cls.unparsed_resume_id = None
        cls.other_resume_id = None

    @classmethod
    def tearDownClass(cls):
        """Clean up database records generated during tests."""
        db = SessionLocal()
        try:
            for email in ["job_match_test@careerpilot.com", "job_match_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    resumes = db.query(Resume).filter(Resume.user_id == test_user.id).all()
                    for r in resumes:
                        db.delete(r)
                    db.delete(test_user)
            db.commit()
        finally:
            db.close()

    def helper_create_resume(self, user_id, filename, parsed_data=None, raw_text=""):
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
                raw_text=raw_text,
                parsed_data=parsed_data
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            return resume.id
        finally:
            db.close()

    # --- Test 10: Health check ---
    def test_01_health(self):
        print("\n--- Running Test: Health ---")
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "healthy")

    # --- Test 1: Perfect match ---
    def test_02_perfect_match(self):
        print("\n--- Running Test: Perfect Match ---")
        perfect_parsed_data = {
            "parser_version": "v2",
            "data": {
                "skills": {"value": ["Python", "FastAPI", "Docker", "SQL"]},
                "experience": {"value": [{"title": "Senior Engineer", "duration": "5 years", "description": "Senior Backend Developer with 5 years of experience using Python, FastAPI, and AWS. Holds a Bachelor degree."}]},
                "education": {"value": [{"degree": "Bachelor of Science", "institution": "Stanford University"}]},
                "certifications": {"value": ["AWS Certified Solutions Architect", "Docker Certified Associate"]}
            }
        }
        TestJobMatchAPI.perfect_resume_id = self.helper_create_resume(
            self.user_id, "perfect_resume.pdf", perfect_parsed_data,
            raw_text="Python FastAPI Docker SQL AWS Certified Solutions Architect Docker Certified Associate Senior Backend Developer with 5 years of experience using Python, FastAPI, and AWS. Holds a Bachelor degree. Bachelor of Science"
        )

        job_desc_text = """
Requirements:
Python
FastAPI

Preferred Skills:
Docker

Experience:
3 years of experience

Education:
Bachelor of Science

Certifications:
AWS Certified Solutions Architect
"""
        response = self.client.post(
            f"/api/v1/job-match/{self.perfect_resume_id}",
            files={"job_description": ("job.txt", job_desc_text.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        print("DEBUG RESPONSE DATA:", data)
        self.assertEqual(data["grade"], "Excellent")
        self.assertEqual(data["match_score"], 100)
        self.assertIn("Python", data["matched_skills"])

    # --- Test 2: Partial match ---
    def test_03_partial_match(self):
        print("\n--- Running Test: Partial Match ---")
        partial_parsed_data = {
            "parser_version": "v2",
            "data": {
                "skills": {"value": ["Python", "FastAPI"]},
                "experience": {"value": [{"title": "Developer", "duration": "3 years", "description": "Developer with experience"}]},
                "education": {"value": [{"degree": "Bachelor of Technology"}]},
                "certifications": {"value": []}
            }
        }
        TestJobMatchAPI.partial_resume_id = self.helper_create_resume(
            self.user_id, "partial_resume.pdf", partial_parsed_data,
            raw_text="Python FastAPI Developer with experience Bachelor of Technology"
        )

        job_desc_text = """
Requirements:
Python
FastAPI

Preferred Skills:
Docker
Kubernetes
AWS

Experience:
3 years of experience

Education:
Bachelor

Certifications:
AWS Certified
"""
        response = self.client.post(
            f"/api/v1/job-match/{self.partial_resume_id}",
            files={"job_description": ("job.txt", job_desc_text.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["grade"], "Good")
        self.assertLess(data["match_score"], 100)

    # --- Test 3: Poor match ---
    def test_04_poor_match(self):
        print("\n--- Running Test: Poor Match ---")
        poor_parsed_data = {
            "parser_version": "v2",
            "data": {
                "skills": {"value": ["HTML", "CSS"]},
                "experience": {"value": []},
                "education": {"value": []},
                "certifications": {"value": []}
            }
        }
        TestJobMatchAPI.poor_resume_id = self.helper_create_resume(
            self.user_id, "poor_resume.pdf", poor_parsed_data,
            raw_text="HTML CSS"
        )

        job_desc_text = """
Requirements:
Python
FastAPI

Experience:
5 years
"""
        response = self.client.post(
            f"/api/v1/job-match/{self.poor_resume_id}",
            files={"job_description": ("job.txt", job_desc_text.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["grade"], "Poor")

    # --- Test 9: GET endpoint (recalculates live) ---
    def test_05_get_endpoint_recalculates(self):
        print("\n--- Running Test: GET Endpoint ---")
        # Perform GET on the perfect resume
        response = self.client.get(f"/api/v1/job-match/{self.perfect_resume_id}")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["grade"], "Excellent")
        self.assertEqual(data["match_score"], 100)

    # --- Additional Test: GET endpoint before POST (should fail) ---
    def test_06_get_endpoint_before_post_fails(self):
        print("\n--- Running Test: GET Endpoint before POST ---")
        fresh_parsed_data = {
            "parser_version": "v2",
            "data": {"skills": {"value": ["Python"]}, "experience": {"value": []}, "education": {"value": []}, "certifications": {"value": []}}
        }
        resume_id = self.helper_create_resume(self.user_id, "fresh_resume.pdf", fresh_parsed_data)
        response = self.client.get(f"/api/v1/job-match/{resume_id}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No job match history", response.json()["message"])

    # --- Test 4: Resume not parsed ---
    def test_07_resume_not_parsed(self):
        print("\n--- Running Test: Resume not parsed ---")
        TestJobMatchAPI.unparsed_resume_id = self.helper_create_resume(
            self.user_id, "unparsed_resume.pdf", parsed_data=None
        )
        job_desc_text = "Requirements:\nPython"
        response = self.client.post(
            f"/api/v1/job-match/{self.unparsed_resume_id}",
            files={"job_description": ("job.txt", job_desc_text.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Resume not parsed", response.json()["message"])

    # --- Test 5: Unauthorized (POST) ---
    def test_08_unauthorized_post(self):
        print("\n--- Running Test: Unauthorized POST ---")
        unauth_client = TestClient(app) # No auth cookies
        job_desc_text = "Requirements:\nPython"
        response = unauth_client.post(
            f"/api/v1/job-match/{uuid.uuid4()}",
            files={"job_description": ("job.txt", job_desc_text.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(response.status_code, 401)

    # --- Additional Test: Unauthorized (GET) ---
    def test_09_unauthorized_get(self):
        print("\n--- Running Test: Unauthorized GET ---")
        unauth_client = TestClient(app)
        response = unauth_client.get(f"/api/v1/job-match/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 401)

    # --- Additional Test: Unauthorized (ANALYZE) ---
    def test_10_unauthorized_analyze(self):
        print("\n--- Running Test: Unauthorized ANALYZE ---")
        unauth_client = TestClient(app)
        payload = {"resume_id": str(uuid.uuid4()), "job_description": "Python"}
        response = unauth_client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 401)

    # --- Test 6: Other user's resume (POST) ---
    def test_11_other_user_resume_post(self):
        print("\n--- Running Test: Other User Resume POST ---")
        other_parsed_data = {
            "parser_version": "v2",
            "data": {"skills": {"value": ["Python"]}, "experience": {"value": []}, "education": {"value": []}, "certifications": {"value": []}}
        }
        TestJobMatchAPI.other_resume_id = self.helper_create_resume(
            self.other_user_id, "other_resume.pdf", other_parsed_data
        )
        job_desc_text = "Requirements:\nPython"
        response = self.client.post(
            f"/api/v1/job-match/{self.other_resume_id}",
            files={"job_description": ("job.txt", job_desc_text.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(response.status_code, 404)

    # --- Additional Test: Other user's resume (GET) ---
    def test_12_other_user_resume_get(self):
        print("\n--- Running Test: Other User Resume GET ---")
        response = self.client.get(f"/api/v1/job-match/{self.other_resume_id}")
        self.assertEqual(response.status_code, 404)

    # --- Additional Test: Other user's resume (ANALYZE) ---
    def test_13_other_user_resume_analyze(self):
        print("\n--- Running Test: Other User Resume ANALYZE ---")
        payload = {"resume_id": str(self.other_resume_id), "job_description": "Python"}
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 404)

    # --- Test 7: Missing job description (POST) ---
    def test_14_missing_job_desc_post(self):
        print("\n--- Running Test: Missing Job Description ---")
        response = self.client.post(f"/api/v1/job-match/{self.perfect_resume_id}")
        # Missing file parameter completely
        self.assertEqual(response.status_code, 422) # FastAPI returns 422 for missing required form fields

    # --- Test 8: Invalid extension (POST) ---
    def test_15_invalid_extension_post(self):
        print("\n--- Running Test: Invalid Extension ---")
        response = self.client.post(
            f"/api/v1/job-match/{self.perfect_resume_id}",
            files={"job_description": ("job.pdf", b"Some PDF bytes", "application/pdf")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file", response.json()["message"])

    # --- Additional Test: Empty job description file (POST) ---
    def test_16_empty_job_desc_post(self):
        print("\n--- Running Test: Empty Job Description file ---")
        response = self.client.post(
            f"/api/v1/job-match/{self.perfect_resume_id}",
            files={"job_description": ("job.txt", b"", "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Empty job description", response.json()["message"])

    # --- Additional Test: Empty job description JSON (ANALYZE) ---
    def test_17_empty_job_desc_analyze(self):
        print("\n--- Running Test: Empty Job Description JSON ---")
        payload = {"resume_id": str(self.perfect_resume_id), "job_description": "   "}
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Empty job description", response.json()["message"])

    # --- Additional Test: JSON Analyze Perfect Match ---
    def test_18_analyze_endpoint_perfect_match(self):
        print("\n--- Running Test: Analyze JSON Perfect Match ---")
        payload = {
            "resume_id": str(self.perfect_resume_id),
            "job_description": "Requirements:\nPython\nFastAPI\n\nPreferred Skills:\nDocker\n\nExperience:\n3 years of experience\n\nEducation:\nBachelor of Science\n\nCertifications:\nAWS Certified Solutions Architect"
        }
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["grade"], "Excellent")
        self.assertEqual(data["match_score"], 100)

    # --- Additional Test: JSON Analyze Partial Match ---
    def test_19_analyze_endpoint_partial_match(self):
        print("\n--- Running Test: Analyze JSON Partial Match ---")
        payload = {
            "resume_id": str(self.partial_resume_id),
            "job_description": "Requirements:\nPython\nFastAPI\n\nPreferred Skills:\nDocker\nKubernetes\nAWS\n\nExperience:\n3 years of experience\n\nEducation:\nBachelor\n\nCertifications:\nAWS Certified"
        }
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["grade"], "Good")

    # --- Additional Test: JSON Analyze Poor Match ---
    def test_20_analyze_endpoint_poor_match(self):
        print("\n--- Running Test: Analyze JSON Poor Match ---")
        payload = {
            "resume_id": str(self.poor_resume_id),
            "job_description": "Requirements:\nPython\nFastAPI\n\nExperience:\n5 years"
        }
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["grade"], "Poor")

    # --- Additional Test: Invalid UUID format in path (POST) ---
    def test_21_invalid_uuid_post(self):
        print("\n--- Running Test: Invalid UUID POST ---")
        response = self.client.post(
            "/api/v1/job-match/invalid-uuid-format",
            files={"job_description": ("job.txt", b"Requirements:\nPython", "text/plain")}
        )
        self.assertEqual(response.status_code, 422) # Pydantic validation fails for UUID field

    # --- Additional Test: Invalid UUID format in path (GET) ---
    def test_22_invalid_uuid_get(self):
        print("\n--- Running Test: Invalid UUID GET ---")
        response = self.client.get("/api/v1/job-match/invalid-uuid-format")
        self.assertEqual(response.status_code, 422)

    # --- Additional Test: Invalid UUID format in body (ANALYZE) ---
    def test_23_invalid_uuid_analyze(self):
        print("\n--- Running Test: Invalid UUID ANALYZE ---")
        payload = {"resume_id": "invalid-uuid-format", "job_description": "Python"}
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
