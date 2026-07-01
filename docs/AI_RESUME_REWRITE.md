# AI Resume Rewrite Engine

The AI Resume Rewrite Engine is a core production feature of CareerPilot AI that automatically improves the writing quality, professional tone, grammar, action verbs, and ATS keywords of a user's resume while strictly preserving all factual achievements, dates, designations, education, and company names. It supports custom Rewrite Modes, section-by-section rewrites, optional job-specific tailoring, detailed diff generation, and undo support (rollback).

---

## Architecture

The engine adheres to clean architecture principles by separating endpoint routing, business orchestration, Python-level word diffing, LLM execution (via `AIService`), and database persistence.

```mermaid
graph TD
    Client[Client / Frontend] -->|HTTP POST /ai/resume/rewrite| API[API Endpoints]
    Client -->|HTTP POST /ai/resume/rewrite/section| API
    Client -->|HTTP POST /ai/resume/rewrite/:id/undo| API
    API -->|Orchestrate| Service[ResumeRewriteService]
    Service -->|Read Parsed JSON| DB[(Database / Postgres)]
    Service -->|Execute Template| AIS[AIService]
    AIS -->|Fetch templates| Registry[Prompt Registry]
    AIS -->|Send system + template| Provider[AI Provider Factory]
    Provider -->|Generate| LLM[Ollama Client / LLM]
    Service -->|Calculate word diff| Diff[Python Diff Engine]
    Service -->|Update parsed_data| DB
    Service -->|Persist Rewrite History| DB
    Service -->|Return Response| API
```

---

## Detailed Data Flow

1. **API Request**: The user submits a rewrite request (`resume_id`, `mode`, `job_description`, `model_override`, `bypass_cache`).
2. **Retrieve & Validate**: The `ResumeRewriteService` retrieves the `Resume` model, verifies ownership, checks that the resume is parsed, and validates the requested rewrite mode.
3. **Database Caching**: If `bypass_cache` is `False`, the database is queried for an identical rewrite configuration. If found, it returns the cached result.
4. **AI Service Call**:
   - The service loads the versioned `resume/rewrite` template.
   - It runs the LLM using the deterministic temperature (`0.2`).
   - If the LLM returns invalid JSON or fails structural validation, the service retries the execution once.
5. **Diff Computation**: After a successful LLM response, the Python Diff Engine (`diff_engine.py`) performs word-level comparisons between original and rewritten sections to compute added, removed, and modified segments.
6. **Persistence & Application**:
   - The original parsed resume JSON is saved as `original_content`.
   - The rewritten segments are merged into the resume to create `rewritten_content`.
   - The service updates the `Resume` table's active `parsed_data` to match the rewritten content.
   - The service links the new rewrite to the previous active rewrite via a `parent_id` for history tracing.
7. **Undo / Rollback**: If a user hits `/undo`, the service restores the resume's `parsed_data` to the `original_content` of that rewrite, reversing the changes.

---

## Rewrite Modes

The engine supports six configuration-driven rewrite modes:

| Rewrite Mode | Temperature | Max Tokens | Description |
| :--- | :--- | :--- | :--- |
| **STANDARD** | 0.2 | 4096 | Balanced edits for readability, flow, and standard professional tone. |
| **PROFESSIONAL** | 0.2 | 4096 | Direct, business-professional language with standard job-specific phrasing. |
| **EXECUTIVE** | 0.2 | 4096 | High-level language emphasizing leadership, strategic impact, and metrics. |
| **ATS** | 0.2 | 4096 | Heavily focused on keywords and alignment with modern tracking systems. |
| **CONCISE** | 0.2 | 2048 | Shortened phrasing, removing wordiness while retaining all accomplishments. |
| **DETAILED** | 0.2 | 4096 | Elaborate phrasing that highlights the full scope of each experience. |

---

## Prompt Template (`resume/rewrite.jinja`)

Forces the LLM to rewrite specific sections (e.g. professional summary, work experience, projects, skills, education) or the entire resume while enforcing:
- **Strict Fact Preservation**: Under no circumstances should the LLM fabricate dates, technologies, designations, certifications, or accomplishments.
- **Job Tailoring**: Adjusting wording to align with target skills and keywords in the job description without fabricating experience.
- **Quality Score Generation**: Estimating readability, grammar, tone, ATS optimization, and action verb improvement.
- **Structured JSON Output**: Returning content strictly adhering to the JSON schema.

---

## Schemas

### Database Table (`ai_resume_rewrites`)
```sql
CREATE TABLE ai_resume_rewrites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES ai_resume_rewrites(id) ON DELETE SET NULL,
    original_content JSONB NOT NULL,
    rewritten_content JSONB NOT NULL,
    rewrite_mode VARCHAR(50) NOT NULL,
    job_description TEXT,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(20) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);
```

### Pydantic Response Schema (`ResumeRewriteResponse`)
Exposed in `app/schemas/ai_resume_rewrite.py`:
- `change_tracking`: Maps rewritten sections to their original value, rewritten value, reasoning, improvement category, confidence, estimated ATS improvement, and word-level diff.
- `quality_scores`: Contains indicators for readability, grammar, tone, ATS, and action verb improvement.
- `keyword_optimization`: Highlights matched, added, and missing keywords if a Job Description is provided.

---

## Developer Guide

### Running Rewrites / Rollbacks
All API endpoints require authentication and are mounted under the `/api/v1/ai/` prefix:
- `POST /api/v1/ai/resume/rewrite`: Full rewrite.
- `POST /api/v1/ai/resume/rewrite/section`: Section rewrite.
- `GET /api/v1/ai/resume/rewrite/{id}`: Fetch rewrite record.
- `GET /api/v1/ai/resume/rewrites`: Fetch user history list.
- `DELETE /api/v1/ai/resume/rewrite/{id}`: Delete rewrite.
- `POST /api/v1/ai/resume/rewrite/{id}/undo`: Revert resume back to pre-rewrite state.

### Running Tests
To run unit, database, diff engine, caching, and API integration tests:
```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/careerpilot_db"
$env:JWT_SECRET_KEY="supersecretchangeitinproduction"
backend/venv/Scripts/pytest -v tests/test_ai_resume_rewrite.py
```
