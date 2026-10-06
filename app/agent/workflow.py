"""
app/agent/workflow.py
===============================================================================
LangGraph Workflow Graph Construction.

Assembles and compiles the StateGraph connecting:
1. Intent Classification Router
2. Vector Retrieval (ChromaDB)
3. Deterministic Tools Execution (SQLite Calculations)
4. Answer Synthesis & Contract Formatting
===============================================================================
"""

import uuid
import datetime
import sqlite3
import logging
from typing import Dict, Any, Optional

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    END = "END"

from app.agent.nodes import (
    AgentState,
    node_classify_intent,
    node_vector_search,
    node_execute_tools,
    node_synthesize_answer
)
try:
    from app.services.vector_store import VectorStoreService
except ImportError:
    VectorStoreService = Any  # type: ignore

logger = logging.getLogger("agent.workflow")


def build_agent_graph():
    """Constructs compiled LangGraph StateGraph (or fallback node chain)."""
    if LANGGRAPH_AVAILABLE:
        workflow = StateGraph(AgentState)

        # 1. Add Execution Nodes
        workflow.add_node("classify_intent", node_classify_intent)
        workflow.add_node("vector_search", node_vector_search)
        workflow.add_node("execute_tools", node_execute_tools)
        workflow.add_node("synthesize_answer", node_synthesize_answer)

        # 2. Set Entry Point and Edges
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "vector_search")
        workflow.add_edge("vector_search", "execute_tools")
        workflow.add_edge("execute_tools", "synthesize_answer")
        workflow.add_edge("synthesize_answer", END)

        return workflow.compile()
    else:
        # Fallback sequential node chain for environment without langgraph package
        class FallbackGraph:
            def invoke(self, state: AgentState) -> AgentState:
                s = node_classify_intent(state)
                s = node_vector_search(s)
                s = node_execute_tools(s)
                s = node_synthesize_answer(s)
                return s
        return FallbackGraph()


# Global Compiled LangGraph Executable Instance
agent_app = build_agent_graph()


def run_student_assistant_agent(
    question: str,
    student_id: Optional[str] = None,
    as_of_date: Optional[str] = None,
    db_conn: Optional[sqlite3.Connection] = None,
    vector_service: Optional[VectorStoreService] = None
) -> Dict[str, Any]:
    """
    High-level entrypoint for running the LangGraph agent workflow.
    
    :param question: Natural language query from student or user.
    :param student_id: Optional authenticated student ID.
    :param as_of_date: Effective date (YYYY-MM-DD).
    :param db_conn: Active SQLite connection.
    :param vector_service: Active VectorStoreService instance.
    :return: Structured response matching Section 6.1 contract JSON schema.
    """
    trace_id = uuid.uuid4().hex[:8]
    effective_date = as_of_date or datetime.date.today().isoformat()

    # Initial State Payload
    initial_state: AgentState = {
        "question": question,
        "student_id": student_id,
        "as_of_date": effective_date,
        "trace_id": trace_id,
        "question_type": "policy_fact",
        "target_course_code": None,
        "db_conn": db_conn,
        "vector_service": vector_service,
        "student_profile": None,
        "retrieved_chunks": [],
        "citations": [],
        "tools_invoked": [],
        "applied_rules": [],
        "conflicts_detected": [],
        "answer": "",
        "answer_type": "retrieved_fact",
        "explanation": None
    }

    # Execute LangGraph Workflow State Transition
    final_state = agent_app.invoke(initial_state)

    # Return response payload matching Section 6.1 contract
    return {
        "trace_id": final_state["trace_id"],
        "answer": final_state["answer"],
        "answer_type": final_state["answer_type"],
        "citations": final_state["citations"],
        "tools_invoked": final_state["tools_invoked"],
        "applied_rules": final_state["applied_rules"],
        "conflicts_detected": final_state["conflicts_detected"],
        "explanation": final_state["explanation"],
        "as_of_date": final_state["as_of_date"]
    }
