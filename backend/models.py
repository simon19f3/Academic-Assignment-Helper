from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL").replace("postgresql://", "postgresql+asyncpg://")
Base = declarative_base()

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    full_name = Column(String)
    student_id = Column(String, unique=True, index=True) # <<< ADDED unique=True and index=True here
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship for assignments, linked by student_id
    # Note: If Student.id is the primary key and Student.student_id is just a unique identifier,
    # then primaryjoin and foreign_keys are necessary for non-primary key relationships.
    assignments = relationship("Assignment", back_populates="student",
                               primaryjoin="Student.student_id == Assignment.student_id",
                               foreign_keys="[Assignment.student_id]")

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    # The ForeignKey here should reference the *unique* column in students
    student_id = Column(String, ForeignKey("students.student_id"))
    filename = Column(String)
    original_text = Column(Text, nullable=True)
    topic = Column(String, nullable=True)
    academic_level = Column(String, nullable=True)
    word_count = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Back-populates the relationship from Student
    student = relationship("Student", back_populates="assignments",
                           primaryjoin="Student.student_id == Assignment.student_id",
                           foreign_keys="[Assignment.student_id]")
    analysis_results = relationship("AnalysisResult", back_populates="assignment")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    suggested_sources = Column(JSON, nullable=True)
    plagiarism_score = Column(Float, nullable=True)
    flagged_sections = Column(JSON, nullable=True)
    research_suggestions = Column(Text, nullable=True)
    citation_recommendations = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    assignment = relationship("Assignment", back_populates="analysis_results")

class AcademicSource(Base):
    __tablename__ = "academic_sources"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    authors = Column(String)
    publication_year = Column(Integer)
    abstract = Column(Text)
    full_text = Column(Text, nullable=True)
    source_type = Column(String)
    embedding = Column(Text)