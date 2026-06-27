# System Workflow Specification

## CareerPilot AI — The Intelligent Career Copilot

---

## 1. Complete User Journey Overview

The user journey in CareerPilot AI is designed to guide a job seeker step-by-step from initial signup to mock interview readiness and career tracking.

```mermaid
flowchart TD
    Start([1. Land on CareerPilot AI]) --> Auth[2. Create Account & Login]
    Auth --> Upload[3. Upload PDF/DOCX Resume]
    Upload --> Parsing[4. Run NLP Parser & View Extracted Entities]
    Parsing --> ATS[5. Execute ATS Compliance & Score Audit]
    ATS --> Optimize[6. Review & Apply AI Bullet Suggestions]
    Optimize --> Match[7. Paste Target Job Description & Vector Match]
    Match --> Gap[8. Analyze Skill Gaps & Action Plan]
    Gap --> Roadmap[9. Generate Step-by-Step AI Transition Roadmap]
    Roadmap --> Prep[10. Initiate Mock Interview for Target Role]
    Prep --> Analytics[11. Track Progress Trends on Plotly Dashboard]
    Analytics --> Loop[12. Re-optimize & Repeat Process]
```

---

## 2. Core Architectural Workflows

This section maps out the detailed execution sequences, message exchanges, and logic paths for the application's core workflows.

### 2.1 Authentication Workflow
This workflow uses secure HttpOnly session cookies to manage authentication, preventing client-side script token theft (XSS protection).

```mermaid
sequenceDiagram
    autonumber
    actor User as Job Seeker
    participant FE as Next.js Client (React)
    participant BE as FastAPI Server
    participant DB as PostgreSQL
    
    User->>FE: Input Email & Password (Login)
    FE->>BE: POST /api/v1/auth/login (JSON Body)
    Note over BE: Validate inputs using Pydantic
    BE->>DB: Query user record by Email
    DB-->>BE: Return user ID & bcrypt hashed password
    BE->>BE: Verify password using bcrypt check
    alt Credentials Invalid
        BE-->>FE: Return HTTP 401 Unauthorized (Error JSON)
        FE-->>User: Render "Invalid Credentials" Toast Alert
    else Credentials Valid
        BE->>BE: Generate stateless JWT token (Expiry: 24h)
        BE-->>FE: Return HTTP 200 OK + JWT in Set-Cookie Header
        Note over FE: Save HttpOnly cookie "access_token" in browser
        FE->>BE: GET /api/v1/auth/me (access_token cookie attached)
        BE->>BE: Extract JWT, decode claims & verify signature
        BE-->>FE: Return Session verified (User UUID & Email)
        FE-->>User: Transition to Dashboard view
    end
```

**Workflow Explanation:**
*   Password verification is handled securely using bcrypt hashing at the database boundary.
*   Once validated, the backend generates a standard JWT containing the user's ID and sets it as an `HttpOnly`, `Secure`, `SameSite=Strict` cookie.
*   Subsequent requests automatically include this cookie. The backend middleware decodes and verifies the token, ensuring secure, stateless session management.

---

### 2.2 Resume Upload & Parsing Workflow
Processes binary document templates, extracts raw text, and generates structured JSON data using spaCy NLP.

```mermaid
flowchart TD
    A[User uploads PDF/DOCX] --> B(Verify File Type & Size)
    B -->|Exceeds 5MB or invalid type| C[Return 422 Unprocessable Entity]
    B -->|Valid File| D{File Extension}
    D -->|.pdf| E[Extract Text using PyPDF]
    D -->|.docx| F[Extract Text using python-docx]
    E --> G[Raw Plaintext String]
    F --> G
    G --> H[Run spaCy NLP Pipeline]
    H --> I[Execute Named Entity Recognition - NER]
    I --> J[Map Section Heads & Skills Tags]
    J --> K[Construct Normalized parsed_json Schema]
    K --> L[Save Resume Model to PostgreSQL]
    L --> M[Return 201 Created with Structured JSON]
```

**Workflow Explanation:**
*   The upload handler validates that the file matches supported MIME types and size limits.
*   The system uses `PyPDF` or `python-docx` to extract raw text, which it passes to the `parser_service`.
*   The parser runs tokenization, part-of-speech tagging, and custom entity matching using a local spaCy pipeline. The structured output is saved to the database and returned to the frontend.

---

### 2.3 Local AI Integration (Ollama Orchestration)
Runs local LLM calls using `httpx` to connect to the local Ollama API, streaming outputs via Server-Sent Events (SSE).

```mermaid
sequenceDiagram
    autonumber
    participant FE as Next.js Client
    participant BE as FastAPI Backend
    participant OL as Ollama Service (Port 11434)
    
    FE->>BE: POST /api/v1/resumes/{id}/optimize-bullet (JSON context)
    BE->>BE: Query database for parsed resume context
    BE->>BE: Assemble instruction prompt (Inject System Rules & STAR constraints)
    BE->>OL: POST /api/generate (JSON payload, stream: true)
    Note over OL: Initiate Qwen 2.5 3B local model inference
    loop Stream Response Tokens
        OL-->>BE: Stream token chunks via HTTP Socket
        BE-->>FE: Stream Server-Sent Events (SSE) data chunks
        Note over FE: Render text dynamically using cursor effects
    end
    OL-->>BE: Stream [DONE] indicator
    BE-->>FE: Stream close event
    Note over FE: Finalize suggestions panel & enable save action
```

**Workflow Explanation:**
*   To keep client interfaces responsive during long LLM calls, the FastAPI backend routes requests asynchronously.
*   The backend connects to the local Ollama instance (`http://127.0.0.1:11434`) using `httpx` and streams response tokens in real-time.
*   These tokens are forwarded to the client using Server-Sent Events (`text/event-stream`), enabling a smooth, dynamic typing effect on the frontend.

---

### 2.4 Semantic Job Matching Workflow
Calculates match ratings between candidate profiles and job requirements using sentence-transformers vector embeddings.

```mermaid
flowchart TD
    A[Post Job Target Description] --> B[Extract Skills List via spaCy NLP]
    B --> C[Retrieve Selected Parsed Resume]
    C --> D[Load Sentence Transformers: all-MiniLM-L6-v2]
    D --> E[Vectorize Resume Text -> 384-dim Vector A]
    D --> F[Vectorize Job Text -> 384-dim Vector B]
    E --> G[Calculate Cosine Similarity between A and B]
    F --> G
    G --> H[Compare Extracted Skills Lists]
    H --> I[Determine Present vs Missing Skills Gaps]
    I --> J[Compile Action Plan Recommendations]
    J --> K[Save Job Match & Gap Analysis to DB]
    K --> L[Return match metrics & Gap analysis report]
```

**Workflow Explanation:**
*   The matching engine extracts target skills from both the resume and the job description.
*   It vectorizes both texts using the `all-MiniLM-L6-v2` transformer model, producing 384-dimensional dense vectors.
*   The system calculates the cosine similarity between the vectors, compares the skills to identify gaps, compiles a recommended action plan, saves the results, and returns the metrics to the frontend.

---

### 2.5 Interactive Mock Interview Loop Workflow
Guides users through mock interview sessions, managing state, generating questions, and grading responses.

```mermaid
sequenceDiagram
    autonumber
    actor User as Candidate
    participant FE as Next.js Console
    participant BE as FastAPI Controller
    participant OL as Ollama Service
    participant DB as PostgreSQL
    
    User->>FE: Select Role & Start Mock Session
    FE->>BE: POST /api/v1/interviews/sessions
    BE->>OL: Prompt LLM for Interview Question 1
    OL-->>BE: Return Question 1
    BE->>DB: Save Session State (Question 1 added to history)
    BE-->>FE: Return Session ID + Question 1
    FE-->>User: Render Question 1 in Console view
    
    loop Question 1 through 5
        User->>FE: Input Response Text & Click Submit
        FE->>BE: POST /api/v1/interviews/sessions/{id}/answer (User Answer)
        BE->>OL: Prompt LLM to evaluate answer & generate next question
        Note over OL: Evaluate answer context, assign score (0-100), and write critique
        OL-->>BE: Return Answer Score, Feedback, and Question N+1
        BE->>DB: Update Session Transcript with Answer, Score, Feedback & next question
        BE-->>FE: Return Score, Feedback, and Question N+1
        FE-->>User: Render instant feedback & display next question
    end
    
    User->>FE: Complete final question
    FE->>BE: POST /api/v1/interviews/sessions/{id}/complete
    BE->>BE: Calculate average score & compile final feedback summary
    BE->>DB: Save session status as "completed"
    BE-->>FE: Return final scorecard details
    FE-->>User: Render radar chart & final feedback page
```

**Workflow Explanation:**
*   The interview module tracks progress through 5 questions using session history stored in the database.
*   For each response, the local LLM evaluates the user's answer, assigns a score (0-100), provides feedback, and generates the next question.
*   Once completed, the system calculates average scores, logs the completed status, and renders performance metrics on the frontend.

---

### 2.6 AI Career Roadmap Workflow
Generates step-by-step career roadmaps based on current profiles and target roles.

```mermaid
flowchart TD
    A[Request Career Roadmap] --> B[Retrieve Profile Current & Target Roles]
    B --> C[Assemble Transition Prompt]
    C --> D[Query Ollama: Qwen 2.5 3B]
    D --> E[Generate Milestones timeline & steps]
    E --> F[Extract Focus Skills, Action Items & Resources]
    F --> G[Parse LLM output into structured JSON]
    G --> H[Save Career Roadmap to PostgreSQL]
    H --> I[Return structured Roadmap JSON to client]
    I --> J[Render vertical interactive node map on frontend]
```

**Workflow Explanation:**
*   The user requests a career roadmap by specifying a current and target role.
*   The backend queries the local LLM to generate transition milestones, including focus areas, timelines, action items, and learning resources.
*   The output is parsed into structured JSON, saved to the database, and rendered as an interactive node map on the frontend.

---

### 2.7 Dashboard Analytics Workflow
Aggregates performance data, matches, and scores to feed interactive charts on the frontend.

```mermaid
sequenceDiagram
    autonumber
    participant FE as Next.js Dashboard
    participant BE as FastAPI Analytics API
    participant DB as PostgreSQL
    
    FE->>BE: GET /api/v1/analytics/dashboard
    BE->>DB: Query pre-aggregated analytics cache table
    alt Cache is valid & calculated within 1 hour
        DB-->>BE: Return cached analytics record
    else Cache is stale/empty
        BE->>DB: Query historical ATS scores, match histories & interview records
        DB-->>BE: Return raw query records
        BE->>BE: Calculate counts & average scores
        BE->>BE: Format historical trend arrays for Plotly charts
        BE->>DB: Update analytics cache table with new metrics
    end
    BE-->>FE: Return metric aggregates & trend JSON arrays
    FE->>FE: Feed data arrays to Plotly chart wrapper
    FE-->>FE: Render line, radar, and metric cards
```

**Workflow Explanation:**
*   To keep dashboard loads fast, the system uses a pre-aggregated `analytics` table.
*   If the cached data is valid, it is returned immediately. Otherwise, the backend runs queries to calculate new averages and trends, updates the cache, and returns the data.
*   The frontend uses the returned JSON arrays to render interactive Plotly charts.

---

### 2.8 System Error Handling Workflow
Enforces error boundaries across the application, returning standard error payloads for unexpected issues.

```mermaid
flowchart TD
    A[API Endpoint Request] --> B{Valid Request?}
    B -->|No: Malformed JSON or input validation failure| C[Return 400 Bad Request / 422 Unprocessable Entity]
    B -->|Yes| D{Auth Token Cookie Present & Valid?}
    D -->|No| E[Return 401 Unauthorized]
    D -->|Yes| F{Resource Exists & Accessible?}
    F -->|No| G[Return 404 Not Found / 403 Forbidden]
    F -->|Yes| H{Backend processing or DB transaction succeeds?}
    H -->|No: DB connection timeout or Ollama socket error| I[Rollback DB Transaction & Return 500 Internal Error]
    H -->|Yes| J[Commit DB Changes & Return 200/201 Success JSON]
```

**Workflow Explanation:**
*   API requests pass through layers of validation and security.
*   Input validation failures return `400` or `422` errors. Authentication checks return `401` errors, and missing resources return `404` errors.
*   Any database or LLM socket errors are caught, pending database changes are rolled back, and the client receives a standardized `500` error payload.
