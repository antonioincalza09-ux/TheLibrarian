from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.librarian.graph.builder import build_graph
from src.librarian.graph.exporters import export_graph_json
from src.librarian.graph.graph_queries import query_entrypoints, query_modules, query_risks
from src.librarian.sidecars import read_manifest


def build_agent_context(root: str | Path) -> dict[str, Any]:
    resolved_root = Path(root).resolve()
    manifest = read_manifest(resolved_root)
    graph = build_graph(resolved_root)
    graph_path = export_graph_json(graph, resolved_root)
    entrypoints = query_entrypoints(graph)
    risks = query_risks(graph)
    modules = query_modules(graph)
    scripts = _scripts(resolved_root)
    top_files = _top_files(manifest)
    top_directories = _top_directories(manifest)
    warnings = list(manifest.warnings)
    if risks:
        warnings.append("Review risks before modifying source, generated, vendor, or lock files.")

    context = {
        "workspace_summary": {
            "workspace_root": str(resolved_root),
            "files": manifest.counts.files,
            "directories": manifest.counts.directories,
            "languages": manifest.detected_languages,
            "domains": manifest.detected_domains,
        },
        "top_files": top_files,
        "top_directories": top_directories,
        "entrypoints": entrypoints,
        "risks": risks,
        "runnable_scripts": scripts,
        "graph_files": {
            "manifest": ".librarian/manifest.json",
            "graph_json": _relative(graph_path, resolved_root),
            "graph_notes": ".librarian/graph_notes",
            "validation_report": ".librarian/validation_report.json",
        },
        "recommended_first_reads": _recommended_first_reads(entrypoints, top_files),
        "warnings": warnings,
        "suggested_queries": [
            "librarian graph query <path> --kind entrypoints",
            "librarian graph query <path> --kind risks",
            "librarian graph query <path> --kind modules",
            "librarian graph query <path> --kind tags",
        ],
        "important_modules": modules[:20],
        "runbooks": _runbooks(resolved_root),
    }
    librarian_root = resolved_root / ".librarian"
    librarian_root.mkdir(parents=True, exist_ok=True)
    (librarian_root / "agent_context.json").write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    (librarian_root / "agent_context.md").write_text(_markdown(context), encoding="utf-8")
    return context


def _top_files(manifest) -> list[dict[str, Any]]:
    files = sorted(
        manifest.files,
        key=lambda node: (
            0 if node.code_metadata and node.code_metadata.entrypoints else 1,
            0 if node.name.lower().startswith("readme") else 1,
            node.depth,
            node.current_path,
        ),
    )
    return [
        {
            "path": node.current_path,
            "type": node.file_kind,
            "language": node.detected_language,
            "risk": node.risk_level,
            "summary": node.summary,
        }
        for node in files[:20]
    ]


def _top_directories(manifest) -> list[dict[str, Any]]:
    directories = sorted(manifest.directories, key=lambda node: (node.depth, node.current_path))
    return [
        {
            "path": node.current_path,
            "roles": node.directory_analysis.possible_roles if node.directory_analysis else [],
            "summary": node.summary,
        }
        for node in directories[:20]
    ]


def _recommended_first_reads(entrypoints: list[dict[str, Any]], top_files: list[dict[str, Any]]) -> list[str]:
    reads = [item["file"] for item in entrypoints[:8]]
    reads.extend(item["path"] for item in top_files if item["path"] not in reads)
    reads.extend([".librarian/manifest.json", ".librarian/graph_notes/agent_start_here.md", ".librarian/graph_notes/risks.md"])
    return reads[:20]


def _scripts(root: Path) -> list[str]:
    scripts: list[str] = []
    for scripts_dir in [root / ".librarian" / "scripts", root / ".librarian" / "graph_scripts"]:
        if scripts_dir.exists():
            scripts.extend(_relative(path, root) for path in sorted(scripts_dir.glob("*.py")))
    return scripts


def _runbooks(root: Path) -> list[str]:
    runbooks_dir = root / ".librarian" / "runbooks"
    if not runbooks_dir.exists():
        return []
    return [_relative(path, root) for path in sorted(runbooks_dir.glob("*.md"))]


def _markdown(context: dict[str, Any]) -> str:
    summary = context["workspace_summary"]
    entrypoint_lines = [f"- `{item['file']}`: {item['entrypoint']}" for item in context["entrypoints"][:12]] or ["- None detected."]
    script_lines = [f"- `python {item}`" for item in context["runnable_scripts"]] or ["- None detected."]
    risk_lines = [f"- `{item['path']}`: {item['risk']}" for item in context["risks"][:20]] or ["- No risks detected."]
    lines = [
        "# Agent Context",
        "",
        "## Workspace",
        "",
        f"- Root: `{summary['workspace_root']}`",
        f"- Files: `{summary['files']}`",
        f"- Directories: `{summary['directories']}`",
        f"- Languages: {', '.join(summary['languages']) or 'none'}",
        f"- Domains: {', '.join(summary['domains']) or 'none'}",
        "",
        "## Where To Start",
        "",
        *[f"- `{item}`" for item in context["recommended_first_reads"]],
        "",
        "## Entrypoints",
        "",
        *entrypoint_lines,
        "",
        "## Runnable Scripts",
        "",
        *script_lines,
        "",
        "## Risks",
        "",
        *risk_lines,
        "",
        "## Query Suggestions",
        "",
        *[f"- `{item}`" for item in context["suggested_queries"]],
        "",
        "## Runtime Paths",
        "",
        f"- Manifest: `{context['graph_files']['manifest']}`",
        f"- Graph JSON: `{context['graph_files']['graph_json']}`",
        f"- Graph notes: `{context['graph_files']['graph_notes']}`",
    ]
    return "\n".join(lines) + "\n"


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
