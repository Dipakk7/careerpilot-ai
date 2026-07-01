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
from app.models.ai_resume_optimization import AIResumeOptimization
from app.core.enums import ResumeStatus, StorageProvider
from app.services.optimization_service import ResumeOptimizationService
from app.services.workflow_service import ResumeWorkflowService
from app.ai.schemas.ai_response import AIStructuredResponse, TokenUsage
from app.ai.exceptions import AIProviderUnavailable
from app.schemas.ai_resume_optimization import (
    ResumeQualityScore,
    MissingSkillDetail,
    ATSOptimizationDetail,
    KeywordAnalysis,
    AchievementOptimizationDetail,
    ResumeCompleteness,
    CareerReadiness,
    IndustryAlignmentDetail,
    OptimizationRecommendation,
    ResumeOptimizationResponse,
)

class TestAIResumeOptimization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test users, database connection, and authenticated client."""
        db = SessionLocal()
        cls.db = db
        try:
            # Cleanup old test users
            for email in ["opt_test@careerpilot.com", "opt_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    db.query(AIResumeOptimization).filter(AIResumeOptimization.user_id == test_user.id).delete()
                    db.query(Resume).filter(Resume.user_id == test_user.id).delete()
                    db.delete(test_user)
            db.commit()

            # Create primary test user
            from app.services import auth_service
            from app.schemas.user import UserCreate
            
            user_in = UserCreate(
                email="opt_test@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Opt Test User"
            )
            cls.user = auth_service.register_user(db, user_create=user_in)
            cls.user_id = cls.user.id

            # Create secondary test user
            other_user_in = UserCreate(
                email="opt_test_other@careerpilot.com",
                password="SecurePassword@2026",
                full_name="Other Opt User"
            )
            cls.other_user = auth_service.register_user(db, user_create=other_user_in)
            cls.other_user_id = cls.other_user.id

            db.commit()
        finally:
            db.close()

        # Login client
        cls.client = TestClient(app)
        login_payload = {
            "email": "opt_test@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        login_response = cls.client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"

        # Login other client
        cls.other_client = TestClient(app)
        other_login_payload = {
            "email": "opt_test_other@careerpilot.com",
            "password": "SecurePassword@2026"
        }
        other_login_response = cls.other_client.post("/api/v1/auth/login", json=other_login_payload)
        assert other_login_response.status_code == 200, f"Other login failed: {other_login_response.text}"

        # Setup standard mock optimization response dict
        cls.mock_opt_dict = {
            "quality_score": {
                "overall_score": 85,
                "ats": 80,
                "technical_skills": 85,
                "experience": 90,
                "projects": 80,
                "grammar": 95,
                "formatting": 90,
                "readability": 90,
                "leadership": 75,
                "professionalism": 90,
                "career_readiness": 85,
                "completeness": 90,
                "consistency": 90
            },
            "missing_skills": [
                {
                    "skill": "Docker",
                    "why_it_matters": "Docker is crucial for containerization and microservices architecture.",
                    "priority": "HIGH",
                    "difficulty": "MEDIUM",
                    "estimated_time": "10 hours",
                    "resources": ["Docker Documentation", "Intro to Docker Course"]
                }
            ],
            "ats_optimization": {
                "current_score": 75,
                "why_score_is_low": "The resume lacks specific keywords.",
                "missing_keywords": ["Kubernetes", "CI/CD"],
                "sections_needing_improvement": ["Experience", "Skills"],
                "expected_improvement": 15
            },
            "keyword_optimization": {
                "matched_keywords": ["Python", "FastAPI"],
                "missing_keywords": ["Kubernetes", "Docker"],
                "recommended_keywords": ["CI/CD", "AWS"],
                "overused_keywords": ["utilized"],
                "weak_keywords": ["helped"],
                "strong_action_verbs": ["implemented", "architected"],
                "industry_keywords": ["microservices", "cloud computing"]
            },
            "achievement_optimization": [
                {
                    "original_bullet": "Helped design backend APIs.",
                    "suggested_bullet": "Architected and implemented high-performance FastAPI backends, reducing API response times by 35%.",
                    "reason": "Specify tech stack and add metrics.",
                    "missing_metrics": True,
                    "missing_impact": True,
                    "missing_business_value": True,
                    "estimated_improvement": "Significant improvement"
                }
            ],
            "completeness": {
                "percentage": 90,
                "missing_sections": ["Certifications"],
                "evaluated_sections": {
                    "summary": True,
                    "projects": True,
                    "skills": True,
                    "education": True,
                    "experience": True,
                    "certifications": False,
                    "achievements": True,
                    "links": True
                }
            },
            "career_readiness": {
                "internship_ready": {
                    "ready": True,
                    "reasoning": "Strong academic record."
                },
                "entry_level_ready": {
                    "ready": True,
                    "reasoning": "Good coding skills."
                },
                "mid_level_ready": {
                    "ready": False,
                    "reasoning": "Needs more industry exposure."
                },
                "senior_ready": {
                    "ready": False,
                    "reasoning": "Needs proven leadership experience."
                }
            },
            "industry_alignment": [
                {"industry": "Software Engineering", "confidence": 0.9},
                {"industry": "AI Engineer", "confidence": 0.5},
                {"industry": "ML Engineer", "confidence": 0.4},
                {"industry": "Data Scientist", "confidence": 0.3},
                {"industry": "Backend Engineer", "confidence": 0.85},
                {"industry": "Python Developer", "confidence": 0.9},
                {"industry": "Data Analyst", "confidence": 0.4}
            ],
            "recommendations": [
                {
                    "section": "experience",
                    "type": "achievement",
                    "original_text": "Helped design backend APIs.",
                    "suggested_text": "Architected and implemented high-performance FastAPI backends, reducing API response times by 35%.",
                    "reason": "Add metrics.",
                    "impact": "Shows business value.",
                    "priority": "HIGH",
                    "estimated_improvement": "15%",
                    "difficulty": "EASY"
                }
            ]
        }

    @classmethod
    def tearDownClass(cls):
        """Clean up all records inserted during tests."""
        db = SessionLocal()
        try:
            for email in ["opt_test@careerpilot.com", "opt_test_other@careerpilot.com"]:
                test_user = db.query(User).filter(User.email == email).first()
                if test_user:
                    db.query(AIResumeOptimization).filter(AIResumeOptimization.user_id == test_user.id).delete()
                    db.query(Resume).filter(Resume.user_id == test_user.id).delete()
                    db.delete(test_user)
            db.commit()
        finally:
            db.close()

    def helper_create_resume(self, user_id, filename, parsed_data=None, status=ResumeStatus.PARSED):
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
                status=status,
                parsed_data=parsed_data,
                storage_provider=StorageProvider.LOCAL
            )
            db_resume.ats_score = 75
            db.add(db_resume)
            db.commit()
            db.refresh(db_resume)
            return db_resume.id
        finally:
            db.close()

    # --- SCHEMA & MODEL TESTS ---

    def test_schema_validations(self):
        """Test that schemas validate structure correctly."""
        score = ResumeQualityScore(
            overall_score=85, ats=80, technical_skills=85, experience=90, projects=80,
            grammar=95, formatting=90, readability=90, leadership=75, professionalism=90,
            career_readiness=85, completeness=90, consistency=90
        )
        self.assertEqual(score.overall_score, 85)

        alignment = IndustryAlignmentDetail(industry="AI Engineer", confidence=0.95)
        self.assertEqual(alignment.confidence, 0.95)

    # --- SERVICE TESTS WITH MOCKED AIService ---

    @patch("app.ai.services.ai_service.AIService.execute")
    @patch("app.services.optimization_service.calculate_ats_score")
    @patch("app.services.optimization_service.calculate_job_match")
    @patch("app.services.optimization_service.analyze_resume_gap")
    @patch("app.services.optimization_service.parse_job_description")
    def test_optimize_resume_service_success(
        self, mock_parse_jd, mock_gap, mock_match, mock_ats, mock_ai_execute
    ):
        """Test ResumeOptimizationService runs ATS/Job Match and returns optimization record."""
        # 1. Setup mock returns
        mock_ats.return_value = AsyncMock()
        mock_match.return_value = AsyncMock()
        mock_gap.return_value = AsyncMock()

        # Mock AIService structured response
        ai_resp = AIStructuredResponse(
            provider="mock",
            model="mock-model",
            latency_ms=150.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_opt_dict,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            token_fields={}
        )
        mock_ai_execute.return_value = ai_resp

        # Create resume
        resume_id = self.helper_create_resume(
            user_id=self.user_id,
            filename="opt_test_resume.pdf",
            parsed_data={"parser_version": "1.0.0", "data": {"skills": ["Python"]}}
        )

        db = SessionLocal()
        try:
            service = ResumeOptimizationService(db)
            db_opt = asyncio.run(service.optimize_resume(
                resume_id=resume_id,
                user_id=self.user_id,
                job_description="Need Python developer",
                mode="PROFESSIONAL",
                bypass_cache=True
            ))

            self.assertIsNotNone(db_opt)
            self.assertEqual(db_opt.model, "mock-model")
            self.assertEqual(db_opt.quality_score["overall_score"], 85)
            self.assertEqual(db_opt.optimization_result["missing_skills"][0]["skill"], "Docker")
        finally:
            db.close()

    # --- VALIDATION ERRORS ---

    def test_optimize_resume_validation_errors(self):
        """Verify optimize_resume rejects empty parses or unsupported versions."""
        db = SessionLocal()
        try:
            service = ResumeOptimizationService(db)
            
            # Non-existent resume
            with self.assertRaises(ValueError) as context:
                asyncio.run(service.optimize_resume(uuid.uuid4(), self.user_id))
            self.assertIn("not found", str(context.exception))

            # Not parsed yet
            unparsed_id = self.helper_create_resume(
                user_id=self.user_id,
                filename="unparsed.pdf",
                status=ResumeStatus.UPLOADED
            )
            with self.assertRaises(ValueError) as context:
                asyncio.run(service.optimize_resume(unparsed_id, self.user_id))
            self.assertIn("must be parsed", str(context.exception))

            # Unsupported parser version
            old_version_id = self.helper_create_resume(
                user_id=self.user_id,
                filename="old_parser.pdf",
                parsed_data={"parser_version": "0.5.0"}
            )
            with self.assertRaises(ValueError) as context:
                asyncio.run(service.optimize_resume(old_version_id, self.user_id))
            self.assertIn("Unsupported resume parser version", str(context.exception))
        finally:
            db.close()

    # --- API ENDPOINTS TESTS ---

    @patch("app.ai.services.ai_service.AIService.execute")
    def test_api_optimize_flow(self, mock_ai_execute):
        """Test API POST optimize, get details, and delete workflow."""
        ai_resp = AIStructuredResponse(
            provider="mock",
            model="mock-model",
            latency_ms=100.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_opt_dict,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            token_fields={}
        )
        mock_ai_execute.return_value = ai_resp

        # Create resume
        resume_id = self.helper_create_resume(
            user_id=self.user_id,
            filename="api_opt.pdf",
            parsed_data={"parser_version": "1.0.0", "data": {"skills": ["Python"]}}
        )

        headers = {
            "Authorization": f"Bearer {self.client.cookies.get('access_token') or ''}"
        }

        # 1. Trigger Optimize endpoint
        payload = {
            "resume_id": str(resume_id),
            "job_description": "We want a Python developer",
            "mode": "PROFESSIONAL",
            "bypass_cache": True
        }
        response = self.client.post("/api/v1/ai/resume/optimize", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["quality_score"]["overall_score"], 85)
        opt_id = data["id"]

        # 2. Get Optimization by ID
        get_resp = self.client.get(f"/api/v1/ai/resume/optimization/{opt_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], opt_id)

        # 3. Get Optimizations history list
        list_resp = self.client.get(f"/api/v1/ai/resume/optimizations?resume_id={resume_id}")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["total"], 1)

        # 4. Delete record
        del_resp = self.client.delete(f"/api/v1/ai/resume/optimization/{opt_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["success"])

        # 5. Get optimization (verify 404)
        get_gone = self.client.get(f"/api/v1/ai/resume/optimization/{opt_id}")
        self.assertEqual(get_gone.status_code, 404)

    @patch("app.ai.services.ai_service.AIService.execute")
    @patch("app.services.workflow_service.parse_resume")
    def test_api_workflow_flow(self, mock_parse_resume, mock_ai_execute):
        """Test full Workflow pipeline execution orchestration."""
        # Mock LLM calls for Review, Rewrite, and Optimization (called in sequence)
        ai_resp = AIStructuredResponse(
            provider="mock",
            model="mock-model",
            latency_ms=100.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response=self.mock_opt_dict,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            token_fields={}
        )
        # Mock review dict
        mock_review_dict = {
            "overall_score": 80,
            "overall_summary": "Summary",
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "missing_sections": []
        }
        # Mock rewrite dict
        mock_rewrite_dict = {
            "rewritten_content": {},
            "change_tracking": {},
            "quality_scores": {
                "readability_improvement": 10,
                "grammar_improvement": 15,
                "professional_tone": 20,
                "ats_optimization": 25,
                "action_verb_score": 30
            },
            "keyword_optimization": {
                "matched_keywords": ["Python"],
                "added_keywords": ["FastAPI"],
                "missing_keywords": ["Docker"]
            }
        }

        # Mock AIService.execute sequentially: 1st review, 2nd rewrite, 3rd optimize
        mock_ai_execute.side_effect = [
            AIStructuredResponse(
                provider="mock", model="mock-model", latency_ms=100.0, prompt_version="1.0.0",
                created_at=datetime.utcnow(), raw_response={}, parsed_response=mock_review_dict,
                usage=TokenUsage(), token_fields={}
            ),
            AIStructuredResponse(
                provider="mock", model="mock-model", latency_ms=100.0, prompt_version="1.0.0",
                created_at=datetime.utcnow(), raw_response={}, parsed_response=mock_rewrite_dict,
                usage=TokenUsage(), token_fields={}
            ),
            ai_resp
        ]

        # Create resume
        resume_id = self.helper_create_resume(
            user_id=self.user_id,
            filename="workflow_test.pdf",
            parsed_data={"parser_version": "1.0.0", "data": {"skills": ["Python"]}}
        )

        payload = {
            "resume_id": str(resume_id),
            "job_description": "We want a Python developer",
            "mode": "PROFESSIONAL",
            "bypass_cache": True
        }
        
        response = self.client.post("/api/v1/ai/resume/workflow", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["stages"]["parser"], "SUCCESS")
        self.assertEqual(data["stages"]["review"], "SUCCESS")
        self.assertEqual(data["stages"]["rewrite"], "SUCCESS")
        self.assertEqual(data["stages"]["optimization"], "SUCCESS")
        self.assertEqual(data["quality_score"], 85)
        self.assertIsNotNone(data["optimization_id"])
        self.assertIsNotNone(data["review_id"])
        self.assertIsNotNone(data["rewrite_id"])
