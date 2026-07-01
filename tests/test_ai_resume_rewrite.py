import os
import sys
import uuid
import json
import unittest
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.core.db import SessionLocal
from app.models.user import User
from app.models.resume import Resume
from app.models.ai_resume_rewrite import AIResumeRewrite
from app.core.enums import ResumeStatus, StorageProvider
from app.services.rewrite_service import ResumeRewriteService
from app.ai.schemas.ai_response import AIStructuredResponse, TokenUsage
from app.ai.exceptions import AIProviderUnavailable
from app.schemas.ai_resume_rewrite import (
    ImprovementCategory,
    SectionDiff,
    ChangeTracking,
    RewriteQualityScore,
    ResumeRewriteResponse,
    ResumeRewriteListResponse,
    UndoResponse,
)
from app.utils.diff_engine import compute_diff

class TestAIResumeRewrite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test users, database connection, and authenticated client."""
        db = SessionLocal()
        cls.db = db
        try:
            # Cleanup old test users
            for email in ["rewrite_test@careerpilot.com", "rewrite_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    db.query(AIResumeRewrite).filter(AIResumeRewrite.user_id == test_user.id).delete()
                    db.query(Resume).filter(Resume.user_id == test_user.id).delete()
                    db.delete(test_user)
            db.commit()

            # Create primary test user
            from app.services import auth_service
            from app.schemas.user import UserCreate
            
            user_in = UserCreate(
                email="rewrite_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Rewrite Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id

            # Create secondary test user
            other_user_in = UserCreate(
                email="rewrite_test_other@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Other Rewrite User"
            )
            cls.other_user = auth_service.register_user(db, user_create=other_user_in)
            cls.other_user_id = cls.other_user.id

            db.commit()
        finally:
            db.close()

        # Login client
        cls.client = TestClient(app)
        login_payload = {
            "email": "rewrite_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"

        # Login other client
        cls.other_client = TestClient(app)
        other_login_payload = {
            "email": "rewrite_test_other@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        other_login_response = cls.other_client.post("/api/v1/auth/login", json=other_login_payload)
        assert other_login_response.status_code == 200, f"Other login failed: {other_login_response.text}"

        # Setup standard mock rewrite response dict
        cls.mock_rewrite_dict = {
            "rewritten_content": {
                "professional_summary": "Highly motivated developer specializing in python backend web systems.",
                "skills": ["Python", "FastAPI", "Docker"]
            },
            "change_tracking": {
                "professional_summary": {
                    "original": "Motivated developer who likes Python.",
                    "rewritten": "Highly motivated developer specializing in python backend web systems.",
                    "reason": "Used action-driven verbs and defined specialization clearly.",
                    "improvement_category": "Professional Tone",
                    "confidence": 0.95,
                    "estimated_ats_improvement": 10.0
                }
            },
            "quality_scores": {
                "readability_improvement": 20,
                "grammar_improvement": 10,
                "professional_tone": 15,
                "ats_optimization": 25,
                "action_verb_score": 30
            },
            "keyword_optimization": {
                "matched_keywords": ["Python"],
                "added_keywords": ["FastAPI", "Docker"],
                "missing_keywords": ["Rust"]
            }
        }

    @classmethod
    def tearDownClass(cls):
        """Clean up all records inserted during tests."""
        db = SessionLocal()
        try:
            for email in ["rewrite_test@careerpilot.com", "rewrite_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    db.query(AIResumeRewrite).filter(AIResumeRewrite.user_id == test_user.id).delete()
                    db.query(Resume).filter(Resume.user_id == test_user.id).delete()
                    db.delete(test_user)
            db.commit()
        finally:
            db.close()

    def helper_create_resume(self, user_id, filename, parsed_data=None):
        """Helper to insert a test resume into DB."""
        db = SessionLocal()
        try:
            db_resume = Resume(
                user_id=user_id,
                original_filename=filename,
                stored_filename=f"stored_{uuid.uuid4()}_{filename}",
                file_path=f"/fake/path/{filename}",
                file_size=1024,
                file_type="pdf",
                mime_type="application/pdf",
                status=ResumeStatus.PARSED if parsed_data else ResumeStatus.UPLOADED,
                parsed_data=parsed_data,
                storage_provider=StorageProvider.LOCAL
            )
            db.add(db_resume)
            db.commit()
            db.refresh(db_resume)
            return db_resume.id
        finally:
            db.close()

    # --- DIFF ENGINE TESTS ---

    def test_diff_engine_computation(self):
        """Test that the diff engine successfully computes word edits."""
        orig = "Motivated python developer"
        rewr = "Motivated backend python developer"
        diff = compute_diff(orig, rewr)
        
        self.assertIn("backend", diff["added"])
        self.assertEqual(len(diff["removed"]), 0)
        self.assertEqual(len(diff["modified"]), 0)

        # Test removed
        orig2 = "Motivated backend python developer"
        rewr2 = "Motivated python developer"
        diff2 = compute_diff(orig2, rewr2)
        self.assertIn("backend", diff2["removed"])

        # Test modified
        orig3 = "Motivated python developer"
        rewr3 = "Motivated java developer"
        diff3 = compute_diff(orig3, rewr3)
        self.assertEqual(diff3["modified"][0], {"from": "python", "to": "java"})

        # Test dictionary conversions
        dict_orig = {"skills": ["C++", "Java"]}
        dict_rewr = {"skills": ["C++", "Java", "Python"]}
        diff_dict = compute_diff(dict_orig, dict_rewr)
        self.assertTrue(any("Python" in item for item in diff_dict["added"]))

    # --- SCHEMA TESTS ---

    def test_schema_validations(self):
        """Test that Pydantic models validate structure properly."""
        diff = SectionDiff(added=["FastAPI"], removed=[], modified=[])
        tracking = ChangeTracking(
            original="Python dev",
            rewritten="FastAPI python dev",
            reason="Added framework info",
            improvement_category=ImprovementCategory.TECHNICAL,
            confidence=0.9,
            estimated_ats_improvement=5.0,
            diff=diff
        )
        scores = RewriteQualityScore(
            readability_improvement=10,
            grammar_improvement=5,
            professional_tone=15,
            ats_optimization=20,
            action_verb_score=25
        )
        self.assertEqual(tracking.improvement_category, "Technical")
        self.assertEqual(scores.action_verb_score, 25)

    # --- SERVICE VALIDATION TESTS ---

    def test_rewrite_validation_failures(self):
        """Test that ResumeRewriteService rejects invalid/empty inputs with meaningful errors."""
        db = SessionLocal()
        service = ResumeRewriteService(db)

        # 1. Missing identifiers
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.rewrite_resume(resume_id=None, user_id=self.user_id))
        self.assertIn("Missing required identifiers", str(ctx.exception))

        # 2. Resume not found
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.rewrite_resume(resume_id=uuid.uuid4(), user_id=self.user_id))
        self.assertIn("not found", str(ctx.exception))

        # 3. Unparsed resume (parsed_data is None)
        unparsed_resume_id = self.helper_create_resume(self.user_id, "unparsed.pdf", parsed_data=None)
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.rewrite_resume(resume_id=unparsed_resume_id, user_id=self.user_id))
        self.assertIn("must be parsed before it can be rewritten", str(ctx.exception))

        # 4. Unsupported rewrite mode
        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "parsed.pdf",
            parsed_data={"parser_version": "1.0.0", "skills": ["Python"]}
        )
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.rewrite_resume(resume_id=parsed_resume_id, user_id=self.user_id, mode="INVALID"))
        self.assertIn("Unsupported rewrite mode", str(ctx.exception))

        # 5. Unsupported section name
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.rewrite_resume(
                resume_id=parsed_resume_id,
                user_id=self.user_id,
                section_name="invalid_section_name"
            ))
        self.assertIn("Unsupported section name", str(ctx.exception))

        db.close()

    # --- MOCK SERVICE TESTS & CACHING ---

    @patch("app.ai.services.ai_service.AIService.execute", new_callable=AsyncMock)
    def test_successful_rewrite_service(self, mock_execute):
        """Test successful service flow, database persistence, caching, and rollback/undo."""
        db = SessionLocal()
        service = ResumeRewriteService(db)

        # Setup parsed resume
        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "rewrite_service_test.pdf",
            parsed_data={
                "parser_version": "1.0.0",
                "professional_summary": "Motivated developer who likes Python.",
                "skills": ["Python"]
            }
        )

        mock_execute.return_value = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=1200.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_rewrite_dict,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=150, total_tokens=250),
            token_fields={}
        )

        # Execute rewrite
        db_rewrite = asyncio.run(service.rewrite_resume(
            resume_id=parsed_resume_id,
            user_id=self.user_id,
            mode="STANDARD"
        ))

        self.assertIsNotNone(db_rewrite)
        self.assertEqual(db_rewrite.user_id, self.user_id)
        self.assertEqual(db_rewrite.resume_id, parsed_resume_id)
        self.assertEqual(db_rewrite.rewrite_mode, "STANDARD")
        self.assertEqual(
            db_rewrite.rewritten_content["professional_summary"],
            "Highly motivated developer specializing in python backend web systems."
        )

        # Test database caching (bypass_cache=False should reuse previous rewrite)
        mock_execute.reset_mock()
        cached_rewrite = asyncio.run(service.rewrite_resume(
            resume_id=parsed_resume_id,
            user_id=self.user_id,
            mode="STANDARD",
            bypass_cache=False
        ))
        self.assertEqual(cached_rewrite.id, db_rewrite.id)
        mock_execute.assert_not_called()

        # Test Rollback/Undo functionality
        undo_res = asyncio.run(service.rollback_rewrite(rewrite_id=db_rewrite.id, user_id=self.user_id))
        self.assertTrue(undo_res["success"])
        
        # Verify resume parsed_data is reverted to original content
        reverted_resume = db.query(Resume).filter(Resume.id == parsed_resume_id).first()
        self.assertEqual(reverted_resume.parsed_data["professional_summary"], "Motivated developer who likes Python.")

        db.close()

    @patch("app.ai.services.ai_service.AIService.execute", new_callable=AsyncMock)
    def test_structured_json_retry_on_failure(self, mock_execute):
        """Test that the service retries executing AIService once if parsing/validation fails initially."""
        db = SessionLocal()
        service = ResumeRewriteService(db)

        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "retry_test.pdf",
            parsed_data={"parser_version": "1.0.0", "skills": ["Python"]}
        )

        # First response is invalid dictionary (e.g. None or missing fields to trigger ValidationError)
        invalid_resp = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=1000.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response={"malformed": "content"}, # missing rewritten_content, quality_scores, etc.
            usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            token_fields={}
        )

        # Second response is successful
        valid_resp = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=1200.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_rewrite_dict,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=150, total_tokens=250),
            token_fields={}
        )

        mock_execute.side_effect = [invalid_resp, valid_resp]

        db_rewrite = asyncio.run(service.rewrite_resume(
            resume_id=parsed_resume_id,
            user_id=self.user_id,
            mode="STANDARD",
            bypass_cache=True
        ))

        # Check call count of execute is 2
        self.assertEqual(mock_execute.call_count, 2)
        self.assertIsNotNone(db_rewrite)
        self.assertEqual(
            db_rewrite.rewritten_content["professional_summary"],
            "Highly motivated developer specializing in python backend web systems."
        )

        db.close()

    # --- API ENDPOINTS TESTS ---

    @patch("app.ai.services.ai_service.AIService.execute", new_callable=AsyncMock)
    def test_api_rewrite_lifecycle(self, mock_execute):
        """Test POST, GET, DELETE, and UNDO rewrite lifecycle through FastAPI endpoints."""
        mock_execute.return_value = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=1100.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_rewrite_dict,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=150, total_tokens=250),
            token_fields={}
        )

        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "api_rewrite_test.pdf",
            parsed_data={
                "parser_version": "1.0.0",
                "professional_summary": "Original summary.",
                "skills": ["Python"]
            }
        )

        # 1. POST Rewrite
        post_payload = {
            "resume_id": str(parsed_resume_id),
            "mode": "STANDARD",
            "bypass_cache": True
        }
        response = self.client.post("/api/v1/ai/resume/rewrite", json=post_payload)
        self.assertEqual(response.status_code, 200, response.text)
        res_data = response.json()
        self.assertEqual(res_data["resume_id"], str(parsed_resume_id))
        self.assertEqual(res_data["rewrite_mode"], "STANDARD")
        
        rewrite_id = res_data["id"]

        # 2. GET Rewrite details
        get_response = self.client.get(f"/api/v1/ai/resume/rewrite/{rewrite_id}")
        self.assertEqual(get_response.status_code, 200)
        get_data = get_response.json()
        self.assertEqual(get_data["id"], rewrite_id)
        
        # Test unauthorized access
        get_unauth = self.other_client.get(f"/api/v1/ai/resume/rewrite/{rewrite_id}")
        self.assertEqual(get_unauth.status_code, 404)

        # 3. GET all rewrites
        list_response = self.client.get("/api/v1/ai/resume/rewrites")
        self.assertEqual(list_response.status_code, 200)
        list_data = list_response.json()
        self.assertGreaterEqual(list_data["total"], 1)

        # 4. UNDO Rewrite
        undo_response = self.client.post(f"/api/v1/ai/resume/rewrite/{rewrite_id}/undo")
        self.assertEqual(undo_response.status_code, 200)
        undo_data = undo_response.json()
        self.assertTrue(undo_data["success"])

        # 5. DELETE Rewrite
        del_response = self.client.delete(f"/api/v1/ai/resume/rewrite/{rewrite_id}")
        self.assertEqual(del_response.status_code, 200)
        
        # Verify it is deleted
        get_deleted = self.client.get(f"/api/v1/ai/resume/rewrite/{rewrite_id}")
        self.assertEqual(get_deleted.status_code, 404)


if __name__ == "__main__":
    unittest.main()
