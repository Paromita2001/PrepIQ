from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import init_db, SessionLocal
from .routers import auth, test, student, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="PrepIQ",
    description="Adaptive multi-agent CBSE Class 10 exam-prep platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(test.router)
app.include_router(student.router)
app.include_router(upload.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "PrepIQ"}


@app.get("/health/full")
def health_full():
    """Diagnostic endpoint — tests DB, embedding model, and Groq key. No auth required."""
    import traceback
    report = {}

    # 1. DB connection + subject count
    try:
        from .models.db_models import Subject, Question, NcertChunk
        db = SessionLocal()
        subjects = db.query(Subject).all()
        q_count = db.query(Question).count()
        chunk_count = db.query(NcertChunk).count()
        report["db"] = {
            "ok": True,
            "subjects": [s.name for s in subjects],
            "question_count": q_count,
            "ncert_chunk_count": chunk_count,
        }
        db.close()
    except Exception as e:
        report["db"] = {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    # 2. Embedding model
    try:
        from .services.embeddings import embed
        vec = embed("test sentence")
        report["embedding"] = {"ok": True, "dim": len(vec)}
    except Exception as e:
        report["embedding"] = {"ok": False, "error": str(e)}

    # 3. Groq API (tiny call)
    try:
        from .agents.llm import small_llm
        from langchain_core.messages import HumanMessage
        resp = small_llm().invoke([HumanMessage(content="Reply with the single word: OK")])
        report["groq"] = {"ok": True, "response": resp.content[:50]}
    except Exception as e:
        report["groq"] = {"ok": False, "error": str(e)}

    all_ok = all(v.get("ok") for v in report.values())
    return {"overall": "ok" if all_ok else "degraded", "checks": report}
