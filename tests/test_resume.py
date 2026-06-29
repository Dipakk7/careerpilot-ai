import os
import sys
import uuid
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.core.db import SessionLocal
from app.models.user import User
from app.models.resume import Resume
from app.core.config import settings
from app.core.enums import ResumeStatus, StorageProvider

class TestResumePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up a test user and obtain authenticated TestClient cookies."""
        db = SessionLocal()
        cls.db = db
        try:
            # Delete any existing test user to clean up state
            test_user = db.query(User).filter(User.email == "resume_test@careerpilot.com").first()
            if test_user:
                # Delete any associated resumes and their files
                resumes = db.query(Resume).filter(Resume.user_id == test_user.id).all()
                for r in resumes:
                    if os.path.exists(r.file_path):
                        os.remove(r.file_path)
                    db.delete(r)
                db.delete(test_user)
                db.commit()

            # Create test user
            # Password must meet strength validation (capital, special, length, number)
            from app.services import auth_service
            from app.schemas.user import UserCreate
            user_in = UserCreate(
                email="resume_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Resume Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id
        finally:
            db.close()

        cls.client = TestClient(app)
        # Log in the user to populate the client's HttpOnly cookie
        login_payload = {
            "email": "resume_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"

    @classmethod
    def tearDownClass(cls):
        """Clean up database records and files generated during tests."""
        db = SessionLocal()
        try:
            test_user = db.query(User).filter(User.email == "resume_test@careerpilot.com").first()
            if test_user:
                resumes = db.query(Resume).filter(Resume.user_id == test_user.id).all()
                for r in resumes:
                    if os.path.exists(r.file_path):
                        try:
                            os.remove(r.file_path)
                        except OSError:
                            pass
                    db.delete(r)
                db.delete(test_user)
                db.commit()
        finally:
            db.close()

    def test_resume_pipeline(self):
        client = self.client
        db = SessionLocal()
        
        # Keep track of generated IDs and file paths for assertion
        resume1_id = None
        resume2_id = None
        resume1_filepath = None

        try:
            # ==========================================
            # TEST 1: Upload valid PDF
            # ==========================================
            print("\n--- Running Test 1: Upload valid PDF ---")
            pdf_content = b"%PDF-1.4\n%EOF\nDummy PDF body content"
            files = {"file": ("my_resume.pdf", pdf_content, "application/pdf")}
            
            with patch("app.services.resume_service.logger.info") as mock_info:
                response = client.post("/api/v1/resumes/upload", files=files)
                self.assertEqual(response.status_code, 201, f"Test 1 failed: {response.text}")
                
                # Check response payload structure and hidden fields omission
                data = response.json()
                self.assertEqual(data["message"], "Resume uploaded successfully")
                self.assertEqual(data["next_step"], "Ready for parsing")
                self.assertIn("resume", data)
                
                resume_data = data["resume"]
                # Hidden fields checklist:
                for hidden in ["file_path", "stored_filename", "raw_text", "parsed_data", "mime_type", "error_message"]:
                    self.assertNotIn(hidden, resume_data)
                
                # Metadata fields validation:
                self.assertIn("id", resume_data)
                self.assertEqual(resume_data["original_filename"], "my_resume.pdf")
                self.assertEqual(resume_data["file_type"], "pdf")
                self.assertEqual(resume_data["status"], ResumeStatus.UPLOADED.value)
                
                resume1_id = uuid.UUID(resume_data["id"])
                
                # Query DB to verify details
                db_resume = db.query(Resume).filter(Resume.id == resume1_id).first()
                self.assertIsNotNone(db_resume)
                self.assertEqual(db_resume.original_filename, "my_resume.pdf")
                resume1_filepath = db_resume.file_path
                
                # Verify file exists on disk
                self.assertTrue(os.path.exists(resume1_filepath))
                
                # Verify logger events
                mock_info.assert_any_call(
                    "resume_upload_completed",
                    resume_id=str(resume1_id),
                    user_id=str(self.user_id),
                    file_type="pdf",
                    file_size=len(pdf_content)
                )
                print("[SUCCESS] Test 1 passed successfully.")

            # ==========================================
            # TEST 2: Upload DOCX
            # ==========================================
            print("\n--- Running Test 2: Upload DOCX ---")
            docx_content = b"PK\x03\x04\nDummy DOCX body content"
            files = {"file": ("my_resume.docx", docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            
            response = client.post("/api/v1/resumes/upload", files=files)
            self.assertEqual(response.status_code, 201, f"Test 2 failed: {response.text}")
            
            data = response.json()
            resume2_id = uuid.UUID(data["resume"]["id"])
            
            # Query DB to check different stored filename
            db_resume2 = db.query(Resume).filter(Resume.id == resume2_id).first()
            db_resume1 = db.query(Resume).filter(Resume.id == resume1_id).first()
            self.assertIsNotNone(db_resume2)
            self.assertNotEqual(db_resume2.stored_filename, db_resume1.stored_filename)
            self.assertTrue(os.path.exists(db_resume2.file_path))
            print("[SUCCESS] Test 2 passed successfully.")

            # ==========================================
            # TEST 3: Invalid extension (TXT)
            # ==========================================
            print("\n--- Running Test 3: Invalid extension TXT ---")
            txt_content = b"Some plain text resume body"
            files = {"file": ("my_resume.txt", txt_content, "text/plain")}
            
            response = client.post("/api/v1/resumes/upload", files=files)
            self.assertEqual(response.status_code, 400, f"Test 3 failed: expected 400, got {response.status_code}")
            print("[SUCCESS] Test 3 passed successfully.")

            # ==========================================
            # TEST 4: MIME spoof attack
            # ==========================================
            print("\n--- Running Test 4: MIME spoof attack (fake.txt -> fake.pdf) ---")
            spoofed_content = b"This is a plain text file spoofing as a PDF file."
            files = {"file": ("fake.pdf", spoofed_content, "application/pdf")}
            
            response = client.post("/api/v1/resumes/upload", files=files)
            self.assertEqual(response.status_code, 400, f"Test 4 failed: expected 400, got {response.status_code}")
            error_data = response.json()
            self.assertIn("MIME type validation failed", error_data["message"])
            print("[SUCCESS] Test 4 passed successfully. Magic bytes rejected upload.")

            # ==========================================
            # TEST 5: Upload larger than MAX_FILE_SIZE_MB
            # ==========================================
            print("\n--- Running Test 5: Upload larger than MAX_FILE_SIZE_MB ---")
            # 6MB size (Limit is 5MB)
            large_content = b"%PDF-" + b"0" * (6 * 1024 * 1024)
            files = {"file": ("large.pdf", large_content, "application/pdf")}
            
            # Record number of resumes before
            resumes_before = db.query(Resume).filter(Resume.user_id == self.user_id).count()
            
            response = client.post("/api/v1/resumes/upload", files=files)
            self.assertEqual(response.status_code, 413, f"Test 5 failed: expected 413, got {response.status_code}")
            
            # Verify no database row created
            resumes_after = db.query(Resume).filter(Resume.user_id == self.user_id).count()
            self.assertEqual(resumes_before, resumes_after)
            
            # Verify no file saved
            large_db_entry = db.query(Resume).filter(Resume.original_filename == "large.pdf").first()
            self.assertIsNone(large_db_entry)
            print("[SUCCESS] Test 5 passed successfully.")

            # ==========================================
            # TEST 6: Upload without authentication
            # ==========================================
            print("\n--- Running Test 6: Upload without authentication ---")
            unauth_client = TestClient(app)
            files = {"file": ("my_resume.pdf", pdf_content, "application/pdf")}
            
            response = unauth_client.post("/api/v1/resumes/upload", files=files)
            self.assertEqual(response.status_code, 401, f"Test 6 failed: expected 401, got {response.status_code}")
            print("[SUCCESS] Test 6 passed successfully.")

            # ==========================================
            # TEST 7: Get all resumes
            # ==========================================
            print("\n--- Running Test 7: Get all resumes ---")
            response = client.get("/api/v1/resumes")
            self.assertEqual(response.status_code, 200, f"Test 7 failed: {response.text}")
            
            data = response.json()
            self.assertIn("resumes", data)
            self.assertEqual(data["total"], 2)
            
            resumes = data["resumes"]
            for r in resumes:
                self.assertEqual(uuid.UUID(r["user_id"]), self.user_id)
                # Verify no hidden fields
                for hidden in ["file_path", "stored_filename", "raw_text", "parsed_data", "mime_type", "error_message"]:
                    self.assertNotIn(hidden, r)
            print("[SUCCESS] Test 7 passed successfully. Returned only authenticated user's resumes.")

            # ==========================================
            # TEST 8: Get single resume metadata
            # ==========================================
            print("\n--- Running Test 8: Get single resume metadata ---")
            response = client.get(f"/api/v1/resumes/{resume1_id}")
            self.assertEqual(response.status_code, 200, f"Test 8 failed: {response.text}")
            
            r = response.json()
            self.assertEqual(uuid.UUID(r["id"]), resume1_id)
            self.assertEqual(r["original_filename"], "my_resume.pdf")
            # Verify no hidden fields
            for hidden in ["file_path", "stored_filename", "raw_text", "parsed_data", "mime_type", "error_message"]:
                self.assertNotIn(hidden, r)
            print("[SUCCESS] Test 8 passed successfully. Returned metadata only, no hidden fields.")

            # ==========================================
            # TEST 9: Nonexistent resume
            # ==========================================
            print("\n--- Running Test 9: Nonexistent resume ---")
            fake_uuid = uuid.uuid4()
            response = client.get(f"/api/v1/resumes/{fake_uuid}")
            self.assertEqual(response.status_code, 404, f"Test 9 failed: expected 404, got {response.status_code}")
            print("[SUCCESS] Test 9 passed successfully.")

            # ==========================================
            # TEST 10: Delete resume
            # ==========================================
            print("\n--- Running Test 10: Delete resume ---")
            with patch("app.services.resume_service.logger.info") as mock_info:
                response = client.delete(f"/api/v1/resumes/{resume1_id}")
                self.assertEqual(response.status_code, 200, f"Test 10 failed: {response.text}")
                
                data = response.json()
                self.assertEqual(data["message"], "Resume deleted successfully")
                
                # Verify DB row is deleted
                db_del_check = db.query(Resume).filter(Resume.id == resume1_id).first()
                self.assertIsNone(db_del_check)
                
                # Verify file on disk is deleted
                self.assertFalse(os.path.exists(resume1_filepath))
                
                # Verify logger events
                mock_info.assert_any_call(
                    "resume_deleted",
                    resume_id=str(resume1_id),
                    user_id=str(self.user_id)
                )
                print("[SUCCESS] Test 10 passed successfully. Database record and local file deleted.")

            # ==========================================
            # TEST 11: Health
            # ==========================================
            print("\n--- Running Test 11: Health check ---")
            response = client.get("/health")
            self.assertEqual(response.status_code, 200, f"Test 11 failed: {response.text}")
            
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["database"], "healthy")
            print("[SUCCESS] Test 11 passed successfully. Server healthy.")

            print("\n===========================================")
            print("[SUCCESS] ALL 11 TESTS PASSED SUCCESSFULLY!")
            print("===========================================")

        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
