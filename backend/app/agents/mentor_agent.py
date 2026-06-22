"""
Mentor Agent — turns test results + mastery profile into actionable advice.
"""
import json
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage
from ..schemas.pydantic_schemas import EvalResult, MentorAdvice
from ..models.db_models import StudentMastery, Topic
from .llm import small_llm

SYSTEM = """You are a caring CBSE Class 10 study mentor.
Given the student's test performance, mastery data, and the chapters where mistakes occurred,
provide highly specific chapter-level advice.

Reply ONLY with JSON — no markdown, no extra keys:
{
  "strong_topics": ["topic names where student scored well"],
  "weak_topics": ["topic names where student made mistakes"],
  "recommendations": [
    "5-6 specific actionable tips. For each weak chapter, say EXACTLY: 'Re-read Chapter X (ChapterName) from your NCERT textbook and solve the exercises at the end.' Be specific about chapter names."
  ],
  "study_plan_summary": "2-3 sentences naming the specific weak chapters and what to do next."
}"""


def run_mentor(
    db: Session,
    student_id: int,
    subject_id: int,
    eval_results: list[EvalResult],
) -> MentorAdvice:
    from sqlalchemy import and_
    from ..models.db_models import Question, Chapter

    rows = db.query(StudentMastery).filter(
        and_(
            StudentMastery.student_id == student_id,
            StudentMastery.subject_id == subject_id,
        )
    ).all()

    mastery_summary = []
    strong, weak = [], []
    for r in rows:
        topic = db.query(Topic).filter(Topic.id == r.topic_id).first()
        name = topic.name if topic else str(r.topic_id)
        mastery_summary.append(f"{name}: {r.mastery:.2f}")
        if r.mastery > 0.7:
            strong.append(name)
        elif r.mastery < 0.45:
            weak.append(name)

    # Build per-question breakdown including chapter name and whether it was wrong
    score_lines = []
    weak_chapters: dict[str, list[str]] = {}   # chapter_name → [topic names with mistakes]
    for ev in eval_results:
        pct = round(ev.score / ev.max_score * 100) if ev.max_score else 0
        q = db.query(Question).filter(Question.id == ev.question_id).first()
        chapter_name = ""
        topic_name = ""
        if q:
            topic_obj = db.query(Topic).filter(Topic.id == q.topic_id).first()
            if topic_obj:
                topic_name = topic_obj.name
                ch = db.query(Chapter).filter(Chapter.id == topic_obj.chapter_id).first()
                if ch:
                    chapter_name = ch.name
        score_lines.append(
            f"Q{ev.question_id} [{chapter_name} / {topic_name}]: {ev.score}/{ev.max_score} ({pct}%)"
        )
        if pct < 60 and chapter_name:
            weak_chapters.setdefault(chapter_name, [])
            if topic_name and topic_name not in weak_chapters[chapter_name]:
                weak_chapters[chapter_name].append(topic_name)

    weak_chapter_lines = "\n".join(
        f"- Chapter '{ch}': weak on {', '.join(topics)}"
        for ch, topics in weak_chapters.items()
    ) or "No specific weak chapters identified."

    prompt = f"""Mastery profile:
{chr(10).join(mastery_summary) or "No mastery data yet (first test)"}

Question-by-question scores (with chapter and topic):
{chr(10).join(score_lines)}

Chapters where mistakes were made:
{weak_chapter_lines}"""

    resp = small_llm().invoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return MentorAdvice(**data)
    except Exception:
        chapter_tips = [
            f"Re-read the chapter '{ch}' from your NCERT textbook and solve the end-of-chapter exercises."
            for ch in list(weak_chapters.keys())[:3]
        ]
        return MentorAdvice(
            strong_topics=strong,
            weak_topics=weak,
            recommendations=chapter_tips or [
                "Review weak topics first.",
                "Practice past year questions.",
                "Focus on understanding marking schemes.",
            ],
            study_plan_summary=(
                f"Focus on revising: {', '.join(weak_chapters.keys())}. "
                "Attempt practice tests for each weak chapter."
            ) if weak_chapters else "Attempt more practice tests to build mastery.",
        )
