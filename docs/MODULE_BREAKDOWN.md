# Module Breakdown Specification

## CareerPilot AI — The Intelligent Career Copilot

---

## 1. Module Directory

The CareerPilot AI backend and frontend architectures are divided into 12 functional modules, designed to separate concerns, ensure testability, and support clean vertical slice architectures.

1.  **Authentication Module**
2.  **User Profile Module**
3.  **Resume Upload Module**
4.  **Resume Parser Module**
5.  **ATS Engine Module**
6.  **Job Matching Module**
7.  **Skill Gap Analysis Module**
8.  **Resume Optimizer Module**
9.  **Interview Preparation Module**
10. **Career Roadmap Module**
11. **AI Career Assistant Module**
12. **Dashboard & Analytics Module**

---

## 2. Detailed Module Specifications

### 2.1 Authentication Module

*   **Module Overview:** Manages user registration, session validation, security checks, and secure logouts.
*   **Purpose:** Enforce secure, stateless authentication boundaries to prevent unauthorized endpoint access and protect personal data.
*   **Responsibilities:**
    *   Hash user credentials using standard bcrypt protocols.
    *   Generate cryptographically signed, short-lived JSON Web Tokens (JWT) upon login.
    *   Store and clear authorization tokens inside `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
    *   Intercept protected routes via FastAPI dependency middleware to extract and validate cookies.
*   **Inputs:**
    *   *Registration:* Email address (string), Password (string).
    *   *Login:* Email address (string), Password (string).
    *   *Protected API Request:* HttpOnly cookie (`access_token`).
*   **Outputs:**
    *   *Registration:* Created status details and user UUID.
    *   *Login:* Set-Cookie header payload + Status success.
    *   *Auth Verification:* Decoded user session payload.
*   **Internal Services:** `auth_service.py` (password hashing, verification, token generation, cookie parsing).
*   **APIs Used:**
    *   `POST /api/v1/auth/register`
    *   `POST /api/v1/auth/login`
    *   `POST /api/v1/auth/logout`
    *   `GET /api/v1/auth/me`
*   **Database Tables:** `users`
*   **Dependencies:** `bcrypt` (password encryption), `PyJWT` (JWT generation/decoding), FastAPI Security dependencies.
*   **Future Improvements:** Introduce multi-factor authentication (MFA) using local TOTP setups and configure refresh-token rotation databases.

---

### 2.2 User Profile Module

*   **Module Overview:** Handles demographic settings, target roles, configurations, and core skills indexes.
*   **Purpose:** Persist user demographic contexts, styling preferences, and high-level career objectives to customize dashboard recommendations.
*   **Responsibilities:**
    *   Load and write profile details (name, target role, contact points).
    *   Maintain the primary skills listing array for direct matching comparisons.
    *   Manage UI preferences (e.g., system themes, dashboard layout preferences).
*   **Inputs:**
    *   *Read Request:* Authenticated User UUID.
    *   *Update Payload:* Profile settings object (first/last name, phone, target role, skills, theme preferences).
*   **Outputs:** Structured profile JSON matching the database schema.
*   **Internal Services:** `profile_service.py` (handles DB transactions for profiles, validates input parameters).
*   **APIs Used:**
    *   `GET /api/v1/profile`
    *   `PUT /api/v1/profile`
*   **Database Tables:** `profiles` (linked 1:1 with `users`).
*   **Dependencies:** `SQLAlchemy` ORM, `Pydantic v2` (validation schemas).
*   **Future Improvements:** Add automated LinkedIn profile import via raw profile PDF parsers and allow multiple target role sub-profiles.

---

### 2.3 Resume Upload Module

*   **Module Overview:** Manages binary file receiving, formatting checks, and text extraction boundaries.
*   **Purpose:** Allow users to securely upload document templates while verifying safety limits before passing plain text to parser engines.
*   **Responsibilities:**
    *   Verify file upload size boundaries (max 5MB limit).
    *   Filter unsupported extensions (allowing only `.pdf` and `.docx`).
    *   Extract raw text payloads from binaries using Python libraries.
    *   Instantiate new entries in the resumes table.
*   **Inputs:** Multipart form data containing the file binary.
*   **Outputs:** Upload status, generated resume UUID, file size metadata, and extracted text string.
*   **Internal Services:** `upload_service.py` (file validator, text extraction utilities for PDF/DOCX).
*   **APIs Used:**
    *   `POST /api/v1/resumes/upload`
    *   `GET /api/v1/resumes`
    *   `DELETE /api/v1/resumes/{id}`
*   **Database Tables:** `resumes`
*   **Dependencies:** `pypdf` (PDF reader), `python-docx` (Word parser), `python-multipart` (fastAPI form processor).
*   **Future Improvements:** Implement optical character recognition (OCR) fallback for scanned image-based PDF uploads.

---

### 2.4 Resume Parser Module

*   **Module Overview:** Extracts structured entities (skills, experience, education, projects) from raw resume plain text using NLP pipelines.
*   **Purpose:** Transform flat unstructured resume text into a normalized JSON document that can be queried by AI modules and search grids.
*   **Responsibilities:**
    *   Clean and pre-process text (strip non-ASCII characters, normalize spacing).
    *   Run spaCy NLP models for Part-of-Speech tagging and Named Entity Recognition (NER).
    *   Extract standard resume blocks (Experience, Education, Projects).
    *   Identify and extract technical and soft skills arrays using structured dictionary models.
*   **Inputs:** Extracted raw text string from the upload module.
*   **Outputs:** Structured JSON matching `resumes.parsed_json` (nested sections, dates, descriptions).
*   **Internal Services:** `parser_service.py` (spaCy NLP pipeline integration, entity mapping utilities).
*   **APIs Used:** Executed implicitly during `/api/v1/resumes/upload`.
*   **Database Tables:** `resumes` (saves output in `parsed_json` column).
*   **Dependencies:** `spaCy` (NLP engine), default spaCy language models (`en_core_web_sm`).
*   **Future Improvements:** Train a custom spaCy Named Entity Recognition (NER) model on a labeled dataset of tech resumes to improve extraction accuracy.

---

### 2.5 ATS Engine Module

*   **Module Overview:** Analyzes resume templates for ATS readability issues and generates formatting scores and optimization steps.
*   **Purpose:** Identify compliance issues that block automated screening systems, helping candidates format resumes for optimal readability.
*   **Responsibilities:**
    *   Scan text configurations for layout issues (e.g. multi-column layouts, tables, images).
    *   Validate the presence of standard sections (e.g. Work Experience, Education, Skills).
    *   Calculate a structural formatting score (0–100).
    *   Generate actionable formatting suggestions and priority ratings.
*   **Inputs:** Resume ID.
*   **Outputs:** Stored ATS report detailing score, formatting flags, missing sections, and optimization tasks.
*   **Internal Services:** `ats_service.py` (layout audit logic, section compliance validators).
*   **APIs Used:**
    *   `POST /api/v1/resumes/{id}/ats-analysis`
    *   `GET /api/v1/resumes/{id}/ats-analysis`
*   **Database Tables:** `ats_reports`
*   **Dependencies:** `re` (regular expressions), custom layout inspection rule patterns.
*   **Future Improvements:** Add automated parsing compatibility tests by comparing raw PDF text with extracted character locations to check for reading order issues.

---

### 2.6 Job Matching Module

*   **Module Overview:** Computes semantic similarity between a user's resume and a target job description.
*   **Purpose:** Move beyond simple keyword matching by using vector embeddings to analyze conceptual alignment and output a match rating.
*   **Responsibilities:**
    *   Vectorize the parsed resume and job description using sentence-transformer models.
    *   Calculate cosine similarity between the resume vector and the job vector.
    *   Calculate an overall match rating (0-100) combining vector similarity and keyword overlap.
*   **Inputs:** Resume ID, Job Description ID.
*   **Outputs:** Job match record, including the match score and ATS compatibility rating.
*   **Internal Services:** `matching_service.py` (sentence vectorization, cosine similarity calculator).
*   **APIs Used:**
    *   `POST /api/v1/jobs`
    *   `GET /api/v1/jobs`
    *   `POST /api/v1/matching/compare`
*   **Database Tables:** `job_descriptions`, `job_matches`
*   **Dependencies:** `sentence-transformers` (pre-trained `all-MiniLM-L6-v2` model), `scikit-learn` (cosine similarity functions).
*   **Future Improvements:** Cache vector embeddings in the database to optimize multi-job match comparisons.

---

### 2.7 Skill Gap Analysis Module

*   **Module Overview:** Compares resume skills against target job requirements to identify missing credentials.
*   **Purpose:** Provide candidates with clear visibility into missing requirements and suggest target skills to acquire.
*   **Responsibilities:**
    *   Extract target skills from job description text using NLP engines.
    *   Compare the user's parsed skills with target job requirements.
    *   Classify skills into: Present Skills, Missing Skills, and Recommended Skills.
    *   Generate a structured learning action plan.
*   **Inputs:** Job Match ID.
*   **Outputs:** Skill gap analysis report, including arrays of present/missing/recommended skills and an action plan.
*   **Internal Services:** `gap_analysis_service.py` (vocabulary set comparisons, action plan generation logic).
*   **APIs Used:** Executed implicitly during `/api/v1/matching/compare`.
*   **Database Tables:** `skill_gap_analyses`
*   **Dependencies:** `spaCy` (job description parsing), `SQLAlchemy` ORM.
*   **Future Improvements:** Integrate a local database of online learning paths and free certification links mapped to specific skills.

---

### 2.8 Resume Optimizer Module

*   **Module Overview:** Rewrites specific resume bullet points using local LLM feedback based on target roles.
*   **Purpose:** Help users reframe their experience using the STAR methodology (Situation, Task, Action, Result) to target specific job descriptions.
*   **Responsibilities:**
    *   Orchestrate prompts containing original bullet points, target roles, and target keywords.
    *   Call the local Ollama LLM to rewrite bullet points using the STAR method.
    *   Return the optimized suggestion alongside an explanation of the changes.
*   **Inputs:** Resume ID, Original Bullet Point (string), Job Description ID (optional), Focus Keywords (optional).
*   **Outputs:** Optimized bullet point suggestion, target keyword status, and modification notes.
*   **Internal Services:** `optimizer_service.py` (Ollama prompt injection, response parsing).
*   **APIs Used:**
    *   `POST /api/v1/resumes/{id}/optimize-bullet`
*   **Database Tables:** `resumes` (or `resume_versions` for history tracking).
*   **Dependencies:** `httpx` (async calls to the local Ollama socket).
*   **Future Improvements:** Allow users to choose from different writing styles (e.g., Technical, Leadership, Academic).

---

### 2.9 Interview Preparation Module

*   **Module Overview:** Runs interactive, role-specific mock interview simulations and grades user responses.
*   **Purpose:** Provide a low-friction practice environment that evaluates candidate responses and gives constructive feedback.
*   **Responsibilities:**
    *   Create interview sessions customized for specific roles, companies, or job descriptions.
    *   Generate a sequence of 5 role-specific behavioral and technical questions using the local LLM.
    *   Evaluate candidate answers in real-time, assigning a score (0-100) and constructive feedback.
    *   Calculate final average session scores and write performance summaries.
*   **Inputs:**
    *   *Create Session:* Target Role (string), Company (string), Job ID (optional).
    *   *Submit Answer:* Candidate response string.
*   **Outputs:**
    *   *Create Session:* Generated first question.
    *   *Submit Answer:* Response score, feedback critique, and the next question.
    *   *Conclude Session:* Final scorecard, feedback, and radar chart metrics.
*   **Internal Services:** `interview_service.py` (interview state manager, question generator, evaluator).
*   **APIs Used:**
    *   `POST /api/v1/interviews/sessions`
    *   `GET /api/v1/interviews/sessions`
    *   `GET /api/v1/interviews/sessions/{id}`
    *   `POST /api/v1/interviews/sessions/{id}/answer`
    *   `POST /api/v1/interviews/sessions/{id}/complete`
*   **Database Tables:** `interview_sessions`
*   **Dependencies:** `httpx` (async calls to local Ollama API), `Pydantic v2` validation models.
*   **Future Improvements:** Add support for speech-to-text response entry and real-time audio/video feedback indicators.

---

### 2.10 Career Roadmap Module

*   **Module Overview:** Generates structured career path milestones mapping transition timelines between roles.
*   **Purpose:** Give users clear visibility into the steps, skill milestones, and study resources needed to reach their target roles.
*   **Responsibilities:**
    *   Formulate transition prompts combining current role profiles and target objectives.
    *   Use the local LLM to generate an ordered sequence of roadmap milestones.
    *   Provide estimated timelines, target skills, study plans, and learning resources for each step.
*   **Inputs:** Current Role (string), Target Role (string).
*   **Outputs:** Generated career roadmap, including an array of milestone objects containing resources and action items.
*   **Internal Services:** `roadmap_service.py` (prompt assembly, LLM orchestration, structured roadmap parser).
*   **APIs Used:**
    *   `POST /api/v1/roadmaps/generate`
    *   `GET /api/v1/roadmaps`
    *   `GET /api/v1/roadmaps/{id}`
*   **Database Tables:** `career_roadmaps`
*   **Dependencies:** `httpx` (Ollama local API connection).
*   **Future Improvements:** Allow users to mark milestones as completed and track progress updates on the dashboard.

---

### 2.11 AI Career Assistant Module

*   **Module Overview:** Provides a system-wide, context-aware chatbot that answer career questions.
*   **Purpose:** Offer real-time, conversational support based on the user's uploaded resumes, matches, and logs.
*   **Responsibilities:**
    *   Initialize chat threads and manage conversation history.
    *   Assemble chat prompts that combine user queries with context from parsed resumes.
    *   Stream response text using Server-Sent Events (SSE) for a responsive chat experience.
*   **Inputs:** User message string.
*   **Outputs:** Streamed chat response tokens, updated conversation transcript.
*   **Internal Services:** `assistant_service.py` (conversation manager, context injector, SSE stream writer).
*   **APIs Used:**
    *   `GET /api/v1/assistant/chats`
    *   `POST /api/v1/assistant/chats`
    *   `POST /api/v1/assistant/chats/{id}/message` (Streaming / Non-Streaming)
    *   `DELETE /api/v1/assistant/chats/{id}`
*   **Database Tables:** `ai_conversations`
*   **Dependencies:** `httpx` (Ollama local integration), FastAPI streaming response utilities.
*   **Future Improvements:** Implement local retrieval-augmented generation (RAG) using SQLite/pgvector to search uploaded resume files.

---

### 2.12 Dashboard & Analytics Module

*   **Module Overview:** Aggregates performance data, matches, and scores to feed interactive charts on the frontend.
*   **Purpose:** Provide users with clear visibility into their career preparation progress, matching trends, and skill metrics.
*   **Responsibilities:**
    *   Query database aggregates (average match rates, total mock sessions, ATS ratings).
    *   Maintain pre-aggregated data in the `analytics` cache table to avoid heavy query loads.
    *   Format data sets for direct rendering by Plotly widgets on the frontend.
*   **Inputs:** Authenticated User ID.
*   **Outputs:** Aggregated metrics, ATS score trends, radar chart datasets, and mock score timelines.
*   **Internal Services:** `analytics_service.py` (database aggregation logic, cache manager).
*   **APIs Used:**
    *   `GET /api/v1/analytics/dashboard`
*   **Database Tables:** `analytics` (linked 1:1 with `users`), reads from `ats_reports`, `job_matches`, and `interview_sessions`.
*   **Dependencies:** `SQLAlchemy` ORM aggregate calculations.
*   **Future Improvements:** Add automated cron jobs to recalculate dashboard analytics caches in the background.
