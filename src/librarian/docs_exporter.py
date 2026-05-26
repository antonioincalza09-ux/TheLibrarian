from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.librarian.rules.schema import Manifest, WorkspaceNode


def write_markdown_notes(root: str | Path, manifest: Manifest) -> None:
    resolved_root = Path(root).resolve()
    notes_directory = resolved_root / ".librarian" / "notes"
    runbooks_directory = resolved_root / ".librarian" / "runbooks"
    notes_directory.mkdir(parents=True, exist_ok=True)
    runbooks_directory.mkdir(parents=True, exist_ok=True)

    (resolved_root / ".librarian" / "README.librarian.md").write_text(_readme_content(manifest), encoding="utf-8")
    (notes_directory / "index.md").write_text(_index_content(manifest), encoding="utf-8")
    (notes_directory / "files.md").write_text(_files_content(manifest), encoding="utf-8")
    (notes_directory / "directories.md").write_text(_directories_content(manifest), encoding="utf-8")
    (notes_directory / "code.md").write_text(_code_content(manifest), encoding="utf-8")
    (notes_directory / "entrypoints.md").write_text(_entrypoints_content(manifest), encoding="utf-8")
    (notes_directory / "risks.md").write_text(_risks_content(manifest), encoding="utf-8")


def write_runbooks(root: str | Path, manifest: Manifest) -> None:
    resolved_root = Path(root).resolve()
    runbooks_directory = resolved_root / ".librarian" / "runbooks"
    runbooks_directory.mkdir(parents=True, exist_ok=True)
    runbooks = {
        "index.md": _runbook_index(manifest),
        "how_to_inspect.md": _runbook_inspect(manifest),
        "how_to_run_python_tools.md": _runbook_python_tools(manifest),
        "how_to_extend_classifiers.md": _runbook_extend_classifiers(manifest),
    }
    for name, content in runbooks.items():
        (runbooks_directory / name).write_text(content, encoding="utf-8")


def explain_workspace(manifest: Manifest) -> str:
    top_directories = [directory for directory in manifest.directories if directory.depth <= 1]
    languages = ", ".join(manifest.detected_languages) or "none detected"
    entrypoints = ", ".join(manifest.entrypoints[:8]) or "none detected"
    risky_files = [node.current_path for node in manifest.files if node.risk_level == "high"][:8]
    risky_text = ", ".join(risky_files) if risky_files else "no high-risk files detected"
    vendor_directories = [
        directory.current_path
        for directory in manifest.directories
        if directory.directory_analysis and any(role in {"vendor", "generated", "cache"} for role in directory.directory_analysis.possible_roles)
    ][:8]
    vendor_text = ", ".join(vendor_directories) if vendor_directories else "none detected"
    starts = _starting_points(manifest)
    return "\n".join(
        [
            f"Workspace root: {manifest.workspace_root}",
            f"Files: {manifest.counts.files}",
            f"Directories: {manifest.counts.directories}",
            f"Main directories: {', '.join(directory.current_path for directory in top_directories[:8]) or '(root only)'}",
            f"Languages: {languages}",
            f"Entrypoints: {entrypoints}",
            f"High-risk files: {risky_text}",
            f"Generated/vendor/cache directories: {vendor_text}",
            f"Where to start: {', '.join(starts)}",
        ]
    )


def _readme_content(manifest: Manifest) -> str:
    return f"""# The Librarian Runtime

This workspace was indexed by The Librarian in developer-first mode.

- Workspace root: `{manifest.workspace_root}`
- Files indexed: `{manifest.counts.files}`
- Directories indexed: `{manifest.counts.directories}`
- Detected languages: `{", ".join(manifest.detected_languages) or "none"}`
- Detected domains: `{", ".join(manifest.detected_domains) or "none"}`

What The Librarian generated:

- `.librarian/manifest.json`: machine-readable manifest for developers and agents.
- `.librarian/plan.json`: dry-run organization plan, if generated.
- `.librarian/logs/operations.jsonl`: append-only move and rollback log.
- `.librarian/notes/*.md`: human-readable workspace notes.
- `.librarian/runbooks/*.md`: step-by-step runbooks.
- `.librarian/scripts/*.py`: runnable helper scripts using only standard library.
- `*.librarian.yaml` and `.librarian.yaml`: sidecar metadata for files and directories.

Original source files were not modified. Metadata is stored out-of-band in sidecars and runtime artifacts.
"""


def _index_content(manifest: Manifest) -> str:
    return """# Notes Index

- [Files](files.md)
- [Directories](directories.md)
- [Code](code.md)
- [Entrypoints](entrypoints.md)
- [Risks](risks.md)
"""


def _files_content(manifest: Manifest) -> str:
    lines = ["# Files", "", "| Path | Kind | Language | Risk | Summary |", "| --- | --- | --- | --- | --- |"]
    for node in manifest.files[:200]:
        lines.append(
            f"| `{node.current_path}` | {node.file_kind} | {node.detected_language or '-'} | {node.risk_level} | {node.summary or '-'} |"
        )
    return "\n".join(lines) + "\n"


def _directories_content(manifest: Manifest) -> str:
    lines = ["# Directories", ""]
    for directory in manifest.directories[:100]:
        roles = ", ".join(directory.directory_analysis.possible_roles if directory.directory_analysis else [])
        theme = directory.directory_analysis.theme if directory.directory_analysis else "General"
        lines.extend(
            [
                f"## `{directory.current_path}`",
                "",
                f"- Theme: {theme}",
                f"- Roles: {roles or 'general'}",
                f"- Summary: {directory.summary or '-'}",
                "",
            ]
        )
    return "\n".join(lines)


def _code_content(manifest: Manifest) -> str:
    languages = Counter(node.detected_language for node in manifest.files if node.detected_language)
    lines = ["# Code Overview", "", "## Languages", ""]
    for language, count in languages.most_common():
        lines.append(f"- {language}: {count}")
    lines.extend(["", "## Likely Main Modules", ""])
    for node in manifest.files:
        if node.code_metadata and node.code_metadata.entrypoints:
            lines.append(f"- `{node.current_path}`: {', '.join(node.code_metadata.entrypoints)}")
    lines.extend(["", "## Generated Or Vendor", ""])
    for node in manifest.files:
        if node.generated_file or node.vendor_file:
            lines.append(f"- `{node.current_path}`")
    return "\n".join(lines)


def _entrypoints_content(manifest: Manifest) -> str:
    lines = ["# Entrypoints", ""]
    for entrypoint in manifest.entrypoints or ["No entrypoints detected."]:
        lines.append(f"- {entrypoint}")
    return "\n".join(lines)


def _risks_content(manifest: Manifest) -> str:
    lines = ["# Risks", ""]
    high_risk = [node for node in manifest.files if node.risk_level == "high"]
    if not high_risk:
        lines.append("- No high-risk files detected.")
    for node in high_risk:
        lines.append(f"- `{node.current_path}` ({node.file_kind})")
    return "\n".join(lines)


def _runbook_index(manifest: Manifest) -> str:
    return """# Runbooks

- [How to inspect the workspace](how_to_inspect.md)
- [How to run Python tools](how_to_run_python_tools.md)
- [How to extend classifiers](how_to_extend_classifiers.md)
"""


def _runbook_inspect(manifest: Manifest) -> str:
    starts = _starting_points(manifest)
    bullets = "\n".join(f"- `{item}`" for item in starts)
    return f"""# How To Inspect

Start with these files or directories:

{bullets}

Then read:

- `.librarian/manifest.json`
- `.librarian/notes/code.md`
- `.librarian/notes/entrypoints.md`
"""


def _runbook_python_tools(manifest: Manifest) -> str:
    python_files = [node.current_path for node in manifest.files if node.detected_language == "Python"][:20]
    bullets = "\n".join(f"- `{item}`" for item in python_files) or "- No Python files detected."
    return f"""# How To Run Python Tools

Potential Python entry files:

{bullets}

Run helper scripts with:

```powershell
python .librarian/scripts/inspect_workspace.py
python .librarian/scripts/find_entrypoints.py
```
"""


def _runbook_extend_classifiers(manifest: Manifest) -> str:
    return """# How To Extend Classifiers

1. Update offline heuristics in `src/librarian/classifiers.py`.
2. Add or refine code analyzers in `src/librarian/code_analyzers/`.
3. Re-run:
   - `librarian scan <path>`
   - `librarian mark <path>`
   - `librarian dev index <path>`
4. Check `.librarian/notes/` and `manifest.json` for expected changes.
"""


def _starting_points(manifest: Manifest) -> list[str]:
    if manifest.entrypoints:
        return manifest.entrypoints[:5]
    top_code = [node.current_path for node in manifest.files if node.detected_language == "Python"][:5]
    if top_code:
        return top_code
    return [directory.current_path for directory in manifest.directories[:5]] or ["."]
