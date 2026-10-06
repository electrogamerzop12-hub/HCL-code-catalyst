"""
app/services/precedence_engine.py
===============================================================================
Annex A Source Precedence & Conflict Resolution Engine.

Implements the official 5-step resolution policy when university documents disagree:
1. Applicability Filtering (as_of_date, effective_from, effective_to, programme/batch scope)
2. Explicit Supersession (supersedes clause at authority levels 1 & 2)
3. Authority Level Ranking (Level 1 Statutes > Level 2 Circulars > Level 3 Department > Level 4 FAQs > Level 5 Unofficial)
4. Recency Priority (Latest effective_from date wins for equal authority levels)
5. Unresolved Conflict Detection (Flags conflicts_detected array & triggers conflict_flagged answer_type)
===============================================================================
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("precedence_engine")


class PrecedenceEngine:
    """
    Evaluates Annex A Precedence Rules to resolve document conflicts and determine 
    winning policy sources.
    """

    @staticmethod
    def _normalize_date(date_str: Optional[str]) -> Optional[str]:
        """Converts YYYY/MM/DD to YYYY-MM-DD for accurate ISO date string comparisons."""
        if not date_str:
            return None
        return str(date_str).strip().replace("/", "-")

    @classmethod
    def is_document_applicable(
        cls, 
        doc: Dict[str, Any], 
        as_of_date: str, 
        student_programme: Optional[str] = None, 
        student_batch: Optional[int] = None
    ) -> bool:
        """
        Step 1: Evaluates document applicability based on effective dates and scope.
        - effective_from <= as_of_date
        - effective_to is empty or >= as_of_date
        - scope_programmes covers student or is 'ALL'
        """
        as_of = cls._normalize_date(as_of_date) or "2026-10-06"
        eff_from = cls._normalize_date(doc.get("effective_from"))
        eff_to = cls._normalize_date(doc.get("effective_to"))

        # 1. Date Applicability Check
        if eff_from and eff_from > as_of:
            logger.info(f"Doc {doc.get('doc_id')} excluded: Not yet effective on {as_of} (starts {eff_from})")
            return False

        if eff_to and eff_to != "" and eff_to < as_of:
            logger.info(f"Doc {doc.get('doc_id')} excluded: Expired prior to {as_of} (ended {eff_to})")
            return False

        # 2. Programme Scope Check
        scope_prog = doc.get("scope_programmes")
        if scope_prog and scope_prog.upper() != "ALL" and student_programme:
            progs = [p.strip().upper() for p in scope_prog.split(",")]
            if student_programme.upper() not in progs and "ALL" not in progs:
                logger.info(f"Doc {doc.get('doc_id')} excluded: Programme scope '{scope_prog}' does not cover '{student_programme}'")
                return False

        return True

    @classmethod
    def resolve_precedence(
        cls, 
        docs: List[Dict[str, Any]], 
        as_of_date: str,
        student_programme: Optional[str] = None,
        student_batch: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes full Annex A 5-step conflict resolution algorithm on retrieved document candidates.
        """
        if not docs:
            return {
                "winning_doc": None,
                "applicable_docs": [],
                "conflicts_detected": [],
                "conflict_flagged": False,
                "explanation": "No candidate documents available."
            }

        # Step 1: Filter Applicable Documents by Date and Scope
        applicable = [
            d for d in docs 
            if cls.is_document_applicable(d, as_of_date, student_programme, student_batch)
        ]

        if not applicable:
            # Fallback to un-filtered docs if date filtering yields 0 matches
            applicable = docs

        # Step 2: Handle Explicit Supersession (Authority Levels 1 & 2 only)
        superseded_ids = set()
        for d in applicable:
            doc_id = d.get("doc_id")
            auth = int(d.get("authority_level", 5))
            supersedes_clause = d.get("supersedes")
            if supersedes_clause and auth in (1, 2):
                for s in supersedes_clause.split(";"):
                    clean_id = s.split("#")[0].strip()
                    # Prevent self-supersession bug (doc_id cannot supersede itself)
                    if clean_id and clean_id != doc_id:
                        superseded_ids.add(clean_id)
                        logger.info(f"Doc '{doc_id}' explicitly supersedes '{clean_id}'")

        # Filter out superseded documents
        active_docs = [d for d in applicable if d.get("doc_id") not in superseded_ids]
        if not active_docs:
            active_docs = applicable

        # Step 3 & 4: Rank by Authority Level (1-5) and Recency (effective_from)
        ranked_docs = sorted(
            active_docs, 
            key=lambda d: (int(d.get("authority_level", 5)), cls._normalize_date(d.get("effective_from")) or ""), 
            reverse=False
        )

        valid_governance_docs = [d for d in ranked_docs if int(d.get("authority_level", 5)) < 5]
        if not valid_governance_docs:
            valid_governance_docs = ranked_docs

        winning_doc = valid_governance_docs[0]

        # Step 5: Check for Unresolved Conflicts
        conflicts = []
        conflict_flagged = False

        if len(valid_governance_docs) > 1:
            top_auth = int(winning_doc.get("authority_level", 5))
            second_doc = valid_governance_docs[1]
            second_auth = int(second_doc.get("authority_level", 5))

            if top_auth == second_auth and cls._normalize_date(winning_doc.get("effective_from")) == cls._normalize_date(second_doc.get("effective_from")):
                if winning_doc.get("doc_id") != second_doc.get("doc_id"):
                    conflict_flagged = True
                    conflicts.append({
                        "doc_id_1": winning_doc.get("doc_id"),
                        "doc_id_2": second_doc.get("doc_id"),
                        "authority_level": top_auth,
                        "description": f"Unresolved conflict between {winning_doc.get('doc_id')} and {second_doc.get('doc_id')}."
                    })

        explanation = (
            f"Winning Document: '{winning_doc.get('doc_id')}' (Authority Level {winning_doc.get('authority_level')}, "
            f"Effective: {winning_doc.get('effective_from')})."
        )

        return {
            "winning_doc": winning_doc,
            "applicable_docs": active_docs,
            "superseded_ids": list(superseded_ids),
            "conflicts_detected": conflicts,
            "conflict_flagged": conflict_flagged,
            "explanation": explanation
        }
