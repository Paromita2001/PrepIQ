# PrepIQ — Adaptive CBSE Class 10 Exam Preparation Platform

PrepIQ is a multi-agent AI platform that prepares Class 10 students for CBSE board exams. It generates personalised tests grounded in real NCERT textbooks and CBSE Previous Year Questions (PYQs), evaluates answers using official CBSE Marking Schemes, tracks mastery per topic, and recommends what to study next.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [1. Get Groq API Keys](#1-get-groq-api-keys)
  - [2. Get a PostgreSQL Database](#2-get-a-postgresql-database)
  - [3. Configure Environment](#3-configure-environment)
  - [4. Backend Setup](#4-backend-setup)
  - [5. Seed the Syllabus](#5-seed-the-syllabus)
  - [6. Ingest NCERT Books & PYQs](#6-ingest-ncert-books--pyqs)
  - [7. Run the Backend](#7-run-the-backend)
  - [8. Frontend Setup](#8-frontend-setup)
- [How the Agents Work](#how-the-agents-work)
- [RAG Pipeline](#rag-pipeline)
- [API Reference](#api-reference)
- [Subjects Supported](#subjects-supported)
- [Diagnostic Health Check](#diagnostic-health-check)
- [Common Errors](#common-errors)
- [Contributing](#contributing)

---

## Features

- **Adaptive testing** — adjusts question difficulty in real time based on student mastery
- **Two modes** — Practice (short adaptive, ~20 min) and Mock Exam (full CBSE board pattern, 80 marks, 3 hrs)
- **Prompt-driven topic selection** — type "test me on probability and algebra" and the system semantically maps your request to actual syllabus topics
- **RAG-grounded questions** — every question is generated or validated against real NCERT chapter content and CBSE PYQs (2021–2025)
- **CBSE Marking Scheme evaluation** — answers are graded using the official marking scheme PDFs, with step-by-step partial credit
- **Mastery heatmap** — visual dashboard showing topic-level mastery across all subjects
- **OCR handwritten answers** — upload a photo of handwritten answers; Tesseract extracts the text
- **Multi-key Groq rotation** — round-robins across up to 4 API keys so rate limits never block the pipeline
- **Mentor recommendations** — after each test, the AI identifies weak topics and suggests targeted revision strategies
- **4,869 NCERT + PYQ chunks** — fully embedded and stored in pgvector for sub-second semantic retrieval

---

## Architecture

PrepIQ uses a **LangGraph state machine** with two separate pipelines:

### Plan Pipeline (on test generation)

```
Student prompt
      │
      ▼
┌─────────────┐     Semantically maps prompt to actual     ┌─────────────┐
│   Router    │ ──► DB topic/chapter names using LLM ────► │  Research   │
│   Agent     │                                             │   Agent     │
└─────────────┘                                             └──────┬──────┘
                                                                   │ PYQ frequency
                                                                   │ ranking (SQL)
                                                            ┌──────▼──────┐
                                                            │   Planner   │
                                                            │   Agent     │
                                                            └──────┬──────┘
                                                                   │ Topic weights
                                                                   │ + difficulty
                                                            ┌──────▼──────┐
                                                            │  Examiner   │
                                                            │   Agent     │
                                                            └──────┬──────┘
                                                                   │ Real PYQ questions
                                                                   │ + LLM fallback
                                                                   ▼
                                                            Questions served
```

### Eval Pipeline (on answer submission)

```
Student answers
      │
      ▼
┌──────────────┐   Retrieves CBSE Marking   ┌──────────────┐
│  Evaluator   │ ──► Scheme chunks via RAG ─►│  Concurrent  │
│   Agent      │                             │  LLM Grading │
└──────────────┘                             └──────┬───────┘
                                                    │ EvalResult per question
                                             ┌──────▼──────┐
                                             │   Mastery   │
                                             │  Updater    │
                                             └──────┬──────┘
                                                    │ Updates StudentMastery table
                                             ┌──────▼──────┐
                                             │    Mentor   │
                                             │    Agent    │
                                             └──────┬──────┘
                                                    │ Revision plan
                                                    ▼
                                             Results + advice
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend framework** | FastAPI + Uvicorn |
| **Agent orchestration** | LangGraph |
| **LLM** | Groq (`llama-3.1-8b-instant` for routing/validation, `llama-3.3-70b-versatile` for evaluation) |
| **Vector database** | PostgreSQL + pgvector |
| **ORM** | SQLAlchemy 2.0 |
| **Embeddings** | `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) |
| **PDF extraction** | pdfplumber |
| **OCR** | Tesseract via pytesseract |
| **Auth** | JWT (python-jose + passlib bcrypt) |
| **Frontend** | React 19 + Vite + Tailwind CSS |
| **HTTP client** | Axios |
| **Free DB host** | Neon (serverless Postgres with pgvector) |

---

## Project Structure

```
PrepIQ/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── llm.py              # RotatingGroq — 4-key round-robin rotator
│   │   │   ├── router_agent.py     # Parses student prompt → structured TestRequest
│   │   │   ├── research_agent.py   # PYQ frequency ranking (SQL) + keyword filtering
│   │   │   ├── planner_agent.py    # Builds TestPlan with topic weights + difficulty
│   │   │   ├── examiner_agent.py   # Retrieves/generates questions (RAG-grounded)
│   │   │   ├── evaluator_agent.py  # CBSE Marking Scheme RAG + concurrent grading
│   │   │   ├── mastery_updater.py  # Two-way mastery adjustment per topic
│   │   │   └── mentor_agent.py     # Revision plan based on weak topics
│   │   ├── models/
│   │   │   └── db_models.py        # SQLAlchemy models (Subject→Chapter→Topic→Question)
│   │   ├── orchestration/
│   │   │   └── graph.py            # LangGraph state machine (plan + eval graphs)
│   │   ├── routers/
│   │   │   ├── auth.py             # POST /auth/register, /auth/login, GET /auth/me
│   │   │   ├── test.py             # POST /test/generate, /test/submit, GET /test/stream
│   │   │   └── student.py          # GET /student/mastery, /student/sessions, /student/subjects
│   │   ├── schemas/
│   │   │   └── pydantic_schemas.py # TestRequest, TestPlan, QuestionOut, EvalResult, ...
│   │   ├── services/
│   │   │   ├── retrieval.py        # Hybrid pgvector + metadata retrieval
│   │   │   ├── embeddings.py       # sentence-transformers wrapper (cached)
│   │   │   ├── auth.py             # JWT token creation + verification
│   │   │   └── ocr.py              # Tesseract OCR for handwritten answers
│   │   ├── config.py               # Pydantic settings (reads .env)
│   │   ├── database.py             # SQLAlchemy engine + session factory
│   │   └── main.py                 # FastAPI app + CORS + /health endpoints
│   ├── scripts/
│   │   ├── seed_syllabus.py        # Seeds Subject / Chapter / Topic tables
│   │   ├── ingest_pdfs.py          # PDF → chunks → embeddings → pgvector
│   │   └── eval_harness.py         # 20-answer evaluation benchmark
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Register.jsx
│       │   ├── Dashboard.jsx       # Mastery heatmap + recent sessions
│       │   ├── TestRequest.jsx     # Subject picker + prompt + mode selector
│       │   ├── TestAttempt.jsx     # Timed test interface with MCQ + text answers
│       │   └── Results.jsx         # Score breakdown + mentor advice
│       ├── components/
│       │   ├── MasteryHeatmap.jsx  # Colour-coded topic mastery grid
│       │   └── AgentTrace.jsx      # Live agent step trace during generation
│       ├── context/
│       │   └── AuthContext.jsx     # JWT storage + auto-redirect
│       └── api/
│           └── client.js           # Axios instance with auth interceptor
│
├── data/
│   ├── books/                      # NCERT PDFs (Mathematics, Science, English, Hindi, SS)
│   └── pyq/                        # CBSE SQPs + Marking Schemes 2021–2025
│
├── .gitattributes                  # Enforces LF line endings
└── README.md
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **1–4 free Groq API keys** → [console.groq.com](https://console.groq.com)
- **PostgreSQL with pgvector** → [neon.tech](https://neon.tech) (free, pgvector pre-installed)
- **Tesseract OCR** (optional, for handwritten answer upload)
  - Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)
  - macOS: `brew install tesseract`
  - Ubuntu: `sudo apt install tesseract-ocr`

---

## Setup

### 1. Get Groq API Keys

1. Go to [console.groq.com](https://console.groq.com) and sign in
2. Left sidebar → **API Keys** → **Create API Key**
3. Copy the key (starts with `gsk_...`)
4. Optionally repeat with up to 3 more accounts for keys 2–4

> The `RotatingGroq` class in `llm.py` automatically switches to the next key on a 429 rate-limit. Key 1 is required; keys 2–4 are optional.

---

### 2. Get a PostgreSQL Database

**Recommended (free): Neon**

1. Sign up at [neon.tech](https://neon.tech) — no credit card required
2. Create a project → name it `prepiq` → pick any region
3. Click **Connect** on the dashboard → copy the **Connection string**
4. It looks like: `postgresql://neondb_owner:AbC123@ep-cool-name.us-east-2.aws.neon.tech/neondb?sslmode=require`
5. pgvector is **already enabled** on Neon — nothing extra needed

**Alternative: Supabase**

1. New project at [supabase.com](https://supabase.com) → **Project Settings → Database → URI**
2. After creating, run in the SQL Editor: `CREATE EXTENSION IF NOT EXISTS vector;`

**Alternative: Local Docker**

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres ankane/pgvector
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
```

---

### 3. Configure Environment

```bash
cd backend
cp .env.example .env     # Windows: copy .env.example .env
```

Edit `backend/.env`:

```env
# Required
GROQ_API_KEY_1=gsk_...
DATABASE_URL=postgresql://...

# Optional — extra Groq keys for rate-limit rotation
GROQ_API_KEY_2=gsk_...
GROQ_API_KEY_3=gsk_...
GROQ_API_KEY_4=gsk_...

# Auth secret — generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-random-32-char-string

# Models (defaults are fine)
GROQ_MODEL=llama-3.1-8b-instant
GROQ_MODEL_LARGE=llama-3.3-70b-versatile
```

---

### 4. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\activate        # Windows PowerShell
source venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

> `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~90 MB) on first use. This is a one-time download.

---

### 5. Seed the Syllabus

This creates all database tables and populates the Subject → Chapter → Topic hierarchy for all 6 subjects.

```bash
# From backend/ with venv active
python -m scripts.seed_syllabus
```

Expected output:
```
Seeded: Mathematics  (15 chapters, 78 topics)
Seeded: Science      (16 chapters, 72 topics)
Seeded: English      ( 2 chapters, 24 topics)
Seeded: Hindi        ( 4 chapters, 46 topics)
Seeded: Social Science (20 chapters, 88 topics)
Seeded: Sanskrit     ( 5 chapters, 20 topics)
```

---

### 6. Ingest NCERT Books & PYQs

This reads the PDFs in `data/`, chunks them, embeds each chunk with `all-MiniLM-L6-v2`, maps each chunk to its nearest syllabus topic, and stores everything in the `ncert_chunk` table.

```bash
# Ingest all NCERT books
python -m scripts.ingest_pdfs --books-only

# Ingest CBSE PYQs and Marking Schemes as searchable chunks
python -m scripts.ingest_pdfs --pyq-only --pyq-as-chunks

# Or ingest everything at once
python -m scripts.ingest_pdfs
```

**Options:**

| Flag | Description |
|---|---|
| `--books-only` | Only process NCERT PDF books |
| `--pyq-only` | Only process PYQ / Marking Scheme PDFs |
| `--pyq-as-chunks` | Store PYQ text as NcertChunks (no LLM extraction) |
| `--subject MATH` | Process a single subject only |
| `--dry-run` | Print what would be ingested without writing to DB |

Expected result: **~4,869 chunks** (2,271 NCERT + 1,655 PYQ + 943 Marking Schemes)

---

### 7. Run the Backend

```bash
# From backend/ with venv active
python -m uvicorn app.main:app --port 8000 --reload
```

Verify it's running:
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- Full diagnostic: [http://localhost:8000/health/full](http://localhost:8000/health/full) ← tests DB + embeddings + Groq

---

### 8. Frontend Setup

```bash
cd frontend

# (Optional) configure API URL — defaults to http://localhost:8000
cp .env.example .env

npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) — register an account and start practising.

---

## How the Agents Work

### Router Agent
Parses the student's free-text prompt and the selected subject into a structured `TestRequest`. When a prompt is provided alongside the dropdown subject, it semantically maps keywords to **actual DB topic names** (e.g. "probability statistics" → "Probability — A Theoretical Approach") so downstream agents match correctly.

### Research Agent
Ranks topics by how often they appear in CBSE PYQs using a SQL COUNT query — no LLM needed for this step. Topics the board has tested frequently get higher priority. Filters to only the topics matching the student's request.

### Planner Agent
Reads the student's mastery profile and the research rankings, then outputs a `TestPlan` — a list of `TopicWeight` objects specifying which topics, how many questions per topic, target difficulty, question type, and marks. In **Mock mode** it follows the official CBSE board pattern: Section A (20 × 1 mark MCQ) + B (6 × 2) + C (7 × 3) + D (3 × 5) + E (3 × 4) = 80 marks.

### Examiner Agent
For each topic weight:
1. Retrieves real PYQ questions from the DB that match the target type and difficulty
2. Runs each candidate through a **Validator** (small LLM) that rejects off-syllabus or ambiguous questions
3. Falls back to **LLM generation** (grounded with NCERT + PYQ RAG context) when the DB has insufficient candidates
4. Saves LLM-generated questions to the DB for future variety

### Evaluator Agent
1. Retrieves relevant CBSE Marking Scheme chunks for each question (sequential, DB-safe)
2. Grades all questions **concurrently** using `ThreadPoolExecutor(max_workers=8)`
3. MCQs are exact-match (no LLM) — instant
4. Short answers get a single LLM judge
5. Long answers (5 marks) get **two independent LLM judges** whose scores are averaged

### Mastery Updater
Pure Python — no LLM. For each graded question, updates the `StudentMastery` row for that (student, subject, chapter, topic) combination. Correct → mastery increases; wrong → mastery decreases. Unanswered questions are skipped (no penalty for blanks). Adjustments scale with question difficulty.

### Mentor Agent
Reads the updated mastery profile, identifies the weakest topics, and generates a prioritised revision plan with specific study suggestions (which NCERT sections to re-read, what types of questions to practise).

---

## RAG Pipeline

PrepIQ uses a **hybrid retrieval** approach:

1. **Chunking** — PDFs are extracted with pdfplumber, split into 600-character sliding windows (100-char overlap), stripped of whitespace and short fragments
2. **Topic mapping** — each chunk is embedded with `all-MiniLM-L6-v2` (384-dim), then cosine distance finds the nearest syllabus topic embedding
3. **Storage** — chunks + embeddings stored in the `ncert_chunk` table (pgvector `vector(384)` column)
4. **Retrieval** — at question generation time, `get_ncert_context()` embeds the query and retrieves the top-N chunks for that topic using pgvector's `<=>` cosine distance operator, filtered by `topic_id`
5. **Grounding** — retrieved chunks are injected into the LLM system prompt before generating questions or evaluating answers

CBSE Marking Scheme chunks are prefixed with `[CBSE Marking Scheme YYYY]` so the evaluator can specifically retrieve official grading criteria.

---

## API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new student account |
| `POST` | `/auth/login` | Login → returns JWT |
| `GET` | `/auth/me` | Get current student profile |

### Test

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/test/generate` | Run Router→Research→Planner→Examiner pipeline |
| `POST` | `/test/submit/{session_id}` | Run Evaluator→Mastery→Mentor pipeline |
| `GET` | `/test/stream/{session_id}` | SSE stream of agent step events |
| `POST` | `/test/upload-answer/{question_id}` | OCR a handwritten answer image |

### Student

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/student/subjects` | List subjects with mastery summary |
| `GET` | `/student/mastery/{subject_name}` | Topic-level mastery heatmap data |
| `GET` | `/student/sessions` | Past test sessions |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Basic liveness check |
| `GET` | `/health/full` | Tests DB, embedding model, and Groq API (no auth) |

---

## Subjects Supported

| Subject | NCERT Books | PYQ Years |
|---|---|---|
| Mathematics | Part 1 + Part 2 | 2021–2025 (Basic + Standard) |
| Science | Combined | 2021–2025 |
| English | First Flight + Footprints Without Feet | 2021–2025 |
| Hindi | Kshitij, Sparsh, Sanchayan, Kritika | 2021–2025 (Course A + B) |
| Social Science | History (7 ch) + Geography (5 ch) + Civics (5 ch) + Economics (5 ch) | 2021–2025 |
| Sanskrit | — | 2021–2025 |

---

## Diagnostic Health Check

If test generation fails, visit [http://localhost:8000/health/full](http://localhost:8000/health/full) (no login needed). It tests all three backend dependencies and returns a JSON report:

```json
{
  "overall": "ok",
  "checks": {
    "db": {
      "ok": true,
      "subjects": ["Mathematics", "Science", "English", ...],
      "question_count": 374,
      "ncert_chunk_count": 4869
    },
    "embedding": { "ok": true, "dim": 384 },
    "groq": { "ok": true, "response": "OK" }
  }
}
```

---

## Common Errors

| Error | Fix |
|---|---|
| `No Groq API keys provided` | Set `GROQ_API_KEY_1` in `backend/.env` |
| `All keys rate-limited` | All 4 free-tier keys hit limits simultaneously — wait ~1 min |
| `pgvector not found` | On Supabase: run `CREATE EXTENSION IF NOT EXISTS vector;` in SQL Editor |
| `relation does not exist` | Run `seed_syllabus.py` before ingesting |
| Slow first request | `all-MiniLM-L6-v2` (~90 MB) downloads once — wait for it |
| `Cannot reach backend server` | Start backend: `cd backend && python -m uvicorn app.main:app --port 8000` |
| CORS error in browser | Backend must be on port 8000; frontend on 5173 |
| `pydantic_settings` can't find `.env` | Run `uvicorn` from inside the `backend/` directory |
| LF/CRLF git warnings | Already fixed via `.gitattributes` |

---

## Contributing

1. Fork the repo and create a feature branch
2. Run `python -m scripts.seed_syllabus` + `python -m scripts.ingest_pdfs` to set up a local DB
3. Start the backend (`uvicorn app.main:app --reload --port 8000`) and frontend (`npm run dev`)
4. Make your changes
5. Verify with `GET /health/full` and a manual test generation
6. Open a pull request with a clear description

---

> Built with LangGraph, FastAPI, pgvector, and Groq.  
> NCERT content © NCERT, India. CBSE PYQs © CBSE. Used for educational purposes only.
