"""
Research Agent — determines topic priority from PYQ frequency (SQL counting).
Only the "read the pattern" step uses an LLM; the counting is plain SQL.
"""
from sqlalchemy.orm import Session
from ..models.db_models import Subject, Chapter, Topic
from ..services.retrieval import pyq_frequency
from ..schemas.pydantic_schemas import TestRequest


def run_research(db: Session, request: TestRequest) -> list[dict]:
    subject = db.query(Subject).filter(Subject.name == request.subject).first()
    if not subject:
        return []

    freq_data = pyq_frequency(db, subject.id)

    # Keyword lists (lowercase) for matching. Each keyword may be a full DB name
    # (from semantic mapping in router) or a raw word — both cases are handled below.
    chapter_kws = [c.lower().strip() for c in (request.chapters or [])]
    topic_kws   = [t.lower().strip() for t in (request.topics   or [])]

    def _matches(f: dict) -> bool:
        ch = f["chapter_name"].lower()
        tp = f["topic_name"].lower()
        # Phrase-level only — router now supplies exact DB names, so word-level
        # splitting creates false positives (e.g. "acid" in "Ethanoic Acid"
        # wrongly matching "Acids, Bases and Salts").
        if chapter_kws and any(kw in ch or ch in kw for kw in chapter_kws):
            return True
        if topic_kws and any(kw in tp or tp in kw for kw in topic_kws):
            return True
        # Cross-match: a topic keyword that contains the chapter name still matches
        if topic_kws and any(kw in ch or ch in kw for kw in topic_kws):
            return True
        return False

    user_specified = bool(chapter_kws or topic_kws)

    if user_specified:
        freq_data = [f for f in freq_data if _matches(f)]

    # If PYQ corpus empty (no questions yet), pull all topics and re-filter
    if not freq_data:
        all_topics = _all_topics_for_subject(db, subject.id)
        if user_specified:
            freq_data = [f for f in all_topics if _matches(f)]
        # Still no match after filtering: return ALL topics for subject so the
        # examiner at least generates the right subject's questions (better than empty)
        if not freq_data:
            freq_data = all_topics

    # Normalise to priority 0–1
    max_count = max((f["q_count"] for f in freq_data), default=1)
    total_marks = max((f["total_marks"] for f in freq_data), default=1)

    result = []
    for f in freq_data:
        priority = min(1.0, f["q_count"] / max(max_count, 1) * 0.6 + f["total_marks"] / max(total_marks, 1) * 0.4)
        result.append({**f, "priority": round(priority, 3)})

    result.sort(key=lambda x: x["priority"], reverse=True)

    # When the user specified chapters, interleave results by chapter so the
    # planner sees all chapters near the top, not just the highest-frequency one.
    if user_specified:
        from collections import defaultdict
        ch_groups: dict[str, list] = defaultdict(list)
        for item in result:
            ch_groups[item["chapter_name"]].append(item)
        if len(ch_groups) > 1:
            interleaved = []
            max_len = max(len(v) for v in ch_groups.values())
            ch_lists = list(ch_groups.values())
            for i in range(max_len):
                for ch_list in ch_lists:
                    if i < len(ch_list):
                        interleaved.append(ch_list[i])
            result = interleaved

    return result


def _all_topics_for_subject(db: Session, subject_id: int) -> list[dict]:
    rows = (
        db.query(Topic, Chapter)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .filter(Chapter.subject_id == subject_id)
        .all()
    )
    return [
        {
            "topic_id": t.id,
            "topic_name": t.name,
            "chapter_name": c.name,
            "q_count": 0,
            "total_marks": 0,
        }
        for t, c in rows
    ]
