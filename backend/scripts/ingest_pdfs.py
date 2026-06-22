"""
PDF ingestion pipeline for PrepIQ RAG.

Reads NCERT books (data/books/) and CBSE SQPs (data/pyq/),
extracts text, chunks it, maps chunks to topics in the DB,
embeds them, and stores:
  - NCERT books → ncert_chunk table (for context retrieval)
  - SQP question papers → question table (source="pyq-YYYY")

Run from PrepIQ/backend/:
    python -m scripts.ingest_pdfs
or with args:
    python -m scripts.ingest_pdfs --books-only
    python -m scripts.ingest_pdfs --pyq-only
    python -m scripts.ingest_pdfs --dry-run
"""
import sys
import os
import re
import json
import argparse
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pdfplumber
from sqlalchemy import text as sql_text
from app.database import SessionLocal, init_db
from app.models.db_models import Subject, Chapter, Topic, Question, NcertChunk
from app.services.embeddings import embed, embed_batch
from app.agents.llm import small_llm
from langchain_core.messages import HumanMessage, SystemMessage

DATA_ROOT = Path(__file__).parent.parent.parent / "data"
BOOKS_DIR = DATA_ROOT / "books"
PYQ_DIR   = DATA_ROOT / "pyq"

CHUNK_SIZE   = 600   # characters per NCERT chunk
CHUNK_OVERLAP = 100  # character overlap between consecutive chunks

# Map folder names → Subject.name in DB
FOLDER_TO_SUBJECT = {
    "mathematics":    "Mathematics",
    "science":        "Science",
    "english":        "English",
    "hindi":          "Hindi",
    "social_science": "Social Science",
    "sanskrit":       "Sanskrit",
}

# Extract year from PYQ filename, e.g. sqp_2023_science.pdf → "pyq-2023"
_YEAR_RE = re.compile(r"sqp_(\d{4})")


# ──────────────────────────────────────────────────────────────────────────────
# PDF text extraction
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF; skip pages with no text (scanned images).
    Caps total output at 500 000 chars to avoid MemoryError on large books."""
    MAX_CHARS = 500_000
    pages = []
    total = 0
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                if total >= MAX_CHARS:
                    break
                t = page.extract_text()
                if t and t.strip():
                    pages.append(t.strip())
                    total += len(t)
    except Exception as e:
        print(f"  WARNING: could not read {pdf_path.name}: {e}")
    return "\n\n".join(pages)


# ──────────────────────────────────────────────────────────────────────────────
# Chunking
# ──────────────────────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding-window character chunker; splits on sentence boundaries where possible."""
    if not text or not text.strip():
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end]
        # Try to break at a sentence boundary (only when not at end of text)
        if end < n:
            last_period = max(chunk.rfind(". "), chunk.rfind(".\n"), chunk.rfind("? "), chunk.rfind("! "))
            if last_period > size // 2:
                end = start + last_period + 1
                chunk = text[start:end]
        chunk = chunk.strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap
    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# Topic mapping (cosine nearest-neighbour in embedding space)
# ──────────────────────────────────────────────────────────────────────────────

_topic_cache: dict[int, list[dict]] = {}  # subject_id → [{id, name, embedding}]


def _load_topics(db, subject_id: int) -> list[dict]:
    if subject_id in _topic_cache:
        return _topic_cache[subject_id]
    rows = (
        db.query(Topic.id, Topic.name)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .filter(Chapter.subject_id == subject_id)
        .all()
    )
    topic_names = [r.name for r in rows]
    if not topic_names:
        _topic_cache[subject_id] = []
        return []
    embeddings = embed_batch(topic_names)
    result = [{"id": r.id, "name": r.name, "emb": emb}
              for r, emb in zip(rows, embeddings)]
    _topic_cache[subject_id] = result
    return result


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot  # embeddings are already L2-normalised


def find_nearest_topic(db, subject_id: int, chunk: str) -> int | None:
    """Return topic_id closest in embedding space to the chunk text."""
    topics = _load_topics(db, subject_id)
    if not topics:
        return None
    chunk_emb = embed(chunk[:300])   # embed first 300 chars for speed
    best_id, best_score = topics[0]["id"], -1.0
    for t in topics:
        score = _cosine(chunk_emb, t["emb"])
        if score > best_score:
            best_score, best_id = score, t["id"]
    return best_id


# ──────────────────────────────────────────────────────────────────────────────
# PYQ question extraction via LLM
# ──────────────────────────────────────────────────────────────────────────────

_PYQ_SYSTEM = """You are a CBSE Class 10 exam paper parser.
Extract ALL questions from the given exam paper text.
Return ONLY a valid JSON array. Each item must have:
{
  "text": "Full question text. For MCQ embed options as (A)...(B)...(C)...(D)...",
  "answer": "Model answer or correct option letter like (A)",
  "marking_scheme": "Brief marking scheme e.g. '1 mark for (B)' or '3 marks: 1 for X, 1 for Y, 1 for Z'",
  "type": "mcq" | "short" | "long",
  "marks": <integer marks for this question>,
  "difficulty": <1-5 integer, estimate from marks: 1mark=2, 2marks=2, 3marks=3, 5marks=4, essay=5>,
  "topic_hint": "Brief topic keyword to help classify this question (e.g. 'Probability', 'Nationalism', 'Acids and Bases')"
}
Rules:
- For MCQ: embed all 4 options inside "text" using \\n(A) opt\\n(B) opt\\n(C) opt\\n(D) opt
- Skip instructions, header text, and figures/diagrams that have no extractable question
- If the paper has marking scheme pages, use them to fill the "answer" and "marking_scheme" fields
- Return [] if no questions found (e.g. for instructions-only pages)"""


def extract_questions_from_text(page_text: str) -> list[dict]:
    """Use LLM to extract structured questions from SQP text."""
    if len(page_text) < 100:
        return []
    # Truncate to avoid token overflow; process in chunks if needed
    truncated = page_text[:8000]
    try:
        resp = small_llm().invoke([
            SystemMessage(content=_PYQ_SYSTEM),
            HumanMessage(content=f"Extract all questions from this exam paper text:\n\n{truncated}"),
        ])
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        if isinstance(data, list):
            return data
    except Exception as e:
        pass
    return []


def ingest_pyq_pdf(db, pdf_path: Path, subject: Subject, dry_run: bool) -> int:
    """Extract questions from one SQP PDF and store them in the Question table."""
    m = _YEAR_RE.search(pdf_path.stem)
    year = m.group(1) if m else "unknown"
    source_tag = f"pyq-{year}"

    full_text = extract_text_from_pdf(pdf_path)
    if not full_text:
        print(f"    No text extracted (possibly scanned PDF) — skipping {pdf_path.name}")
        return 0

    # Process in large chunks to stay within LLM context
    segments = chunk_text(full_text, size=4000, overlap=200)
    all_questions: list[dict] = []
    for seg in segments:
        qs = extract_questions_from_text(seg)
        all_questions.extend(qs)

    if not all_questions:
        print(f"    No questions extracted from {pdf_path.name}")
        return 0

    # Deduplicate by first 100 chars of text
    seen: set[str] = set()
    unique_qs = []
    for q in all_questions:
        key = q.get("text", "")[:100].strip()
        if key and key not in seen:
            seen.add(key)
            unique_qs.append(q)

    # Check for already-ingested source tag
    existing_count = db.query(Question).join(Topic).join(Chapter).filter(
        Chapter.subject_id == subject.id,
        Question.source == source_tag,
    ).count()

    inserted = 0
    for item in unique_qs:
        q_text = (item.get("text") or "").strip()
        q_ans  = (item.get("answer") or "").strip()
        q_ms   = (item.get("marking_scheme") or "").strip()
        q_type = (item.get("type") or "short").strip()
        q_marks = int(item.get("marks") or 3)
        q_diff  = max(1, min(5, int(item.get("difficulty") or 3)))
        hint    = (item.get("topic_hint") or q_text[:50]).strip()

        if not q_text or not q_ans:
            continue
        if q_type not in ("mcq", "short", "long"):
            q_type = "short"
        if q_marks not in (1, 2, 3, 4, 5):
            q_marks = 3

        # For MCQ without embedded options, skip
        if q_type == "mcq" and "(A)" not in q_text:
            continue

        topic_id = find_nearest_topic(db, subject.id, hint + " " + q_text[:200])
        if not topic_id:
            continue

        # Deduplicate against DB
        exists = db.query(Question).filter(
            Question.topic_id == topic_id,
            Question.text == q_text,
        ).first()
        if exists:
            continue

        if not dry_run:
            emb = embed(q_text[:400])
            db.add(Question(
                topic_id=topic_id,
                difficulty=q_diff,
                marks=q_marks,
                type=q_type,
                text=q_text,
                answer=q_ans,
                marking_scheme=q_ms or f"Award {q_marks} mark(s) for correct answer.",
                source=source_tag,
                embedding=emb,
            ))
        inserted += 1

    if not dry_run:
        db.commit()
    return inserted


# ──────────────────────────────────────────────────────────────────────────────
# NCERT book chunk ingestion
# ──────────────────────────────────────────────────────────────────────────────

def ingest_ncert_pdf(db, pdf_path: Path, subject: Subject, dry_run: bool) -> int:
    """Extract text from one NCERT PDF, chunk it, and store as NcertChunk."""
    full_text = extract_text_from_pdf(pdf_path)
    if not full_text:
        print(f"    No text extracted (possibly scanned PDF) — skipping {pdf_path.name}")
        return 0

    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    # Batch embed all chunks
    embeddings = embed_batch(chunks)

    inserted = 0
    for chunk, emb in zip(chunks, embeddings):
        topic_id = find_nearest_topic(db, subject.id, chunk)
        if not topic_id:
            continue

        # Rough dedup: skip if identical chunk already exists for this topic
        exists = db.query(NcertChunk).filter(
            NcertChunk.topic_id == topic_id,
            NcertChunk.text == chunk,
        ).first()
        if exists:
            continue

        if not dry_run:
            db.add(NcertChunk(topic_id=topic_id, text=chunk, embedding=emb))
        inserted += 1

    if not dry_run:
        db.commit()
    return inserted


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def ingest_pyq_as_chunks(db, pdf_path: Path, subject: Subject, dry_run: bool) -> int:
    """
    Store SQP text directly as NcertChunk records (no LLM needed).
    This gives the RAG system PYQ context without needing question extraction.
    Year is embedded in chunk text as a prefix for provenance.
    """
    m = _YEAR_RE.search(pdf_path.stem)
    year = m.group(1) if m else "unknown"

    full_text = extract_text_from_pdf(pdf_path)
    if not full_text:
        return 0

    # Prefix each chunk with year so the LLM knows the PYQ year
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    prefixed = [f"[CBSE PYQ {year}] {c}" for c in chunks]
    embeddings = embed_batch(prefixed)

    inserted = 0
    for chunk, emb in zip(prefixed, embeddings):
        topic_id = find_nearest_topic(db, subject.id, chunk)
        if not topic_id:
            continue
        exists = db.query(NcertChunk).filter(
            NcertChunk.topic_id == topic_id,
            NcertChunk.text == chunk,
        ).first()
        if exists:
            continue
        if not dry_run:
            db.add(NcertChunk(topic_id=topic_id, text=chunk, embedding=emb))
        inserted += 1

    if not dry_run:
        db.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Ingest NCERT books and CBSE PYQs into PrepIQ RAG")
    parser.add_argument("--books-only",     action="store_true")
    parser.add_argument("--pyq-only",       action="store_true")
    parser.add_argument("--pyq-as-chunks",  action="store_true",
                        help="Store PYQ text as NcertChunks (fast, no LLM) instead of extracting questions")
    parser.add_argument("--subject",        help="Only process this subject folder (e.g. mathematics)")
    parser.add_argument("--dry-run",        action="store_true", help="Parse but don't write to DB")
    args = parser.parse_args()

    do_books = not args.pyq_only
    do_pyq   = not args.books_only

    init_db()
    db = SessionLocal()
    try:
        total_chunks    = 0
        total_questions = 0

        for folder_name, subject_name in FOLDER_TO_SUBJECT.items():
            if args.subject and args.subject != folder_name:
                continue

            subject = db.query(Subject).filter(Subject.name == subject_name).first()
            if not subject:
                print(f"Subject '{subject_name}' not found in DB -- skipping")
                continue

            # NCERT books
            if do_books:
                book_dir = BOOKS_DIR / folder_name
                if book_dir.exists():
                    for pdf in sorted(book_dir.glob("*.pdf")):
                        print(f"[BOOK] {subject_name} / {pdf.name} ...")
                        n = ingest_ncert_pdf(db, pdf, subject, args.dry_run)
                        print(f"       -> {n} chunks {'(dry-run)' if args.dry_run else 'stored'}")
                        total_chunks += n

            # CBSE PYQs
            if do_pyq:
                pyq_dir = PYQ_DIR / folder_name
                if pyq_dir.exists():
                    for pdf in sorted(pyq_dir.glob("*.pdf")):
                        if args.pyq_as_chunks:
                            print(f"[PYQ-CHUNK] {subject_name} / {pdf.name} ...")
                            n = ingest_pyq_as_chunks(db, pdf, subject, args.dry_run)
                            print(f"            -> {n} chunks {'(dry-run)' if args.dry_run else 'stored'}")
                            total_chunks += n
                        else:
                            print(f"[PYQ]  {subject_name} / {pdf.name} ...")
                            n = ingest_pyq_pdf(db, pdf, subject, args.dry_run)
                            print(f"       -> {n} questions {'(dry-run)' if args.dry_run else 'stored'}")
                            total_questions += n

        print(f"\nDone. NCERT+PYQ chunks: {total_chunks} | PYQ questions: {total_questions}")
        if args.dry_run:
            print("(dry-run: nothing written to DB)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
