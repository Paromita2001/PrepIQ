"""
Examiner Agent — retrieves real PYQ questions at target difficulty.
Validator subagent rejects off-syllabus / ambiguous questions → regenerate loop.
Falls back to LLM-generated questions when DB has insufficient candidates.
"""
import json
import re
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage
from ..schemas.pydantic_schemas import TestPlan, QuestionOut, TopicWeight
from ..models.db_models import Question, Topic, Chapter, Response, TestSession
from ..services.retrieval import retrieve_questions, get_ncert_context
from .llm import small_llm

# Matches "In the given figure, " / "From the figure, " / "Refer to the figure." etc.
_FIGURE_PREFIX_RE = re.compile(
    r"^(in (the |this |a )?(given |above |below |following )?figure[^,\.]*[,\.]\s*"
    r"|from (the |this )?figure[^,\.]*[,\.]\s*"
    r"|refer(ring)? to (the )?figure[^,\.]*[,\.]\s*"
    r"|as shown (in|by) (the )?figure[^,\.]*[,\.]\s*)",
    re.IGNORECASE,
)
# If ANY of these remain after stripping the prefix, discard the question entirely
_FIGURE_BODY_RE = re.compile(
    r"\b(figure|diagram|shown below|given below|attached figure|above figure|as shown|"
    r"the circuit|the table above|see diagram|refer to|from the table)\b",
    re.IGNORECASE,
)
# MCQ-style phrasing that must never appear in short/long questions
_MCQ_PHRASING_RE = re.compile(
    r"\b(which of the following|choose the correct|select the correct|"
    r"from the options|tick the correct|from the following options)\b",
    re.IGNORECASE,
)
# Suspiciously short answer → likely bad extraction
_MIN_ANSWER_LEN = 8


def _quick_quality_check(text: str, answer: str, q_type: str) -> bool:
    """
    Fast regex-based checks — no LLM call.
    Returns False if the question should be discarded immediately.
    """
    if not text or not text.strip():
        return False
    # Figure references in body
    if _FIGURE_BODY_RE.search(text):
        return False
    # MCQ phrasing in a written-answer slot
    if q_type in ("short", "long", "any") and _MCQ_PHRASING_RE.search(text):
        return False
    # Empty or trivially short answer
    if not answer or len(answer.strip()) < _MIN_ANSWER_LEN:
        return False
    return True


def _clean_question_text(text: str) -> str | None:
    """Strip a leading figure-reference phrase; return None to discard the question."""
    stripped = _FIGURE_PREFIX_RE.sub("", text).strip()
    # Capitalise first letter after stripping
    if stripped and stripped[0].islower():
        stripped = stripped[0].upper() + stripped[1:]
    # If "figure" / "diagram" still appears anywhere, question can't stand alone
    if _FIGURE_BODY_RE.search(stripped):
        return None
    return stripped or None

VALIDATOR_SYSTEM = """You are a CBSE Class 10 quality checker.
Given a question and its topic, reply ONLY with JSON:
{"valid": true/false, "reason": "short reason if invalid"}

A question is INVALID if ANY of the following are true:
- It uses "which of the following", "from the options below", "choose the correct option",
  or any phrasing that implies a multiple-choice format, BUT the type is short or long answer.
- It asks for a specific numerical answer (ratio, length, value, area, speed…) but does NOT
  provide all the required data (measurements, lengths, angles, values) in the question text.
- It references a figure, diagram, table, graph, or image ("as shown", "given below",
  "refer to", "from the figure", "above diagram", etc.).
- It tests content outside CBSE Class 10 syllabus.
- The answer or marking scheme is missing, blank, or obviously wrong.
- It contains a factual error.
- It is ambiguous or cannot be answered from the question text alone.

A question is VALID only if it is fully self-contained, clearly answerable without any
external reference, on CBSE Class 10 syllabus, and has a correct marking scheme."""

GENERATOR_SYSTEM = """You are a CBSE Class 10 {subject} question setter.
Generate {count} {q_type} question(s) for:
  Topic: {topic_name} (Chapter: {chapter_name})
  Marks per question: {marks}
  Difficulty: {difficulty}/5

{language_instruction}
{ncert_context_block}

━━ ABSOLUTE RULES (violating any = question is rejected) ━━

1. NO FIGURES OR DIAGRAMS — every question must be 100% text-only.
   Never use: "as shown", "given figure", "refer to diagram", "from the figure",
   "the diagram above/below", "see figure", "in the circuit shown", etc.

2. SELF-CONTAINED DATA — if the question asks for a specific numerical answer
   (ratio, length, area, angle, value, speed, resistance…), ALL required numbers
   must appear INSIDE the question text. Never ask "find the value" without giving
   the data needed to find it.
   WRONG: "If △PQR ~ △STU, find the ratio of their perimeters."  ← no side data
   RIGHT: "If △PQR ~ △STU and PQ = 4 cm, ST = 6 cm, find the ratio of their perimeters."
   OR RIGHT: "State the relationship between the perimeters of two similar triangles
              and the ratio of their corresponding sides."  ← asks for the property, not a number

3. NEVER USE "WHICH OF THE FOLLOWING" FOR SHORT OR LONG TYPES — that phrasing
   implies options exist. For short/long, ask directly:
   WRONG: "Which of the following is a necessary condition for △ABC ~ △PQR?"
   RIGHT: "State the necessary conditions for △ABC ~ △PQR."
   RIGHT: "What conditions must be satisfied for two triangles to be similar?"

4. MCQ ONLY — options format applies only to type="mcq". Short and long must NOT
   contain (A) (B) (C) (D) choices.

━━ QUESTION TYPE FORMAT ━━

type="mcq" (1 mark):
  "text": "Question?\\n\\n(A) option1\\n(B) option2\\n(C) option3\\n(D) option4"
  "answer": letter only, e.g. "(A)"
  "marking_scheme": "1 mark for (X)"

type="short" (2–3 marks):
  Direct written-answer. Student writes 2–4 sentences.
  "answer": key points the student must mention
  "marking_scheme": "1 mark each for: point1 / point2 / ..."

type="long" (4–5 marks):
  Detailed explanation requiring steps or derivation.
  "answer": full model answer with all key points
  "marking_scheme": mark-by-mark breakdown

Return ONLY a JSON array — no markdown, no explanation:
[{{
  "text": "Question text",
  "answer": "Model answer",
  "marking_scheme": "Marking breakdown",
  "type": "{q_type}",
  "marks": {marks},
  "difficulty": {difficulty}
}}]"""

# Language instruction per subject
_SUBJECT_LANGUAGE = {
    "Sanskrit": (
        "LANGUAGE: This is a Sanskrit subject exam. Write the question text in Hindi (Devanagari script). "
        "Sanskrit terms and verses should be in Devanagari (e.g., तत्पुरुष समास, बहुव्रीहि समास). "
        "The answer and marking_scheme may be in Hindi. "
        "Do NOT write Sanskrit questions in English or Roman transliteration."
    ),
    "Hindi": (
        "LANGUAGE: This is a Hindi subject exam. Write the question text, answer, and marking_scheme in Hindi (Devanagari script). "
        "Do NOT write Hindi questions in English."
    ),
}


def _validate_raw(text: str, answer: str, marking_scheme: str, topic_name: str) -> tuple[bool, str]:
    """Validate question data before or after DB save."""
    prompt = f"Topic: {topic_name}\nQuestion: {text}\nAnswer: {answer}\nMarking scheme: {marking_scheme}"
    resp = small_llm().invoke([
        SystemMessage(content=VALIDATOR_SYSTEM),
        HumanMessage(content=prompt),
    ])
    try:
        data = json.loads(resp.content.strip())
        return data.get("valid", True), data.get("reason", "")
    except Exception:
        return True, ""


def _validate_question(q: Question, topic_name: str) -> tuple[bool, str]:
    return _validate_raw(q.text or "", q.answer or "", q.marking_scheme or "", topic_name)


def _generate_questions(
    db,
    subject_name: str,
    topic_name: str,
    chapter_name: str,
    topic_id: int,
    q_type: str,
    marks: int,
    difficulty: int,
    count: int,
) -> list[dict]:
    """Call LLM to generate questions, grounded with NCERT + PYQ context from RAG."""
    # "any" means practice mode — generate written (short) answers, never MCQ
    effective_q_type = "short" if q_type == "any" else q_type
    effective_marks = marks if marks > 0 else 3

    # Retrieve NCERT context for all question types — keeps LLM grounded in syllabus
    # MCQ gets fewer chunks (2) since options are short; short/long get more (4)
    ncert_block = ""
    query = f"{topic_name} {chapter_name} {subject_name}"
    n_chunks = 2 if effective_q_type == "mcq" else 4
    ncert_text = get_ncert_context(db, [topic_id], query, n=n_chunks)
    if ncert_text.strip():
        ncert_block = (
            f"Use the following NCERT/textbook reference to write accurate, "
            f"on-syllabus questions. Do not invent facts outside this material:\n"
            f"---\n{ncert_text[:2000]}\n---"
        )

    language_instruction = _SUBJECT_LANGUAGE.get(subject_name, "")

    system_prompt = GENERATOR_SYSTEM.format(
        subject=subject_name,
        count=count,
        q_type=effective_q_type,
        topic_name=topic_name,
        chapter_name=chapter_name,
        language_instruction=language_instruction,
        marks=effective_marks,
        difficulty=difficulty,
        ncert_context_block=ncert_block,
    )
    resp = small_llm().invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Generate {count} question(s) now."),
    ])
    try:
        # Strip markdown code fences if present
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _save_generated_questions(
    db: Session,
    topic: Topic,
    generated: list[dict],
    effective_q_type: str = "short",
    topic_name: str = "",
) -> list[Question]:
    """Validate then persist LLM-generated questions. Bad questions never enter the DB."""
    saved = []
    for item in generated:
        qtext  = item.get("text", "")
        qtype  = item.get("type", "short")
        qmarks = int(item.get("marks", 3))
        answer = item.get("answer", "")
        scheme = item.get("marking_scheme", "")

        # ── Layer 1: fast regex checks (free) ─────────────────────────────
        cleaned = _clean_question_text(qtext)
        if cleaned is None:
            continue
        qtext = cleaned

        if not _quick_quality_check(qtext, answer, effective_q_type):
            continue

        # If LLM embedded (A)(B)(C)(D) options, treat as MCQ
        has_options = all(f"({x})" in qtext for x in "ABCD")
        if has_options:
            qtype  = "mcq"
            qmarks = 1
        if qtype == "mcq":
            qmarks = 1
        # Asked for short/long but LLM returned MCQ → discard
        if qtype == "mcq" and effective_q_type not in ("mcq", "any"):
            continue

        # ── Layer 2: LLM validator (catches data-missing, off-syllabus) ───
        valid, _ = _validate_raw(qtext, answer, scheme, topic_name or topic.name)
        if not valid:
            continue   # reject before touching the DB

        q = Question(
            topic_id=topic.id,
            text=qtext,
            answer=answer,
            marking_scheme=scheme,
            type=qtype,
            marks=qmarks,
            difficulty=int(item.get("difficulty", 3)),
            source="llm_generated",
        )
        db.add(q)
        saved.append(q)
    db.commit()
    for q in saved:
        db.refresh(q)
    return saved


def run_examiner(
    db: Session,
    plan: TestPlan,
    student_id: int = 0,
    subject_id: int = 0,
) -> list[QuestionOut]:
    # Seed served_ids with every question this student has already answered
    # for this subject — so repeats never appear across test sessions
    if student_id and subject_id:
        prev_rows = (
            db.query(Response.question_id)
            .join(TestSession, Response.session_id == TestSession.id)
            .filter(
                TestSession.student_id == student_id,
                TestSession.subject_id == subject_id,
            )
            .all()
        )
        served_ids: list[int] = [r.question_id for r in prev_rows]
    else:
        served_ids: list[int] = []

    all_questions: list[QuestionOut] = []
    subject_name = plan.subject_name or plan.subject

    for tw in plan.topics:
        topic = db.query(Topic).filter(Topic.id == tw.topic_id).first()
        if not topic:
            continue
        chapter = db.query(Chapter).filter(Chapter.id == topic.chapter_id).first()

        # Level 1: try exact topic match
        candidates = retrieve_questions(
            db=db,
            topic_ids=[tw.topic_id],
            difficulty=tw.target_difficulty,
            n=tw.num_questions * 4,
            exclude_ids=served_ids,
            query_text=tw.topic_name,
            q_type=tw.q_type,
            marks=tw.marks_per_q,
        )

        # Level 2: widen to all topics in the same chapter (avoids LLM fallback)
        if len(candidates) < tw.num_questions and chapter:
            ch_topic_ids = [
                t.id for t in db.query(Topic).filter(Topic.chapter_id == chapter.id).all()
            ]
            extra = retrieve_questions(
                db=db,
                topic_ids=ch_topic_ids,
                difficulty=tw.target_difficulty,
                n=tw.num_questions * 4,
                exclude_ids=served_ids + [q.id for q in candidates],
                query_text=tw.topic_name,
                q_type=tw.q_type,
                marks=tw.marks_per_q,
            )
            candidates = candidates + extra

        accepted = 0
        for q in candidates:
            if accepted >= tw.num_questions:
                break

            # Layer 1: fast regex on ALL questions (free, instant)
            if not _quick_quality_check(q.text or "", q.answer or "", tw.q_type):
                continue

            # Layer 2: LLM validator only for LLM-generated questions
            if q.source and q.source.startswith("llm_generated"):
                valid, _ = _validate_question(q, tw.topic_name)
                if not valid:
                    continue

            served_ids.append(q.id)
            accepted += 1
            all_questions.append(QuestionOut(
                id=q.id,
                text=q.text,
                marks=q.marks,
                type=q.type,
                topic_name=topic.name,
                chapter_name=chapter.name if chapter else "",
                difficulty=q.difficulty,
                section=tw.section,
                source=q.source or "",
            ))

        # Level 3 (last resort): LLM generation only if DB truly has nothing
        remaining = tw.num_questions - accepted
        if remaining > 0:
            generated_dicts = _generate_questions(
                db=db,
                subject_name=subject_name,
                topic_name=tw.topic_name,
                chapter_name=tw.chapter_name,
                topic_id=tw.topic_id,
                q_type=tw.q_type,
                marks=tw.marks_per_q,
                difficulty=tw.target_difficulty,
                count=remaining + 2,   # small buffer only — DB grows over time
            )
            if generated_dicts:
                effective_type = "short" if tw.q_type == "any" else tw.q_type
                saved_qs = _save_generated_questions(
                    db, topic, generated_dicts,
                    effective_q_type=effective_type,
                    topic_name=tw.topic_name,
                )
                for q in saved_qs[:remaining]:
                    served_ids.append(q.id)
                    all_questions.append(QuestionOut(
                        id=q.id,
                        text=q.text,
                        marks=q.marks,
                        type=q.type,
                        topic_name=topic.name,
                        chapter_name=chapter.name if chapter else "",
                        difficulty=q.difficulty,
                        section=tw.section,
                        source="llm_generated",
                    ))

    return all_questions
