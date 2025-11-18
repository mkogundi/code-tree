"""Canonical state definitions shared across the LangGraph pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from .artifact import AnalysisArtifact, CodeSymbol


@dataclass(slots=True)
class FileSummary:
    """Intermediate representation for each analyzed file."""

    path: Path
    language: str
    summary: str
    symbols: List[CodeSymbol] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)


class AnalysisState(TypedDict, total=False):
    """State container exchanged between LangGraph nodes."""

    root_path: Path
    files: List[Path]
    file_summaries: Dict[str, FileSummary]
    dependency_graph: Dict[str, List[str]]
    artifact_path: Optional[Path]
    errors: List[str]
    artifact: Optional[AnalysisArtifact]


def build_initial_state(root_path: Path) -> AnalysisState:
    """Return the initial state given a repository root path."""

    return AnalysisState(
        root_path=root_path,
        files=[],
        file_summaries={},
        dependency_graph={},
        artifact_path=None,
        errors=[],
        artifact=None,
    )
