"""Command-line interface for the LangGraph-based code tree agent."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .graph import build_analysis_graph
from .state import AnalysisState, build_initial_state

console = Console()


def _analyze(
    target: Path = typer.Option(
        Path("."),
        "--target",
        "-t",
        help="Path to the repository or source tree.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination JSON file for the generated artifact.",
    ),
) -> None:
    """Run the analysis graph against the selected target."""

    root = target.resolve()
    if not root.exists():
        raise typer.Exit(code=1)

    state: AnalysisState = build_initial_state(root)
    if output is not None:
        state["artifact_path"] = output.resolve()
    else:
        default_path = Path.cwd() / "artifacts" / "code_tree.json"
        state["artifact_path"] = default_path

    graph = build_analysis_graph()
    result_state = graph.invoke(state)

    artifact = result_state.get("artifact")
    artifact_path = result_state.get("artifact_path") or state.get("artifact_path")

    if artifact is None:
        console.print("[red]Analysis did not produce an artifact.[/red]")
        raise typer.Exit(code=1)

    if artifact_path:
        artifact.to_json(Path(artifact_path))
        console.print(f"[green]Artifact written to[/green] {artifact_path}")

    table = Table(title="Analysis Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Files", artifact.metadata.get("file_count", "0"))
    table.add_row("Dependency Edges", artifact.metadata.get("dependency_edges", "0"))
    table.add_row("Errors", str(len(artifact.errors)))
    console.print(table)

    if artifact.errors:
        console.print("[yellow]Warnings detected during analysis:[/yellow]")
        for warning in artifact.errors:
            console.print(f" - {warning}")


def app() -> None:
    """Entry point used by the console script."""

    typer.run(_analyze)


if __name__ == "__main__":  # pragma: no cover
    app()
