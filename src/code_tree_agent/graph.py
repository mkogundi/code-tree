"""Graph definition for the code tree analysis agent."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes.artifact_builder import build_artifact
from .nodes.dependency_analysis import analyze_dependencies
from .nodes.file_analysis import analyze_files
from .nodes.file_discovery import discover_files
from .state import AnalysisState


def build_analysis_graph() -> StateGraph[AnalysisState]:
    """Return a compiled LangGraph instance representing the pipeline."""

    graph = StateGraph(AnalysisState)
    graph.add_node("discover_files", discover_files)
    graph.add_node("analyze_files", analyze_files)
    graph.add_node("dependency_analysis", analyze_dependencies)
    graph.add_node("artifact_builder", build_artifact)

    graph.set_entry_point("discover_files")
    graph.add_edge("discover_files", "analyze_files")
    graph.add_edge("analyze_files", "dependency_analysis")
    graph.add_edge("dependency_analysis", "artifact_builder")
    graph.add_edge("artifact_builder", END)

    return graph.compile()
