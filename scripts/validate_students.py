"""
scripts/validate_students.py
===============================================================================
Student Dataset Validation Script (Annex C & Section 4.2).

Enforces strict logical and schema constraints:
1. classes_attended <= classes_held (attendance)
2. internal_marks + external_marks == total_marks <= max_marks (results)
3. result is consistent with total marks (PASS if total >= 40 else FAIL/DETAINED)
4. student_id format (S followed by 4 digits)
5. CGPA between 0.00 and 10.00
===============================================================================
"""

import sys
import os
import json
import argparse
from typing import List, Dict, Any


def validate_student_dataset(file_path: str) -> bool:
    """Validates student JSON dataset against logical and schema constraints."""
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found at '{file_path}'")
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    violations = []
    
    # 1. Validate Students
    students = data.get("students", [])
    for s in students:
        sid = s.get("student_id", "")
        if not sid.startswith("S") or len(sid) != 5 or not sid[1:].isdigit():
            violations.append(f"Student ID '{sid}' invalid format. Must be 'S' followed by 4 digits (e.g. S1001).")
        cgpa = s.get("cgpa", 0.0)
        if not (0.0 <= cgpa <= 10.0):
            violations.append(f"Student {sid} CGPA '{cgpa}' out of valid range (0.00 - 10.00).")

    # 2. Validate Attendance
    attendance = data.get("attendance", [])
    for a in attendance:
        sid = a.get("student_id")
        ccode = a.get("course_code")
        held = a.get("classes_held", 0)
        attended = a.get("classes_attended", 0)
        if attended > held:
            violations.append(f"Attendance violation for {sid} in {ccode}: classes_attended ({attended}) > classes_held ({held}).")
        if held <= 0:
            violations.append(f"Attendance violation for {sid} in {ccode}: classes_held ({held}) must be > 0.")

    # 3. Validate Results
    results = data.get("results", [])
    for r in results:
        sid = r.get("student_id")
        ccode = r.get("course_code")
        internal = r.get("internal_marks", 0)
        external = r.get("external_marks", 0)
        total = r.get("total_marks", 0)
        max_m = r.get("max_marks", 100)
        res_str = r.get("result", "").upper()

        if internal + external != total:
            violations.append(f"Result violation for {sid} in {ccode}: internal ({internal}) + external ({external}) != total ({total}).")
        if total > max_m:
            violations.append(f"Result violation for {sid} in {ccode}: total ({total}) > max_marks ({max_m}).")
        if res_str == "PASS" and total < 40:
            violations.append(f"Result violation for {sid} in {ccode}: Marked PASS but total marks ({total}) < pass threshold (40).")

    print("\n=======================================================")
    print(f"[+] DATASET VALIDATION REPORT: {file_path}")
    print("=======================================================")
    print(f"Total Students  : {len(students)}")
    print(f"Total Courses   : {len(data.get('courses', []))}")
    print(f"Attendance Rows : {len(attendance)}")
    print(f"Result Rows     : {len(results)}")
    
    if violations:
        print(f"\n[-] FOUND {len(violations)} VIOLATIONS:")
        for v in violations:
            print(f"  - {v}")
        return False
    else:
        print("\n[+] ALL LOGICAL CONSTRAINTS PASSED CLEANLY (0 VIOLATIONS)!")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Student Dataset")
    parser.add_argument("--file", type=str, default="data/sample_students.json", help="Path to student dataset JSON")
    args = parser.parse_args()

    success = validate_student_dataset(args.file)
    sys.exit(0 if success else 1)
