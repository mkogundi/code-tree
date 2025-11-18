"""Utilities for reading source files and extracting structural information."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..artifact import CodeSymbol

try:  # pragma: no cover - optional dependency
    import javalang  # type: ignore
except Exception:  # pragma: no cover - graceful degradation if missing
    javalang = None  # type: ignore[assignment]


_PYTHON_EXTENSIONS = {".py", ".pyi"}
_TEXT_EXTENSIONS = {".md", ".txt"}
_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_JAVA_EXTENSIONS = {".java"}
_JS_CANDIDATE_EXTENSIONS: Sequence[str] = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json")

_JAVA_IMPORT_PATTERN = re.compile(r"^\s*import\s+([^;\s]+)\s*;?", re.MULTILINE)
_JAVA_CLASS_PATTERN = re.compile(r"^\s*(?:public|protected|private|abstract|final|static)?\s*(class|interface|enum)\s+(\w+)", re.MULTILINE)
_JAVA_METHOD_PATTERN = re.compile(
    r"^\s*(?:public|protected|private|static|final|synchronized|abstract)\s+[\w\[\]<>?,\s]+\s+(\w+)\s*\(",
    re.MULTILINE,
)

_JS_IMPORT_PATTERN = re.compile(r"^\s*import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE)
_JS_REQUIRE_PATTERN = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")
_JS_DYNAMIC_IMPORT_PATTERN = re.compile(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)")
_JS_EXPORT_FUNCTION_PATTERN = re.compile(r"export\s+function\s+(\w+)\s*\(")
_JS_EXPORT_CLASS_PATTERN = re.compile(r"export\s+class\s+(\w+)\b")
_JS_EXPORT_CONST_PATTERN = re.compile(r"export\s+(?:const|let|var)\s+(\w+)\s*=")
_JS_DEFAULT_FUNCTION_PATTERN = re.compile(r"export\s+default\s+function\s*(\w+)?\s*\(")
_JS_CLASS_COMPONENT_PATTERN = re.compile(r"class\s+(\w+)\s+extends\s+React\.Component")
_JS_FUNCTION_DECL_PATTERN = re.compile(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_JS_ARROW_COMPONENT_PATTERN = re.compile(
    r"const\s+([A-Z][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[^=]+)=>",
    re.MULTILINE,
)


def detect_language(path: Path) -> str:
    """Infer a human-readable language label from a file path."""

    suffix = path.suffix.lower()
    if suffix in _PYTHON_EXTENSIONS:
        return "python"
    if suffix in {".js", ".jsx"}:
        return "javascript"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in _JAVA_EXTENSIONS:
        return "java"
    if suffix == ".json":
        return "json"
    if suffix in {".yml", ".yaml"}:
        return "yaml"
    if suffix in _TEXT_EXTENSIONS:
        return "text"
    return suffix.lstrip(".") or "unknown"


def read_source(path: Path) -> str:
    """Load a file as UTF-8 text, ignoring decoding errors."""

    return path.read_text(encoding="utf-8", errors="ignore")


def _line_number_from_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def extract_python_symbols(path: Path, source: str) -> List[CodeSymbol]:
    """Return a nested collection of symbol nodes discovered via AST parsing."""

    try:
        parsed = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    symbols: List[CodeSymbol] = []

    def _walk(node: ast.AST, container: List[CodeSymbol]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(child)
                symbol = CodeSymbol(
                    name=child.name,
                    symbol_type=child.__class__.__name__.lower(),
                    lineno=getattr(child, "lineno", 0),
                    docstring=doc,
                )
                container.append(symbol)
                _walk(child, symbol.children)
            else:
                _walk(child, container)

    _walk(parsed, symbols)
    return symbols


def extract_python_imports(source: str) -> List[str]:
    """Collect import targets from Python source text."""

    results: List[str] = []
    try:
        parsed = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if module:
                    results.append(f"{module}.{alias.name}")
                else:
                    results.append(alias.name)
    return results


def extract_java_symbols(path: Path, source: str) -> List[CodeSymbol]:
    """Return type and method information for Java source files."""

    if javalang is None:  # pragma: no cover - fallback if dependency unavailable
        return _extract_java_symbols_fallback(source)

    try:  # pragma: no branch - parser may raise on invalid syntax
        tree = javalang.parse.parse(source)
    except Exception:  # pragma: no cover - fallback for parse errors
        return _extract_java_symbols_fallback(source)

    symbols: List[CodeSymbol] = []
    for type_decl in getattr(tree, "types", []):
        name = getattr(type_decl, "name", None)
        if not name:
            continue
        symbol = CodeSymbol(
            name=name,
            symbol_type=type_decl.__class__.__name__.lower(),
            lineno=(type_decl.position.line if getattr(type_decl, "position", None) else 0),
            docstring=getattr(type_decl, "documentation", None),
        )
        for method in getattr(type_decl, "methods", []):
            method_symbol = CodeSymbol(
                name=method.name,
                symbol_type="method",
                lineno=(method.position.line if getattr(method, "position", None) else 0),
                docstring=getattr(method, "documentation", None),
            )
            symbol.children.append(method_symbol)
        symbols.append(symbol)
    return symbols


def _extract_java_symbols_fallback(source: str) -> List[CodeSymbol]:
    symbols: List[CodeSymbol] = []
    for match in _JAVA_CLASS_PATTERN.finditer(source):
        kind, name = match.groups()
        lineno = _line_number_from_offset(source, match.start(2))
        class_symbol = CodeSymbol(name=name, symbol_type=kind.lower(), lineno=lineno)
        body_slice = source[match.end() :]
        for method_match in _JAVA_METHOD_PATTERN.finditer(body_slice):
            method_name = method_match.group(1)
            method_lineno = lineno + _line_number_from_offset(body_slice, method_match.start(1)) - 1
            class_symbol.children.append(
                CodeSymbol(name=method_name, symbol_type="method", lineno=method_lineno)
            )
        symbols.append(class_symbol)
    return symbols


def extract_java_imports(source: str) -> List[str]:
    return [match.group(1) for match in _JAVA_IMPORT_PATTERN.finditer(source)]


def extract_js_symbols(source: str) -> List[CodeSymbol]:
    seen: dict[tuple[str, str], CodeSymbol] = {}

    def _register(name: str, symbol_type: str, match: re.Match[str]) -> None:
        key = (name, symbol_type)
        if not name or key in seen:
            return
        lineno = _line_number_from_offset(source, match.start(1))
        seen[key] = CodeSymbol(name=name, symbol_type=symbol_type, lineno=lineno)

    for pattern, symbol_type in (
        (_JS_EXPORT_FUNCTION_PATTERN, "function"),
        (_JS_EXPORT_CLASS_PATTERN, "class"),
        (_JS_EXPORT_CONST_PATTERN, "variable"),
        (_JS_CLASS_COMPONENT_PATTERN, "component"),
    ):
        for match in pattern.finditer(source):
            _register(match.group(1), symbol_type, match)

    for match in _JS_DEFAULT_FUNCTION_PATTERN.finditer(source):
        name = match.group(1) or "default"
        _register(name, "default_export", match)

    for match in _JS_FUNCTION_DECL_PATTERN.finditer(source):
        name = match.group(1)
        if name and name[0].isupper():
            _register(name, "component", match)
        else:
            _register(name, "function", match)

    for match in _JS_ARROW_COMPONENT_PATTERN.finditer(source):
        _register(match.group(1), "component", match)

    return sorted(seen.values(), key=lambda symbol: symbol.lineno)


def extract_js_imports(source: str) -> List[str]:
    results = [match.group(1) for match in _JS_IMPORT_PATTERN.finditer(source)]
    results.extend(match.group(1) for match in _JS_REQUIRE_PATTERN.finditer(source))
    results.extend(match.group(1) for match in _JS_DYNAMIC_IMPORT_PATTERN.finditer(source))
    return results


def basic_text_summary(source: str) -> str:
    """Quick summary describing file size and complexity."""

    lines = [line for line in source.splitlines() if line.strip()]
    return f"{len(lines)} non-empty lines"


def python_summary(path: Path, source: str) -> str:
    """Return a human-friendly summary for Python modules."""

    try:
        parsed = ast.parse(source, filename=str(path))
    except SyntaxError:
        return "Syntax error encountered; detailed summary unavailable."

    top_level_defs = [
        node
        for node in parsed.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    class_count = sum(isinstance(node, ast.ClassDef) for node in top_level_defs)
    func_count = len(top_level_defs) - class_count
    return (
        f"Top-level declarations: {class_count} classes, {func_count} functions; "
        f"module length {len(parsed.body)} statements."
    )


def java_summary(path: Path, source: str) -> str:
    symbols = extract_java_symbols(path, source)
    class_like = sum(1 for symbol in symbols if symbol.symbol_type in {"class", "interface", "enum"})
    method_count = sum(len(symbol.children) for symbol in symbols)
    return f"Declares {class_like} types with {method_count} methods."


def javascript_summary(source: str) -> str:
    symbols = extract_js_symbols(source)
    components = sum(1 for symbol in symbols if symbol.symbol_type == "component")
    functions = sum(1 for symbol in symbols if symbol.symbol_type in {"function", "default_export"})
    classes = sum(1 for symbol in symbols if symbol.symbol_type == "class")
    return (
        f"Exports {components} components, {functions} functions, {classes} classes; "
        f"{len(symbols)} top-level symbols detected."
    )


def summarize_file(path: Path, source: str) -> str:
    """Generate a short description tailored to the detected language."""

    language = detect_language(path)
    if language == "python":
        return python_summary(path, source)
    if language == "java":
        return java_summary(path, source)
    if language in {"javascript", "typescript"}:
        return javascript_summary(source)
    return basic_text_summary(source)


def _resolve_python_import(root: Path, origin: Path, target: str) -> Optional[Path]:
    normalized = target.replace("::", ".").replace("/", ".")
    candidate = origin.parent / (normalized.replace(".", "/") + ".py")
    if candidate.exists():
        return candidate.resolve()

    package_dir = root / normalized.replace(".", "/")
    if (package_dir / "__init__.py").exists():
        return (package_dir / "__init__.py").resolve()

    absolute_candidate = root / (normalized.replace(".", "/") + ".py")
    if absolute_candidate.exists():
        return absolute_candidate.resolve()

    return None


def _resolve_js_path(candidate: Path) -> Optional[Path]:
    if candidate.is_file():
        return candidate.resolve()
    if candidate.suffix and candidate.with_suffix("").exists():
        base = candidate.with_suffix("")
        if base.exists():
            return base.resolve()
    for ext in _JS_CANDIDATE_EXTENSIONS:
        option = candidate.with_suffix(ext)
        if option.exists():
            return option.resolve()
    if candidate.exists() and candidate.is_dir():
        for ext in _JS_CANDIDATE_EXTENSIONS:
            index_candidate = candidate / f"index{ext}"
            if index_candidate.exists():
                return index_candidate.resolve()
    return None


def _resolve_js_import(root: Path, origin: Path, target: str) -> Optional[Path]:
    target_path: Optional[Path] = None
    if target.startswith(('.', '..')):
        target_path = (origin.parent / target).resolve()
    elif target.startswith('/'):
        target_path = (root / target.lstrip('/')).resolve()
    elif '/' in target:
        target_path = (root / target).resolve()

    if target_path is not None:
        resolved = _resolve_js_path(target_path)
        if resolved:
            return resolved

    return None


def _resolve_java_import(root: Path, target: str) -> Optional[Path]:
    if target.endswith(".*"):
        directory = root / target[:-2].replace(".", "/")
        if directory.exists():
            return directory.resolve()
        return None

    candidate = root / (target.replace(".", "/") + ".java")
    if candidate.exists():
        return candidate.resolve()

    return None


def resolve_dependencies(path: Path, imports: Iterable[str], language: str, root: Path) -> List[str]:
    """Resolve import strings to repository paths when possible."""

    resolved: List[str] = []
    for item in imports:
        match: Optional[Path] = None
        if language == "python":
            match = _resolve_python_import(root, path, item)
        elif language in {"javascript", "typescript"}:
            match = _resolve_js_import(root, path, item)
        elif language == "java":
            match = _resolve_java_import(root, item)

        if match is not None:
            resolved.append(str(match))
        else:
            resolved.append(item)

    return resolved
