"""
Mastery Updater — plain Python, NO LLM call.
Two-way adaptive: correct → mastery up, wrong → mastery down.
Scoped strictly by (student, subject, chapter, topic).
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..models.db_models import StudentMastery, Question, Topic, Chapter
from ..schemas.pydantic_schemas import EvalResult

STEP = 0.1


def _target_difficulty(mastery: float) -> int:
    if mastery < 0.2: return 1
    if mastery < 0.4: return 2
    if mastery < 0.6: return 3
    if mastery < 0.8: return 4
    return 5


def run_mastery_updater(
    db: Session,
    student_id: int,
    subject_id: int,
    eval_results: list[EvalResult],
    answers: dict = None,
) -> None:
    for result in eval_results:
        # Skip unattempted questions — don't penalise blank submissions
        # answers keys may be int or str depending on caller
        if answers is not None:
            raw = answers.get(result.question_id, "") or answers.get(str(result.question_id), "")
            if not raw or not str(raw).strip():
                continue
        q = db.query(Question).filter(Question.id == result.question_id).first()
        if not q:
            continue
        topic = db.query(Topic).filter(Topic.id == q.topic_id).first()
        if not topic:
            continue
        chapter = db.query(Chapter).filter(Chapter.id == topic.chapter_id).first()
        if not chapter:
            continue

        # Fetch or create mastery row
        row = db.query(StudentMastery).filter(and_(
            StudentMastery.student_id == student_id,
            StudentMastery.subject_id == subject_id,
            StudentMastery.chapter_id == chapter.id,
            StudentMastery.topic_id == topic.id,
        )).first()

        if not row:
            row = StudentMastery(
                student_id=student_id,
                subject_id=subject_id,
                chapter_id=chapter.id,
                topic_id=topic.id,
                mastery=0.5,
                attempts=0,
                correct=0,
                last_difficulty=3,
            )
            db.add(row)
            db.flush()  # make row visible to subsequent iterations for same topic

        # Two-way adjustment
        correct = result.score >= (result.max_score * 0.5)
        # larger step for harder questions
        step = STEP * (1 + (q.difficulty - 3) * 0.05)
        if correct:
            row.mastery = min(1.0, row.mastery + step)
            row.correct = (row.correct or 0) + 1
        else:
            row.mastery = max(0.0, row.mastery - step)

        row.attempts = (row.attempts or 0) + 1
        row.last_difficulty = q.difficulty

    db.commit()


def get_weak_topics(db: Session, student_id: int, subject_id: int, threshold: float = 0.45) -> list[dict]:
    rows = db.query(StudentMastery).filter(and_(
        StudentMastery.student_id == student_id,
        StudentMastery.subject_id == subject_id,
        StudentMastery.mastery < threshold,
    )).order_by(StudentMastery.mastery.asc()).all()

    result = []
    for r in rows:
        topic = db.query(Topic).filter(Topic.id == r.topic_id).first()
        chapter = db.query(Chapter).filter(Chapter.id == r.chapter_id).first()
        result.append({
            "topic_id": r.topic_id,
            "topic_name": topic.name if topic else str(r.topic_id),
            "chapter_name": chapter.name if chapter else "",
            "mastery": r.mastery,
            "target_difficulty": _target_difficulty(r.mastery),
        })
    return result
