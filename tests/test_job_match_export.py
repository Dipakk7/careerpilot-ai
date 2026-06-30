import os
import sys
import uuid
import time
import unittest
from datetime import datetime
from fastapi.testclient import TestClient

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.core.db import SessionLocal
from app.models.user import User
from app.models.resume import Resume
from app.core.enums import ResumeStatus, StorageProvider
from app.services.job_match.history import add_to_history, get_recent_matches, _history_cache
from app.services.job_match.export import generate_match_json, generate_match_markdown

class TestJobMatchExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test users and obtain authenticated TestClients."""
        db = SessionLocal()
        cls.db = db
        try:
            # Delete any existing test users to clean up state
            for email in ["export_test@careerpilot.com", "export_test_other@careerpilot.com"]:
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
                email="export_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Export Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id

            # Create secondary test user (other user)
            other_user_in = UserCreate(
                email="export_test_other@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Other Export User"
            )
            cls.other_user = auth_service.register_user(db, user_create=other_user_in)
            cls.other_user_id = cls.other_user.id

            db.commit()
        finally:
            db.close()

        # Primary user client
        cls.client = TestClient(app)
        login_payload = {
            "email": "export_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Primary login failed: {login_response.text}"

        # Other user client
        cls.other_client = TestClient(app)
        other_login_payload = {
            "email": "export_test_other@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        other_login_response = cls.other_client.post("/api/v1/auth/login", json=other_login_payload)
        assert other_login_response.status_code == 200, f"Other login failed: {other_login_response.text}"

        # Setup test resume IDs
        cls.test_resume_id = None
        cls.unparsed_resume_id = None
        cls.other_resume_id = None

    @classmethod
    def tearDownClass(cls):
        """Clean up database records generated during tests."""
        db = SessionLocal()
        try:
            for email in ["export_test@careerpilot.com", "export_test_other@careerpilot.com"]:
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

    # --- Test 1: Health check ---
    def test_01_health(self):
        print("\n--- Running Test: Health check ---")
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "healthy")

    # --- Test 2: Unauthorized Download JSON ---
    def test_02_export_json_unauthorized(self):
        print("\n--- Running Test: Export JSON Unauthorized ---")
        unauth_client = TestClient(app)
        response = unauth_client.get(f"/api/v1/job-match/{uuid.uuid4()}/export/json")
        self.assertEqual(response.status_code, 401)

    # --- Test 3: Unauthorized Download Markdown ---
    def test_03_export_markdown_unauthorized(self):
        print("\n--- Running Test: Export Markdown Unauthorized ---")
        unauth_client = TestClient(app)
        response = unauth_client.get(f"/api/v1/job-match/{uuid.uuid4()}/export/markdown")
        self.assertEqual(response.status_code, 401)

    # --- Test 4: Unauthorized History Retrieval ---
    def test_04_history_unauthorized(self):
        print("\n--- Running Test: History Unauthorized ---")
        unauth_client = TestClient(app)
        response = unauth_client.get(f"/api/v1/job-match/{uuid.uuid4()}/history")
        self.assertEqual(response.status_code, 401)

    # --- Test 5: Other User Access to Export JSON ---
    def test_05_export_json_other_user(self):
        print("\n--- Running Test: Export JSON Other User ---")
        other_parsed_data = {
            "parser_version": "v2",
            "data": {"skills": {"value": ["Python"]}}
        }
        TestJobMatchExport.other_resume_id = self.helper_create_resume(
            self.other_user_id, "other_user_resume.pdf", other_parsed_data
        )
        response = self.client.get(f"/api/v1/job-match/{self.other_resume_id}/export/json")
        self.assertEqual(response.status_code, 404)

    # --- Test 6: Other User Access to Export Markdown ---
    def test_06_export_markdown_other_user(self):
        print("\n--- Running Test: Export Markdown Other User ---")
        response = self.client.get(f"/api/v1/job-match/{self.other_resume_id}/export/markdown")
        self.assertEqual(response.status_code, 404)

    # --- Test 7: Other User Access to History ---
    def test_07_history_other_user(self):
        print("\n--- Running Test: History Other User ---")
        response = self.client.get(f"/api/v1/job-match/{self.other_resume_id}/history")
        self.assertEqual(response.status_code, 404)

    # --- Test 8: Non-existent Resume JSON Export ---
    def test_08_export_json_not_found(self):
        print("\n--- Running Test: Export JSON Not Found ---")
        response = self.client.get(f"/api/v1/job-match/{uuid.uuid4()}/export/json")
        self.assertEqual(response.status_code, 404)

    # --- Test 9: Non-existent Resume Markdown Export ---
    def test_09_export_markdown_not_found(self):
        print("\n--- Running Test: Export Markdown Not Found ---")
        response = self.client.get(f"/api/v1/job-match/{uuid.uuid4()}/export/markdown")
        self.assertEqual(response.status_code, 404)

    # --- Test 10: Non-existent Resume History ---
    def test_10_history_not_found(self):
        print("\n--- Running Test: History Not Found ---")
        response = self.client.get(f"/api/v1/job-match/{uuid.uuid4()}/history")
        self.assertEqual(response.status_code, 404)

    # --- Test 11: Export JSON before matching fails ---
    def test_11_export_json_before_match(self):
        print("\n--- Running Test: Export JSON Before Match ---")
        parsed_data = {
            "parser_version": "v2",
            "data": {
                "skills": {"value": ["Python", "FastAPI"]},
                "experience": {"value": []},
                "education": {"value": []},
                "certifications": {"value": []}
            }
        }
        TestJobMatchExport.test_resume_id = self.helper_create_resume(
            self.user_id, "primary_user_resume.pdf", parsed_data,
            raw_text="Python FastAPI Developer"
        )
        response = self.client.get(f"/api/v1/job-match/{self.test_resume_id}/export/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No job match history", response.json()["message"])

    # --- Test 12: Export Markdown before matching fails ---
    def test_12_export_markdown_before_match(self):
        print("\n--- Running Test: Export Markdown Before Match ---")
        response = self.client.get(f"/api/v1/job-match/{self.test_resume_id}/export/markdown")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No job match history", response.json()["message"])

    # --- Test 13: Perform Match and Verify Performance field exists ---
    def test_13_match_and_verify_performance_field(self):
        print("\n--- Running Test: Perform Match and Verify Performance ---")
        job_desc_text = """Job Title: Senior Software Engineer
Company: Google
Requirements:
Python
FastAPI
Experience:
3 years of experience
"""
        payload = {
            "resume_id": str(self.test_resume_id),
            "job_description": job_desc_text
        }
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("processing_time_ms", data)
        self.assertIsNotNone(data["processing_time_ms"])
        self.assertGreater(data["processing_time_ms"], 0.0)

    # --- Test 14: Export JSON Success ---
    def test_14_export_json_success(self):
        print("\n--- Running Test: Export JSON Success ---")
        response = self.client.get(f"/api/v1/job-match/{self.test_resume_id}/export/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/json")
        self.assertIn("attachment", response.headers.get("content-disposition"))
        
        data = response.json()
        self.assertEqual(str(data["resume_id"]), str(self.test_resume_id))
        self.assertIn("match_score", data)
        self.assertIn("breakdown", data)
        self.assertIn("matched_skills", data)
        self.assertIn("missing_skills", data)
        self.assertIn("priority_improvements", data)

    # --- Test 15: Export Markdown Success ---
    def test_15_export_markdown_success(self):
        print("\n--- Running Test: Export Markdown Success ---")
        response = self.client.get(f"/api/v1/job-match/{self.test_resume_id}/export/markdown")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response.headers.get("content-type"))
        self.assertIn("attachment", response.headers.get("content-disposition"))
        
        md_text = response.text
        self.assertIn("# Job Match & Gap Analysis Report", md_text)
        self.assertIn("## Overall Match", md_text)
        self.assertIn("## Score Breakdown", md_text)
        self.assertIn("## Matched Skills", md_text)
        self.assertIn("## Missing Skills", md_text)
        self.assertIn("## Education Gap", md_text)
        self.assertIn("## Experience Gap", md_text)
        self.assertIn("## Certification Gap", md_text)
        self.assertIn("## Recommendations", md_text)
        self.assertIn("## Priority Improvements", md_text)

    # --- Test 16: History retrieval success via endpoint ---
    def test_16_history_retrieval_success(self):
        print("\n--- Running Test: History Retrieval ---")
        response = self.client.get(f"/api/v1/job-match/{self.test_resume_id}/history")
        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)
        
        record = history[0]
        self.assertEqual(str(record["resume_id"]), str(self.test_resume_id))
        self.assertIn("overall_score", record)
        self.assertIn("grade", record)
        self.assertEqual(record["company"], "Google")
        self.assertEqual(record["job_title"], "Senior Software Engineer")
        self.assertIn("timestamp", record)

    # --- Test 17: History cache storage and retrieval ---
    def test_17_history_cache_storage_and_retrieval(self):
        print("\n--- Running Test: Direct Cache Storage and Retrieval ---")
        dummy_resume_id = uuid.uuid4()
        add_to_history(
            resume_id=dummy_resume_id,
            overall_score=85,
            grade="Good",
            job_title="Test Software Engineer",
            company="CareerPilot AI"
        )
        history = get_recent_matches(dummy_resume_id)
        self.assertEqual(len(history), 1)
        record = history[0]
        self.assertEqual(record["resume_id"], str(dummy_resume_id))
        self.assertEqual(record["overall_score"], 85)
        self.assertEqual(record["grade"], "Good")
        self.assertEqual(record["job_title"], "Test Software Engineer")
        self.assertEqual(record["company"], "CareerPilot AI")

    # --- Test 18: History cache size bounding (100 elements limit) ---
    def test_18_cache_bounding(self):
        print("\n--- Running Test: Cache Size Bounding ---")
        # Clear/initialize dummy records
        dummy_resume_id = uuid.uuid4()
        for i in range(120):
            add_to_history(
                resume_id=dummy_resume_id,
                overall_score=70 + (i % 30),
                grade="Good",
                job_title=f"Engineer {i}",
                company="Bounded Tech"
            )
        self.assertLessEqual(len(_history_cache), 100)

    # --- Test 19: Large Job Description ---
    def test_19_large_job_description(self):
        print("\n--- Running Test: Large Job Description ---")
        # Generate 15KB of text to simulate a very large job description
        large_job_text = "Requirements:\n" + "\n".join([f"Skill{i}" for i in range(1000)])
        large_job_text += "\nPreferred Skills:\n" + "\n".join([f"PrefSkill{i}" for i in range(100)])
        large_job_text += "\nExperience:\n5 years of experience in backend services."
        large_job_text += "\nEducation:\nBachelor of Science."
        large_job_text += "\nCertifications:\nAWS Certified Solutions Architect."
        
        payload = {
            "resume_id": str(self.test_resume_id),
            "job_description": large_job_text
        }
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("processing_time_ms", data)
        self.assertIsNotNone(data["processing_time_ms"])

    # --- Test 20: Performance time measurement ---
    def test_20_performance_time_measurement(self):
        print("\n--- Running Test: Performance time measurement ---")
        start = time.perf_counter()
        job_desc_text = "Title: Junior dev\nRequirements: Python"
        payload = {
            "resume_id": str(self.test_resume_id),
            "job_description": job_desc_text
        }
        response = self.client.post("/api/v1/job-match/analyze", json=payload)
        elapsed = (time.perf_counter() - start) * 1000.0
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(data["processing_time_ms"], elapsed)

    # --- Test 21: Unparsed resume JSON export fails ---
    def test_21_export_json_unparsed_resume(self):
        print("\n--- Running Test: Export JSON Unparsed Resume ---")
        TestJobMatchExport.unparsed_resume_id = self.helper_create_resume(
            self.user_id, "unparsed_resume.pdf", parsed_data=None
        )
        response = self.client.get(f"/api/v1/job-match/{self.unparsed_resume_id}/export/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Resume not parsed", response.json()["message"])

    # --- Test 22: Unparsed resume Markdown export fails ---
    def test_22_export_markdown_unparsed_resume(self):
        print("\n--- Running Test: Export Markdown Unparsed Resume ---")
        response = self.client.get(f"/api/v1/job-match/{self.unparsed_resume_id}/export/markdown")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Resume not parsed", response.json()["message"])

if __name__ == "__main__":
    unittest.main()
