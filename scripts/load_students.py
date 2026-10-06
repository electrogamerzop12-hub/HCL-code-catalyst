"""
scripts/load_students.py
===============================================================================
CLI Script to Load Student Datasets (Annex C Schema) into SQLite.

Usage:
    python scripts/load_students.py --file data/sample_students.json
===============================================================================
"""

import sys
import os
import json
import argparse

# Add project root directory to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, get_db_connection
from app.models.schemas import StudentDataLoaderPayload
from app.services.student_service import StudentService


def load_students_from_file(file_path: str):
    """Loads student dataset JSON file into SQLite database."""
    if not os.path.exists(file_path):
        print(f"Error: File not found at path: {file_path}")
        sys.exit(1)

    print(f"Initializing database tables...")
    init_db()

    conn = get_db_connection()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        payload = StudentDataLoaderPayload.model_validate(data)
        counts = StudentService.load_dataset(conn, payload)

        print("\n=== Dataset Load Successful ===")
        print(f"Students Loaded   : {counts['students']}")
        print(f"Courses Loaded    : {counts['courses']}")
        print(f"Attendance Loaded : {counts['attendance']}")
        print(f"Results Loaded    : {counts['results']}")
        print("===============================\n")

        # Print loaded students and generated passwords
        students = StudentService.list_all_students(conn)
        print("Loaded Student Credentials:")
        for s in students:
            print(f" - Student ID: {s['student_id']} | Name: {s['full_name']} | Password: {s['password']}")

    except Exception as e:
        print(f"Error loading student dataset: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Student Dataset into SQLite")
    parser.add_argument("--file", type=str, default="data/sample_students.json", help="Path to student JSON file")
    args = parser.parse_args()

    load_students_from_file(args.file)
