"""Streamlit UI for browsing generated code tree artifacts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import streamlit as st

st.set_page_config(page_title="Code Tree Explorer", layout="wide")

MAX_GRAPH_NODES = 400


@lru_cache(maxsize=8)
def _load_artifact(path_str: str) -> Dict[str, object]:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _render_symbol_tree(symbols: Iterable[Dict[str, object]], depth: int = 0) -> None:
    indent = "  " * depth
    for symbol in symbols:
        name = symbol.get("name", "?<name>")
        symbol_type = symbol.get("symbol_type", "symbol")
        lineno = symbol.get("lineno", "?")
        st.markdown(f"{indent}- `{symbol_type}` **{name}** (line {lineno})")
        children = symbol.get("children", [])
        if children:
            _render_symbol_tree(children, depth + 1)


def _normalize_label(value: str) -> str:
    return value.replace("\\", "/")


def _format_label(node: str, root: Optional[Path]) -> str:
    sanitized = _normalize_label(node)
    if root is None:
        return sanitized
    try:
        node_path = Path(node)
        if node_path.is_absolute():
            return node_path.resolve().relative_to(root).as_posix()
    except Exception:
        pass
    return sanitized


def _prepare_node_maps(
    dot_map: Dict[str, List[str]],
    root: Optional[Path],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    all_nodes: Set[str] = set()
    for source, targets in dot_map.items():
        all_nodes.add(source)
        all_nodes.update(targets)

    node_to_label: Dict[str, str] = {}
    label_to_node: Dict[str, str] = {}
    for node in all_nodes:
        label = _format_label(node, root)
        node_to_label[node] = label
        label_to_node.setdefault(label, node)
    return node_to_label, label_to_node


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _sanitize_id(node: str) -> str:
    return _normalize_label(node)


def _build_graphviz(
    dot_map: Dict[str, List[str]],
    root: Optional[Path],
    node_to_label: Dict[str, str],
    included_nodes: Optional[Set[str]] = None,
    node_styles: Optional[Dict[str, Dict[str, str]]] = None,
    edge_styles: Optional[Dict[Tuple[str, str], str]] = None,
) -> str:
    node_styles = node_styles or {}
    edge_styles = edge_styles or {}

    nodes: Set[str] = set()
    if included_nodes:
        nodes.update(included_nodes)
    else:
        for source, targets in dot_map.items():
            nodes.add(source)
            nodes.update(targets)

    for source, target in edge_styles.keys():
        nodes.add(source)
        nodes.add(target)

    for node in list(nodes):
        if node not in node_to_label:
            node_to_label[node] = _format_label(node, root)

    lines = [
        "digraph Dependencies {",
        "  rankdir=LR;",
        '  graph [splines=true, nodesep=0.6, ranksep=1.0];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#f8f9fa", color="#d5d8dc"];',
        '  edge [color="#95a5a6", arrowsize=0.7, penwidth=1.1];',
    ]

    def _node_attr_string(node: str) -> str:
        style = node_styles.get(node, {})
        attributes = [f'label="{_escape_label(node_to_label.get(node, _format_label(node, root)))}"']
        if "fillcolor" in style:
            attributes.append(f'fillcolor="{style["fillcolor"]}"')
        if "color" in style:
            attributes.append(f'color="{style["color"]}"')
        if "fontcolor" in style:
            attributes.append(f'fontcolor="{style["fontcolor"]}"')
        if "penwidth" in style:
            attributes.append(f'penwidth="{style["penwidth"]}"')
        return ", ".join(attributes)

    for node in sorted(nodes, key=lambda item: node_to_label.get(item, _format_label(item, root))):
        node_id = _sanitize_id(node)
        lines.append(f'  "{_escape_label(node_id)}" [{_node_attr_string(node)}];')

    for source in sorted(dot_map.keys(), key=lambda item: node_to_label.get(item, _format_label(item, root))):
        if source not in nodes:
            continue
        for target in sorted(dot_map[source], key=lambda item: node_to_label.get(item, _format_label(item, root))):
            if included_nodes and target not in nodes:
                continue
            if target not in node_to_label:
                node_to_label[target] = _format_label(target, root)
            source_id = _escape_label(_sanitize_id(source))
            target_id = _escape_label(_sanitize_id(target))
            style_color = edge_styles.get((source, target))
            if style_color:
                attr = f' [color="{style_color}", penwidth="2.2"]'
            else:
                attr = ""
            lines.append(f'  "{source_id}" -> "{target_id}"{attr};')

    lines.append("}")
    return "\n".join(lines)


def _collect_all_nodes(dot_map: Dict[str, List[str]]) -> Set[str]:
    nodes: Set[str] = set()
    for source, targets in dot_map.items():
        nodes.add(source)
        nodes.update(targets)
    return nodes


def main() -> None:
    st.title("Code Tree Explorer")

    default_path = Path.cwd() / "artifacts" / "code_tree.json"
    artifact_input = st.sidebar.text_input("Artifact JSON path", str(default_path))
    reload_key = st.sidebar.button("Load Artifact")

    if not artifact_input:
        st.info("Provide the path to a generated artifact to begin.")
        return

    if reload_key or "artifact" not in st.session_state:
        try:
            st.session_state["artifact"] = _load_artifact(artifact_input)
        except FileNotFoundError as exc:
            st.error(str(exc))
            return

    artifact = st.session_state.get("artifact", {})
    files = artifact.get("files", [])
    dependency_graph = artifact.get("dependency_graph", {})
    metadata = artifact.get("metadata", {})
    root_path_str = artifact.get("root_path")
    root_path = Path(root_path_str).resolve() if root_path_str else None
    all_graph_nodes = _collect_all_nodes(dependency_graph)
    graph_node_count = len(all_graph_nodes)
    graph_too_large = graph_node_count > MAX_GRAPH_NODES
    node_to_label, label_to_node = _prepare_node_maps(dependency_graph, root_path)

    cols = st.columns(3)
    cols[0].metric("Files", metadata.get("file_count", len(files)))
    cols[1].metric("Dependencies", metadata.get("dependency_edges", 0))
    cols[2].metric("Warnings", len(artifact.get("errors", [])))
    if dependency_graph:
        st.sidebar.caption(
            f"Graph contains {graph_node_count} nodes. Full view is {'disabled' if graph_too_large else 'available'}."
        )

    file_options = [file.get("path", "<unknown>") for file in files]

    if not files:
        st.info("The artifact does not contain any file entries yet.")
        return

    selected_label = st.sidebar.selectbox("File", file_options, index=0)
    selected_file = next((file for file in files if file.get("path") == selected_label), files[0])

    st.subheader(f"File: {selected_file.get('path', '<unknown>')}")
    st.caption(selected_file.get("summary", ""))

    st.markdown("**Dependencies**")
    dependencies = selected_file.get("dependencies", [])
    if dependencies:
        for dep in dependencies:
            st.write(f"- {dep}")
    else:
        st.write("- None")

    st.markdown("**Dependents**")
    dependents = selected_file.get("dependents", [])
    if dependents:
        for dep in dependents:
            st.write(f"- {dep}")
    else:
        st.write("- None")

    st.markdown("**Symbols**")
    symbols = selected_file.get("symbols", [])
    if symbols:
        _render_symbol_tree(symbols)
    else:
        st.write("- None detected")

    st.subheader("Dependency Graph")

    def ensure_node(reference: str) -> str:
        normalized = _normalize_label(reference)
        node = label_to_node.get(normalized)
        if node:
            return node
        label = _format_label(reference, root_path)
        node_to_label[reference] = label
        label_to_node.setdefault(label, reference)
        return reference

    selected_relative = selected_file.get("path", "")
    normalized_selected = _normalize_label(selected_relative)
    selected_node = label_to_node.get(normalized_selected)
    if not selected_node and root_path and selected_relative:
        try:
            absolute_candidate = str((root_path / selected_relative).resolve())
            if absolute_candidate in node_to_label:
                selected_node = absolute_candidate
        except Exception:
            selected_node = None
    if not selected_node and selected_relative:
        selected_node = ensure_node(selected_relative)

    dependency_nodes: Set[str] = set()
    dependent_nodes: Set[str] = set()

    for dep in selected_file.get("dependencies", []):
        dependency_nodes.add(ensure_node(dep))
    for dep in selected_file.get("dependents", []):
        dependent_nodes.add(ensure_node(dep))

    if selected_node and selected_node in dependency_graph:
        dependency_nodes.update(dependency_graph[selected_node])
    if selected_node:
        for source, targets in dependency_graph.items():
            if selected_node in targets:
                dependent_nodes.add(source)

    edge_styles: Dict[Tuple[str, str], str] = {}
    if selected_node and selected_node in dependency_graph:
        for target in dependency_graph[selected_node]:
            edge_styles[(selected_node, target)] = "#2471a3"
    if selected_node:
        for source, targets in dependency_graph.items():
            if selected_node in targets:
                edge_styles[(source, selected_node)] = "#c0392b"

    node_styles: Dict[str, Dict[str, str]] = {}
    if selected_node:
        node_styles[selected_node] = {
            "fillcolor": "#fdebd0",
            "color": "#e67e22",
            "fontcolor": "#4a4a4a",
            "penwidth": "2.4",
        }
    for node in dependency_nodes:
        node_styles.setdefault(node, {"fillcolor": "#d6eaf8", "color": "#3498db"})
    for node in dependent_nodes:
        node_styles.setdefault(node, {"fillcolor": "#f5b7b1", "color": "#e74c3c"})

    focus_nodes: Set[str] = set()
    if selected_node:
        focus_nodes.add(selected_node)
    focus_nodes.update(dependency_nodes)
    focus_nodes.update(dependent_nodes)

    view_options: List[str] = ["Focused (selected file)"]
    if dependency_graph and not graph_too_large:
        view_options.append("Full graph")

    view_mode = st.sidebar.radio(
        "Dependency graph view",
        tuple(view_options),
        index=0,
        help="Full graph is hidden for large projects." if graph_too_large else "Switch to focus mode to highlight the selected file with its direct dependencies and dependents.",
    )

    st.caption(
        ":large_orange_square: Selected file · :large_blue_square: Dependencies · :large_red_square: Dependents"
    )

    if not dependency_graph:
        st.info("Dependency graph is empty for this artifact.")
    else:
        graph_source = _build_graphviz(
            dependency_graph,
            root_path,
            node_to_label,
            included_nodes=focus_nodes if view_mode.startswith("Focused") and focus_nodes else None,
            node_styles=node_styles,
            edge_styles=edge_styles,
        )
        st.graphviz_chart(graph_source)

    if artifact.get("errors"):
        st.subheader("Warnings")
        for warning in artifact["errors"]:
            st.warning(warning)


if __name__ == "__main__":
    main()
