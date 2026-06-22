"""
Router Agent — parses free-text student prompt into structured TestRequest.
Uses small/cheap model. Dropdown input skips this entirely.
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session
from ..schemas.pydantic_schemas import TestRequest
from ..models.db_models import Subject, Chapter, Topic
from .llm import small_llm

SYSTEM = """You are a CBSE Class 10 exam assistant.
Parse the student's request into JSON with these fields:
- subject: string — MUST be one of the known subjects listed below
- chapters: list of chapter names mentioned (empty list if none specified)
- topics: list of topic names mentioned (empty list if none specified)
- mode: "practice" or "mock" (default "practice")

IMPORTANT subject mapping rules:
- Physics, Chemistry, Biology, light, refraction, acids, bases, carbon, cells,
  respiration, control, coordination, heredity, evolution, ecosystems → "Science"
- Algebra, quadratic, trigonometry, circles, statistics, probability, arithmetic → "Mathematics"
- History, geography, civics, economics, democracy → "Social Science"

Reply ONLY with valid JSON. No explanation. No markdown.
Example: {"subject":"Science","chapters":["Electricity"],"topics":["Ohm's Law"],"mode":"practice"}"""

# Science topic keywords — used in fallback when LLM is unavailable
_SCIENCE_KEYWORDS = {
    "physics", "chemistry", "biology", "light", "refraction", "reflection",
    "electricity", "magnetic", "acid", "base", "carbon", "cell", "cells",
    "control", "coordination", "heredity", "evolution", "ecosystem",
    "photosynthesis", "respiration", "reproduction", "nutrition", "metals",
    "nonmetals", "chemical", "reaction", "refraction", "lens", "mirror",
    "current", "circuit", "force", "motion", "sound", "wave", "atom",
    "molecule", "periodic", "element", "compound", "mixture", "solution",
    "organic", "inorganic", "life", "process", "transport", "excretion",
    "nervous", "hormone", "plant", "animal", "genetics", "dna",
}
_MATH_KEYWORDS = {
    "equation", "polynomial", "triangle", "algebra", "probability", "statistics",
    "arithmetic", "circle", "quadratic", "coordinate", "trigonometry", "theorem",
    "proof", "matrix", "progression", "series", "surface", "volume", "area",
    "number", "real", "rational", "irrational", "integer",
}
_SOCIAL_KEYWORDS = {
    "history", "geography", "civics", "economics", "democracy", "development",
    "nationalist", "colonialism", "resource", "agriculture", "industry",
    "government", "constitution", "election", "power", "federalism",
}


def run_router(prompt: str, db: Session) -> TestRequest:
    subjects = [s.name for s in db.query(Subject).all()]
    system_msg = SYSTEM + f"\nKnown subjects (use EXACTLY these names): {subjects}"

    response = small_llm().invoke([
        SystemMessage(content=system_msg),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content.strip())
        # Validate subject is actually in DB; if not, remap
        if data.get("subject") not in subjects:
            data["subject"] = _keyword_subject(prompt, subjects)
        return TestRequest(**data, raw_prompt=prompt)
    except Exception:
        return TestRequest(subject=_keyword_subject(prompt, subjects), raw_prompt=prompt)


def _keyword_subject(prompt: str, subjects: list[str]) -> str:
    """Keyword-based subject detection. Falls back to Mathematics."""
    words = set(prompt.lower().split())
    # Check literal subject name first
    for s in subjects:
        if s.lower() in prompt.lower():
            return s
    # Score against keyword sets
    scores = {
        "Science":       len(words & _SCIENCE_KEYWORDS),
        "Mathematics":   len(words & _MATH_KEYWORDS),
        "Social Science": len(words & _SOCIAL_KEYWORDS),
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        # Make sure the detected subject exists in the DB
        if best in subjects:
            return best
    return "Mathematics"  # safe default


def extract_topics_from_prompt(prompt: str, db: Session, subject_name: str = "") -> dict:
    """
    Semantically map the student's prompt to ACTUAL topic/chapter names in the DB.
    Returns {"topics": [...], "chapters": [...]} using real DB names, not raw keywords.
    This prevents substring-match failures (e.g. "algebra" vs "Algebraic Method").
    """
    if not prompt or not prompt.strip():
        return {"topics": [], "chapters": []}

    # Build list of actual DB topics/chapters for the subject (or all subjects)
    if subject_name:
        subject = db.query(Subject).filter(Subject.name == subject_name).first()
        chapters = db.query(Chapter).filter(
            Chapter.subject_id == subject.id
        ).all() if subject else []
    else:
        chapters = db.query(Chapter).all()

    chapter_names = [c.name for c in chapters]
    # Cap at 80 topics to stay within Groq token limits — enough for any subject
    all_topic_names = list({
        t.name
        for c in chapters
        for t in db.query(Topic).filter(Topic.chapter_id == c.id).all()
    })
    topic_names = all_topic_names[:80]

    map_system = f"""You are a CBSE Class 10 exam assistant.
The student wrote a prompt describing what they want to study.
Match their intent to the ACTUAL topic and chapter names listed below.

Available chapters: {json.dumps(chapter_names)}
Available topics:   {json.dumps(topic_names)}

Reply ONLY with valid JSON — use exact names from the lists above:
{{
  "topics":   ["exact topic name from list", ...],
  "chapters": ["exact chapter name from list", ...]
}}
- Include a chapter if the student mentions anything related to it
- Include a topic if the student mentions anything related to it
- Return empty lists only if the prompt has no subject-matter content
- Do NOT invent names — only use names from the lists above"""

    valid_chapters = set(chapter_names)
    valid_topics   = set(topic_names)

    def _keyword_fallback() -> dict:
        """
        Fast keyword fallback when the LLM is unavailable (rate-limited / exception).
        Splits prompt into significant words and finds chapters/topics that contain them.
        """
        STOP = {"test", "me", "on", "the", "and", "for", "with", "of", "a", "in",
                "on", "to", "is", "are", "i", "want", "please", "about", "some",
                "questions", "practice", "study", "learn", "check"}
        words = [w.lower() for w in prompt.replace("-", " ").split() if len(w) > 2 and w.lower() not in STOP]
        matched_chapters = [c for c in chapter_names if any(w in c.lower() for w in words)]
        matched_topics   = [t for t in topic_names   if any(w in t.lower() for w in words)]
        return {"topics": matched_topics[:10], "chapters": matched_chapters[:5]}

    try:
        response = small_llm().invoke([
            SystemMessage(content=map_system),
            HumanMessage(content=f"Student prompt: {prompt}"),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        result = {
            "topics":   [t for t in (data.get("topics")   or []) if t in valid_topics],
            "chapters": [c for c in (data.get("chapters") or []) if c in valid_chapters],
        }
        # If LLM returned nothing useful, fall back to keyword matching
        if not result["topics"] and not result["chapters"]:
            return _keyword_fallback()
        return result
    except Exception:
        # LLM unavailable (rate limit, network, parse error) — degrade gracefully
        return _keyword_fallback()
