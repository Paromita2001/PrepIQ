"""
Processes uploaded PDFs:
  - book  → extract text → chunk → embed → store as UserChunk (personal RAG)
  - pyq   → extract text → LLM parse → store as Question rows (personal question bank)
"""
import json
import re
from sqlalchemy.orm import Session
from ..models.db_models import UserDocument, UserChunk, Question, Subject, Chapter, Topic
from .embeddings import embed
from ..agents.llm import small_llm
from langchain_core.messages import SystemMessage, HumanMessage


# ── PDF text extraction ────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    import io
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    full_text = "\n".join(text_parts).strip()
    if not full_text:
        raise ValueError("No text could be extracted from this PDF. It may be a scanned image.")
    return full_text


# ── Chunking ───────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_words: int = 500, overlap_words: int = 75) -> list[str]:
    words = text.split()
    chunks = []
    step = chunk_words - overlap_words
    for i in range(0, len(words), step):
        chunk = " ".join(words[i: i + chunk_words])
        if len(chunk) >= 60:
            chunks.append(chunk)
    return chunks


# ── Book processing ────────────────────────────────────────────────────────────

def process_book(db: Session, doc: UserDocument, text: str) -> None:
    chunks = _chunk_text(text)
    for chunk_text in chunks:
        vec = embed(chunk_text)
        chunk = UserChunk(
            document_id=doc.id,
            student_id=doc.student_id,
            subject_name=doc.subject_name,
            text=chunk_text,
            embedding=vec,
        )
        db.add(chunk)
    doc.chunk_count = len(chunks)
    doc.status = "ready"
    db.commit()


# ── PYQ processing ─────────────────────────────────────────────────────────────

_PARSE_SYSTEM = """You are a CBSE exam question extractor.
Extract ALL exam questions from the text and return a JSON array.
Each item must have these exact keys:
  "type":           "mcq" | "short" | "long"
  "marks":          integer (1, 2, 3, 4, or 5)
  "difficulty":     integer (1=easy, 3=medium, 5=hard)
  "text":           the full question text
  "answer":         the answer or correct option
  "marking_scheme": how marks are awarded

Rules:
- Skip questions that reference a figure, diagram, or image.
- If marks are not stated, infer: MCQ=1, short answer=2 or 3, long=5.
- Return ONLY the JSON array, no other text.
- If no questions are found return [].
"""


def _parse_questions_from_slice(text_slice: str) -> list[dict]:
    try:
        resp = small_llm().invoke([
            SystemMessage(content=_PARSE_SYSTEM),
            HumanMessage(content=text_slice),
        ])
        raw = resp.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _get_or_create_upload_topic(db: Session, subject_name: str) -> tuple[int, int, int]:
    """Returns (subject_id, chapter_id, topic_id) for the upload bucket."""
    subj = db.query(Subject).filter(Subject.name == subject_name).first()
    if not subj:
        subj = Subject(name=subject_name)
        db.add(subj)
        db.flush()

    chap = db.query(Chapter).filter(
        Chapter.subject_id == subj.id,
        Chapter.name == "Uploaded Content",
    ).first()
    if not chap:
        chap = Chapter(subject_id=subj.id, name="Uploaded Content", number=99)
        db.add(chap)
        db.flush()

    topic = db.query(Topic).filter(
        Topic.chapter_id == chap.id,
        Topic.name == "Mixed",
    ).first()
    if not topic:
        topic = Topic(chapter_id=chap.id, name="Mixed")
        db.add(topic)
        db.flush()

    return subj.id, chap.id, topic.id


def process_pyq(db: Session, doc: UserDocument, text: str) -> None:
    _, _, topic_id = _get_or_create_upload_topic(db, doc.subject_name)

    slice_size = 2500
    slices = [text[i: i + slice_size] for i in range(0, len(text), slice_size)]

    total_saved = 0
    source_tag = f"user_upload_{doc.student_id}_{doc.id}"

    for text_slice in slices:
        parsed = _parse_questions_from_slice(text_slice)
        for q in parsed:
            q_text = str(q.get("text", "")).strip()
            if not q_text or len(q_text) < 10:
                continue
            # skip figure-referencing questions
            if re.search(r"given figure|see diagram|refer to|the figure", q_text, re.I):
                continue
            try:
                question = Question(
                    topic_id=topic_id,
                    difficulty=max(1, min(5, int(q.get("difficulty", 3)))),
                    marks=max(1, min(5, int(q.get("marks", 2)))),
                    type=q.get("type", "short") if q.get("type") in ("mcq", "short", "long") else "short",
                    text=q_text,
                    answer=str(q.get("answer", "")).strip() or "See marking scheme.",
                    marking_scheme=str(q.get("marking_scheme", "")).strip() or "Award marks for correct answer.",
                    source=source_tag,
                    embedding=embed(q_text),
                )
                db.add(question)
                total_saved += 1
            except Exception:
                continue

    doc.question_count = total_saved
    doc.status = "ready"
    db.commit()
