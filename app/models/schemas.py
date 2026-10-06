"""
app/models/schemas.py
===============================================================================
Pydantic v2 Data Models & Schema Specifications.

Defines schemas for:
- Source Register metadata validation
- Academic rule registry entries
- Student, Course, Attendance, Result data entities (Annex C)
- API request / response payloads for POST /ingest, POST /ask, GET /health, GET /sources, POST /load-students
===============================================================================
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class SourceRegisterMetadata(BaseModel):
    """
    Pydantic v2 schema for validating metadata associated with ingested PDF documents.
    Matches the Annex B specification for the University Source Register.
    """
    model_config = ConfigDict(extra="ignore")

    doc_id: str = Field(..., description="Unique document ID (Primary Key, e.g. ACAD-REG-2024)")
    title: str = Field(..., description="Full title of the university policy/document")
    issuer: Optional[str] = Field(None, description="Issuing authority (e.g. Academic Council)")
    authority_level: int = Field(1, ge=1, le=5, description="Authority Level integer between 1 and 5")
    doc_type: Optional[str] = Field(None, description="Document type (e.g. Regulation, Ordinance, Manual)")
    version: Optional[str] = Field("1.0", description="Document version number")
    effective_from: Optional[str] = Field(None, description="Start date of document validity (YYYY-MM-DD)")
    effective_to: Optional[str] = Field(None, description="End date of document validity (YYYY-MM-DD)")
    supersedes: Optional[str] = Field(None, description="doc_id of superseded document replaced by this file")
    scope_programmes: Optional[str] = Field(None, description="Programmes governed (e.g. B.Tech CSE)")
    scope_batches: Optional[str] = Field(None, description="Batches governed (e.g. 2023+)")
    provenance: Optional[str] = Field(None, description="Origin URL or file path description")
    retrieved_on: Optional[str] = Field(None, description="Retrieval timestamp (YYYY-MM-DD)")
    synthetic: Optional[int] = Field(0, description="Flag: 1 if synthetic/test document, 0 if official")


class RuleItem(BaseModel):
    """
    Pydantic v2 schema representing an extracted academic rule or threshold policy.
    Maps directly to rows in the SQLite rule_registry table.
    """
    model_config = ConfigDict(extra="ignore")

    rule_id: str = Field(..., description="Unique Rule Identifier (e.g. ATT-MIN-01)")
    description: Optional[str] = Field(None, description="Human readable description of policy rule")
    parameter: Optional[str] = Field(None, description="Target parameter evaluated (e.g. min_attendance_pct)")
    operator: Optional[str] = Field(None, description="Relational operator (>=, <=, ==, <, >)")
    value: Optional[str] = Field(None, description="Threshold value(s) (e.g. 75%)")
    scope_programmes: Optional[str] = Field(None, description="Applicable programmes (ALL or list)")
    scope_batches: Optional[str] = Field(None, description="Applicable student batches (ALL or 2023+)")
    effective_from: Optional[str] = Field(None, description="Rule effective start date")
    effective_to: Optional[str] = Field(None, description="Rule effective end date")
    source_doc_id: Optional[str] = Field(None, description="doc_id of origin document")
    source_section: Optional[str] = Field(None, description="Section heading or chunk reference")


# =============================================================================
# Annex C Data Entities (Students, Courses, Attendance, Results)
# =============================================================================

class StudentModel(BaseModel):
    """Student profile entity matching Annex C requirements."""
    model_config = ConfigDict(extra="ignore")

    student_id: str = Field(..., description="Student ID (Format S followed by 4 digits, e.g. S1001)")
    full_name: str = Field(..., description="Full name of student")
    programme: str = Field(..., description="Academic programme (e.g. B.Tech CSE)")
    batch_year: int = Field(..., description="Year of admission (e.g. 2023)")
    current_semester: int = Field(..., description="Semester number (1-10)")
    cgpa: float = Field(..., ge=0.0, le=10.0, description="Cumulative GPA (0.00 to 10.00)")
    active_backlogs: int = Field(0, ge=0, description="Number of active backlogs (>= 0)")
    password: Optional[str] = Field(None, description="Generated password (fullname+programme by default)")


class CourseModel(BaseModel):
    """Course entity matching Annex C requirements."""
    model_config = ConfigDict(extra="ignore")

    course_code: str = Field(..., description="Course code (e.g. CS201)")
    course_name: str = Field(..., description="Full course name")
    programme: str = Field(..., description="Target programme")
    semester: int = Field(..., description="Semester offered")
    credits: int = Field(..., description="Credits allocated")


class AttendanceModel(BaseModel):
    """Attendance record entity matching Annex C requirements."""
    model_config = ConfigDict(extra="ignore")

    student_id: str = Field(..., description="Student ID FK")
    course_code: str = Field(..., description="Course code FK")
    classes_held: int = Field(..., gt=0, description="Total classes held (> 0)")
    classes_attended: int = Field(..., ge=0, description="Classes attended by student (0 <= attended <= held)")


class ResultModel(BaseModel):
    """Academic result record entity matching Annex C requirements."""
    model_config = ConfigDict(extra="ignore")

    student_id: str = Field(..., description="Student ID FK")
    course_code: str = Field(..., description="Course code FK")
    exam_session: str = Field(..., description="Exam session (e.g. 2026-MAY)")
    exam_type: str = Field("REGULAR", description="REGULAR or SUPPLEMENTARY")
    internal_marks: int = Field(..., ge=0, description="Internal marks component")
    external_marks: int = Field(..., ge=0, description="External marks component")
    total_marks: int = Field(..., ge=0, description="Total marks (= internal + external)")
    max_marks: int = Field(100, gt=0, description="Maximum total marks")
    result: str = Field(..., description="PASS, FAIL, ABSENT, or DETAINED")


class StudentDataLoaderPayload(BaseModel):
    """Payload for importing student test dataset via JSON."""
    students: Optional[List[StudentModel]] = []
    courses: Optional[List[CourseModel]] = []
    attendance: Optional[List[AttendanceModel]] = []
    results: Optional[List[ResultModel]] = []


# =============================================================================
# Q&A API Request & Response Contracts (Section 6)
# =============================================================================

class AskRequest(BaseModel):
    """Request schema for POST /ask endpoint."""
    question: str = Field(..., description="Question asked by student or user")
    as_of_date: Optional[str] = Field(None, description="Evaluation effective date (YYYY-MM-DD), defaults to today")


class CitationItem(BaseModel):
    """Citation metadata for referenced document section."""
    doc_id: str
    title: str
    section: Optional[str] = None
    page: Optional[int] = None
    version: Optional[str] = None
    effective_from: Optional[str] = None


class ToolInvocationItem(BaseModel):
    """Audit log item for executed tools/calculations."""
    tool: str
    input: Dict[str, Any]
    output: Dict[str, Any]


class AskResponse(BaseModel):
    """Response contract for POST /ask (Section 6.1 fixed schema)."""
    trace_id: str = Field(..., description="Unique audit trace identifier")
    answer: str = Field(..., description="Answer text generated or calculated")
    answer_type: str = Field(..., description="retrieved_fact | calculated | not_found | clarification_needed | refused | conflict_flagged")
    citations: List[CitationItem] = Field(default_factory=list)
    tools_invoked: List[ToolInvocationItem] = Field(default_factory=list)
    applied_rules: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts_detected: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: Optional[str] = Field(None, description="Step-by-step reasoning or calculation explanation")
    as_of_date: str = Field(..., description="Effective evaluation date (YYYY-MM-DD)")


# =============================================================================
# Health & Status Responses
# =============================================================================

class IngestResponse(BaseModel):
    """API Response model returned by POST /ingest."""
    doc_id: str
    chunks_indexed: int
    status: str = "success"
    message: Optional[str] = None
    rules_extracted: Optional[int] = 0


class HealthResponse(BaseModel):
    """API Response model returned by GET /health."""
    status: str
    sqlite_connected: bool
    chromadb_connected: bool
    embedding_model: str
