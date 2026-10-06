"""
app/agent/tools.py
===============================================================================
Deterministic Tool Definitions for LangGraph Agent.

Performs exact mathematical calculations and database queries for student data:
- Attendance percentage calculation & attendance status
- End-semester exam eligibility verification against rules
- Student academic results & marks verification
- Student profile (CGPA, active backlogs, programme) retrieval
===============================================================================
"""

import sqlite3
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("agent.tools")


def tool_get_attendance(
    conn: sqlite3.Connection, 
    student_id: str, 
    course_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: Computes student class attendance records and attendance percentage.
    
    :param conn: SQLite database connection.
    :param student_id: Student ID (e.g. S1001).
    :param course_code: Optional course code (e.g. CS201).
    :return: Dictionary containing attendance details and calculated percentage.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if course_code:
        query = """
            SELECT a.student_id, a.course_code, c.course_name, a.classes_held, a.classes_attended,
                   ROUND((CAST(a.classes_attended AS FLOAT) / a.classes_held) * 100.0, 2) as attendance_pct
            FROM attendance a
            LEFT JOIN courses c ON a.course_code = c.course_code
            WHERE a.student_id = ? AND a.course_code = ?
        """
        row = cursor.execute(query, (student_id, course_code.upper())).fetchone()
        if row:
            d = dict(row)
            return {
                "status": "success",
                "course_code": d["course_code"],
                "course_name": d["course_name"],
                "classes_held": d["classes_held"],
                "classes_attended": d["classes_attended"],
                "attendance_pct": d["attendance_pct"]
            }
        return {"status": "not_found", "message": f"No attendance record found for student {student_id} in course {course_code}"}
    else:
        query = """
            SELECT a.student_id, a.course_code, c.course_name, a.classes_held, a.classes_attended,
                   ROUND((CAST(a.classes_attended AS FLOAT) / a.classes_held) * 100.0, 2) as attendance_pct
            FROM attendance a
            LEFT JOIN courses c ON a.course_code = c.course_code
            WHERE a.student_id = ?
        """
        rows = cursor.execute(query, (student_id,)).fetchall()
        records = [dict(r) for r in rows]
        return {
            "status": "success" if records else "not_found",
            "records": records
        }


def tool_check_exam_eligibility(
    conn: sqlite3.Connection,
    student_id: str,
    course_code: str,
    required_attendance_pct: float = 75.0
) -> Dict[str, Any]:
    """
    Tool: Verifies student eligibility for end-semester exam in a specific course.
    Compares attendance percentage against required minimum threshold (75%).
    
    :return: Decision dictionary with result ('ELIGIBLE' or 'DETAINED'), calculated attendance, and applied rule.
    """
    att_res = tool_get_attendance(conn, student_id, course_code)
    
    if att_res.get("status") != "success":
        return {
            "result": "UNKNOWN",
            "eligible": False,
            "reason": f"No attendance data recorded for student {student_id} in course {course_code}."
        }

    att_pct = att_res["attendance_pct"]
    is_eligible = att_pct >= required_attendance_pct

    return {
        "result": "ELIGIBLE" if is_eligible else "DETAINED",
        "eligible": is_eligible,
        "course_code": course_code,
        "classes_held": att_res["classes_held"],
        "classes_attended": att_res["classes_attended"],
        "attendance_pct": att_pct,
        "required_threshold_pct": required_attendance_pct,
        "applied_rule": {
            "rule_id": "ATT-MIN-01",
            "parameter": "min_attendance_pct",
            "operator": ">=",
            "value": f"{required_attendance_pct}%",
            "source_doc_id": "ACAD-REG-2024"
        }
    }


def tool_get_student_results(
    conn: sqlite3.Connection,
    student_id: str,
    course_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: Retrieves exam results, internal/external marks, and pass/fail statuses.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if course_code:
        query = """
            SELECT r.*, c.course_name
            FROM results r
            LEFT JOIN courses c ON r.course_code = c.course_code
            WHERE r.student_id = ? AND r.course_code = ?
        """
        row = cursor.execute(query, (student_id, course_code.upper())).fetchone()
        return {"status": "success", "result": dict(row)} if row else {"status": "not_found"}
    else:
        query = """
            SELECT r.*, c.course_name
            FROM results r
            LEFT JOIN courses c ON r.course_code = c.course_code
            WHERE r.student_id = ?
        """
        rows = cursor.execute(query, (student_id,)).fetchall()
        return {"status": "success", "results": [dict(r) for r in rows]}


def tool_get_student_profile(
    conn: sqlite3.Connection,
    student_id: str
) -> Dict[str, Any]:
    """
    Tool: Retrieves student academic profile (programme, batch year, CGPA, backlogs).
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if row:
        return {"status": "success", "profile": dict(row)}
    return {"status": "not_found", "message": f"Student ID '{student_id}' not found."}
