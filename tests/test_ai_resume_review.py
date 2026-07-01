import os
import sys
import uuid
import json
import unittest
from datetime import datetime
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.core.db import SessionLocal
from app.models.user import User
from app.models.resume import Resume
from app.models.ai_resume_review import AIResumeReview
from app.core.enums import ResumeStatus, StorageProvider
from app.services.review_service import ResumeReviewService
from app.ai.schemas.ai_response import AIStructuredResponse, TokenUsage
from app.ai.exceptions import AIProviderUnavailable
from app.schemas.ai_resume_review import PriorityLevel, Recommendation, ResumeSectionReview, ResumeReviewResponse


class TestAIResumeReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test users, database connection, and authenticated client."""
        db = SessionLocal()
        cls.db = db
        try:
            # Cleanup old test users
            for email in ["review_test@careerpilot.com", "review_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    db.query(AIResumeReview).filter(AIResumeReview.user_id == test_user.id).delete()
                    db.query(Resume).filter(Resume.user_id == test_user.id).delete()
                    db.delete(test_user)
            db.commit()

            # Create primary test user
            from app.services import auth_service
            from app.schemas.user import UserCreate
            
            user_in = UserCreate(
                email="review_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Review Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id

            # Create secondary test user
            other_user_in = UserCreate(
                email="review_test_other@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Other Review User"
            )
            cls.other_user = auth_service.register_user(db, user_create=other_user_in)
            cls.other_user_id = cls.other_user.id

            db.commit()
        finally:
            db.close()

        # Login client
        cls.client = TestClient(app)
        login_payload = {
            "email": "review_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"

        # Login other client
        cls.other_client = TestClient(app)
        other_login_payload = {
            "email": "review_test_other@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        other_login_response = cls.other_client.post("/api/v1/auth/login", json=other_login_payload)
        assert other_login_response.status_code == 200, f"Other login failed: {other_login_response.text}"

        # Setup standard mock review response dict
        cls.mock_review_dict = {
            "overall_score": 85,
            "overall_summary": "Solid resume overall.",
            "strengths": ["Clear formatting", "Strong skills section"],
            "weaknesses": ["Achievements lack numbers", "Missing certifications"],
            "recommendations": [
                {
                    "priority": "HIGH",
                    "reason": "Achievements are too qualitative.",
                    "impact": "Reduces quantified impact.",
                    "suggested_fix": "Add metrics to professional achievements.",
                    "estimated_benefit": "Makes achievements much more persuasive."
                }
            ],
            "missing_sections": ["Certifications"],
            "grammar_feedback": "Perfect grammar detected.",
            "ats_feedback": "Explainable: Good ATS compatibility, has all correct headers.",
            "technical_feedback": "Solid python and cloud architecture description.",
            "career_feedback": "Prepared well for a Senior Python Developer role.",
            "priority_improvements": [
                {
                    "priority": "HIGH",
                    "reason": "Missing certifications.",
                    "impact": "Reduces credibility.",
                    "suggested_fix": "List AWS Solution Architect Associate.",
                    "estimated_benefit": "Increases trust."
                }
            ],
            "confidence": 0.95,
            "sections": {
                "Professional Summary": {
                    "score": 80,
                    "feedback": "Needs slightly more alignment with career goals.",
                    "recommendations": []
                },
                "Skills": {
                    "score": 90,
                    "feedback": "Excellent technical keywords.",
                    "recommendations": []
                },
                "Experience": {
                    "score": 85,
                    "feedback": "Good description of roles.",
                    "recommendations": []
                },
                "Projects": {
                    "score": 75,
                    "feedback": "Quantitative impact is missing.",
                    "recommendations": []
                },
                "Education": {
                    "score": 95,
                    "feedback": "Clear education detail.",
                    "recommendations": []
                },
                "Certifications": {
                    "score": 0,
                    "feedback": "Information not provided.",
                    "recommendations": []
                }
            }
        }

    @classmethod
    def tearDownClass(cls):
        """Clean up all records inserted during tests."""
        db = SessionLocal()
        try:
            for email in ["review_test@careerpilot.com", "review_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    db.query(AIResumeReview).filter(AIResumeReview.user_id == test_user.id).delete()
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

    # --- SCHEMA TESTS ---

    def test_schema_validations(self):
        """Test that Pydantic models validate input and raise error on invalid types."""
        # Test valid recommendation
        rec = Recommendation(
            priority=PriorityLevel.HIGH,
            reason="Reason",
            impact="Impact",
            suggested_fix="Fix",
            estimated_benefit="Benefit"
        )
        self.assertEqual(rec.priority, PriorityLevel.HIGH)

        # Test valid Section Review
        sec = ResumeSectionReview(
            score=85,
            feedback="Great work",
            recommendations=[rec]
        )
        self.assertEqual(sec.score, 85)

        # Test invalid Section Review score
        with self.assertRaises(ValueError):
            ResumeSectionReview(
                score=105, # Capped at 100
                feedback="Too high",
                recommendations=[]
            )

    # --- REVIEW VALIDATION TESTS ---

    def test_review_validation_failures(self):
        """Test that ResumeReviewService rejects invalid/empty inputs with meaningful errors."""
        db = SessionLocal()
        service = ResumeReviewService(db)

        # 1. Missing identifiers
        with self.assertRaises(ValueError) as ctx:
            db.query(AIResumeReview).filter(AIResumeReview.user_id == self.user_id).delete()
            # Pass None as identifiers
            import asyncio
            asyncio.run(service.review_resume(resume_id=None, user_id=self.user_id))
        self.assertIn("Missing required identifiers", str(ctx.exception))

        # 2. Resume not found
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.review_resume(resume_id=uuid.uuid4(), user_id=self.user_id))
        self.assertIn("not found", str(ctx.exception))

        # 3. Unparsed resume (parsed_data is None)
        unparsed_resume_id = self.helper_create_resume(self.user_id, "unparsed.pdf", parsed_data=None)
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.review_resume(resume_id=unparsed_resume_id, user_id=self.user_id))
        self.assertIn("must be parsed before it can be reviewed", str(ctx.exception))

        # 4. Invalid parsed JSON type (not dict)
        invalid_parsed_resume_id = self.helper_create_resume(self.user_id, "invalid.pdf", parsed_data="NotADict")
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.review_resume(resume_id=invalid_parsed_resume_id, user_id=self.user_id))
        self.assertIn("Invalid parsed JSON format", str(ctx.exception))

        # 5. Unsupported parser version
        unsupported_version_resume_id = self.helper_create_resume(
            self.user_id,
            "unsupported.pdf",
            parsed_data={"parser_version": "0.5.0", "skills": []}
        )
        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.review_resume(resume_id=unsupported_version_resume_id, user_id=self.user_id))
        self.assertIn("Unsupported resume parser version", str(ctx.exception))

        db.close()

    # --- MOCK OLLAMA & SERVICE TESTS ---

    @patch("app.ai.services.ai_service.AIService.execute", new_callable=AsyncMock)
    def test_successful_resume_review_service(self, mock_execute):
        """Test successful review logic, verification of prompt rendering variables, and persistence."""
        db = SessionLocal()
        service = ResumeReviewService(db)

        # Setup parsed resume
        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "parsed.pdf",
            parsed_data={
                "parser_version": "1.0.0",
                "personal_info": {"name": "John Doe"},
                "skills": ["Python", "Docker"]
            }
        )

        # Configure mock AIService response
        mock_execute.return_value = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=1500.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_review_dict,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=150, total_tokens=250),
            token_fields={}
        )

        # Run service orchestration
        import asyncio
        db_review = asyncio.run(service.review_resume(
            resume_id=parsed_resume_id,
            user_id=self.user_id,
            mode="DETAILED",
            language="en"
        ))

        # Assertions
        self.assertIsNotNone(db_review)
        self.assertEqual(db_review.user_id, self.user_id)
        self.assertEqual(db_review.resume_id, parsed_resume_id)
        self.assertEqual(db_review.provider, "ollama")
        self.assertEqual(db_review.model, "qwen2.5:3b")
        self.assertEqual(db_review.prompt_version, "1.0.0")
        self.assertEqual(db_review.review["overall_score"], 85)
        self.assertEqual(db_review.review_metadata["mode"], "DETAILED")
        self.assertEqual(db_review.review_metadata["latency_ms"], 1500.0)

        # Test database caching (bypass_cache=False should reuse previous review)
        mock_execute.reset_mock()
        cached_review = asyncio.run(service.review_resume(
            resume_id=parsed_resume_id,
            user_id=self.user_id,
            mode="DETAILED",
            language="en",
            bypass_cache=False
        ))
        self.assertEqual(cached_review.id, db_review.id)
        mock_execute.assert_not_called()

        # Test bypass_cache=True should regenerate review
        cached_review = asyncio.run(service.review_resume(
            resume_id=parsed_resume_id,
            user_id=self.user_id,
            mode="DETAILED",
            language="en",
            bypass_cache=True
        ))
        mock_execute.assert_called_once()

        db.close()

    @patch("app.ai.services.ai_service.AIService.execute", new_callable=AsyncMock)
    def test_unhappy_path_never_exposes_raw_llm_errors(self, mock_execute):
        """Test that service intercepts raw provider exceptions and logs failures."""
        db = SessionLocal()
        service = ResumeReviewService(db)

        # Setup parsed resume
        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "parsed_unhappy.pdf",
            parsed_data={"parser_version": "1.0.0", "skills": ["Python"]}
        )

        mock_execute.side_effect = AIProviderUnavailable("Ollama is not running!")

        # Running should propagate AIProviderUnavailable which is an AIError
        import asyncio
        with self.assertRaises(AIProviderUnavailable):
            asyncio.run(service.review_resume(
                resume_id=parsed_resume_id,
                user_id=self.user_id
            ))

        db.close()

    # --- API ENDPOINTS TESTS ---

    @patch("app.ai.services.ai_service.AIService.execute", new_callable=AsyncMock)
    def test_api_review_lifecycle(self, mock_execute):
        """Test POST, GET, DELETE review history through FastAPI endpoints."""
        mock_execute.return_value = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=1100.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_review_dict,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=150, total_tokens=250),
            token_fields={}
        )

        # Create parsed resume
        parsed_resume_id = self.helper_create_resume(
            self.user_id,
            "api_test_resume.pdf",
            parsed_data={"parser_version": "1.2.0", "skills": ["FastAPI", "SQLAlchemy"]}
        )

        # 1. POST Review
        post_payload = {
            "resume_id": str(parsed_resume_id),
            "mode": "STANDARD",
            "language": "en",
            "bypass_cache": True
        }
        response = self.client.post("/api/v1/ai/resume/review", json=post_payload)
        self.assertEqual(response.status_code, 200, response.text)
        res_data = response.json()
        self.assertEqual(res_data["overall_score"], 85)
        self.assertEqual(res_data["resume_id"], str(parsed_resume_id))
        self.assertEqual(res_data["metadata"]["mode"], "STANDARD")
        
        review_id = res_data["id"]

        # 2. GET Review details
        get_response = self.client.get(f"/api/v1/ai/resume/review/{review_id}")
        self.assertEqual(get_response.status_code, 200)
        get_data = get_response.json()
        self.assertEqual(get_data["id"], review_id)
        self.assertEqual(get_data["overall_score"], 85)

        # Test unauthorized access: other user client tries to fetch review ID
        get_unauth = self.other_client.get(f"/api/v1/ai/resume/review/{review_id}")
        self.assertEqual(get_unauth.status_code, 404) # Not found or unauthorized

        # 3. GET all reviews history for user
        list_response = self.client.get("/api/v1/ai/resume/reviews")
        self.assertEqual(list_response.status_code, 200)
        list_data = list_response.json()
        self.assertGreaterEqual(list_data["total"], 1)

        # GET reviews history filtered by resume_id
        list_filtered = self.client.get(f"/api/v1/ai/resume/reviews?resume_id={parsed_resume_id}")
        self.assertEqual(list_filtered.status_code, 200)
        self.assertEqual(list_filtered.json()["total"], 1)

        # 4. DELETE review
        del_response = self.client.delete(f"/api/v1/ai/resume/review/{review_id}")
        self.assertEqual(del_response.status_code, 200)
        
        # Verify it is deleted
        get_deleted = self.client.get(f"/api/v1/ai/resume/review/{review_id}")
        self.assertEqual(get_deleted.status_code, 404)


if __name__ == "__main__":
    unittest.main()
