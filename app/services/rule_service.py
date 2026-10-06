"""
app/services/rule_service.py
===============================================================================
Rule Registry and Source Register Service Module.

Manages SQLite relational database storage for source document metadata
and extracts/persists academic rules (CGPA thresholds, attendance %, credit requirements).
===============================================================================
"""

import re
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from app.models.schemas import SourceRegisterMetadata, RuleItem

logger = logging.getLogger("rule_service")


class RuleService:
    """
    Service layer providing database CRUD operations for source_register and rule_registry.
    Includes deterministic rule pattern extraction engine.
    """

    @staticmethod
    def save_source_metadata(conn: sqlite3.Connection, metadata: SourceRegisterMetadata):
        """
        Inserts or updates document governance record in source_register table.
        
        :param conn: SQLite database connection.
        :param metadata: Validated SourceRegisterMetadata object.
        """
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO source_register (
                doc_id, title, issuer, authority_level, doc_type, version,
                effective_from, effective_to, supersedes, scope_programmes,
                scope_batches, provenance, retrieved_on, synthetic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.doc_id,
            metadata.title,
            metadata.issuer,
            metadata.authority_level,
            metadata.doc_type,
            metadata.version,
            metadata.effective_from,
            metadata.effective_to,
            metadata.supersedes,
            metadata.scope_programmes,
            metadata.scope_batches,
            metadata.provenance,
            metadata.retrieved_on,
            metadata.synthetic
        ))
        conn.commit()

    @staticmethod
    def save_rule(conn: sqlite3.Connection, rule: RuleItem):
        """
        Inserts or updates a single policy rule record in rule_registry table.
        
        :param conn: SQLite database connection.
        :param rule: Validated RuleItem object.
        """
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO rule_registry (
                rule_id, description, parameter, operator, value,
                scope_programmes, scope_batches, effective_from, effective_to,
                source_doc_id, source_section
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule.rule_id,
            rule.description,
            rule.parameter,
            rule.operator,
            rule.value,
            rule.scope_programmes,
            rule.scope_batches,
            rule.effective_from,
            rule.effective_to,
            rule.source_doc_id,
            rule.source_section
        ))
        conn.commit()

    @classmethod
    def sync_rules(cls, conn: sqlite3.Connection, rules: List[RuleItem]) -> int:
        """
        Batch saves multiple rules into rule_registry table.
        
        :param conn: SQLite database connection.
        :param rules: List of RuleItem objects.
        :return: Count of rules saved.
        """
        count = 0
        for rule in rules:
            cls.save_rule(conn, rule)
            count += 1
        return count

    @classmethod
    def extract_rules_from_chunks(
        cls,
        conn: sqlite3.Connection,
        metadata: SourceRegisterMetadata,
        chunks: List[Dict[str, Any]],
        structured_rules: Optional[List[RuleItem]] = None
    ) -> int:
        """
        Scans text chunks for numeric threshold policy rules (CGPA, attendance %, credits)
        and inserts extracted entries into rule_registry table.
        
        :param conn: SQLite database connection.
        :param metadata: Document metadata object.
        :param chunks: List of extracted text chunks.
        :param structured_rules: Optional list of pre-structured rules passed in request.
        :return: Total count of rules saved to database.
        """
        rules_to_save: List[RuleItem] = []

        # Include structured rules if passed explicitly
        if structured_rules:
            rules_to_save.extend(structured_rules)

        # Run pattern extraction engine across text chunks
        extracted_from_text = cls._extract_threshold_rules(metadata, chunks)
        rules_to_save.extend(extracted_from_text)

        # Persist extracted rules into SQLite
        return cls.sync_rules(conn, rules_to_save)

    @staticmethod
    def _extract_threshold_rules(metadata: SourceRegisterMetadata, chunks: List[Dict[str, Any]]) -> List[RuleItem]:
        """
        Internal Regex Pattern Matching Engine.
        Identifies statements defining CGPA thresholds, attendance requirements, and minimum credit counts.
        """
        extracted = []
        rule_counter = 1

        # Regular expression patterns for common academic rule structures
        patterns = [
            (r'(CGPA|SGPA|GPA)\s*(>=|>|<=|<|=|is at least|minimum of)\s*([\d\.]+)', 'cgpa'),
            (r'(attendance)\s*(>=|>|<=|<|=|is at least|minimum of)\s*([\d\.]+%?)', 'attendance'),
            (r'(credits?)\s*(>=|>|<=|<|=|is at least|minimum of)\s*(\d+)', 'credits'),
            (r'minimum\s+(\d+%?)\s+(attendance)', 'attendance_alt')
        ]

        for chunk in chunks:
            text = chunk["text"]
            chunk_id = chunk["id"]

            for pattern, param_type in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    rule_id = f"RULE-{metadata.doc_id}-{rule_counter}"
                    rule_counter += 1

                    if param_type in ('cgpa', 'attendance', 'credits'):
                        param = groups[0].lower()
                        op_raw = groups[1].lower()
                        val = groups[2]

                        # Normalize operator strings into standard symbols
                        operator = ">="
                        if "less" in op_raw or "<" in op_raw:
                            operator = "<=" if ("=" in op_raw or "at most" in op_raw) else "<"
                        elif "equal" in op_raw or "=" in op_raw:
                            operator = "=="

                        extracted.append(RuleItem(
                            rule_id=rule_id,
                            description=f"Automated rule extracted from text: {match.group(0)}",
                            parameter=param,
                            operator=operator,
                            value=val,
                            scope_programmes=metadata.scope_programmes,
                            scope_batches=metadata.scope_batches,
                            effective_from=metadata.effective_from,
                            effective_to=metadata.effective_to,
                            source_doc_id=metadata.doc_id,
                            source_section=chunk_id
                        ))
                    elif param_type == 'attendance_alt':
                        val = groups[0]
                        extracted.append(RuleItem(
                            rule_id=rule_id,
                            description=f"Minimum attendance policy: {match.group(0)}",
                            parameter="attendance",
                            operator=">=",
                            value=val,
                            scope_programmes=metadata.scope_programmes,
                            scope_batches=metadata.scope_batches,
                            effective_from=metadata.effective_from,
                            effective_to=metadata.effective_to,
                            source_doc_id=metadata.doc_id,
                            source_section=chunk_id
                        ))

        return extracted
