"""
Test router — two endpoints:
  POST /test/generate  → run Router→Research→Planner→Examiner, return questions
  POST /test/submit    → run Evaluator→Mastery→Mentor, return scores + advice
  GET  /test/stream/{session_id} → SSE stream of agent events
"""
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.db_models import Student, TestSession, Response as ResponseModel, Subject
from ..schemas.pydantic_schemas import TestRequest, QuestionOut, EvalResult, MentorAdvice
from ..services.auth import get_current_student
from ..services.ocr import extract_text_from_image, get_ocr_debug_info
from ..orchestration.graph import PLAN_GRAPH, EVAL_GRAPH, PipelineState

router = APIRouter(prefix="/test", tags=["test"])

# Simple in-process SSE event store (replace with Redis pub/sub for production)
_sse_store: dict[int, list[str]] = {}


@router.post("/generate")
async def generate_test(
    payload: TestRequest,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    """Router → Research → Planner → Examiner pipeline."""
    init_state: PipelineState = {
        "student_id": student.id,
        "subject_id": None,
        "raw_prompt": payload.raw_prompt or f"test me on {payload.subject}",
        "subject_name": payload.subject,
        "request": payload.model_dump(),
        "research_topics": [],
        "plan": None,
        "questions": [],
        "answers": {},
        "eval_results": [],
        "mentor_advice": None,
        "session_id": None,
        "events": [],
        "error": None,
        "db": db,
    }

    try:
        result = await asyncio.to_thread(PLAN_GRAPH.invoke, init_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline crashed: {exc}")

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    if not result.get("questions"):
        raise HTTPException(
            status_code=500,
            detail=f"No questions generated for subject '{payload.subject}'. "
                   "Check that the subject exists in the database and has topics seeded."
        )

    session_id = result["session_id"]
    _sse_store[session_id] = result["events"]

    return {
        "session_id": session_id,
        "plan": result["plan"],
        "questions": result["questions"],
        "events": result["events"],
    }


@router.post("/submit/{session_id}")
async def submit_answers(
    session_id: int,
    answers: dict[str, str],
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    """Evaluator → Mastery → Mentor pipeline (runs in thread pool to avoid blocking)."""
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session or session.student_id != student.id:
        raise HTTPException(status_code=404, detail="Session not found")

    subject = db.query(Subject).filter(Subject.id == session.subject_id).first()

    int_answers = {int(k): v for k, v in answers.items()}

    init_state: PipelineState = {
        "student_id": student.id,
        "subject_id": session.subject_id,
        "raw_prompt": None,
        "subject_name": subject.name if subject else "",
        "request": None,
        "research_topics": [],
        "plan": None,
        "questions": [{"id": qid} for qid in int_answers],
        "answers": int_answers,
        "eval_results": [],
        "mentor_advice": None,
        "session_id": session_id,
        "events": [],
        "error": None,
        "db": db,
    }

    # Run the blocking LangGraph pipeline in a thread so the event loop stays free
    try:
        result = await asyncio.to_thread(EVAL_GRAPH.invoke, init_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation pipeline crashed: {exc}")

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    # Persist responses
    for r in result["eval_results"]:
        db.add(ResponseModel(
            session_id=session_id,
            question_id=r["question_id"],
            student_answer=int_answers.get(r["question_id"], ""),
            score=r["score"],
            max_score=r["max_score"],
            feedback=r["feedback"],
            awarded_points=json.dumps([p for p in r["awarded_points"]]),
            missing_points=json.dumps(r["missing_points"]),
            citation=r["citation"],
        ))

    total_score = sum(r["score"] for r in result["eval_results"])
    total_marks = sum(r["max_score"] for r in result["eval_results"])
    session.total_score = total_score
    session.total_marks = total_marks
    db.commit()

    return {
        "session_id": session_id,
        "total_score": total_score,
        "total_marks": total_marks,
        "percentage": round(total_score / total_marks * 100, 1) if total_marks else 0,
        "eval_results": result["eval_results"],
        "mentor_advice": result["mentor_advice"],
        "events": result["events"],
    }


@router.post("/upload-answer/{question_id}")
async def upload_answer(
    question_id: int,
    file: UploadFile = File(...),
    student: Student = Depends(get_current_student),
):
    """OCR handwritten answer image → returns extracted text."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    image_bytes = await file.read()
    text = extract_text_from_image(image_bytes)
    return {"question_id": question_id, "extracted_text": text}


@router.post("/debug/ocr")
async def debug_ocr(file: UploadFile = File(...)):
    """Diagnostic — shows per-model OCR results with real error messages."""
    image_bytes = await file.read()
    result = get_ocr_debug_info(image_bytes)
    return result


@router.get("/stream/{session_id}")
def stream_events(session_id: int):
    """SSE endpoint — streams agent step events to frontend."""
    events = _sse_store.get(session_id, [])

    async def generator():
        for event in events:
            yield f"data: {json.dumps({'step': event})}\n\n"
        yield "data: {\"step\": \"done\"}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
