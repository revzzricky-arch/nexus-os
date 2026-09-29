# ADR 002: Agent Framework - LangGraph

**Status:** Accepted
**Date:** 2026-09-29

## Context
Need durable DAG orchestration, checkpointing, human-in-loop approval gates.

## Decision
Use LangGraph with:
- PostgresSaver for checkpoint durability
- TypedDict MissionState
- Nodes: decompose, plan_dag, assign, execute_task, evaluate_task, handle_approval, replan, finalize
- Conditional edges based on task status
- interrupt_before for approval gates
- Simple topological sort MVP, no complex scheduler

## Consequences
- Durable, resumable missions
- Native approval interrupt support
- Requires learning LangGraph
- Escape hatch: run without checkpoint in dev

## Alternatives Rejected
- Custom DAG engine: too much work, no checkpoint
- Temporal: heavy, overkill for MVP
