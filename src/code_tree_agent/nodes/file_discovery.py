"""LangGraph node for enumerating eligible source files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List

from ..state import AnalysisState

_EXCLUDED_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv", "venv"}
_ALLOWED_SUFFIXES = {
    ".py",
    ".pyi",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
}


def _iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _EXCLUDED_DIR_NAMES]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() in _ALLOWED_SUFFIXES:
                yield path


def discover_files(state: AnalysisState) -> Dict[str, List[Path]]:
    """Populate the state with the list of files to analyze."""

    root = state["root_path"]
    files = sorted(_iter_files(root))
    return {"files": files}
