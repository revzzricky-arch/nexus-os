"""
DAG Planning Utility - Phase 2B-3
Dependency validation, cycle detection, topological ordering, task layers for 3D UI, deterministic ordering, clear errors
"""

from typing import List, Dict, Set, Tuple, Optional
import uuid
from collections import defaultdict, deque
from pydantic import BaseModel, Field


class DAGValidationError(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class TaskNode(BaseModel):
    id: str  # task id or temp id
    title: str
    dependencies: List[str] = Field(default_factory=list)


class DAGResult(BaseModel):
    nodes: List[str]  # ordered node ids
    edges: List[Dict[str, str]]  # {from, to}
    layers: Dict[str, int]  # node_id -> layer
    topological_order: List[str]
    has_cycle: bool = False


def validate_dependencies(task_ids: Set[str], dependencies: Dict[str, List[str]]) -> None:
    """
    Validate that all dependencies exist in task_ids
    """
    for task_id, deps in dependencies.items():
        for dep in deps:
            if dep not in task_ids:
                raise DAGValidationError(
                    f"Task {task_id} depends on missing task {dep}",
                    details={"task_id": task_id, "missing_dependency": dep, "available": list(task_ids)},
                )


def detect_cycle(task_ids: List[str], dependencies: Dict[str, List[str]]) -> Optional[List[str]]:
    """
    Detect cycle using DFS, returns cycle path if found, None if no cycle
    Deterministic ordering
    """
    # Build adjacency list
    graph = defaultdict(list)
    for task_id in task_ids:
        for dep in dependencies.get(task_id, []):
            graph[dep].append(task_id)  # dep -> task_id edge

    # Deterministic: sort neighbors
    for k in graph:
        graph[k] = sorted(graph[k])

    visited = set()
    rec_stack = set()
    parent = {}

    def dfs(node: str) -> Optional[List[str]]:
        visited.add(node)
        rec_stack.add(node)

        for neighbor in sorted(graph.get(node, [])):
            if neighbor not in visited:
                parent[neighbor] = node
                cycle = dfs(neighbor)
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                # Found cycle, reconstruct path
                cycle_path = [neighbor]
                cur = node
                while cur != neighbor and cur in parent:
                    cycle_path.append(cur)
                    cur = parent[cur]
                cycle_path.append(neighbor)
                cycle_path.reverse()
                return cycle_path

        rec_stack.remove(node)
        return None

    for node in sorted(task_ids):
        if node not in visited:
            parent[node] = None
            cycle = dfs(node)
            if cycle:
                return cycle

    return None


def topological_sort(task_ids: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
    """
    Kahn's algorithm for topological ordering, deterministic
    """
    # Build graph and in-degree
    in_degree = {tid: 0 for tid in task_ids}
    graph = defaultdict(list)

    for task_id in task_ids:
        for dep in dependencies.get(task_id, []):
            graph[dep].append(task_id)
            in_degree[task_id] += 1

    # Deterministic: use sorted queue
    queue = deque(sorted([tid for tid in task_ids if in_degree[tid] == 0]))
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)

        for neighbor in sorted(graph.get(node, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

        # Keep queue sorted for determinism
        queue = deque(sorted(queue))

    if len(result) != len(task_ids):
        # Cycle detected
        cycle = detect_cycle(task_ids, dependencies)
        raise DAGValidationError(
            f"Cycle detected in DAG, topological sort failed",
            details={"cycle": cycle, "task_ids": task_ids},
        )

    return result


def compute_layers(task_ids: List[str], dependencies: Dict[str, List[str]], topo_order: List[str]) -> Dict[str, int]:
    """
    Compute layers for 3D UI: layer 0 = no dependencies, layer increases with dependency depth
    Deterministic
    """
    layers = {}

    for task_id in topo_order:
        deps = dependencies.get(task_id, [])
        if not deps:
            layers[task_id] = 0
        else:
            # Layer = max dependency layer + 1
            max_dep_layer = max(layers.get(dep, 0) for dep in deps)
            layers[task_id] = max_dep_layer + 1

    return layers


def validate_and_plan_dag(
    tasks: List[Dict],
) -> DAGResult:
    """
    Main entry: validate and plan DAG from tasks
    tasks: list of dicts with id, title, dependencies
    Returns DAGResult with nodes, edges, layers, topological_order
    """
    if not tasks:
        return DAGResult(nodes=[], edges=[], layers={}, topological_order=[], has_cycle=False)

    # Extract task ids
    task_ids = [t["id"] for t in tasks]
    task_ids_set = set(task_ids)

    # Check duplicate ids
    if len(task_ids) != len(task_ids_set):
        raise DAGValidationError("Duplicate task ids found", details={"task_ids": task_ids})

    # Build dependencies map
    dependencies = {}
    for t in tasks:
        dependencies[t["id"]] = t.get("dependencies", [])

    # Validate dependencies exist
    validate_dependencies(task_ids_set, dependencies)

    # Detect cycle
    cycle = detect_cycle(task_ids, dependencies)
    if cycle:
        raise DAGValidationError(f"Cycle detected: {' -> '.join(cycle)}", details={"cycle": cycle})

    # Topological sort
    topo_order = topological_sort(task_ids, dependencies)

    # Compute layers
    layers = compute_layers(task_ids, dependencies, topo_order)

    # Build edges
    edges = []
    for task_id in task_ids:
        for dep in dependencies.get(task_id, []):
            edges.append({"from": dep, "to": task_id})

    # Deterministic ordering for edges
    edges = sorted(edges, key=lambda e: (e["from"], e["to"]))

    return DAGResult(
        nodes=sorted(task_ids),
        edges=edges,
        layers=layers,
        topological_order=topo_order,
        has_cycle=False,
    )


def create_dag_from_plan(plan_tasks: List[Dict]) -> Dict:
    """
    Create DAG dict suitable for storing on mission (missions.dag JSONB)
    Returns dict with nodes, edges, layers, topological_order
    """
    result = validate_and_plan_dag(plan_tasks)

    return {
        "nodes": result.nodes,
        "edges": result.edges,
        "layers": result.layers,
        "topological_order": result.topological_order,
    }
