"""LangGraph node that performs per-file structural analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..state import AnalysisState, FileSummary
from ..utils.file_parsing import (
    detect_language,
    extract_java_imports,
    extract_java_symbols,
    extract_js_imports,
    extract_js_symbols,
    extract_python_imports,
    extract_python_symbols,
    read_source,
    resolve_dependencies,
    summarize_file,
)


def _analyze_single_file(path: Path, root: Path) -> FileSummary:
    source = read_source(path)
    language = detect_language(path)
    summary = summarize_file(path, source)
    symbols = []
    dependencies: List[str] = []

    if language == "python":
        symbols = extract_python_symbols(path, source)
        dependencies = extract_python_imports(source)
    elif language == "java":
        symbols = extract_java_symbols(path, source)
        dependencies = extract_java_imports(source)
    elif language in {"javascript", "typescript"}:
        symbols = extract_js_symbols(source)
        dependencies = extract_js_imports(source)

    dependencies = resolve_dependencies(path, dependencies, language, root)
    return FileSummary(
        path=path,
        language=language,
        summary=summary,
        symbols=symbols,
        dependencies=dependencies,
    )


def analyze_files(state: AnalysisState) -> Dict[str, Dict[str, FileSummary]]:
    """Analyze each file captured during discovery."""

    summaries: Dict[str, FileSummary] = {}
    errors = state.get("errors", [])
    root = state["root_path"]

    for path in state.get("files", []):
        try:
            summary = _analyze_single_file(path, root)
            summaries[str(path)] = summary
        except OSError as exc:  # pragma: no cover - file read errors are rare
            errors.append(f"Failed to read {path}: {exc}")

    updates: Dict[str, object] = {"file_summaries": summaries}
    if errors:
        updates["errors"] = errors
    return updates
