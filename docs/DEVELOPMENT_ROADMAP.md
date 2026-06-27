# Development Roadmap Specification

## CareerPilot AI — The Intelligent Career Copilot

---

## Phase 1: Planning & Architecture (Days 1–3)

### Day 1: Project Initiation & Scaffolding
*   **Objectives:** Define core project parameters, establish folder structures, and align requirements.
*   **Tasks:**
    *   Initialize the project workspace structure and subfolders.
    *   Draft the project requirements document containing all functional and non-functional specifications.
    *   Formulate the high-level Clean Architecture system specifications.
*   **Deliverables:** `PROJECT_REQUIREMENTS.md`, `SOFTWARE_ARCHITECTURE.md`, `README.md`.
*   **Testing:** Manual inspection of folder mapping alignments.
*   **Expected Outcome:** Workspace scaffolding complete with approved core requirements and architecture documents.
*   **Suggested Git Commit:** `feat: initialize project scaffolding and core planning documentation`

---

### Day 2: Database, API & Design Specification
*   **Objectives:** Establish the data models, specify the REST endpoints, and outline the UI/UX style system.
*   **Tasks:**
    *   Design the PostgreSQL relational schema, indexes, and check constraints.
    *   Define all REST endpoint paths, request parameters, response JSON contracts, and status codes.
    *   Outline the obsidian-glassmorphic style system variables, color schemes, typography, and motion rules.
*   **Deliverables:** `DATABASE_DESIGN.md`, `API_SPECIFICATION.md`, `UI_UX_GUIDE.md`.
*   **Testing:** Validate Mermaid schema syntax structures for the ERD and style guidelines.
*   **Expected Outcome:** Data models, API contracts, and design systems approved before development starts.
*   **Suggested Git Commit:** `docs: add database design, API specs, and UI/UX style guide`

---

### Day 3: Module Breakdown, Workflows & Implementation Roadmap
*   **Objectives:** Define responsibilities for all 12 modules, document core sequences, and create the implementation schedule.
*   **Tasks:**
    *   Draft the module breakdown document detailing inputs, outputs, database tables, and dependencies for all modules.
    *   Model sequence and flow diagrams mapping auth, parsing, matching, and mock interviews.
    *   Formulate the complete 28-day implementation roadmap.
*   **Deliverables:** `MODULE_BREAKDOWN.md`, `SYSTEM_WORKFLOW.md`, `DEVELOPMENT_ROADMAP.md`.
*   **Testing:** Verify consistency across all Phase 1 documentation.
*   **Expected Outcome:** Final planning documents completed, Git repository initialized, and remote repository linked on GitHub.
*   **Suggested Git Commit:** `docs: complete module breakdowns, system workflows, and 28-day roadmap`

---

## Phase 2: Project Setup & Authentication (Days 4–6)

### Day 4: Backend Setup & Database Migration Scaffolding
*   **Objectives:** Setup the FastAPI workspace environment, configure database engines, and initialize migrations.
*   **Tasks:**
    *   Install Python 3.12, initialize virtual environment, and populate `requirements.txt`.
    *   Configure the FastAPI base engine, routing schemas, and global error handlers.
    *   Initialize SQLAlchemy models matching the DB design and setup Alembic migration scripts.
*   **Deliverables:** `backend/app/main.py`, `backend/app/core/db.py`, initial database migration script.
*   **Testing:** Run local database connection checks and execute a test migration using SQLite/Postgres.
*   **Expected Outcome:** FastAPI backend server successfully initialized and connected to the database.
*   **Suggested Git Commit:** `chore: setup backend environment, database engines, and migrations`

---

### Day 5: Frontend Project Initialization & Design Scaffolding
*   **Objectives:** Initialize Next.js 14, integrate Tailwind, and import shadcn/ui components.
*   **Tasks:**
    *   Scaffold Next.js App Router workspace using TypeScript.
    *   Configure Tailwind HSL tokens in `globals.css` matching UI style guidelines.
    *   Initialize Radix UI primitives and install core shadcn/ui primitives (Button, Input, Card).
*   **Deliverables:** `frontend/package.json`, `frontend/tailwind.config.js`, base styling configuration files.
*   **Testing:** Run the Next.js development server locally and verify base component styling rendering.
*   **Expected Outcome:** Next.js client initialized and styled using Tailwind and shadcn/ui base tokens.
*   **Suggested Git Commit:** `chore: initialize frontend Next.js application and style system`

---

### Day 6: User Authentication & JWT Cookies
*   **Objectives:** Build user registration, login, and session validation endpoints with HttpOnly cookie storage.
*   **Tasks:**
    *   Implement bcrypt password hashing and write user registration/login APIs in the backend.
    *   Configure JWT token generation and setup middleware to write HttpOnly auth cookies.
    *   Build authentication forms (Login, Register) and set up routing guards in the Next.js client.
*   **Deliverables:** `backend/app/api/auth.py`, `frontend/src/app/login/page.tsx`, `frontend/src/app/register/page.tsx`.
*   **Testing:** Verify registration, cookie storage upon login, and route guards for protected paths.
*   **Expected Outcome:** Secure user registration, authentication, and session cookie validation successfully integrated.
*   **Suggested Git Commit:** `feat: implement user registration, login, and secure JWT cookies`

---

## Phase 3: Resume Upload (Days 7–9)

### Day 7: Resume Upload API & Validation
*   **Objectives:** Build multipart form upload endpoints and write file format/size validators.
*   **Tasks:**
    *   Create the POST upload endpoint in FastAPI to receive file attachments.
    *   Write validators to enforce the 5MB size limit and verify PDF/DOCX file formats.
    *   Implement local file storage utilities and save basic file metadata to the database.
*   **Deliverables:** `backend/app/api/resumes.py` (upload endpoints), `backend/app/services/upload.py`.
*   **Testing:** Upload files to test size limits and format validations.
*   **Expected Outcome:** The backend successfully receives, validates, and stores uploaded files.
*   **Suggested Git Commit:** `feat: add backend file upload API and validation logic`

---

### Day 8: PDF & DOCX Text Extraction Services
*   **Objectives:** Write backend utilities to extract plain text from PDF and Word documents.
*   **Tasks:**
    *   Integrate `pypdf` to extract raw text blocks from PDF attachments.
    *   Integrate `python-docx` to extract text from DOCX files.
    *   Write text formatting utilities to clean whitespace and normalize characters.
*   **Deliverables:** `backend/app/services/extractor.py` (text extraction helpers).
*   **Testing:** Extract text from sample PDF/DOCX files and verify output formatting.
*   **Expected Outcome:** Documents are parsed into clean, normalized text strings.
*   **Suggested Git Commit:** `feat: implement PDF and DOCX text extraction utilities`

---

### Day 9: Frontend Upload Dashboard Component
*   **Objectives:** Build the upload component with drag-and-drop support and upload progress indicators.
*   **Tasks:**
    *   Build a drag-and-drop file upload zone using Tailwind.
    *   Implement upload progress indicator animations using Next.js state.
    *   Build a list view showing upload histories and file details.
*   **Deliverables:** `frontend/src/components/features/UploadWidget.tsx`, upload history page.
*   **Testing:** Test file drops, verify progress bar animations, and check details displays.
*   **Expected Outcome:** A responsive, drag-and-drop upload widget styled to match design guidelines.
*   **Suggested Git Commit:** `feat: build frontend drag-and-drop resume upload dashboard`

---

## Phase 4: Resume Parser (Days 10–12)

### Day 10: Section Extraction (spaCy NLP)
*   **Objectives:** Map raw text into distinct resume sections (Work History, Education, Skills, Projects).
*   **Tasks:**
    *   Set up the local spaCy NLP pipeline in the backend.
    *   Write rule-based segmenters to identify section boundaries.
    *   Map extracted text blocks to resume schema attributes.
*   **Deliverables:** `backend/app/services/parser.py` (section segmenter methods).
*   **Testing:** Verify section extraction accuracy across various resume layouts.
*   **Expected Outcome:** Raw text is successfully split into structured resume sections.
*   **Suggested Git Commit:** `feat: implement resume section extraction using spaCy`

---

### Day 11: Named Entity Recognition & Skills Parser
*   **Objectives:** Extract structured skills, dates, and locations, saving the parsed JSON to the database.
*   **Tasks:**
    *   Write NER extractors to parse details (job titles, dates, locations, organizations).
    *   Integrate dictionary-based matching to extract technical and soft skills.
    *   Save structured outputs to the database in the `resumes.parsed_json` column.
*   **Deliverables:** `backend/app/services/ner_extractor.py`, updated database parser integrations.
*   **Testing:** Verify parsing accuracy for skills, dates, and locations.
*   **Expected Outcome:** Extracted metadata is successfully saved as structured JSON.
*   **Suggested Git Commit:** `feat: implement skills and entity extraction via NER`

---

### Day 12: Frontend Parser Visualization Layout
*   **Objectives:** Build a dashboard panel showing side-by-side comparisons of raw resumes and parsed data.
*   **Tasks:**
    *   Create a split layout page showing raw text next to parsed schemas.
    *   Build interactive tag grids for skills, experience timelines, and education details.
    *   Implement options to edit and manually confirm parsed data.
*   **Deliverables:** `frontend/src/app/resumes/[id]/parsed/page.tsx` (split visualization screen).
*   **Testing:** Render parsed datasets, verify editor features, and check responsiveness.
*   **Expected Outcome:** An interactive interface to review and confirm parsed resume data.
*   **Suggested Git Commit:** `feat: build parsed resume visualization dashboard`

---

## Phase 5: ATS Engine & Resume Optimization (Days 13–15)

### Day 13: ATS Scorer & Layout Compliance
*   **Objectives:** Write the ATS score calculation engine and analyze formatting compliance.
*   **Tasks:**
    *   Write validators to flag layout issues (multi-column formats, images, tables).
    *   Verify the presence of standard sections and calculate an overall compliance score (0-100).
    *   Write recommendations generators to output prioritized fixes.
*   **Deliverables:** `backend/app/services/ats_engine.py`, ATS report API endpoints.
*   **Testing:** Run ATS checks on resumes to verify formatting and score calculation logic.
*   **Expected Outcome:** The system successfully identifies formatting issues and generates compliance scores.
*   **Suggested Git Commit:** `feat: build backend ATS score engine and formatting checker`

---

### Day 14: AI Bullet Point Rewrite API (Local Ollama)
*   **Objectives:** Write backend utilities to prompt the local Ollama LLM to rewrite resume bullets.
*   **Tasks:**
    *   Set up asynchronous HTTP connections to the local Ollama socket.
    *   Design prompts that direct the LLM to rewrite bullet points using the STAR method.
    *   Build endpoints to stream rewritten suggestions to the frontend.
*   **Deliverables:** `backend/app/services/optimizer.py`, rewrite API endpoints.
*   **Testing:** Trigger bullet rewrite calls and verify stream outputs.
*   **Expected Outcome:** Resume bullet points are successfully rewritten using local AI streaming.
*   **Suggested Git Commit:** `feat: create local Ollama bullet optimization service`

---

### Day 15: Frontend ATS Dashboard & Optimizer Panel
*   **Objectives:** Build the ATS score display, recommendations lists, and bullet rewrite interface.
*   **Tasks:**
    *   Build a circular score gauge component using Tailwind.
    *   Build a categorized lists view showing formatting recommendations.
    *   Create a slide-out drawer containing bullet optimization inputs and comparisons.
*   **Deliverables:** `frontend/src/components/features/AtsReport.tsx`, bullet optimization drawer.
*   **Testing:** Verify score gauge rendering, check recommendations, and test inline rewrites.
*   **Expected Outcome:** A dashboard view showing formatting suggestions and AI-driven optimizations.
*   **Suggested Git Commit:** `feat: build frontend ATS scorecard and rewrite drawer`

---

## Phase 6: Job Matching & Skill Gap Analysis (Days 16–19)

### Day 16: Job Description API & NLP Parser
*   **Objectives:** Create job description endpoints and extract required skills using NLP.
*   **Tasks:**
    *   Build APIs to create, read, and delete job descriptions.
    *   Write backend NLP utilities to extract skills from job text.
    *   Create a copy-paste interface on the frontend for job descriptions.
*   **Deliverables:** `backend/app/api/jobs.py`, `frontend/src/components/features/JobDialog.tsx`.
*   **Testing:** Paste job descriptions and verify skills extraction.
*   **Expected Outcome:** Job descriptions are saved and parsed for required skills.
*   **Suggested Git Commit:** `feat: add job description APIs and parser utilities`

---

### Day 17: Semantic Matching (Sentence Transformers)
*   **Objectives:** Vectorize resumes and job descriptions, calculating cosine similarity.
*   **Tasks:**
    *   Load the `all-MiniLM-L6-v2` transformer model on the backend.
    *   Vectorize parsed resume details and job descriptions into embeddings.
    *   Calculate cosine similarity matches between the vectors.
*   **Deliverables:** `backend/app/services/matcher.py` (embedding generator and comparator).
*   **Testing:** Compare resumes against job descriptions to verify similarity score ranges.
*   **Expected Outcome:** Similarity ratings calculated using local embedding models.
*   **Suggested Git Commit:** `feat: implement semantic matching using sentence transformers`

---

### Day 18: Skill Gap Analysis Engine
*   **Objectives:** Build comparison helpers to identify missing skills and generate action plans.
*   **Tasks:**
    *   Write comparison services to identify present and missing skills.
    *   Write recommendation generators to suggest skills and certifications.
    *   Write generators to compile step-by-step learning action plans.
*   **Deliverables:** `backend/app/services/gap_analyzer.py`, matching report APIs.
*   **Testing:** Compare skills to check lists generation.
*   **Expected Outcome:** Skill gap reports successfully compile missing requirements and action items.
*   **Suggested Git Commit:** `feat: build backend skill gap analysis engine`

---

### Day 19: Frontend Matching Details & Skill Radar Chart
*   **Objectives:** Build matching dashboards, comparative tables, and skill radar charts.
*   **Tasks:**
    *   Build a dashboard matching summary layout.
    *   Integrate Plotly to render a skill comparison radar chart.
    *   Build a side-by-side table comparing present and missing skills.
*   **Deliverables:** `frontend/src/app/matching/[id]/page.tsx` (matching results screen).
*   **Testing:** Render radar charts, review comparison tables, and verify responsive behaviors.
*   **Expected Outcome:** Match reports with interactive charts and comparative data layouts.
*   **Suggested Git Commit:** `feat: build matching dashboard with Plotly radar charts`

---

## Phase 7: Interview, Career Roadmap & AI Assistant (Days 20–23)

### Day 20: Backend Mock Interview State & Grading
*   **Objectives:** Write mock interview session handlers, state managers, and grading engines.
*   **Tasks:**
    *   Create endpoints to initialize interview sessions and track question states.
    *   Write engines to generate 5 sequential mock interview questions.
    *   Write graders to evaluate responses and return scores and feedback.
*   **Deliverables:** `backend/app/api/interviews.py`, `backend/app/services/interview.py`.
*   **Testing:** Initialize sessions, submit answers, and verify scores.
*   **Expected Outcome:** Multi-step interview logic running, grading responses, and saving transcripts.
*   **Suggested Git Commit:** `feat: create mock interview session APIs and grading services`

---

### Day 21: Career Roadmap Generation Engine
*   **Objectives:** Write career roadmap generators to map transition milestones.
*   **Tasks:**
    *   Design LLM prompts targeting transition paths between roles.
    *   Use the local LLM to generate milestone steps and timelines.
    *   Parse the LLM output into structured JSON containing study resources.
*   **Deliverables:** `backend/app/api/roadmaps.py`, `backend/app/services/roadmap.py`.
*   **Testing:** Generate roadmaps and verify structured output parsing.
*   **Expected Outcome:** Custom roadmaps compiled into structured JSON.
*   **Suggested Git Commit:** `feat: implement career roadmap generator service`

---

### Day 22: Persistent AI Assistant API (SSE Streaming)
*   **Objectives:** Build the persistent assistant chat endpoint with Server-Sent Events (SSE).
*   **Tasks:**
    *   Build endpoints to initialize chat threads and manage conversation history.
    *   Assemble prompts that inject parsed resume context into chat windows.
    *   Implement SSE response loops to stream token chunks to the client.
*   **Deliverables:** `backend/app/api/assistant.py`, `backend/app/services/assistant.py`.
*   **Testing:** Send messages to check history retention and token streaming.
*   **Expected Outcome:** Context-aware chat assistants streaming responses with low latency.
*   **Suggested Git Commit:** `feat: build persistent AI chat assistant with SSE streaming`

---

### Day 23: Frontend Interview Console, Roadmap & Chat Drawer
*   **Objectives:** Build the mock interview dashboard, roadmap timelines, and assistant drawers.
*   **Tasks:**
    *   Build a distraction-free mock interview console.
    *   Build an interactive roadmap timeline showing milestone steps.
    *   Build a persistent, slide-out assistant chat drawer.
*   **Deliverables:** `frontend/src/components/shared/AssistantDrawer.tsx`, interview and roadmap pages.
*   **Testing:** Test mock interviews, check timelines, and verify chat performance.
*   **Expected Outcome:** Interactive UI components for mock interviews, roadmaps, and chat.
*   **Suggested Git Commit:** `feat: build interview console, roadmap timeline, and assistant drawer`

---

## Phase 8: Dashboard, Analytics & UI Polish (Days 24–25)

### Day 24: Pre-aggregated Analytics & Plotly Charts
*   **Objectives:** Build the pre-aggregated analytics cache and integrate dashboard charts.
*   **Tasks:**
    *   Build backend services to compute and cache aggregate analytics.
    *   Configure cron tasks to automatically refresh the cache.
    *   Build dashboard views containing Plotly line and metric widgets.
*   **Deliverables:** `backend/app/services/analytics.py`, `frontend/src/app/dashboard/page.tsx`.
*   **Testing:** Verify database query performance and check chart displays.
*   **Expected Outcome:** A dashboard view loading metrics and trends with minimal query load.
*   **Suggested Git Commit:** `feat: implement analytics caching and main dashboard view`

---

### Day 25: Global UI Styling Adjustments & Polish
*   **Objectives:** Polish UI aesthetics, glassmorphic styles, transitions, and alerts.
*   **Tasks:**
    *   Verify consistency of glassmorphic styles and dark mode themes.
    *   Refine Framer Motion transition curves and hover effects.
    *   Integrate alert notifications (toasts) for user action feedback.
*   **Deliverables:** Refined CSS global stylesheets, unified animation configurations.
*   **Testing:** Run design checks on various viewports to check responsive scaling.
*   **Expected Outcome:** A polished user interface featuring smooth transitions and consistent styling.
*   **Suggested Git Commit:** `style: polish design variables, animations, and toast alerts`

---

## Phase 9: Testing & Deployment (Days 26–28)

### Day 26: Unit & End-to-End Test Suite Execution
*   **Objectives:** Write unit tests for APIs and run end-to-end tests for core workflows.
*   **Tasks:**
    *   Write backend unit tests for APIs using `pytest`.
    *   Write end-to-end tests using Playwright/Cypress mapping core paths (upload, parse, match).
    *   Fix any identified bugs or edge cases.
*   **Deliverables:** `backend/tests/`, `frontend/tests/`, test execution logs.
*   **Testing:** Run backend and frontend test suites and verify execution status.
*   **Expected Outcome:** All test suites pass successfully.
*   **Suggested Git Commit:** `test: implement unit and E2E test suites`

---

### Day 27: Production Deployment (Vercel & Render)
*   **Objectives:** Build production packages and deploy application modules to Vercel and Render.
*   **Tasks:**
    *   Configure environment files and build targets for production.
    *   Deploy the Next.js frontend to Vercel.
    *   Deploy the FastAPI backend to Render and set up a Render PostgreSQL instance.
*   **Deliverables:** Active live server hosting URLs, configuration setup logs.
*   **Testing:** Run end-to-end verification checks against the live production builds.
*   **Expected Outcome:** The application successfully deployed and running live on production hosts.
*   **Suggested Git Commit:** `deploy: configure production settings and deploy live instances`

---

### Day 28: GitHub Polish & Final Documentation Reviews
*   **Objectives:** Clean up git branches, finalize documentation, and capture showcase assets.
*   **Tasks:**
    *   Clean up temporary branches, review documentation files, and write contribution guides.
    *   Capture screenshots of the dashboard, parser visualizer, and roadmap panels.
    *   Finalize portfolio presentation files.
*   **Deliverables:** Completed repository files, updated markdown documents, repository screenshots.
*   **Testing:** Verify links in markdown files and check visual asset folders.
*   **Expected Outcome:** A clean production-ready repository ready for showcase.
*   **Suggested Git Commit:** `docs: finalize contribution guidelines and document assets`
