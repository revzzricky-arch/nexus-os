"""
LangGraph Graph - Phase 2B-3 Supervisor + LangGraph Runtime Foundation

Graph structure:
decompose → plan_dag → assign → execute_task → finalize

Execution must support multiple independent tasks conceptually, but keep actual Phase 2B-3 execution safe and deterministic.

Checkpoint abstraction: uses InMemoryCheckpoint for Phase 2B-3, Postgres deferred (see checkpoint.py and ADR 015)
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from app.core.langgraph.state import MissionState
from app.core.langgraph.nodes import (
    decompose_node,
    plan_dag_node,
    assign_node,
    execute_task_node,
    finalize_node,
)


def _route_after_decompose(state: MissionState) -> str:
    if state.get("error") or state.get("status") == "failed":
        return "finalize"
    return "plan_dag"


def _route_after_plan_dag(state: MissionState) -> str:
    if state.get("error") or state.get("status") == "failed":
        return "finalize"
    return "assign"


def _route_after_assign(state: MissionState) -> str:
    if state.get("error") or state.get("status") == "failed":
        return "finalize"
    return "execute_task"


def _route_after_execute(state: MissionState) -> str:
    # Always go to finalize in Phase 2B-3
    # Future: could route to evaluate_task or handle_approval
    return "finalize"


def create_mission_graph(checkpointer: Optional[Any] = None):
    """
    Create mission execution graph
    - Nodes: decompose, plan_dag, assign, execute_task, finalize
    - Edges: decompose→plan_dag→assign→execute_task→finalize
    - Supports failure path: any node can route to finalize on error
    - Checkpointing: optional, uses abstraction, InMemory for Phase 2B-3

    Args:
        checkpointer: Optional LangGraph checkpointer (e.g., MemorySaver, PostgresSaver)
                     For Phase 2B-3, we use no checkpointer by default (deterministic test impl)
                     Checkpoint abstraction is isolated behind interface in checkpoint.py
    """
    graph = StateGraph(MissionState)

    # Add nodes
    graph.add_node("decompose", decompose_node)
    graph.add_node("plan_dag", plan_dag_node)
    graph.add_node("assign", assign_node)
    graph.add_node("execute_task", execute_task_node)
    graph.add_node("finalize", finalize_node)

    # Set entry point
    graph.set_entry_point("decompose")

    # Add conditional edges for failure handling
    graph.add_conditional_edges(
        "decompose",
        _route_after_decompose,
        {"plan_dag": "plan_dag", "finalize": "finalize"},
    )

    graph.add_conditional_edges(
        "plan_dag",
        _route_after_plan_dag,
        {"assign": "assign", "finalize": "finalize"},
    )

    graph.add_conditional_edges(
        "assign",
        _route_after_assign,
        {"execute_task": "execute_task", "finalize": "finalize"},
    )

    graph.add_conditional_edges(
        "execute_task",
        _route_after_execute,
        {"finalize": "finalize"},
    )

    # Finalize → END
    graph.add_edge("finalize", END)

    # Compile with optional checkpointer
    # For Phase 2B-3, we compile without checkpointer for simplicity and determinism
    # Checkpointing can be added cleanly via checkpointer param
    if checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        compiled = graph.compile()

    return compiled


def get_mission_graph():
    """Get compiled mission graph without checkpointer (deterministic for tests)"""
    return create_mission_graph()


# For testing: graph with memory saver (LangGraph's built-in in-memory checkpointer)
def get_mission_graph_with_memory_checkpointer():
    """
    Get graph with LangGraph's MemorySaver for checkpoint testing
    This is different from our checkpoint abstraction - it's LangGraph's own
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver

        memory = MemorySaver()
        return create_mission_graph(checkpointer=memory)
    except ImportError:
        # Fallback to no checkpointer if MemorySaver not available
        return create_mission_graph()
