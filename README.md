# Code Tree Agent

LangGraph-based agent that generates a detailed, machine-readable code tree artifact for a codebase and serves it through a Streamlit UI for human exploration.

## Features

- Automated file discovery with configurable language coverage.
- Static analysis of Python modules with docstring capture.
- Heuristic symbol and dependency extraction for Java and JavaScript/TypeScript (including JSX/TSX components).
- Dependency graph construction with intra-repository resolution heuristics.
- Artifact export as JSON for consumption by other coding agents.
- Streamlit dashboard to inspect file summaries, dependencies, and symbol hierarchies.
- Streamlit dashboard with a focused dependency view that auto-limits oversized graphs for large projects.

## Requirements

- Python 3.10+
- Optional: OpenAI or other LLM credentials if you extend the graph with LLM-backed nodes.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## CLI Usage

```bash
code-tree-agent --target PATH_TO_REPO --output artifacts/code_tree.json
```

The `--target` flag defaults to the current directory, so you can omit it to analyze the active workspace. The command produces a JSON artifact that includes per-file structural metadata (Python, Java, and JS/TS/JSX symbols) and a dependency graph. By default the output is placed at `artifacts/code_tree.json`.

For very large repositories the Streamlit UI automatically falls back to a focused dependency view to keep the graph responsive. Use the sidebar toggle to switch between focused and full views (full view appears only when the graph size is below the safety threshold).

## Streamlit UI

```bash
streamlit run ui/app.py
```

Use the sidebar to point the UI at the latest artifact (defaults to `artifacts/code_tree.json`).

## Project Structure

- `src/code_tree_agent/graph.py`: LangGraph pipeline wiring.
- `src/code_tree_agent/nodes/`: Individual graph nodes for discovery, analysis, dependency resolution, and artifact emission.
- `ui/app.py`: Streamlit interface for visualization.
- `artifacts/`: Default location for generated artifacts.

## Extending the Agent

1. Add new nodes under `src/code_tree_agent/nodes/` to incorporate additional analyses.
2. Register the nodes in `graph.py` to extend the pipeline.
3. Update the Streamlit UI to surface new artifact fields as needed.

## Testing

Run the static checks with:

```bash
pytest
```
