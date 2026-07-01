# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.8.0] - 2026-07-01 (Phase 8)
### Added
- **AI Foundation**: Implemented a decoupled factory pattern for AI providers, a robust client for local Ollama deployments, and health check validation.
- **Prompt Management System**: Created a Prompts Registry for loading, rendering via Jinja templates, caching outputs, handling retries, and recording token and time metrics.
- **AI Resume Review Engine**: Developed a service to scan resumes, evaluate layout, structure, and impact, and output a structured JSON review with a Resume Quality Score.
- **AI Resume Rewrite Engine**: Built interactive rewriting capabilities that structure bullet points to align with job descriptions or specific professional modes.
- **AI Resume Optimization Engine**: Designed a service that calculates career readiness, industry alignment, keyword match ratios, and suggested improvement resources.
- **Workflow Orchestration Engine**: Built a unified Orchestrator to parse, review, rewrite, and optimize resumes in a single end-to-end execution.
- **Database Schema & Migrations**: Configured models and migrations for reviews, rewrites, and optimizations, resolving all head revisions in Alembic.
- **Robust Endpoints**: Exposed FastAPI controllers for all AI operations, supporting streaming, schema-validated payloads, and historical CRUD.
- **Test Coverage**: Added comprehensive test files covering AI Foundation, Prompt Cache, Review, Rewrite, and Optimization services with all 296 workspace tests passing.
- **Technical Documentation**: Generated developer onboarding documents for AI Review, AI Rewrite, Prompt Management, and AI Resume Optimization modules.

---

## [0.7.0] - 2026-07-01
### Added
- **Analytics Foundation**: Implemented centralized statistics layer and mathematical utility functions inside `BaseStatistics`.
- **Dashboard Analytics**: Created system-wide aggregation for total users, resumes, job matches, and averages.
- **Resume Analytics**: Integrated detailed parsed content distribution, skill frequencies, education cohorts, and timeline metrics.
- **ATS Analytics**: Added aggregate ATS scoring, grade distribution cohorts, category breakdowns, and weakness lists.
- **Job Match Analytics**: Developed job match score bucket distribution, top missing skills list, and history timeline.
- **GitHub Profile Analytics**: Created public GitHub API integration with metadata caching for user profiles and repository summaries.
- **GitHub Repository Insights**: Designed repository-level language analysis, activity recency, and Developer Score formula.
- **Charts Engine**: Created dynamic, registry-driven chart generation with fallback behavior (partial failures skip failed charts).
- **FastAPI Endpoints**: Exposed robust endpoints for all analytics and charts under `/api/v1/analytics/`.
- **Comprehensive Testing**: Added 42 new unit and integration tests specifically covering analytics modules, mock endpoints, and edge cases.
- **Detailed Documentation**: Created `docs/PHASE7_ANALYTICS.md` documenting the structure, routes, known limitations, and performance audit.

---

## [0.6.0] - 2026-06-20
### Added
- **Job Matching Engine**: Implemented intelligent resume-to-job matching, gap analysis, and missing keyword/skill extraction.
- **Job Match Export**: Added PDF/JSON export support for job matching metrics.

---

## [0.5.0] - 2026-06-10
### Added
- **ATS Scoring Engine**: Created section-by-section evaluation algorithms and automated feedback generators.

---

## [0.4.0] - 2026-05-30
### Added
- **Intelligent Parser Engine**: Configured SpaCy model, section detectors, and normalization mappings.

---

## [0.3.0] - 2026-05-15
### Added
- **Resume Pipeline**: Created secure document storage, validation rules, and parser hooks.

---

## [0.2.0] - 2026-04-30
### Added
- **Authentication**: Built JWT authentication, login workflows, and token validations.

---

## [0.1.0] - 2026-04-15
### Added
- **Core backend**: Initialized FastAPI structure, SQLAlchemy engine, logging configuration, and health endpoints.
