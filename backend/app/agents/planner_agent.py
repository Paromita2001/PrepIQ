"""
Planner Agent — reads student mastery + exam date → decides what test to give.
Outputs a TestPlan with topic weights and target difficulties.

Mock mode: uses CBSE board pattern sections A/B/C/D/E (80 marks, 3 hrs).
Practice mode: adaptive short test (~15 questions, 30 min).
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..schemas.pydantic_schemas import TestPlan, TestRequest, TopicWeight
from ..models.db_models import (
    Subject, Chapter, Topic, StudentMastery, TestSession
)
from .llm import small_llm
from .research_agent import _all_topics_for_subject
from langchain_core.messages import HumanMessage, SystemMessage


# CBSE Class 10 board exam patterns per subject
# (section_name, q_type, marks_per_q, count)

# Default: Mathematics / Science / Social Science
BOARD_SECTIONS_DEFAULT = [
    ("A",  "mcq",   1, 20),
    ("B",  "short", 2,  6),
    ("C",  "short", 3,  7),
    ("D",  "long",  5,  3),
    ("E",  "short", 4,  3),
]
# Total: 39 questions, 80 marks

# English Language & Literature (Code 184)
# Sec A Reading (20M) | Sec B Grammar+Writing (20M) | Sec C Literature (40M)
BOARD_SECTIONS_ENGLISH = [
    ("A - Reading: MCQ",        "mcq",   1,  8),  #  8 marks  (unseen passages MCQ/vocab)
    ("A - Reading: Short",      "short", 3,  4),  # 12 marks  (comprehension/inference)
    ("B - Grammar",             "mcq",   1, 10),  # 10 marks  (gap-fill/editing/transformation)
    ("B - Writing",             "long",  5,  2),  # 10 marks  (formal letter + analytical para)
    ("C - Literature: Short",   "short", 3,  4),  # 12 marks  (extract-based prose questions)
    ("C - Literature: VSA",     "short", 2,  4),  #  8 marks  (extract-based poem questions)
    ("C - Literature: Long",    "long",  5,  4),  # 20 marks  (theme/character/plot long answers)
]
# Total: 36 questions, 80 marks

# Hindi Course A (Code 002) / Course B (Code 085)
# Sec A Reading+Grammar (~15M) | Sec B Literature (~35M) | Sec C Creative Writing (~30M)
BOARD_SECTIONS_HINDI = [
    ("A - Reading",             "short", 2,  5),  # 10 marks  (unseen passage comprehension)
    ("A - Grammar",             "mcq",   1,  5),  #  5 marks  (Samas/Muhavare/Upsarg)
    ("B - Literature: Passage", "short", 3,  5),  # 15 marks  (seen passages from Kshitij/Sparsh)
    ("B - Literature: Short",   "short", 2,  5),  # 10 marks  (character/moral value questions)
    ("B - Literature: Long",    "long",  5,  2),  # 10 marks  (long answer — theme/plot)
    ("C - Essay (Nibandh)",     "long",  5,  2),  # 10 marks  (essay writing)
    ("C - Letter (Patra)",      "long",  5,  2),  # 10 marks  (formal/informal letter)
    ("C - Short Writing",       "short", 3,  2),  #  6 marks  (advertisement/Vigyaapan)
    ("C - Message (Sandesh)",   "short", 2,  2),  #  4 marks  (message writing)
]
# Total: 30 questions, 80 marks

# Sanskrit (Code 122)
# Sec A Reading (10M) | Sec B Creative Writing (15M) | Sec C Grammar (25M) | Sec D Literature (30M)
BOARD_SECTIONS_SANSKRIT = [
    ("A - Reading",             "short", 2,  5),  # 10 marks  (unseen passage comprehension)
    ("B - Letter Writing",      "long",  5,  1),  #  5 marks  (Patra lekhan)
    ("B - Picture Description", "short", 3,  2),  #  6 marks  (Chitra varnan)
    ("B - Translation",         "short", 2,  2),  #  4 marks  (Hindi→Sanskrit / Sanskrit→Hindi)
    ("C - Grammar MCQ",         "mcq",   1, 10),  # 10 marks  (Sandhi/Samas/Pratyay)
    ("C - Grammar Short",       "short", 2,  5),  # 10 marks  (Karak/Upapad Vibhakti)
    ("C - Avyaya",              "mcq",   1,  5),  #  5 marks  (indeclinable words)
    ("D - Literature: Extract", "short", 3,  4),  # 12 marks  (seen passages from Shemushi)
    ("D - Literature: Vocab",   "mcq",   1,  6),  #  6 marks  (word meanings / extracts)
    ("D - Literature: Long",    "long",  4,  3),  # 12 marks  (question-answering in Sanskrit)
]
# Total: 43 questions, 80 marks

# Map subject name → section list
SUBJECT_BOARD_SECTIONS: dict[str, list] = {
    "english":       BOARD_SECTIONS_ENGLISH,
    "hindi":         BOARD_SECTIONS_HINDI,
    "sanskrit":      BOARD_SECTIONS_SANSKRIT,
}

def _get_board_sections(subject_name: str) -> list:
    return SUBJECT_BOARD_SECTIONS.get(subject_name.lower(), BOARD_SECTIONS_DEFAULT)

# Keep alias so existing references don't break
BOARD_SECTIONS = BOARD_SECTIONS_DEFAULT


def _mastery_for_student(db: Session, student_id: int, subject_id: int) -> dict[int, float]:
    rows = db.query(StudentMastery).filter(
        and_(StudentMastery.student_id == student_id, StudentMastery.subject_id == subject_id)
    ).all()
    return {r.topic_id: r.mastery for r in rows}


def _target_difficulty(mastery: float) -> int:
    if mastery < 0.2: return 1
    if mastery < 0.4: return 2
    if mastery < 0.6: return 3
    if mastery < 0.8: return 4
    return 5


def _is_diagnostic(db: Session, student_id: int, subject_id: int) -> bool:
    exists = db.query(TestSession).filter(
        and_(TestSession.student_id == student_id, TestSession.subject_id == subject_id)
    ).first()
    return exists is None


def _filter_topics_by_request(topics: list[dict], request) -> list[dict]:
    """
    When the user named specific chapters/topics, keep only those.
    Uses the same phrase-level matching as the research agent.
    """
    chapter_kws = [c.lower().strip() for c in (request.chapters or [])]
    topic_kws   = [t.lower().strip() for t in (request.topics   or [])]
    if not chapter_kws and not topic_kws:
        return topics

    def _matches(t: dict) -> bool:
        ch = t["chapter_name"].lower()
        tp = t["topic_name"].lower()
        if chapter_kws and any(kw in ch or ch in kw for kw in chapter_kws):
            return True
        if topic_kws and any(kw in tp or tp in kw for kw in topic_kws):
            return True
        return False

    filtered = [t for t in topics if _matches(t)]
    return filtered if filtered else topics  # fall back to all if nothing matched


def _build_mock_plan(
    db: Session,
    student_id: int,
    subject: Subject,
    mastery_map: dict[int, float],
    is_diag: bool,
    request=None,
) -> list[TopicWeight]:
    """
    Build TopicWeights for CBSE board pattern mock exam.
    If the user specified chapters/topics, restricts to those; otherwise uses all.
    Distributes topics round-robin across each section's question slots.
    Uses subject-specific paper pattern for English, Hindi, and Sanskrit.
    """
    all_topics_raw = _all_topics_for_subject(db, subject.id)
    # Respect chapter/topic selection if provided
    if request and (request.chapters or request.topics):
        all_topics = _filter_topics_by_request(all_topics_raw, request)
    else:
        all_topics = all_topics_raw
    if not all_topics:
        return []

    board_sections = _get_board_sections(subject.name)

    topic_weights: list[TopicWeight] = []
    topic_idx = 0
    n_topics = len(all_topics)

    for section_name, q_type, marks_per_q, count in board_sections:
        # Collect topic assignments for this section's slots round-robin
        # Group consecutive slots for the same topic together
        topic_slot_map: dict[int, dict] = {}  # topic_id → {topic_data, num_questions}

        for slot in range(count):
            t = all_topics[topic_idx % n_topics]
            tid = t["topic_id"]
            if tid not in topic_slot_map:
                topic_slot_map[tid] = {**t, "num_questions": 0}
            topic_slot_map[tid]["num_questions"] += 1
            topic_idx += 1

        for tid, tdata in topic_slot_map.items():
            mastery = mastery_map.get(tid, 0.5) if not is_diag else 0.5
            diff = 3 if is_diag else _target_difficulty(mastery)
            topic_weights.append(TopicWeight(
                topic_id=tid,
                topic_name=tdata["topic_name"],
                chapter_name=tdata["chapter_name"],
                priority=1.0,
                target_difficulty=diff,
                num_questions=tdata["num_questions"],
                section=section_name,
                q_type=q_type,
                marks_per_q=marks_per_q,
            ))

    return topic_weights


def run_planner(
    db: Session,
    student_id: int,
    request: TestRequest,
    research_topics: list[dict],
    exam_date: datetime | None = None,
) -> TestPlan:
    subject = db.query(Subject).filter(Subject.name == request.subject).first()
    if not subject:
        raise ValueError(f"Subject '{request.subject}' not found in DB")

    is_diag = _is_diagnostic(db, student_id, subject.id)
    mastery_map = _mastery_for_student(db, student_id, subject.id)

    if request.mode == "mock":
        time_limit = 180
    else:
        time_limit = 30

    # Mark new session
    session = TestSession(
        student_id=student_id,
        subject_id=subject.id,
        mode=request.mode,
        is_diagnostic=is_diag,
        time_limit_minutes=time_limit,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if request.mode == "mock":
        # Board exam pattern: fixed sections, respects chapter selection
        topic_weights = _build_mock_plan(db, student_id, subject, mastery_map, is_diag, request)
        total_q = sum(tw.num_questions for tw in topic_weights)
        # Compute from the subject-specific sections (all CBSE subjects = 80 marks)
        total_m = sum(marks * count for _, _, marks, count in _get_board_sections(subject.name))
    else:
        # Practice mode: adaptive, chapter-balanced
        topic_weights: list[TopicWeight] = []
        total_q = 0
        total_m = 0

        merged: list[dict] = []
        seen_ids: set[int] = set()

        # If the user requested specific topics/chapters, respect that EXACTLY.
        # Only inject weak topics from other areas when the request is generic.
        user_requested_specific = bool(request.topics or request.chapters)

        if not is_diag and not user_requested_specific:
            # Generic request → boost weak topics, but ONLY within the current subject
            valid_topic_ids = {
                t["topic_id"]
                for t in _all_topics_for_subject(db, subject.id)
            }
            weak = sorted(
                [{"topic_id": tid, "mastery": m}
                 for tid, m in mastery_map.items()
                 if m < 0.45 and tid in valid_topic_ids],  # ← subject-scoped
                key=lambda x: x["mastery"],
            )
            for w in weak:
                tid = w["topic_id"]
                topic_obj = db.query(Topic).filter(Topic.id == tid).first()
                chapter_obj = db.query(Chapter).filter(Chapter.id == topic_obj.chapter_id).first() if topic_obj else None
                if topic_obj and tid not in seen_ids:
                    merged.append({
                        "topic_id": tid,
                        "topic_name": topic_obj.name,
                        "chapter_name": chapter_obj.name if chapter_obj else "",
                        "priority": 1.0 - w["mastery"],
                    })
                    seen_ids.add(tid)

        # Always append research topics (already filtered to match the request)
        for rt in research_topics:
            if rt["topic_id"] not in seen_ids:
                merged.append(rt)
                seen_ids.add(rt["topic_id"])

        TARGET_Q = 20   # practice mode target questions
        MAX_Q    = 20   # hard cap

        if user_requested_specific and merged:
            # Group by chapter and distribute proportionally.
            from collections import defaultdict
            ch_groups: dict[str, list[dict]] = defaultdict(list)
            for rt in merged:
                ch_groups[rt["chapter_name"]].append(rt)

            n_chapters = len(ch_groups)
            # At least 5 per chapter; scale to hit TARGET_Q total
            q_per_ch = max(5, TARGET_Q // max(n_chapters, 1))

            for ch_name, ch_topics in ch_groups.items():
                ch_budget = q_per_ch
                # Pick top-priority topics within this chapter (up to 5 topics)
                for rt in sorted(ch_topics, key=lambda x: x["priority"], reverse=True)[:5]:
                    if total_q >= MAX_Q or ch_budget <= 0:
                        break
                    topic_id = rt["topic_id"]
                    mastery = mastery_map.get(topic_id, 0.5) if not is_diag else 0.5
                    diff = 3 if is_diag else _target_difficulty(mastery)
                    # Guarantee at least 2 per topic regardless of priority (priority 0
                    # happens when there are no PYQ questions — still need questions)
                    nq = min(ch_budget, max(2, round(rt["priority"] * 5)))
                    if total_q + nq > MAX_Q:
                        nq = max(1, MAX_Q - total_q)
                    nm = nq * 3
                    total_q += nq
                    total_m += nm
                    ch_budget -= nq
                    topic_weights.append(TopicWeight(
                        topic_id=topic_id,
                        topic_name=rt["topic_name"],
                        chapter_name=rt["chapter_name"],
                        priority=rt["priority"],
                        target_difficulty=diff,
                        num_questions=nq,
                        section="",
                        q_type="any",
                        marks_per_q=0,
                    ))
                if total_q >= MAX_Q:
                    break
        else:
            # Generic or diagnostic: priority-weighted across top topics
            for rt in merged[:10]:
                topic_id = rt["topic_id"]
                mastery = mastery_map.get(topic_id, 0.5) if not is_diag else 0.5
                diff = 3 if is_diag else _target_difficulty(mastery)
                nq = max(2, round(rt["priority"] * 8))
                if total_q + nq > MAX_Q:
                    nq = max(1, MAX_Q - total_q)
                nm = nq * 3
                total_q += nq
                total_m += nm
                topic_weights.append(TopicWeight(
                    topic_id=topic_id,
                    topic_name=rt["topic_name"],
                    chapter_name=rt["chapter_name"],
                    priority=rt["priority"],
                    target_difficulty=diff,
                    num_questions=nq,
                    section="",
                    q_type="any",
                    marks_per_q=0,
                ))
                if total_q >= MAX_Q:
                    break
                if total_q >= 15:
                    break

    plan = TestPlan(
        session_id=session.id,
        subject=request.subject,
        subject_name=subject.name,
        topics=topic_weights,
        total_questions=total_q,
        total_marks=total_m,
        time_limit_minutes=session.time_limit_minutes,
        mode=request.mode,
        is_diagnostic=is_diag,
    )

    # persist plan snapshot
    session.plan_snapshot = plan.model_dump_json()
    db.commit()

    return plan
