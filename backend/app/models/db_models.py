from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey,
    DateTime, Boolean, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from ..database import Base
from ..config import get_settings

settings = get_settings()
EMBED_DIM = settings.embed_dim


class Subject(Base):
    __tablename__ = "subject"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    chapters = relationship("Chapter", back_populates="subject", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapter"
    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    number = Column(Integer)
    subject = relationship("Subject", back_populates="chapters")
    topics = relationship("Topic", back_populates="chapter", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topic"
    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapter.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(300), nullable=False)
    chapter = relationship("Chapter", back_populates="topics")
    questions = relationship("Question", back_populates="topic")
    ncert_chunks = relationship("NcertChunk", back_populates="topic")


class Question(Base):
    __tablename__ = "question"
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topic.id", ondelete="CASCADE"), nullable=False)
    difficulty = Column(Integer, nullable=False)
    marks = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False)           # mcq / short / long
    text = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    marking_scheme = Column(Text, nullable=False)
    source = Column(String(100))                        # pyq-2023 / sample / ncert
    embedding = Column(Vector(EMBED_DIM))
    topic = relationship("Topic", back_populates="questions")
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_difficulty"),
        CheckConstraint("type IN ('mcq','short','long')", name="ck_type"),
    )


class NcertChunk(Base):
    __tablename__ = "ncert_chunk"
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topic.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBED_DIM))
    topic = relationship("Topic", back_populates="ncert_chunks")


class UserDocument(Base):
    """Tracks every PDF a student uploads (book or PYQ paper)."""
    __tablename__ = "user_document"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    subject_name = Column(String(200), nullable=False)   # free-text name student gave
    doc_type = Column(String(50), nullable=False)         # "book" | "pyq"
    status = Column(String(50), default="processing")     # processing | ready | failed
    chunk_count = Column(Integer, default=0)
    question_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    chunks = relationship("UserChunk", back_populates="document", cascade="all, delete-orphan")


class UserChunk(Base):
    """Embedded text chunks from an uploaded book — used as personal RAG context."""
    __tablename__ = "user_chunk"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("user_document.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student.id"), nullable=False)
    subject_name = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBED_DIM))
    document = relationship("UserDocument", back_populates="chunks")


class Student(Base):
    __tablename__ = "student"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(300), nullable=False)
    board = Column(String(50), default="CBSE")
    exam_date = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    masteries = relationship("StudentMastery", back_populates="student", cascade="all, delete-orphan")
    sessions = relationship("TestSession", back_populates="student", cascade="all, delete-orphan")
    documents = relationship("UserDocument", foreign_keys="[UserDocument.student_id]", cascade="all, delete-orphan")


class StudentMastery(Base):
    """
    Composite PK = (student, subject, chapter, topic) — strict scoping,
    prevents cross-subject mixup (Physics weak topics never appear in Chemistry test).
    """
    __tablename__ = "student_mastery"
    student_id = Column(Integer, ForeignKey("student.id", ondelete="CASCADE"), primary_key=True)
    subject_id = Column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapter.id", ondelete="CASCADE"), primary_key=True)
    topic_id = Column(Integer, ForeignKey("topic.id",  ondelete="CASCADE"), primary_key=True)
    mastery = Column(Float, default=0.5)
    attempts = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    last_difficulty = Column(Integer, default=3)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    student = relationship("Student", back_populates="masteries")


class TestSession(Base):
    __tablename__ = "test_session"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("student.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id"), nullable=False)
    mode = Column(String(20), default="practice")       # practice / mock
    started_at = Column(DateTime, server_default=func.now())
    submitted_at = Column(DateTime)
    time_limit_minutes = Column(Integer, default=30)
    is_diagnostic = Column(Boolean, default=False)
    total_score = Column(Float)
    total_marks = Column(Integer)
    plan_snapshot = Column(Text)                        # JSON: what planner decided
    student = relationship("Student", back_populates="sessions")
    responses = relationship("Response", back_populates="session", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "response"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("test_session.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    student_answer = Column(Text)
    score = Column(Float)
    max_score = Column(Integer)
    feedback = Column(Text)
    awarded_points = Column(Text)                       # JSON list
    missing_points = Column(Text)                       # JSON list
    citation = Column(Text)
    session = relationship("TestSession", back_populates="responses")


