"""
LangGraph orchestration — the multi-agent state machine.
Flow: Router → Research → Planner → Examiner → (student answers) → Evaluator → Mastery → Mentor
The feedback loop: mastery profile feeds back into Examiner/Planner on the next run.
"""
from typing import TypedDict, Optional, List, Any
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from ..schemas.pydantic_schemas import (
    TestRequest, TestPlan, QuestionOut, EvalResult, MentorAdvice
)
from ..agents.router_agent import run_router, extract_topics_from_prompt
from ..agents.research_agent import run_research
from ..agents.planner_agent import run_planner
from ..agents.examiner_agent import run_examiner
from ..agents.evaluator_agent import run_evaluator
from ..agents.mastery_updater import run_mastery_updater
from ..agents.mentor_agent import run_mentor
from ..models.db_models import Subject


class PipelineState(TypedDict):
    student_id: int
    subject_id: Optional[int]
    raw_prompt: Optional[str]
    subject_name: Optional[str]
    request: Optional[Any]           # TestRequest dict
    research_topics: List[dict]
    plan: Optional[Any]              # TestPlan dict
    questions: List[dict]            # List[QuestionOut dict]
    answers: dict                    # {question_id: student_answer}
    eval_results: List[dict]
    mentor_advice: Optional[dict]
    session_id: Optional[int]
    events: List[str]
    error: Optional[str]
    db: Any                          # SQLAlchemy Session — injected


# ─── Node functions ───────────────────────────────────────────────────────────

def node_router(state: PipelineState) -> PipelineState:
    state["events"].append("Router: parsing request")
    try:
        if state.get("request"):
            # Dropdown path: request already set, but enrich with raw_prompt topics/chapters
            raw_prompt = state.get("raw_prompt") or ""
            if raw_prompt.strip():
                req_dict = state["request"]
                subject_name = req_dict.get("subject", "")
                extracted = extract_topics_from_prompt(raw_prompt, state["db"], subject_name=subject_name)
                extracted_topics   = extracted.get("topics")   or []
                extracted_chapters = extracted.get("chapters") or []
                # Keep topics and chapters separate so _matches() can avoid
                # false positives from word-level cross-contamination.
                # Fall back to the other list if one side is empty.
                if not req_dict.get("topics"):
                    req_dict["topics"]   = extracted_topics   or extracted_chapters
                if not req_dict.get("chapters"):
                    req_dict["chapters"] = extracted_chapters or extracted_topics
                state["request"] = req_dict
            return state
        req = run_router(state["raw_prompt"], state["db"])
        state["request"] = req.model_dump()
        state["subject_name"] = req.subject
    except Exception as e:
        state["error"] = f"Router error: {e}"
    return state


def node_research(state: PipelineState) -> PipelineState:
    state["events"].append("Research: analysing PYQ frequency")
    try:
        req = TestRequest(**state["request"])
        topics = run_research(state["db"], req)
        state["research_topics"] = topics

        subject = state["db"].query(Subject).filter(
            Subject.name == req.subject
        ).first()
        state["subject_id"] = subject.id if subject else None
    except Exception as e:
        state["error"] = f"Research error: {e}"
    return state


def node_planner(state: PipelineState) -> PipelineState:
    state["events"].append("Planner: building test plan")
    try:
        req = TestRequest(**state["request"])
        plan = run_planner(
            db=state["db"],
            student_id=state["student_id"],
            request=req,
            research_topics=state["research_topics"],
        )
        state["plan"] = plan.model_dump()
        state["session_id"] = plan.session_id
    except Exception as e:
        state["error"] = f"Planner error: {e}"
    return state


def node_examiner(state: PipelineState) -> PipelineState:
    state["events"].append("Examiner: selecting questions (Validator running)")
    try:
        plan = TestPlan(**state["plan"])
        questions = run_examiner(
            state["db"],
            plan,
            student_id=state.get("student_id", 0),
            subject_id=state.get("subject_id", 0),
        )
        state["questions"] = [q.model_dump() for q in questions]
    except Exception as e:
        state["error"] = f"Examiner error: {e}"
    return state


def node_evaluator(state: PipelineState) -> PipelineState:
    state["events"].append("Evaluator: grading answers")
    try:
        question_ids = [q["id"] for q in state["questions"]]
        results = run_evaluator(state["db"], question_ids, state["answers"])
        state["eval_results"] = [r.model_dump() for r in results]
    except Exception as e:
        state["error"] = f"Evaluator error: {e}"
    return state


def node_mastery(state: PipelineState) -> PipelineState:
    state["events"].append("Mastery Updater: updating student profile")
    try:
        results = [EvalResult(**r) for r in state["eval_results"]]
        run_mastery_updater(
            db=state["db"],
            student_id=state["student_id"],
            subject_id=state["subject_id"],
            eval_results=results,
            answers=state.get("answers", {}),
        )
    except Exception as e:
        state["error"] = f"Mastery error: {e}"
    return state


def node_mentor(state: PipelineState) -> PipelineState:
    state["events"].append("Mentor: generating recommendations")
    try:
        results = [EvalResult(**r) for r in state["eval_results"]]
        advice = run_mentor(
            db=state["db"],
            student_id=state["student_id"],
            subject_id=state["subject_id"],
            eval_results=results,
        )
        state["mentor_advice"] = advice.model_dump()
    except Exception as e:
        state["error"] = f"Mentor error: {e}"
    return state


# ─── Error guard ──────────────────────────────────────────────────────────────

def should_stop(state: PipelineState) -> str:
    return "stop" if state.get("error") else "continue"


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_plan_graph() -> StateGraph:
    """Graph for: Router → Research → Planner → Examiner (stops before answers)."""
    g = StateGraph(PipelineState)
    g.add_node("router",   node_router)
    g.add_node("research", node_research)
    g.add_node("planner",  node_planner)
    g.add_node("examiner", node_examiner)

    g.set_entry_point("router")
    g.add_conditional_edges("router",   should_stop, {"stop": END, "continue": "research"})
    g.add_conditional_edges("research", should_stop, {"stop": END, "continue": "planner"})
    g.add_conditional_edges("planner",  should_stop, {"stop": END, "continue": "examiner"})
    g.add_edge("examiner", END)
    return g.compile()


def build_eval_graph() -> StateGraph:
    """Graph for: Evaluator → Mastery → Mentor (after answers submitted)."""
    g = StateGraph(PipelineState)
    g.add_node("evaluator", node_evaluator)
    g.add_node("mastery",   node_mastery)
    g.add_node("mentor",    node_mentor)

    g.set_entry_point("evaluator")
    g.add_conditional_edges("evaluator", should_stop, {"stop": END, "continue": "mastery"})
    g.add_conditional_edges("mastery",   should_stop, {"stop": END, "continue": "mentor"})
    g.add_edge("mentor", END)
    return g.compile()


PLAN_GRAPH = build_plan_graph()
EVAL_GRAPH = build_eval_graph()
