"""
DAG Tests - Phase 2B-3
Valid DAG, topological ordering, layers, cycle detection, missing dependency
"""

import pytest

from app.core.dag import validate_and_plan_dag, DAGValidationError, detect_cycle, topological_sort, compute_layers


def test_valid_dag_simple():
    tasks = [
        {"id": "task_1", "title": "Task 1", "dependencies": []},
        {"id": "task_2", "title": "Task 2", "dependencies": ["task_1"]},
        {"id": "task_3", "title": "Task 3", "dependencies": ["task_2"]},
    ]

    result = validate_and_plan_dag(tasks)

    assert len(result.nodes) == 3
    assert len(result.edges) == 2
    assert result.topological_order == ["task_1", "task_2", "task_3"]
    assert result.layers["task_1"] == 0
    assert result.layers["task_2"] == 1
    assert result.layers["task_3"] == 2
    assert result.has_cycle is False


def test_valid_dag_parallel():
    tasks = [
        {"id": "a", "title": "A", "dependencies": []},
        {"id": "b", "title": "B", "dependencies": []},
        {"id": "c", "title": "C", "dependencies": ["a", "b"]},
    ]

    result = validate_and_plan_dag(tasks)

    assert len(result.nodes) == 3
    assert result.layers["a"] == 0
    assert result.layers["b"] == 0
    assert result.layers["c"] == 1
    # Topological order deterministic: a, b, c (sorted)
    assert result.topological_order[0] in ["a", "b"]
    assert result.topological_order[2] == "c"


def test_topological_ordering_deterministic():
    tasks = [
        {"id": "c", "title": "C", "dependencies": ["a"]},
        {"id": "b", "title": "B", "dependencies": ["a"]},
        {"id": "a", "title": "A", "dependencies": []},
    ]

    result1 = validate_and_plan_dag(tasks)
    result2 = validate_and_plan_dag(tasks)

    # Deterministic ordering
    assert result1.topological_order == result2.topological_order
    assert result1.topological_order == ["a", "b", "c"]  # sorted for determinism


def test_layers_for_3d_ui():
    tasks = [
        {"id": "t1", "title": "T1", "dependencies": []},
        {"id": "t2", "title": "T2", "dependencies": ["t1"]},
        {"id": "t3", "title": "T3", "dependencies": ["t1"]},
        {"id": "t4", "title": "T4", "dependencies": ["t2", "t3"]},
    ]

    result = validate_and_plan_dag(tasks)

    assert result.layers["t1"] == 0
    assert result.layers["t2"] == 1
    assert result.layers["t3"] == 1
    assert result.layers["t4"] == 2


def test_cycle_detection():
    tasks = [
        {"id": "a", "title": "A", "dependencies": ["c"]},
        {"id": "b", "title": "B", "dependencies": ["a"]},
        {"id": "c", "title": "C", "dependencies": ["b"]},
    ]

    with pytest.raises(DAGValidationError) as exc_info:
        validate_and_plan_dag(tasks)

    assert "Cycle" in str(exc_info.value.message)
    assert exc_info.value.details.get("cycle") is not None


def test_cycle_detection_direct():
    task_ids = ["a", "b", "c"]
    dependencies = {"a": ["c"], "b": ["a"], "c": ["b"]}

    cycle = detect_cycle(task_ids, dependencies)
    assert cycle is not None
    assert len(cycle) >= 3


def test_missing_dependency():
    tasks = [
        {"id": "a", "title": "A", "dependencies": []},
        {"id": "b", "title": "B", "dependencies": ["missing_task"]},
    ]

    with pytest.raises(DAGValidationError) as exc_info:
        validate_and_plan_dag(tasks)

    assert "missing" in exc_info.value.message.lower()
    assert exc_info.value.details["missing_dependency"] == "missing_task"


def test_duplicate_task_ids():
    tasks = [
        {"id": "a", "title": "A", "dependencies": []},
        {"id": "a", "title": "A duplicate", "dependencies": []},
    ]

    with pytest.raises(DAGValidationError) as exc_info:
        validate_and_plan_dag(tasks)

    assert "Duplicate" in exc_info.value.message


def test_empty_dag():
    tasks = []
    result = validate_and_plan_dag(tasks)

    assert result.nodes == []
    assert result.edges == []
    assert result.topological_order == []


def test_complex_dag():
    tasks = [
        {"id": "research", "title": "Research", "dependencies": []},
        {"id": "design", "title": "Design", "dependencies": ["research"]},
        {"id": "implement", "title": "Implement", "dependencies": ["design"]},
        {"id": "test", "title": "Test", "dependencies": ["implement"]},
        {"id": "document", "title": "Document", "dependencies": ["test"]},
        {"id": "review", "title": "Review", "dependencies": ["document"]},
    ]

    result = validate_and_plan_dag(tasks)

    assert len(result.nodes) == 6
    assert result.topological_order == ["research", "design", "implement", "test", "document", "review"]
    assert result.layers["research"] == 0
    assert result.layers["review"] == 5


def test_dag_deterministic_ordering():
    # Test that same input always gives same output
    tasks = [
        {"id": "z", "title": "Z", "dependencies": []},
        {"id": "a", "title": "A", "dependencies": []},
        {"id": "m", "title": "M", "dependencies": ["a", "z"]},
    ]

    results = [validate_and_plan_dag(tasks) for _ in range(5)]

    for r in results[1:]:
        assert r.topological_order == results[0].topological_order
        assert r.layers == results[0].layers
        assert r.edges == results[0].edges


def test_topological_sort_function():
    task_ids = ["a", "b", "c"]
    dependencies = {"a": [], "b": ["a"], "c": ["b"]}

    order = topological_sort(task_ids, dependencies)
    assert order == ["a", "b", "c"]


def test_compute_layers_function():
    task_ids = ["a", "b", "c"]
    dependencies = {"a": [], "b": ["a"], "c": ["a", "b"]}
    topo = ["a", "b", "c"]

    layers = compute_layers(task_ids, dependencies, topo)
    assert layers["a"] == 0
    assert layers["b"] == 1
    assert layers["c"] == 2
