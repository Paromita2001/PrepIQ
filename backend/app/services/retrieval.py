"""
Hybrid retrieval: vector similarity (pgvector) + keyword (Postgres full-text BM25-like)
filtered by topic_id + difficulty band. Returns grounded, on-syllabus questions only.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from ..models.db_models import Question, Topic, Chapter
from .embeddings import embed


def retrieve_questions(
    db: Session,
    topic_ids: list[int],
    difficulty: int,
    n: int = 5,
    exclude_ids: list[int] | None = None,
    query_text: str = "",
    q_type: str = "any",
    marks: int = 0,
) -> list[Question]:
    """
    Hybrid retrieval:
    1. Filter by topic_ids + difficulty band (±1 if exact runs dry)
    2. Optional filter by q_type and marks
    3. Vector similarity if query_text provided, else fallback to random sample
    4. Merge + deduplicate, return top-n
    """
    exclude_ids = exclude_ids or []

    # difficulty band: target ±0, widen to ±1 if needed
    for band_delta in [0, 1, 2]:
        lo = max(1, difficulty - band_delta)
        hi = min(5, difficulty + band_delta)

        conditions = [
            Question.topic_id.in_(topic_ids),
            Question.difficulty.between(lo, hi),
        ]
        if exclude_ids:
            conditions.append(~Question.id.in_(exclude_ids))
        if q_type == "any":
            # Practice mode ("any") = written answers only. MCQ questions must
            # never appear in practice — they belong exclusively in mock Section A.
            conditions.append(Question.type != "mcq")
        else:
            conditions.append(Question.type == q_type)

        # Never serve MCQ questions that have no embedded options — they show blank buttons
        from sqlalchemy import or_
        conditions.append(or_(
            Question.type != "mcq",
            Question.text.like("%(A)%"),
        ))
        # For all non-MCQ modes (practice "any", explicit short, explicit long),
        # exclude questions whose text still has embedded (A)(B)(C)(D) option markers.
        if q_type != "mcq":
            conditions.append(
                ~and_(
                    Question.text.like("%(A)%"),
                    Question.text.like("%(B)%"),
                    Question.text.like("%(C)%"),
                    Question.text.like("%(D)%"),
                )
            )
        if marks > 0:
            conditions.append(Question.marks == marks)
        # Never serve questions that reference a figure/diagram not shown in the UI
        from sqlalchemy import or_ as _or
        conditions.append(
            ~_or(
                Question.text.ilike("%in the given figure%"),
                Question.text.ilike("%given figure%"),
                Question.text.ilike("%from the figure%"),
                Question.text.ilike("%refer to the figure%"),
                Question.text.ilike("%shown in figure%"),
                Question.text.ilike("%see figure%"),
                Question.text.ilike("%above figure%"),
                Question.text.ilike("%below figure%"),
                Question.text.ilike("%attached figure%"),
                Question.text.ilike("%as shown%"),
            )
        )
        # For short/long: filter MCQ-phrased questions that have no options
        if q_type in ("short", "long", "any"):
            conditions.append(
                ~_or(
                    Question.text.ilike("%which of the following%"),
                    Question.text.ilike("%choose the correct%"),
                    Question.text.ilike("%from the options%"),
                    Question.text.ilike("%select the correct%"),
                    Question.text.ilike("%tick the correct%"),
                )
            )
        # Filter questions with obviously missing data:
        # blank answer or trivially short answer (< 5 chars) → likely bad extraction
        conditions.append(Question.answer.isnot(None))
        conditions.append(func.length(Question.answer) > 4)
        base_filter = and_(*conditions)

        if query_text:
            query_vec = embed(query_text)
            # vector similarity + metadata filter
            rows = (
                db.query(Question)
                .filter(base_filter)
                .order_by(Question.embedding.cosine_distance(query_vec))
                .limit(n * 2)
                .all()
            )
        else:
            rows = (
                db.query(Question)
                .filter(base_filter)
                .order_by(func.random())
                .limit(n * 2)
                .all()
            )

        if rows:
            return rows[:n]

    return []


def get_marking_scheme(db: Session, question_id: int) -> str:
    q = db.query(Question).filter(Question.id == question_id).first()
    return q.marking_scheme if q else ""


def pyq_frequency(db: Session, subject_id: int) -> list[dict]:
    """
    Count PYQ appearances per topic. Returns ranked list.
    This is plain SQL counting — no LLM needed for this step.
    """
    rows = (
        db.query(
            Topic.id.label("topic_id"),
            Topic.name.label("topic_name"),
            Chapter.name.label("chapter_name"),
            func.count(Question.id).label("q_count"),
            func.sum(Question.marks).label("total_marks"),
        )
        .join(Question, Question.topic_id == Topic.id)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .filter(
            Chapter.subject_id == subject_id,
            Question.source.like("pyq%"),
        )
        .group_by(Topic.id, Topic.name, Chapter.name)
        .order_by(func.count(Question.id).desc())
        .all()
    )
    return [
        {
            "topic_id": r.topic_id,
            "topic_name": r.topic_name,
            "chapter_name": r.chapter_name,
            "q_count": r.q_count,
            "total_marks": r.total_marks or 0,
        }
        for r in rows
    ]


def get_ncert_context(db: Session, topic_ids: list[int], query: str, n: int = 3) -> str:
    """Retrieve NCERT chunks relevant to the query for few-shot context."""
    from ..models.db_models import NcertChunk
    query_vec = embed(query)
    chunks = (
        db.query(NcertChunk)
        .filter(NcertChunk.topic_id.in_(topic_ids))
        .order_by(NcertChunk.embedding.cosine_distance(query_vec))
        .limit(n)
        .all()
    )
    return "\n\n".join(c.text for c in chunks)
