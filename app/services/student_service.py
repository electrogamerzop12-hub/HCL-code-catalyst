"""
app/services/student_service.py
===============================================================================
Student Data Service Module.

Manages SQLite CRUD operations for Annex C entities:
- Students
- Courses
- Attendance
- Results

Handles password generation logic (fullname + programme/course by default).
===============================================================================
"""

import sqlite3
import logging
from typing import List, Optional, Dict, Any
from app.models.schemas import (
    StudentModel, CourseModel, AttendanceModel, ResultModel, StudentDataLoaderPayload
)

logger = logging.getLogger("student_service")


class StudentService:
    """Service layer for student academic data operations in SQLite."""

    @staticmethod
    def generate_password(full_name: str, programme_or_course: str) -> str:
        """
        Generates student login password requirement:
        password = full_name + programme (spaces removed, lowercase).
        """
        raw = f"{full_name}{programme_or_course}"
        return "".join(e for e in raw if e.isalnum()).lower()

    @classmethod
    def save_student(cls, conn: sqlite3.Connection, student: StudentModel) -> str:
        """Inserts or replaces a student record into SQLite students table."""
        cursor = conn.cursor()
        
        # Calculate password if not explicitly supplied
        password = student.password
        if not password:
            password = cls.generate_password(student.full_name, student.programme)

        cursor.execute("""
            INSERT OR REPLACE INTO students (
                student_id, full_name, programme, batch_year,
                current_semester, cgpa, active_backlogs, password
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            student.student_id,
            student.full_name,
            student.programme,
            student.batch_year,
            student.current_semester,
            student.cgpa,
            student.active_backlogs,
            password
        ))
        conn.commit()
        return password

    @staticmethod
    def save_course(conn: sqlite3.Connection, course: CourseModel):
        """Inserts or replaces a course record in SQLite courses table."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO courses (
                course_code, course_name, programme, semester, credits
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            course.course_code,
            course.course_name,
            course.programme,
            course.semester,
            course.credits
        ))
        conn.commit()

    @staticmethod
    def save_attendance(conn: sqlite3.Connection, attendance: AttendanceModel):
        """Inserts or replaces attendance record in SQLite attendance table."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO attendance (
                student_id, course_code, classes_held, classes_attended
            ) VALUES (?, ?, ?, ?)
        """, (
            attendance.student_id,
            attendance.course_code,
            attendance.classes_held,
            attendance.classes_attended
        ))
        conn.commit()

    @staticmethod
    def save_result(conn: sqlite3.Connection, result: ResultModel):
        """Inserts or replaces academic result in SQLite results table."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO results (
                student_id, course_code, exam_session, exam_type,
                internal_marks, external_marks, total_marks, max_marks, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.student_id,
            result.course_code,
            result.exam_session,
            result.exam_type,
            result.internal_marks,
            result.external_marks,
            result.total_marks,
            result.max_marks,
            result.result
        ))
        conn.commit()

    @classmethod
    def load_dataset(cls, conn: sqlite3.Connection, payload: StudentDataLoaderPayload) -> Dict[str, int]:
        """Loads complete student dataset (students, courses, attendance, results)."""
        counts = {"students": 0, "courses": 0, "attendance": 0, "results": 0}

        if payload.students:
            for s in payload.students:
                cls.save_student(conn, s)
                counts["students"] += 1

        if payload.courses:
            for c in payload.courses:
                cls.save_course(conn, c)
                counts["courses"] += 1

        if payload.attendance:
            for a in payload.attendance:
                cls.save_attendance(conn, a)
                counts["attendance"] += 1

        if payload.results:
            for r in payload.results:
                cls.save_result(conn, r)
                counts["results"] += 1

        return counts

    @staticmethod
    def get_student_by_id(conn: sqlite3.Connection, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves student profile by student_id."""
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_all_students(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Lists all registered students."""
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM students ORDER BY student_id").fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def authenticate_student(conn: sqlite3.Connection, student_id: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticates student with student_id and password."""
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM students WHERE student_id = ? AND password = ?", 
            (student_id, password)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_student_attendance(conn: sqlite3.Connection, student_id: str) -> List[Dict[str, Any]]:
        """Retrieves attendance records joined with course names for a given student."""
        cursor = conn.cursor()
        query = """
            SELECT a.student_id, a.course_code, c.course_name, a.classes_held, a.classes_attended,
                   ROUND((CAST(a.classes_attended AS FLOAT) / a.classes_held) * 100, 2) as attendance_pct
            FROM attendance a
            LEFT JOIN courses c ON a.course_code = c.course_code
            WHERE a.student_id = ?
        """
        rows = cursor.execute(query, (student_id,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_student_results(conn: sqlite3.Connection, student_id: str) -> List[Dict[str, Any]]:
        """Retrieves exam results joined with course names for a given student."""
        cursor = conn.cursor()
        query = """
            SELECT r.*, c.course_name
            FROM results r
            LEFT JOIN courses c ON r.course_code = c.course_code
            WHERE r.student_id = ?
        """
        rows = cursor.execute(query, (student_id,)).fetchall()
        return [dict(r) for r in rows]
