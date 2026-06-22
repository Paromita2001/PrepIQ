from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    board: str = "CBSE"
    exam_date: Optional[datetime] = None


class StudentLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StudentOut(BaseModel):
    id: int
    name: str
    email: str
    board: str
    exam_date: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Test Request ──────────────────────────────────────────────────────────────

class TestRequest(BaseModel):
    subject: str                            # "Physics"
    chapters: Optional[List[str]] = None   # ["Electricity", "Light"]
    topics: Optional[List[str]] = None     # free-form from prompt
    mode: str = "practice"                 # practice / mock
    raw_prompt: Optional[str] = None       # "test me on Electricity medium"

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        if v not in ("practice", "mock", "diagnostic"):
            raise ValueError("mode must be practice, mock, or diagnostic")
        return v


# ─── Planner / Research output ────────────────────────────────────────────────

class TopicWeight(BaseModel):
    topic_id: int
    topic_name: str
    chapter_name: str
    priority: float                         # 0–1, from PYQ frequency
    target_difficulty: int                  # 1–5 from mastery
    num_questions: int
    section: str = ""        # "A","B","C","D","E" for board pattern
    q_type: str = "any"      # "mcq","short","long","any"
    marks_per_q: int = 0     # 0 = any marks


class TestPlan(BaseModel):
    session_id: int
    subject: str
    subject_name: str = ""
    topics: List[TopicWeight]
    total_questions: int
    total_marks: int
    time_limit_minutes: int
    mode: str
    is_diagnostic: bool = False


# ─── Question ─────────────────────────────────────────────────────────────────

class QuestionOut(BaseModel):
    id: int
    text: str
    marks: int
    type: str
    topic_name: str
    chapter_name: str
    difficulty: int
    section: str = ""        # populated for mock exams
    source: str = ""         # "pyq-2023", "sample", "ncert", "llm_generated"

    class Config:
        from_attributes = True


# ─── Evaluator output ─────────────────────────────────────────────────────────

class PointResult(BaseModel):
    point: str
    awarded: bool
    marks: float


class EvalResult(BaseModel):
    question_id: int
    score: float
    max_score: int
    awarded_points: List[PointResult]
    missing_points: List[str]
    citation: str
    feedback: str


# ─── Mastery ──────────────────────────────────────────────────────────────────

class MasteryOut(BaseModel):
    subject_id: int
    subject_name: str
    chapter_id: int
    chapter_name: str
    topic_id: int
    topic_name: str
    mastery: float
    attempts: int


# ─── Mentor ───────────────────────────────────────────────────────────────────

class MentorAdvice(BaseModel):
    strong_topics: List[str]
    weak_topics: List[str]
    recommendations: List[str]
    study_plan_summary: str


# ─── Agent shared state (LangGraph) ───────────────────────────────────────────

class AgentState(BaseModel):
    student_id: int
    subject_id: Optional[int] = None
    request: Optional[TestRequest] = None
    plan: Optional[TestPlan] = None
    questions: List[QuestionOut] = []
    answers: dict = {}                      # question_id → student_answer (str)
    eval_results: List[EvalResult] = []
    mentor_advice: Optional[MentorAdvice] = None
    session_id: Optional[int] = None
    sse_events: List[str] = []              # for streaming to frontend
    error: Optional[str] = None
