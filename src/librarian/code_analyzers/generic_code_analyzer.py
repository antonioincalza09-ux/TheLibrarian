from __future__ import annotations

import re
from pathlib import Path

from src.librarian.rules.schema import CodeMetadata


IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+([A-Za-z0-9_./-]+)", re.MULTILINE),
    re.compile(r"^\s*from\s+([A-Za-z0-9_./-]+)\s+import", re.MULTILINE),
    re.compile(r"^\s*require\(['\"]([^'\"]+)['\"]\)", re.MULTILINE),
]
FUNCTION_PATTERNS = [
    re.compile(r"^\s*function\s+([A-Za-z0-9_]+)\s*\(", re.MULTILINE),
    re.compile(r"^\s*export\s+function\s+([A-Za-z0-9_]+)\s*\(", re.MULTILINE),
    re.compile(r"^\s*def\s+([A-Za-z0-9_]+)\s*\(", re.MULTILINE),
]
CLASS_PATTERNS = [
    re.compile(r"^\s*class\s+([A-Za-z0-9_]+)", re.MULTILINE),
    re.compile(r"^\s*export\s+class\s+([A-Za-z0-9_]+)", re.MULTILINE),
]


def analyze_generic_code_file(path: Path, language: str | None = None) -> CodeMetadata:
    metadata = CodeMetadata(language=language)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        metadata.reason = f"Generic code analysis unavailable: {exc}"
        return metadata

    imports: list[str] = []
    for pattern in IMPORT_PATTERNS:
        imports.extend(pattern.findall(source))
    metadata.imports["external"] = sorted(set(imports))

    functions = [{"name": name, "line_start": None, "line_end": None} for pattern in FUNCTION_PATTERNS for name in pattern.findall(source)]
    classes = [{"name": name, "line_start": None, "line_end": None} for pattern in CLASS_PATTERNS for name in pattern.findall(source)]
    metadata.symbols["functions"] = functions
    metadata.symbols["classes"] = classes

    lowered = source.lower()
    if "fastapi" in lowered:
        metadata.framework_hints.append("FastAPI")
    if "typer" in lowered:
        metadata.framework_hints.append("Typer")
    if "click.command" in lowered:
        metadata.framework_hints.append("Click")
    if "main(" in lowered or "if __name__" in lowered or "process.argv" in lowered:
        metadata.entrypoints.append("heuristic:main")
    if "test" in path.name.lower():
        metadata.test_hints.append(path.name)
    metadata.reason = "Generic code heuristics completed."
    return metadata
