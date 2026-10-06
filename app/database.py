"""
app/database.py
===============================================================================
Database Connection & Initialization Module (SQLite).

This module handles SQLite database creation, table migrations, connection management,
and provides a FastAPI dependency for database sessions.
===============================================================================
"""

import os
import sqlite3
from typing import Generator
from app.config import settings


def get_db_connection() -> sqlite3.Connection:
    """
    Creates and returns a thread-safe connection to the SQLite database.
    
    - Ensures target directory exists before connecting.
    - Sets row_factory to sqlite3.Row so query results can be accessed by column name.
    """
    # 1. Create parent directory if it doesn't already exist
    os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
    
    # 2. Establish connection to SQLite database file
    conn = sqlite3.connect(settings.SQLITE_DB_PATH, check_same_thread=False)
    
    # 3. Allow accessing query results as dictionary-like Row objects (row['column_name'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes SQLite tables according to exact schema specifications:
    
    1. rule_registry   - Stores extracted threshold rules (CGPA, attendance, credits).
    2. source_register - Catalogs uploaded document metadata, authority levels, and dates.
    """
    # Ensure directory path exists
    os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # -------------------------------------------------------------------------
    # 1. Create Table: rule_registry
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_registry (
            rule_id TEXT PRIMARY KEY,
            description TEXT,
            parameter TEXT,
            operator TEXT,
            value TEXT,
            scope_programmes TEXT,
            scope_batches TEXT,
            effective_from TEXT,
            effective_to TEXT,
            source_doc_id TEXT,
            source_section TEXT
        );
    """)

    # -------------------------------------------------------------------------
    # 2. Create Table: source_register
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_register (
            doc_id TEXT PRIMARY KEY,
            title TEXT,
            issuer TEXT,
            authority_level INTEGER,
            doc_type TEXT,
            version TEXT,
            effective_from TEXT,
            effective_to TEXT,
            supersedes TEXT,
            scope_programmes TEXT,
            scope_batches TEXT,
            provenance TEXT,
            retrieved_on TEXT,
            synthetic INTEGER
        );
    """)

    # -------------------------------------------------------------------------
    # 3. Create Table: students (Annex C)
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            full_name TEXT,
            programme TEXT,
            batch_year INTEGER,
            current_semester INTEGER,
            cgpa REAL,
            active_backlogs INTEGER,
            password TEXT
        );
    """)

    # -------------------------------------------------------------------------
    # 4. Create Table: courses (Annex C)
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            course_code TEXT PRIMARY KEY,
            course_name TEXT,
            programme TEXT,
            semester INTEGER,
            credits INTEGER
        );
    """)

    # -------------------------------------------------------------------------
    # 5. Create Table: attendance (Annex C)
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            student_id TEXT,
            course_code TEXT,
            classes_held INTEGER,
            classes_attended INTEGER,
            PRIMARY KEY (student_id, course_code),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (course_code) REFERENCES courses(course_code)
        );
    """)

    # -------------------------------------------------------------------------
    # 6. Create Table: results (Annex C)
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            student_id TEXT,
            course_code TEXT,
            exam_session TEXT,
            exam_type TEXT,
            internal_marks INTEGER,
            external_marks INTEGER,
            result TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (course_code) REFERENCES courses(course_code)
        );
    """)

    # -------------------------------------------------------------------------
    # 7. Create Table: audit_log (Q&A Audit Traces)
    # -------------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            trace_id TEXT PRIMARY KEY,
            question TEXT,
            student_id TEXT,
            as_of_date TEXT,
            answer_type TEXT,
            answer TEXT,
            explanation TEXT,
            timestamp TEXT,
            raw_payload TEXT
        );
    """)

    conn.commit()
    conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency function to manage database connection lifecycle per HTTP request.
    Automatically closes the database connection when request processing completes.
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
