"""LangGraph node that converts import data into a dependency graph."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from ..state import AnalysisState, FileSummary


def _module_candidates(path: Path, root: Path) -> List[str]:
    relative = path.relative_to(root)
    dotted_path = ".".join(relative.with_suffix("").parts)
    slash_path = "/".join(relative.parts)
    candidates = {slash_path, dotted_path, relative.stem}
    if path.suffix == ".py":
        candidates.add(relative.with_suffix("").name)
    return [candidate for candidate in candidates if candidate]


def _build_module_index(summaries: Dict[str, FileSummary], root: Path) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for path_str, summary in summaries.items():
        for candidate in _module_candidates(summary.path, root):
            index.setdefault(candidate, path_str)
    return index


def analyze_dependencies(state: AnalysisState) -> Dict[str, object]:
    """Populate dependency graph and dependents by resolving imports."""

    summaries = state.get("file_summaries", {})
    root = state["root_path"]
    index = _build_module_index(summaries, root)

    dependency_graph: Dict[str, List[str]] = {}
    dependents_map: Dict[str, List[str]] = defaultdict(list)

    for path_str, summary in summaries.items():
        resolved: List[str] = []
        for dependency in summary.dependencies:
            normalized_path = dependency.replace("\\", "/")
            dotted = normalized_path.replace("/", ".")
            target = index.get(dotted) or index.get(normalized_path) or index.get(dependency)
            if not target and dependency in summaries:
                target = dependency
            if target and target != path_str:
                resolved.append(target)
                dependents_map[target].append(path_str)
            else:
                resolved.append(dependency)
        dependency_graph[path_str] = sorted(set(resolved))

    for path_str, summary in summaries.items():
        summary.dependents = sorted(set(dependents_map.get(path_str, [])))
        summary.dependencies = dependency_graph.get(path_str, [])

    return {"dependency_graph": dependency_graph, "file_summaries": summaries}
