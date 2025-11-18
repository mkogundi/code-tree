"""Structured artifacts emitted by the code tree analysis graph."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(slots=True)
class CodeSymbol:
    """Represents an extracted code symbol such as a class or function."""

    name: str
    symbol_type: str
    lineno: int
    docstring: Optional[str] = None
    children: List["CodeSymbol"] = field(default_factory=list)


@dataclass(slots=True)
class FileArtifact:
    """Holds the structured analysis for a single source file."""

    path: str
    language: str
    summary: str
    symbols: List[CodeSymbol] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)


@dataclass(slots=True)
class AnalysisArtifact:
    """Top-level artifact describing the entire repository tree."""

    root_path: str
    files: List[FileArtifact] = field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)

    def to_json(self, output_path: Path) -> Path:
        """Persist the artifact to disk and return the destination path."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            __import__("json").dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )
        return output_path
