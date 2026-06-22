import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..database import get_db
from ..models.db_models import Student, StudentMastery, Topic, Chapter, Subject, TestSession, Response
from ..services.auth import get_current_student
from ..schemas.pydantic_schemas import MasteryOut


def _grade(pct: float | None) -> str:
    if pct is None:
        return "—"
    if pct >= 91: return "A1"
    if pct >= 81: return "A2"
    if pct >= 71: return "B1"
    if pct >= 61: return "B2"
    if pct >= 51: return "C1"
    if pct >= 41: return "C2"
    if pct >= 33: return "D"
    return "E"


def _chapters_from_snapshot(plan_snapshot: str | None) -> str:
    """Extract unique chapter names from plan JSON, return top-2 as a short string."""
    if not plan_snapshot:
        return ""
    try:
        plan = json.loads(plan_snapshot)
        chapters = []
        seen = set()
        for t in plan.get("topics", []):
            ch = t.get("chapter_name", "")
            if ch and ch not in seen:
                seen.add(ch)
                chapters.append(ch)
        if not chapters:
            return ""
        if len(chapters) == 1:
            return chapters[0]
        if len(chapters) == 2:
            return f"{chapters[0]}, {chapters[1]}"
        return f"{chapters[0]}, {chapters[1]} +{len(chapters)-2} more"
    except Exception:
        return ""

router = APIRouter(prefix="/student", tags=["student"])


@router.get("/mastery/{subject_name}")
def get_mastery(
    subject_name: str,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    subject = db.query(Subject).filter(Subject.name == subject_name).first()
    if not subject:
        return []

    rows = db.query(StudentMastery).filter(
        and_(StudentMastery.student_id == student.id, StudentMastery.subject_id == subject.id)
    ).all()

    result = []
    for r in rows:
        topic = db.query(Topic).filter(Topic.id == r.topic_id).first()
        chapter = db.query(Chapter).filter(Chapter.id == r.chapter_id).first()
        result.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "chapter_id": r.chapter_id,
            "chapter_name": chapter.name if chapter else "",
            "topic_id": r.topic_id,
            "topic_name": topic.name if topic else "",
            "mastery": r.mastery,
            "attempts": r.attempts,
        })
    return result


@router.get("/sessions")
def get_sessions(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    sessions = db.query(TestSession).filter(
        TestSession.student_id == student.id
    ).order_by(TestSession.started_at.desc()).limit(20).all()

    result = []
    for s in sessions:
        subject = db.query(Subject).filter(Subject.id == s.subject_id).first()
        pct = round(s.total_score / s.total_marks * 100, 1) if (s.total_score is not None and s.total_marks) else None
        result.append({
            "id": s.id,
            "subject_id": s.subject_id,
            "subject_name": subject.name if subject else "",
            "mode": s.mode,
            "started_at": s.started_at,
            "total_score": s.total_score,
            "total_marks": s.total_marks,
            "percentage": pct,
            "grade": _grade(pct),
            "chapters": _chapters_from_snapshot(s.plan_snapshot),
        })
    return result


@router.get("/subjects")
def get_subjects(db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name} for s in db.query(Subject).all()]


@router.delete("/tests")
def delete_all_tests(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    session_ids = [
        row[0]
        for row in db.query(TestSession.id)
        .filter(TestSession.student_id == student.id)
        .all()
    ]
    if session_ids:
        db.query(Response).filter(Response.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
    db.query(TestSession).filter(TestSession.student_id == student.id).delete(
        synchronize_session=False
    )
    db.query(StudentMastery).filter(StudentMastery.student_id == student.id).delete(
        synchronize_session=False
    )
    db.commit()
    return {"deleted": True}
