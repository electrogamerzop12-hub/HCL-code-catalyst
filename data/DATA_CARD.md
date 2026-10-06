# Annex E — Synthetic Data Card

## 1. Data Purpose & Domain Scope
This synthetic dataset simulates university academic, course, attendance, and examination result records for evaluating the AI-Powered University Student Services Assistant.

- **Primary Goal**: Validate deterministic tool calculations (attendance %, CGPA eligibility, backlog counts) and schema constraint enforcement.
- **Privacy Assurance**: Contains ZERO real student personal data. All names, student IDs, and marks are synthetically generated.

---

## 2. Generation Methodology & Tools
- **Generator Tools**: Custom Python synthetic generator scripts & LLM prompt templates (`data/sample_students.json`).
- **Schema Enforcement**: Pydantic v2 schemas (`StudentModel`, `CourseModel`, `AttendanceModel`, `ResultModel`).
- **Validation Execution**: Enforced via `scripts/validate_students.py`.

---

## 3. Row Counts & Distribution

| Table | Total Rows | Target Scope |
| :--- | :--- | :--- |
| **Students** | 5 (Expandable to 30+) | B.Tech CSE, B.Tech ECE (Batches 2022, 2023) |
| **Courses** | 3 (Expandable to 6+) | CS201, CS202, EC301 |
| **Attendance** | 4 records | Classes held range: 40 - 42 |
| **Results** | 2 records | Regular exam session 2026-MAY |

---

## 4. Edge Cases Included Deliberately
1. **Attendance Exactly at Threshold (75.0%)**: Tests boundary condition for exam eligibility (`ELIGIBLE`).
2. **Attendance One Class Below Threshold (< 75.0%)**: Tests boundary condition for detainment (`DETAINED`).
3. **Active Backlogs (1 or 2)**: Tests placement and supplementary eligibility tools.
4. **Pass / Fail Component Boundaries**: Tests mark total validation (`internal_marks + external_marks == total_marks`).

---

## 5. Constraint Validation Checks & Results
Executed via `python scripts/validate_students.py`:
- `classes_attended <= classes_held`: **0 Violations**
- `internal + external == total <= max`: **0 Violations**
- `result` consistent with marks: **0 Violations**
- `student_id` format (`S` + 4 digits): **0 Violations**
