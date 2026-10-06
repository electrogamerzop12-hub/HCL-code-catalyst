"""
app/main.py
===============================================================================
FastAPI Main Application and Router.

Exposes mandatory Section 6 API contract endpoints:
- POST /ask           : Student Q&A endpoint returning grounded answers and citations.
- POST /ingest        : Multipart PDF document ingestion into ChromaDB & SQLite.
- GET  /sources       : Source Register list of all ingested documents.
- POST /load-students : Endpoint to load judge/test student dataset (Annex C).
- POST /auth/login    : Student authentication endpoint.
- GET  /health        : System diagnostic readiness check.
- GET  /audit/{trace} : Detailed audit trace logging.
===============================================================================
"""

import os
import json
import uuid
import datetime
import sqlite3
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, get_db
from app.models.schemas import (
    SourceRegisterMetadata, IngestResponse, HealthResponse, RuleItem,
    AskRequest, AskResponse, CitationItem, ToolInvocationItem,
    StudentDataLoaderPayload, StudentModel
)
from app.services.pdf_processor import PDFProcessor
from app.services.vector_store import VectorStoreService
from app.services.rule_service import RuleService
from app.services.student_service import StudentService

# Initialize logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# Global VectorStoreService instance
vector_store_service: Optional[VectorStoreService] = None

# In-memory audit log store (trace_id -> audit record)
audit_log_store: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite tables and ChromaDB vector store upon server startup."""
    global vector_store_service
    logger.info("Initializing SQLite database tables...")
    init_db()

    logger.info("Initializing persistent ChromaDB vector store & embedding model...")
    vector_store_service = VectorStoreService()

    logger.info("Application startup complete.")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Data Ingestion & Q&A Assistant Pipeline for University Student Services",
    lifespan=lifespan
)

# Enable CORS for Streamlit UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, summary="System Health Diagnostic")
async def health_check(db: sqlite3.Connection = Depends(get_db)):
    """Probes SQLite connectivity and ChromaDB client heartbeat status."""
    sqlite_ok = False
    try:
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        sqlite_ok = True
    except Exception as e:
        logger.error(f"SQLite health check failed: {e}")

    chroma_ok = vector_store_service.is_healthy() if vector_store_service else False
    overall_status = "healthy" if (sqlite_ok and chroma_ok) else "unhealthy"

    return HealthResponse(
        status=overall_status,
        sqlite_connected=sqlite_ok,
        chromadb_connected=chroma_ok,
        embedding_model=settings.EMBEDDING_MODEL_NAME
    )


@app.get("/sources", summary="Get Ingested Source Register Documents")
async def get_sources(db: sqlite3.Connection = Depends(get_db)):
    """Returns list of all ingested documents and metadata stored in source_register."""
    cursor = db.cursor()
    rows = cursor.execute("SELECT * FROM source_register ORDER BY authority_level ASC, doc_id ASC").fetchall()
    return [dict(r) for r in rows]


@app.post("/auth/login", summary="Student Password Login")
async def student_login(
    student_id: str = Form(...),
    password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """Authenticates student using student_id and password."""
    student = StudentService.authenticate_student(db, student_id, password)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Student ID or Password."
        )
    return {
        "status": "authenticated",
        "student": student
    }


@app.post("/auth/admin-login", summary="Admin User Authentication")
async def admin_login(
    username: str = Form(...),
    password: str = Form(...)
):
    """Authenticates administrative user credentials for data ingestion access."""
    try:
        u = str(username).strip()
        p = str(password).strip()

        admin_user = os.getenv("ADMIN_USERNAME", "admin").strip()
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin123").strip()

        if u.lower() == admin_user.lower() and p == admin_pass:
            return {
                "status": "authenticated",
                "role": "admin",
                "username": u
            }

        logger.warning(f"Failed admin login attempt: '{u}' / '{p}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin Username or Password."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin_login endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admin login processing error: {str(e)}"
        )


@app.post("/load-students", summary="Load Judge/Test Student Dataset")
async def load_students(
    payload: StudentDataLoaderPayload,
    db: sqlite3.Connection = Depends(get_db)
):
    """Loads student dataset (students, courses, attendance, results) into SQLite."""
    try:
        counts = StudentService.load_dataset(db, payload)
        return {
            "status": "success",
            "message": "Student dataset loaded successfully",
            "counts": counts
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load student dataset: {str(e)}"
        )


@app.post("/ask", response_model=AskResponse, summary="Ask Student Services Assistant Question")
async def ask_question(
    request: AskRequest,
    x_student_id: Optional[str] = Header(None, alias="X-Student-Id"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Q&A Endpoint (Mandatory Section 6 Contract).
    Executes compiled LangGraph agent workflow connecting Intent Classification,
    ChromaDB Vector Retrieval, Deterministic Tool Calculations, and Answer Synthesis.
    """
    from app.agent.workflow import run_student_assistant_agent

    try:
        response_dict = run_student_assistant_agent(
            question=request.question,
            student_id=x_student_id,
            as_of_date=request.as_of_date,
            db_conn=db,
            vector_service=vector_store_service
        )

        # Store in audit log registry
        trace_id = response_dict["trace_id"]
        audit_log_store[trace_id] = response_dict

        return AskResponse.model_validate(response_dict)
    except Exception as e:
        logger.error(f"LangGraph Agent execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent orchestration failure: {str(e)}"
        )


@app.get("/audit/{trace_id}", summary="Get Audit Record by Trace ID")
async def get_audit_record(trace_id: str):
    """Returns full audit trace record for a Q&A request."""
    if trace_id not in audit_log_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit trace ID '{trace_id}' not found."
        )
    return audit_log_store[trace_id]


@app.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED, summary="Ingest PDF Document")
async def ingest_document(
    file: UploadFile = File(..., description="PDF document file to process"),
    metadata: str = Form(..., description="JSON string matching Source Register metadata schema"),
    db: sqlite3.Connection = Depends(get_db)
):
    """Ingests PDF document, extracts text chunks, embeds into ChromaDB, and syncs rules to SQLite."""
    if not file.filename.endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF documents (.pdf) are supported."
        )

    parsed_rules = []
    try:
        meta_dict = json.loads(metadata)
        if "rules" in meta_dict and isinstance(meta_dict["rules"], list):
            for r in meta_dict.pop("rules"):
                parsed_rules.append(RuleItem.model_validate(r))

        source_meta = SourceRegisterMetadata.model_validate(meta_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON string format for metadata parameter: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Metadata validation error: {str(e)}"
        )

    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF file is empty."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read uploaded PDF file stream: {str(e)}"
        )

    try:
        RuleService.save_source_metadata(db, source_meta)
    except Exception as e:
        logger.error(f"Failed to record source metadata in SQLite database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while cataloging metadata: {str(e)}"
        )

    try:
        processor = PDFProcessor()
        chunks = processor.process_pdf(pdf_bytes, source_meta)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting text and chunking PDF: {str(e)}"
        )

    try:
        chunks_indexed = vector_store_service.add_chunks(chunks)
    except Exception as e:
        logger.error(f"ChromaDB indexing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error indexing chunks in vector store: {str(e)}"
        )

    try:
        rules_extracted_count = RuleService.extract_rules_from_chunks(
            conn=db,
            metadata=source_meta,
            chunks=chunks,
            structured_rules=parsed_rules
        )
    except Exception as e:
        logger.warning(f"Rule extraction warning: {e}")
        rules_extracted_count = 0

    return IngestResponse(
        doc_id=source_meta.doc_id,
        chunks_indexed=chunks_indexed,
        status="success",
        rules_extracted=rules_extracted_count
    )
