"""
Upload router — students upload their own PDF books or PYQ papers.

  POST /upload/document            → upload a PDF (background processing)
  GET  /upload/documents           → list student's uploaded docs
  GET  /upload/subjects            → subjects with ready docs (for TestRequest)
  DELETE /upload/document/{doc_id} → delete a doc + its chunks/questions
  POST /upload/test/{subject_name} → fast-path test from uploaded PYQs
"""
import random
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models.db_models import (
    Student, UserDocument, UserChunk, Question, Subject, TestSession
)
from ..services.auth import get_current_student
from ..services import document_processor as dp

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_PDF_BYTES = 20 * 1024 * 1024   # 20 MB


# ── Background processing ──────────────────────────────────────────────────────

def _process_in_background(doc_id: int, content: bytes, doc_type: str) -> None:
    db = SessionLocal()
    try:
        doc = db.query(UserDocument).filter(UserDocument.id == doc_id).first()
        if not doc:
            return
        text = dp.extract_text_from_pdf(content)
        if doc_type == "book":
            dp.process_book(db, doc, text)
        else:
            dp.process_pyq(db, doc, text)
    except Exception as e:
        db2 = SessionLocal()
        try:
            d = db2.query(UserDocument).filter(UserDocument.id == doc_id).first()
            if d:
                d.status = "failed"
                db2.commit()
        finally:
            db2.close()
    finally:
        db.close()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/document")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject_name: str = Form(...),
    doc_type: str = Form(...),        # "book" | "pyq"
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    if doc_type not in ("book", "pyq"):
        raise HTTPException(400, "doc_type must be 'book' or 'pyq'.")

    content = await file.read()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(400, "File too large — maximum size is 20 MB.")

    doc = UserDocument(
        student_id=student.id,
        filename=file.filename,
        subject_name=subject_name.strip(),
        doc_type=doc_type,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_process_in_background, doc.id, content, doc_type)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "subject_name": doc.subject_name,
        "doc_type": doc.doc_type,
        "status": doc.status,
    }


@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    docs = (
        db.query(UserDocument)
        .filter(UserDocument.student_id == student.id)
        .order_by(UserDocument.created_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "subject_name": d.subject_name,
            "doc_type": d.doc_type,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "question_count": d.question_count,
        }
        for d in docs
    ]


@router.get("/subjects")
def uploaded_subjects(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    """Returns distinct ready subjects with flags for what types are available."""
    docs = (
        db.query(UserDocument)
        .filter(
            UserDocument.student_id == student.id,
            UserDocument.status == "ready",
        )
        .all()
    )
    seen: dict[str, dict] = {}
    for d in docs:
        name = d.subject_name
        if name not in seen:
            seen[name] = {"name": name, "has_book": False, "has_pyq": False}
        if d.doc_type == "book":
            seen[name]["has_book"] = True
        else:
            seen[name]["has_pyq"] = True
    return list(seen.values())


@router.delete("/document/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    doc = db.query(UserDocument).filter(
        UserDocument.id == doc_id,
        UserDocument.student_id == student.id,
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found.")

    # Remove uploaded questions (tagged with this doc's source)
    source_tag = f"user_upload_{student.id}_{doc_id}"
    db.query(Question).filter(Question.source == source_tag).delete(synchronize_session=False)

    # UserChunks are cascade-deleted with the doc
    db.delete(doc)
    db.commit()
    return {"deleted": True}


@router.post("/test/{subject_name}")
def generate_uploaded_test(
    subject_name: str,
    mode: str = "practice",
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    """Fast-path: skip the full multi-agent pipeline and directly sample uploaded PYQ questions."""
    # Find all PYQ docs for this student + subject
    doc_ids = [
        d.id for d in db.query(UserDocument).filter(
            UserDocument.student_id == student.id,
            UserDocument.subject_name == subject_name,
            UserDocument.status == "ready",
            UserDocument.doc_type == "pyq",
        ).all()
    ]
    if not doc_ids:
        raise HTTPException(404, f"No uploaded PYQ found for '{subject_name}'. Upload a PYQ PDF first.")

    # Collect questions tagged with any of those docs
    source_tags = [f"user_upload_{student.id}_{did}" for did in doc_ids]
    questions = (
        db.query(Question)
        .filter(Question.source.in_(source_tags))
        .all()
    )

    if not questions:
        raise HTTPException(404, f"No uploaded questions found for '{subject_name}'. Upload a PYQ PDF first.")

    target = 15 if mode == "practice" else 25
    sample = random.sample(questions, min(target, len(questions)))

    # Find or create a subject row for this upload
    subj = db.query(Subject).filter(Subject.name == subject_name).first()
    subj_id = subj.id if subj else 0

    session = TestSession(
        student_id=student.id,
        subject_id=subj_id,
        mode=mode,
        time_limit_minutes=30 if mode == "practice" else 90,
        plan_snapshot=json.dumps({"source": "upload", "subject": subject_name}),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    q_out = [
        {
            "id": q.id,
            "text": q.text,
            "type": q.type,
            "marks": q.marks,
            "difficulty": q.difficulty,
            "options": None,
            "answer": q.answer if q.type == "mcq" else None,
        }
        for q in sample
    ]

    return {
        "session_id": session.id,
        "questions": q_out,
        "events": [f"Loaded {len(sample)} questions from your uploaded {subject_name} material."],
        "plan": {"subject": subject_name, "mode": mode, "source": "upload"},
    }
