"""Final LangGraph node that assembles the persistent artifact."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..artifact import AnalysisArtifact, FileArtifact
from ..state import AnalysisState, FileSummary


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_artifact(state: AnalysisState) -> Dict[str, object]:
    """Construct the final artifact and optionally flush it to disk."""

    root = state["root_path"]
    summaries = state.get("file_summaries", {})
    dependency_graph = state.get("dependency_graph", {})
    errors = state.get("errors", [])

    file_artifacts: List[FileArtifact] = []
    for path_str, summary in summaries.items():
        file_artifacts.append(
            FileArtifact(
                path=_relative(summary.path, root),
                language=summary.language,
                summary=summary.summary,
                symbols=summary.symbols,
                dependencies=summary.dependencies,
                dependents=summary.dependents,
            )
        )

    metadata = {
        "file_count": str(len(file_artifacts)),
        "dependency_edges": str(sum(len(values) for values in dependency_graph.values())),
    }

    artifact = AnalysisArtifact(
        root_path=str(root),
        files=sorted(file_artifacts, key=lambda item: item.path),
        dependency_graph=dependency_graph,
        metadata=metadata,
        errors=errors,
    )

    output_path = state.get("artifact_path")
    if output_path:
        artifact.to_json(output_path)

    return {"artifact": artifact}
