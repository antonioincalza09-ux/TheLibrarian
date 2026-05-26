from __future__ import annotations

import ast
import sys
from pathlib import Path

from src.librarian.rules.schema import CodeMetadata


def analyze_python_file(path: Path, root: Path) -> CodeMetadata:
    metadata = CodeMetadata(language="Python")
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        metadata.reason = f"Python analysis unavailable: {exc}"
        metadata.risk_level = "medium"
        return metadata

    metadata.module_name = path.stem
    try:
        relative = path.relative_to(root)
        metadata.package_name = ".".join(relative.with_suffix("").parts)
    except ValueError:
        metadata.package_name = path.stem

    metadata.docstrings.module = ast.get_docstring(tree)
    internal_imports: list[str] = []
    external_imports: list[str] = []
    standard_imports: list[str] = []
    methods: list[dict[str, int | str | None]] = []

    stdlib_names = getattr(sys, "stdlib_module_names", set())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _record_import(alias.name, root, path, stdlib_names, internal_imports, external_imports, standard_imports)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _record_import(node.module, root, path, stdlib_names, internal_imports, external_imports, standard_imports)
        elif isinstance(node, ast.FunctionDef):
            symbol = {"name": node.name, "line_start": node.lineno, "line_end": getattr(node, "end_lineno", node.lineno)}
            metadata.symbols["functions"].append(symbol)
            docstring = ast.get_docstring(node)
            if docstring:
                metadata.docstrings.functions[node.name] = docstring
            if node.name == "main":
                metadata.entrypoints.append(f"function:{node.name}")
            if node.name.startswith("test_"):
                metadata.test_hints.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            symbol = {"name": node.name, "line_start": node.lineno, "line_end": getattr(node, "end_lineno", node.lineno)}
            metadata.symbols["functions"].append(symbol)
        elif isinstance(node, ast.ClassDef):
            symbol = {"name": node.name, "line_start": node.lineno, "line_end": getattr(node, "end_lineno", node.lineno)}
            metadata.symbols["classes"].append(symbol)
            docstring = ast.get_docstring(node)
            if docstring:
                metadata.docstrings.classes[node.name] = docstring
            if node.name.startswith("Test"):
                metadata.test_hints.append(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(
                        {"name": f"{node.name}.{child.name}", "line_start": child.lineno, "line_end": getattr(child, "end_lineno", child.lineno)}
                    )
        elif isinstance(node, ast.If) and _is_main_guard(node):
            metadata.entrypoints.append('guard:if __name__ == "__main__"')
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "app" in targets:
                value_text = ast.unparse(node.value) if hasattr(ast, "unparse") else ""
                if "FastAPI" in value_text:
                    metadata.framework_hints.append("FastAPI")
                    metadata.entrypoints.append("fastapi:app")
                if "Typer" in value_text:
                    metadata.framework_hints.append("Typer")
                    metadata.entrypoints.append("typer:app")

    metadata.symbols["methods"] = methods
    metadata.imports["internal"] = sorted(set(internal_imports))
    metadata.imports["external"] = sorted(set(external_imports))
    metadata.imports["standard_library"] = sorted(set(standard_imports))
    if any(name.startswith("pytest") for name in metadata.imports["external"]):
        metadata.framework_hints.append("pytest")
    if "click" in metadata.imports["external"]:
        metadata.framework_hints.append("Click")
    metadata.reason = "Python AST analysis completed."
    return metadata


def _record_import(
    module_name: str,
    root: Path,
    current_path: Path,
    stdlib_names: set[str],
    internal_imports: list[str],
    external_imports: list[str],
    standard_imports: list[str],
) -> None:
    top_level = module_name.split(".")[0]
    if top_level in stdlib_names:
        standard_imports.append(module_name)
        return
    if (root / top_level).exists() or (current_path.parent / f"{top_level}.py").exists():
        internal_imports.append(module_name)
        return
    external_imports.append(module_name)


def _is_main_guard(node: ast.If) -> bool:
    try:
        return (
            isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "__main__"
        )
    except AttributeError:
        return False
