# PrepIQ — Start Here

## Prerequisites
- Python 3.11+
- Node.js 18+
- 1–4 free Groq API keys  →  https://console.groq.com
- A free PostgreSQL DB   →  https://neon.tech  (recommended)

---

## Step 1 — Get your Groq API keys

1. Go to **https://console.groq.com**
2. Sign in (Google / GitHub / email)
3. Left sidebar → **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`)
5. Repeat with up to 3 more email accounts for keys 2–4

> The rotator in `llm.py` automatically switches to the next key when one hits a rate limit.
> Key 1 is required. Keys 2–4 are optional — just leave them blank in `.env` if you have fewer.

---

## Step 2 — Get a free PostgreSQL database (Neon — recommended)

1. Go to **https://neon.tech**
2. Click **Sign Up** (free, no credit card)
3. Create a project → name it `studyos` → pick any region
4. On the dashboard click **Connect** → copy the **Connection string**
5. It looks like:
   ```
   postgresql://neondb_owner:AbC123xYz@ep-cool-name-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
6. pgvector is **already enabled** on Neon — nothing extra needed.

> Alternative: **https://supabase.com** → New project → Project Settings → Database → URI
> (After creating, run `CREATE EXTENSION IF NOT EXISTS vector;` in the Supabase SQL Editor)

---

## Step 3 — Create your .env file

```bash
cd backend
copy .env.example .env
```

Open `backend/.env` and fill in:

```env
GROQ_API_KEY_1=gsk_...      ← paste key 1 here
GROQ_API_KEY_2=gsk_...      ← paste key 2 here (or leave blank)
GROQ_API_KEY_3=gsk_...      ← paste key 3 here (or leave blank)
GROQ_API_KEY_4=gsk_...      ← paste key 4 here (or leave blank)

DATABASE_URL=postgresql://neondb_owner:...@....neon.tech/neondb?sslmode=require

SECRET_KEY=any-random-string-at-least-32-chars
```

Generate a random SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Step 4 — Backend setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate          # Windows PowerShell
# source venv/bin/activate     # Mac / Linux

# Install all dependencies
pip install -r requirements.txt
```

---

## Step 5 — Seed the database

```bash
# Make sure venv is active and you're in the backend/ folder

# Creates all tables + seeds Physics syllabus tree
python -m scripts.seed_syllabus

# Embeds and ingests the question bank (downloads ~90MB model on first run — wait for it)
python -m scripts.ingest
```

---

## Step 6 — Run the backend

```bash
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** — you should see the Swagger UI with all endpoints.

---

## Step 7 — Frontend setup

```bash
cd frontend

copy .env.example .env     # VITE_API_URL=http://localhost:8000

npm install
npm run dev
```

Open **http://localhost:5173** — the app should load.

---

## Step 8 — Run the eval harness (get your resume number)

```bash
# From backend/ with venv active
python -m scripts.eval_harness
```

Look for this line in the output:
```
Within ±1.0 marks : 17/20  = 85.0%  ← HEADLINE
```

That percentage is what you put on your resume.

---

## How the key rotation works

```
Request comes in
      │
      ▼
 RotatingGroq.invoke()
      │
      ├─ try KEY 1 → success → return response
      │
      ├─ try KEY 1 → 429 rate limit → try KEY 2
      │
      ├─ try KEY 2 → 429 rate limit → try KEY 3
      │
      └─ try KEY 3 → success → return response
```

- Round-robin across all available keys for even distribution
- Thread-safe (parallel agent calls don't collide on the index)
- No extra dependencies — uses `langchain-groq` already in `requirements.txt`

---

## Common errors

| Error | Fix |
|---|---|
| `No Groq API keys provided` | Check `GROQ_API_KEY_1` is set in `backend/.env` |
| `All keys rate-limited` | You've hit all 4 free tier limits — wait 1 min and retry |
| `pgvector not found` | On Supabase run `CREATE EXTENSION IF NOT EXISTS vector;` in SQL Editor |
| `relation does not exist` | Run `seed_syllabus.py` before `ingest.py` |
| `sentence_transformers slow first run` | Downloads `all-MiniLM-L6-v2` (~90MB) once — wait for it |
| CORS error in browser | Confirm backend is on port 8000, frontend on 5173 |
| `pydantic_settings` can't find `.env` | Run `uvicorn` from inside the `backend/` folder |

---

## Project structure

```
PrepIQ/
├── backend/
│   ├── app/
│   │   ├── agents/          ← Router, Planner, Research, Examiner, Evaluator, Mastery, Mentor
│   │   │   └── llm.py       ← RotatingGroq — 4-key round-robin rotator
│   │   ├── models/          ← SQLAlchemy DB models (FK chain enforces subject→chapter→topic)
│   │   ├── orchestration/   ← LangGraph state machine (plan-graph + eval-graph)
│   │   ├── routers/         ← FastAPI endpoints (auth, test, student)
│   │   ├── schemas/         ← Pydantic schemas (all structured outputs)
│   │   └── services/        ← retrieval (hybrid pgvector+BM25), embeddings, auth, OCR
│   ├── scripts/
│   │   ├── seed_syllabus.py ← run first
│   │   ├── ingest.py        ← run second
│   │   └── eval_harness.py  ← run to get your resume number
│   └── requirements.txt
├── frontend/src/
│   ├── pages/               ← Login, Register, Dashboard, TestRequest, TestAttempt, Results
│   ├── components/          ← MasteryHeatmap, AgentTrace
│   ├── context/             ← AuthContext (JWT)
│   └── api/                 ← axios client
└── data/
    ├── physics_questions.json   ← seed questions (add more here)
    └── eval_set.json            ← 20 hand-graded answers for eval harness
```
