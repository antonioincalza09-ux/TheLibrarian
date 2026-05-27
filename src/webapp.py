from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.chat import create_chat_session, execute_chat_command
from src.config import RuntimeConfig
from src.executor import execute_plan
from src.jobs import JobRunner, JobStore
from src.jsonio import read_plan
from src.managed import load_managed_session, list_managed_sessions, start_managed_cleanup
from src.policy_packs import get_policy_pack, list_policy_packs, recommend_policy_packs
from src.planner import build_plan
from src.providers import ProviderContext, available_providers, get_provider
from src.providers.diagnostics import diagnose_provider
from src.reporter import write_plan_artifact
from src.scanner import scan_directory
from src.security import SafetyError, resolve_root


class ConfirmationRequired(SafetyError):
    pass


def _load_json_if_present(path: Path) -> tuple[object | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _load_text_if_present(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, str(exc)


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _abbr_path(path: Path, max_parts: int = 4) -> str:
    parts = path.parts
    if len(parts) <= max_parts:
        return str(path)
    return str(Path("...", *parts[-max_parts:]))


def _status_variant(kind: str) -> str:
    lowered = kind.lower()
    if lowered in {"error", "errors", "high", "failed"}:
        return "danger"
    if lowered in {"warning", "warnings", "medium", "stale", "missing"}:
        return "warn"
    return "ok"


def _manifest_sidecar_path(root: Path, item_path: str, node_type: str) -> Path:
    if node_type == "directory":
        return root / ".librarian.yaml" if item_path == "." else root / item_path / ".librarian.yaml"
    return root / f"{item_path}.librarian.yaml"


def _normalize_graph_node(raw: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(raw.get("id") or raw.get("node_id") or raw.get("path") or raw.get("label") or "unknown"),
        "label": str(raw.get("label") or raw.get("name") or raw.get("title") or raw.get("id") or "Unknown"),
        "type": str(raw.get("type") or raw.get("node_type") or "unknown"),
        "path": raw.get("path"),
        "tags": list(raw.get("tags", [])) if isinstance(raw.get("tags"), list) else [],
        "confidence": float(raw.get("confidence", 0.0) or 0.0),
        "summary": str(raw.get("summary") or raw.get("description") or ""),
    }


def _normalize_graph_edge(raw: dict[str, object]) -> dict[str, object]:
    return {
        "source": str(raw.get("source") or raw.get("from") or raw.get("src") or ""),
        "target": str(raw.get("target") or raw.get("to") or raw.get("dst") or ""),
        "type": str(raw.get("type") or raw.get("edge_type") or "related"),
        "confidence": float(raw.get("confidence", 0.0) or 0.0),
        "reason": str(raw.get("reason") or raw.get("label") or ""),
    }


def _read_librarian_state(root: Path) -> dict[str, object]:
    runtime = root / ".librarian"
    manifest, manifest_error = _load_json_if_present(runtime / "manifest.json")
    graph, graph_error = _load_json_if_present(runtime / "graph.json")
    validation, validation_error = _load_json_if_present(runtime / "validation_report.json")
    agent_context, agent_context_error = _load_json_if_present(runtime / "agent_context.json")
    plan, plan_error = _load_json_if_present(runtime / "plan.json")
    graph_report, graph_report_error = _load_text_if_present(runtime / "graph_report.md")
    notes = sorted((runtime / "notes").glob("*.md")) if (runtime / "notes").exists() else []
    graph_notes = sorted((runtime / "graph_notes").glob("*.md")) if (runtime / "graph_notes").exists() else []
    runbooks = sorted((runtime / "runbooks").glob("*.md")) if (runtime / "runbooks").exists() else []
    scripts = sorted((runtime / "scripts").glob("*.py")) if (runtime / "scripts").exists() else []
    operations_path = runtime / "logs" / "operations.jsonl"
    operations: list[dict[str, object]] = []
    if operations_path.exists():
        for line in operations_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                operations.append(json.loads(line))
            except json.JSONDecodeError:
                operations.append({"timestamp": "", "action": "parse_error", "status": "warning", "message": "Invalid operations log line."})
    graph_nodes = []
    graph_edges = []
    if isinstance(graph, dict):
        raw_nodes = graph.get("nodes") or graph.get("graph", {}).get("nodes") or []
        raw_edges = graph.get("edges") or graph.get("graph", {}).get("edges") or []
        if isinstance(raw_nodes, list):
            graph_nodes = [_normalize_graph_node(node) for node in raw_nodes if isinstance(node, dict)]
        if isinstance(raw_edges, list):
            graph_edges = [_normalize_graph_edge(edge) for edge in raw_edges if isinstance(edge, dict)]
    return {
        "runtime": runtime,
        "manifest": manifest if isinstance(manifest, dict) else None,
        "manifest_error": manifest_error,
        "graph": graph if isinstance(graph, dict) else None,
        "graph_error": graph_error,
        "validation": validation if isinstance(validation, dict) else None,
        "validation_error": validation_error,
        "agent_context": agent_context if isinstance(agent_context, dict) else None,
        "agent_context_error": agent_context_error,
        "plan": plan if isinstance(plan, dict) else None,
        "plan_error": plan_error,
        "graph_report": graph_report,
        "graph_report_error": graph_report_error,
        "notes": notes,
        "graph_notes": graph_notes,
        "runbooks": runbooks,
        "scripts": scripts,
        "operations": operations,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
    }


def _build_librarian_dashboard(root: Path) -> dict[str, object]:
    state = _read_librarian_state(root)
    manifest = state["manifest"] if isinstance(state["manifest"], dict) else None
    files = _build_file_rows(root, manifest)
    directories = _build_directory_rows(root, manifest)
    code = _build_code_summary(files)
    graph = _build_graph_summary(state, files, code["entrypoints"])
    risks = _build_risks(state, files, directories)
    diagnostics = _build_diagnostics(root, state, files, directories, risks, graph)
    overview = _build_overview(root, manifest, files, directories, code, graph, risks, state, diagnostics)
    start_here = _build_start_here(root, state, manifest, files, code, risks, diagnostics)
    runbooks = _build_runbook_rows(root, state)
    scripts = _build_script_rows(root, state)
    operations = _build_operation_rows(state)
    workspace = {
        "name": root.name,
        "path": str(root),
        "short_path": _abbr_path(root),
        "last_indexed": manifest.get("generated_at") if manifest else None,
        "status": overview["status"],
        "summary": overview["hero"]["description"],
        "project_type": overview["hero"]["project_type"],
        "confidence": overview["hero"]["confidence"],
        "languages": overview["hero"]["languages"],
        "frameworks": overview["hero"]["frameworks"],
    }
    return {
        "workspace": workspace,
        "overview": overview,
        "start_here": start_here,
        "files": files,
        "directories": directories,
        "code": code,
        "graph": graph,
        "risks": risks,
        "runbooks": runbooks,
        "scripts": scripts,
        "operations": operations,
        "diagnostics": diagnostics,
        "agent_brief": _build_agent_brief(workspace, start_here, code, risks, state),
    }


def _build_file_rows(root: Path, manifest: dict[str, object] | None) -> list[dict[str, object]]:
    if manifest is None:
        return []
    rows: list[dict[str, object]] = []
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        current_path = str(item.get("current_path") or item.get("original_path") or "")
        sidecar_exists = _manifest_sidecar_path(root, current_path, "file").exists()
        classification = item.get("classification", {}) if isinstance(item.get("classification"), dict) else {}
        code_metadata = item.get("code_metadata", {}) if isinstance(item.get("code_metadata"), dict) else {}
        rows.append(
            {
                "name": item.get("name") or Path(current_path).name,
                "path": current_path,
                "kind": item.get("file_kind") or "unknown",
                "language": item.get("detected_language") or code_metadata.get("language"),
                "tags": list(item.get("tags", [])) if isinstance(item.get("tags"), list) else [],
                "risk": item.get("risk_level") or "low",
                "confidence": float(classification.get("confidence", 0.0) or 0.0),
                "summary": item.get("summary") or classification.get("reason") or "",
                "generated": bool(item.get("generated_file")),
                "vendor": bool(item.get("vendor_file")),
                "lockfile": bool(item.get("lock_file")),
                "should_modify": bool(item.get("should_modify")),
                "should_move": bool(item.get("should_move")),
                "sidecar_status": "present" if sidecar_exists else "missing",
                "modified_at": item.get("modified_at"),
                "size_bytes": int(item.get("size_bytes", 0) or 0),
                "mime_type": item.get("mime_type"),
                "domain": classification.get("domain") or "General",
                "category": classification.get("category") or "Unsorted",
                "entrypoints": list(code_metadata.get("entrypoints", [])) if isinstance(code_metadata.get("entrypoints"), list) else [],
                "framework_hints": list(code_metadata.get("framework_hints", [])) if isinstance(code_metadata.get("framework_hints"), list) else [],
                "test_hints": list(code_metadata.get("test_hints", [])) if isinstance(code_metadata.get("test_hints"), list) else [],
                "imports_internal": list((code_metadata.get("imports", {}) or {}).get("internal", [])) if isinstance(code_metadata.get("imports"), dict) else [],
                "imports_external": list((code_metadata.get("imports", {}) or {}).get("external", [])) if isinstance(code_metadata.get("imports"), dict) else [],
                "symbols": code_metadata.get("symbols", {}),
                "readable": bool(item.get("readable", True)),
                "human_description": item.get("human_description") or "",
            }
        )
    return rows


def _build_directory_rows(root: Path, manifest: dict[str, object] | None) -> list[dict[str, object]]:
    if manifest is None:
        return []
    rows: list[dict[str, object]] = []
    for item in manifest.get("directories", []):
        if not isinstance(item, dict):
            continue
        current_path = str(item.get("current_path") or ".")
        analysis = item.get("directory_analysis", {}) if isinstance(item.get("directory_analysis"), dict) else {}
        roles = list(analysis.get("possible_roles", [])) if isinstance(analysis.get("possible_roles"), list) else []
        sidecar_exists = _manifest_sidecar_path(root, current_path, "directory").exists()
        confidence = 0.94 if roles else 0.55
        rows.append(
            {
                "name": item.get("name") or Path(current_path).name or root.name,
                "path": current_path,
                "roles": roles,
                "theme": analysis.get("theme") or "General",
                "direct_file_count": int(analysis.get("direct_file_count", 0) or 0),
                "direct_subdirectory_count": int(analysis.get("direct_subdirectory_count", 0) or 0),
                "total_file_count": int(analysis.get("total_file_count", 0) or 0),
                "dominant_languages": list(analysis.get("dominant_languages", [])) if isinstance(analysis.get("dominant_languages"), list) else [],
                "dominant_extensions": list(analysis.get("dominant_extensions", [])) if isinstance(analysis.get("dominant_extensions"), list) else [],
                "should_reorganize": bool(analysis.get("should_reorganize")),
                "risk": "high" if "project_root" in roles else "medium" if any(role in {"vendor", "generated"} for role in roles) else "low",
                "confidence": confidence,
                "description": item.get("human_description") or analysis.get("reason") or "",
                "sidecar_status": "present" if sidecar_exists else "missing",
            }
        )
    return rows


def _build_code_summary(files: list[dict[str, object]]) -> dict[str, object]:
    languages = Counter(str(item.get("language") or "") for item in files if item.get("language"))
    frameworks = Counter(
        hint
        for item in files
        for hint in item.get("framework_hints", [])
        if isinstance(hint, str) and hint
    )
    modules = []
    imported_by = defaultdict(int)
    for item in files:
        if item.get("language") == "Python":
            module_name = str(Path(str(item["path"])).with_suffix("").as_posix()).replace("/", ".")
            modules.append(
                {
                    "module": module_name,
                    "file": item["path"],
                    "imports_count": len(item.get("imports_internal", [])) + len(item.get("imports_external", [])),
                    "imported_by_count": 0,
                    "risk": item["risk"],
                    "summary": item["summary"],
                }
            )
            for target in item.get("imports_internal", []):
                imported_by[target] += 1
    for module in modules:
        module["imported_by_count"] = imported_by.get(module["module"], 0)
    entrypoints = []
    tests = []
    config_files = []
    for item in files:
        for entrypoint in item.get("entrypoints", []):
            entrypoints.append(
                {
                    "file": item["path"],
                    "symbol": entrypoint,
                    "type": entrypoint.split(":", 1)[0] if ":" in entrypoint else "entrypoint",
                    "confidence": item["confidence"],
                    "reason": item["summary"],
                    "command": f'python "{item["path"]}"' if item.get("language") == "Python" else item["path"],
                }
            )
        if item.get("test_hints") or item.get("category") == "Tests":
            tests.append(
                {
                    "file": item["path"],
                    "tested_target": item.get("imports_internal", [None])[0],
                    "framework": ", ".join(item.get("framework_hints", []) or ["pytest" if "test" in str(item["path"]).lower() else "unknown"]),
                    "confidence": item["confidence"],
                }
            )
        if item.get("kind") == "config":
            config_files.append(item["path"])
    return {
        "languages": [{"name": name, "count": count} for name, count in languages.most_common()],
        "frameworks": [{"name": name, "count": count} for name, count in frameworks.most_common()],
        "packages": sorted({str(Path(item["path"]).parts[0]) for item in files if item.get("language") == "Python" and "/" in str(item["path"])})[:20],
        "modules": modules,
        "entrypoints": entrypoints,
        "tests": tests,
        "config_files": config_files[:50],
    }


def _build_graph_summary(state: dict[str, object], files: list[dict[str, object]], entrypoints: list[dict[str, object]]) -> dict[str, object]:
    nodes = list(state.get("graph_nodes", []))
    edges = list(state.get("graph_edges", []))
    available = bool(nodes or edges)
    node_types = Counter(str(node.get("type") or "unknown") for node in nodes)
    edge_types = Counter(str(edge.get("type") or "related") for edge in edges)
    degree = Counter()
    for edge in edges:
        degree[str(edge.get("source"))] += 1
        degree[str(edge.get("target"))] += 1
    top_connected = []
    for node in nodes:
        node_id = str(node.get("id"))
        top_connected.append({"id": node_id, "label": node.get("label"), "degree": degree.get(node_id, 0), "type": node.get("type")})
    top_connected.sort(key=lambda item: item["degree"], reverse=True)
    isolated = [node for node in nodes if degree.get(str(node.get("id")), 0) == 0][:20]
    entrypoint_files = {item["file"] for item in entrypoints}
    entrypoint_neighborhood = [edge for edge in edges if str(edge.get("source")) in entrypoint_files or str(edge.get("target")) in entrypoint_files][:40]
    return {
        "available": available,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "top_connected": top_connected[:10],
            "top_tags": [{"name": name, "count": count} for name, count in node_types.most_common()],
            "top_edge_types": [{"name": name, "count": count} for name, count in edge_types.most_common()],
            "isolated_nodes": isolated,
        },
        "entrypoint_neighborhood": entrypoint_neighborhood,
        "empty_message": "Graph is missing. Generate graph data to unlock relationship views." if not available else "",
    }


def _build_risks(state: dict[str, object], files: list[dict[str, object]], directories: list[dict[str, object]]) -> list[dict[str, object]]:
    risks: list[dict[str, object]] = []
    for item in files:
        if item["risk"] == "high":
            risks.append({"severity": "Error", "item": item["path"], "reason": item["summary"] or "High-risk file.", "recommended_action": "Inspect before editing.", "source": "manifest", "confidence": item["confidence"]})
        if item["generated"] or item["vendor"] or item["lockfile"]:
            risks.append({"severity": "Warning", "item": item["path"], "reason": "Generated/vendor/lock file.", "recommended_action": "Avoid editing unless necessary.", "source": "manifest", "confidence": item["confidence"]})
        if item["confidence"] < 0.6:
            risks.append({"severity": "Info", "item": item["path"], "reason": "Low-confidence classification.", "recommended_action": "Review metadata before relying on this classification.", "source": "manifest", "confidence": item["confidence"]})
        if not item["readable"]:
            risks.append({"severity": "Warning", "item": item["path"], "reason": "Unreadable file.", "recommended_action": "Check file permissions or file encoding.", "source": "manifest", "confidence": item["confidence"]})
        if item["sidecar_status"] == "missing":
            risks.append({"severity": "Warning", "item": item["path"], "reason": "Missing sidecar metadata.", "recommended_action": 'Run "librarian mark <path>".', "source": "filesystem", "confidence": 1.0})
        if item["size_bytes"] > 5_000_000:
            risks.append({"severity": "Warning", "item": item["path"], "reason": "Large file.", "recommended_action": "Inspect carefully before loading or editing.", "source": "manifest", "confidence": 1.0})
    for item in directories:
        if item["sidecar_status"] == "missing":
            risks.append({"severity": "Warning", "item": item["path"], "reason": "Missing directory sidecar.", "recommended_action": 'Run "librarian mark <path>".', "source": "filesystem", "confidence": 1.0})
    validation = state.get("validation")
    if isinstance(validation, dict):
        for error in validation.get("errors", []):
            risks.append({"severity": "Error", "item": "validation", "reason": str(error), "recommended_action": "Review validation report.", "source": "validation_report.json", "confidence": 1.0})
        for warning in validation.get("warnings", []):
            risks.append({"severity": "Warning", "item": "validation", "reason": str(warning), "recommended_action": "Inspect validation warning.", "source": "validation_report.json", "confidence": 1.0})
    if state.get("graph_error") == "missing":
        risks.append({"severity": "Info", "item": ".librarian/graph.json", "reason": "Graph is missing.", "recommended_action": "Generate graph to unlock relationship views.", "source": "filesystem", "confidence": 1.0})
    return risks[:300]


def _build_diagnostics(
    root: Path,
    state: dict[str, object],
    files: list[dict[str, object]],
    directories: list[dict[str, object]],
    risks: list[dict[str, object]],
    graph: dict[str, object],
) -> dict[str, object]:
    manifest = state.get("manifest")
    manifest_status = "ok" if manifest else "missing"
    last_indexed = manifest.get("generated_at") if isinstance(manifest, dict) else None
    stale = False
    if isinstance(last_indexed, str):
        try:
            generated_at = datetime.fromisoformat(last_indexed)
            stale = datetime.now(timezone.utc) - generated_at > __import__("datetime").timedelta(days=7)
        except ValueError:
            stale = False
    diagnostics_items = [
        {"label": "Manifest", "status": "warning" if manifest_status == "missing" else "ok", "detail": ".librarian/manifest.json"},
        {"label": "Graph", "status": "warning" if not graph["available"] else "ok", "detail": ".librarian/graph.json"},
        {"label": "Validation", "status": "warning" if state.get("validation_error") == "missing" else "ok", "detail": ".librarian/validation_report.json"},
        {"label": "Notes", "status": "ok" if state.get("notes") else "warning", "detail": f"{len(state.get('notes', []))} markdown notes"},
        {"label": "Runbooks", "status": "ok" if state.get("runbooks") else "warning", "detail": f"{len(state.get('runbooks', []))} runbooks"},
        {"label": "Scripts", "status": "ok" if state.get("scripts") else "warning", "detail": f"{len(state.get('scripts', []))} runnable scripts"},
    ]
    return {
        "items": diagnostics_items,
        "manifest_status": manifest_status,
        "graph_status": "ok" if graph["available"] else "missing",
        "validation_status": "missing" if state.get("validation_error") == "missing" else "ok",
        "stale_index": stale,
        "schema_version": manifest.get("librarian_version") if isinstance(manifest, dict) else None,
        "parsing_errors": [value for key, value in state.items() if key.endswith("_error") and value not in {None, "missing"}],
        "warnings": len([risk for risk in risks if risk["severity"] in {"Warning", "Info"}]),
        "errors": len([risk for risk in risks if risk["severity"] == "Error"]),
        "suggestions": _diagnostic_suggestions(state, files, directories, graph, stale),
    }


def _build_overview(
    root: Path,
    manifest: dict[str, object] | None,
    files: list[dict[str, object]],
    directories: list[dict[str, object]],
    code: dict[str, object],
    graph: dict[str, object],
    risks: list[dict[str, object]],
    state: dict[str, object],
    diagnostics: dict[str, object],
) -> dict[str, object]:
    languages = [item["name"] for item in code["languages"][:4]]
    frameworks = [item["name"] for item in code["frameworks"][:4]]
    project_type = "Workspace"
    if any(directory["risk"] == "high" and "project_root" in directory["roles"] for directory in directories):
        project_type = "Codebase"
    elif languages:
        project_type = f"{languages[0]} workspace"
    hero_confidence = round(min(0.98, 0.55 + (0.08 * min(len(languages), 3)) + (0.05 * min(len(frameworks), 2))), 2)
    if manifest is None:
        hero_confidence = 0.2
    high_risks = len([risk for risk in risks if risk["severity"] == "Error"])
    warnings = len([risk for risk in risks if risk["severity"] == "Warning"])
    status = "Healthy"
    if manifest is None:
        status = "Needs Index"
    elif high_risks:
        status = "Errors"
    elif warnings or diagnostics["stale_index"]:
        status = "Warnings"
    metrics = [
        {"label": "Files", "value": len(files), "variant": "neutral"},
        {"label": "Directories", "value": len(directories), "variant": "neutral"},
        {"label": "Entrypoints", "value": len(code["entrypoints"]), "variant": "neutral"},
        {"label": "Tests", "value": len(code["tests"]), "variant": "neutral"},
        {"label": "Risks", "value": len(risks), "variant": "warn" if risks else "ok"},
        {"label": "Tags", "value": len({tag for item in files for tag in item["tags"]}), "variant": "neutral"},
        {"label": "Graph nodes", "value": graph["summary"]["nodes"], "variant": "neutral"},
        {"label": "Graph edges", "value": graph["summary"]["edges"], "variant": "neutral"},
    ]
    do_not_touch = [item for item in files if item["generated"] or item["vendor"] or item["lockfile"] or item["risk"] == "high"][:7]
    recent_operations = _build_operation_rows(state)[:7]
    health_items = [
        {"label": "Missing manifest", "value": 0 if manifest else 1, "variant": "danger" if manifest is None else "ok"},
        {"label": "Validation errors", "value": len([risk for risk in risks if risk["source"] == "validation_report.json" and risk["severity"] == "Error"]), "variant": "danger"},
        {"label": "Low confidence items", "value": len([item for item in files if item["confidence"] < 0.6]), "variant": "warn"},
        {"label": "Stale graph", "value": 0 if graph["available"] else 1, "variant": "warn"},
        {"label": "Missing runbooks", "value": 0 if state.get("runbooks") else 1, "variant": "warn"},
        {"label": "Missing sidecars", "value": len([risk for risk in risks if "sidecar" in risk["reason"].lower()]), "variant": "warn"},
    ]
    return {
        "status": status,
        "hero": {
            "title": root.name,
            "description": "Developer-first workspace dashboard for understanding structure, code intelligence, risk, and runnable context.",
            "languages": languages,
            "frameworks": frameworks,
            "project_type": project_type,
            "confidence": hero_confidence,
        },
        "metrics": metrics,
        "do_not_touch": do_not_touch,
        "health": health_items,
        "recent_operations": recent_operations,
    }


def _build_start_here(
    root: Path,
    state: dict[str, object],
    manifest: dict[str, object] | None,
    files: list[dict[str, object]],
    code: dict[str, object],
    risks: list[dict[str, object]],
    diagnostics: dict[str, object],
) -> dict[str, object]:
    recommended_reads = []
    candidate_paths = [
        "README.md",
        ".librarian/README.librarian.md",
        ".librarian/notes/index.md",
        ".librarian/notes/explain.md",
        ".librarian/graph_report.md",
        ".librarian/runbooks/index.md",
    ]
    for candidate in candidate_paths:
        candidate_path = root / candidate
        if candidate_path.exists():
            recommended_reads.append({"label": candidate_path.name, "path": candidate, "reason": "Recommended first read."})
    for entrypoint in code["entrypoints"][:3]:
        recommended_reads.append({"label": entrypoint["file"], "path": entrypoint["file"], "reason": entrypoint["reason"]})
    important_files = [item for item in files if item["entrypoints"] or item["risk"] == "high" or item["kind"] == "config"][:10]
    commands = [
        {"label": "Re-index workspace", "command": f'librarian dev index "{root}"', "modifies": True},
        {"label": "Refresh metadata", "command": f'librarian mark "{root}"', "modifies": True},
        {"label": "Show workspace status", "command": f'librarian status "{root}"', "modifies": False},
        {"label": "Inspect manifest summary", "command": 'python .librarian/scripts/print_manifest_summary.py', "modifies": False},
    ]
    return {
        "recommended_reads": recommended_reads[:7],
        "recommended_commands": commands,
        "runnable_scripts": _build_script_rows(root, state)[:6],
        "important_files": important_files,
        "main_entrypoints": code["entrypoints"][:8],
        "main_risks": risks[:8],
        "agent_instructions": state.get("agent_context") or {"message": "No agent context file found. Use the generated brief below."},
        "empty_message": "Run librarian mark and librarian dev index to generate a richer start-here view." if manifest is None else "",
    }


def _build_runbook_rows(root: Path, state: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for path in state.get("runbooks", []):
        if not isinstance(path, Path):
            continue
        rows.append(
            {
                "name": path.name,
                "path": _relative_to_root(root, path),
                "description": f"Runbook generated by The Librarian: {path.stem.replace('_', ' ')}",
                "command": f'type "{_relative_to_root(root, path)}"',
                "read_only": True,
                "validated": path.exists(),
            }
        )
    return rows


def _build_script_rows(root: Path, state: dict[str, object]) -> list[dict[str, object]]:
    descriptions = {
        "inspect_workspace.py": "Inspect the manifest and print a quick workspace summary.",
        "print_manifest_summary.py": "Print counts, languages, domains, entrypoints, and warnings.",
        "find_entrypoints.py": "List likely entrypoints extracted from manifest and sidecars.",
        "find_unmarked.py": "List files or directories that are missing sidecars.",
    }
    rows = []
    for path in state.get("scripts", []):
        if not isinstance(path, Path):
            continue
        rows.append(
            {
                "name": path.name,
                "path": _relative_to_root(root, path),
                "description": descriptions.get(path.name, "Runnable helper generated by The Librarian."),
                "command": f'python "{_relative_to_root(root, path)}"',
                "read_only": path.name != "find_unmarked.py" or True,
                "validated": path.exists(),
                "expected_input": ".librarian/manifest.json",
                "expected_output": "Console summary",
            }
        )
    return rows


def _build_operation_rows(state: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for operation in list(state.get("operations", []))[-80:]:
        if not isinstance(operation, dict):
            continue
        rows.append(
            {
                "timestamp": operation.get("timestamp") or "",
                "type": operation.get("action") or operation.get("type") or "operation",
                "item": operation.get("source") or operation.get("item") or "",
                "result": operation.get("status") or "unknown",
                "detail": operation.get("message") or operation.get("destination") or "",
                "rollback_available": operation.get("action") == "move" and operation.get("status") == "applied",
            }
        )
    rows.reverse()
    return rows


def _build_agent_brief(
    workspace: dict[str, object],
    start_here: dict[str, object],
    code: dict[str, object],
    risks: list[dict[str, object]],
    state: dict[str, object],
) -> str:
    reads = "\n".join(f"- {item['path']}" for item in start_here["recommended_reads"][:5]) or "- No recommended reads available."
    scripts = "\n".join(f"- {item['command']}" for item in start_here["runnable_scripts"][:4]) or "- No runnable scripts available."
    risk_items = "\n".join(f"- {item['item']}: {item['reason']}" for item in risks[:5]) or "- No major risks detected."
    entrypoints = "\n".join(f"- {item['file']} ({item['symbol']})" for item in code["entrypoints"][:5]) or "- No entrypoints detected."
    graph_path = ".librarian/graph.json" if state.get("graph") else "(graph missing)"
    return f"""Workspace summary: {workspace['summary']}

Recommended first reads:
{reads}

Runnable scripts:
{scripts}

Entrypoints:
{entrypoints}

Risks:
{risk_items}

Graph path: {graph_path}
"""


def _diagnostic_suggestions(
    state: dict[str, object],
    files: list[dict[str, object]],
    directories: list[dict[str, object]],
    graph: dict[str, object],
    stale: bool,
) -> list[str]:
    suggestions = []
    if state.get("manifest_error") == "missing":
        suggestions.append('Run "librarian mark <path>" to create metadata.')
    if not state.get("notes"):
        suggestions.append('Run "librarian dev init <path>" to generate notes and scripts.')
    if not graph["available"]:
        suggestions.append("Graph is missing. Generate graph data to unlock relationship views.")
    if stale:
        suggestions.append('Run "librarian dev index <path>" to refresh stale metadata.')
    if any(item["sidecar_status"] == "missing" for item in files + directories):
        suggestions.append('Run "librarian mark <path>" to repair missing sidecars.')
    return suggestions


def _filter_files(files: list[dict[str, object]], query: dict[str, list[str]]) -> list[dict[str, object]]:
    search = query.get("q", [""])[0].strip().lower()
    risk = query.get("risk", [""])[0]
    language = query.get("language", [""])[0]
    kind = query.get("kind", [""])[0]
    tag = query.get("tag", [""])[0]
    sort_by = query.get("sort", ["name"])[0]
    descending = query.get("desc", ["false"])[0].lower() == "true"
    rows = []
    for item in files:
        if risk and item["risk"] != risk:
            continue
        if language and str(item.get("language") or "") != language:
            continue
        if kind and str(item.get("kind") or "") != kind:
            continue
        if tag and tag not in item.get("tags", []):
            continue
        if search:
            haystack = " ".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("path") or ""),
                    str(item.get("summary") or ""),
                    " ".join(item.get("tags", [])),
                    str(item.get("language") or ""),
                ]
            ).lower()
            if search not in haystack:
                continue
        rows.append(item)
    key_map = {
        "name": lambda row: str(row.get("name") or ""),
        "size": lambda row: int(row.get("size_bytes") or 0),
        "risk": lambda row: str(row.get("risk") or ""),
        "confidence": lambda row: float(row.get("confidence") or 0.0),
        "modified": lambda row: str(row.get("modified_at") or ""),
    }
    rows.sort(key=key_map.get(sort_by, key_map["name"]), reverse=descending)
    return rows


def _filter_directories(directories: list[dict[str, object]], query: dict[str, list[str]]) -> list[dict[str, object]]:
    search = query.get("q", [""])[0].strip().lower()
    risk = query.get("risk", [""])[0]
    role = query.get("role", [""])[0]
    rows = []
    for item in directories:
        if risk and item["risk"] != risk:
            continue
        if role and role not in item.get("roles", []):
            continue
        if search:
            haystack = " ".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("path") or ""),
                    str(item.get("description") or ""),
                    " ".join(item.get("roles", [])),
                    str(item.get("theme") or ""),
                ]
            ).lower()
            if search not in haystack:
                continue
        rows.append(item)
    rows.sort(key=lambda row: str(row.get("path") or ""))
    return rows


def create_server(root: str | Path, *, host: str, port: int, config: RuntimeConfig) -> ThreadingHTTPServer:
    root_lock = threading.RLock()
    resolved_root = resolve_root(root)
    root_state = {"path": resolved_root, "chat": create_chat_session(resolved_root)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, status: int, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _body(self) -> dict[str, object]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length == 0:
                return {}
            payload = json.loads(self.rfile.read(content_length).decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def _confirm(self, query: dict[str, list[str]], action: str) -> None:
            if query.get("confirm", ["false"])[0].lower() != "true":
                raise ConfirmationRequired(f"{action} requires confirm=true.")

        def _root(self) -> Path:
            with root_lock:
                return root_state["path"]

        def _set_root(self, root_value: object) -> Path:
            if not isinstance(root_value, str) or not root_value.strip():
                raise SafetyError("Request body must include root path.")
            next_root = resolve_root(root_value)
            with root_lock:
                root_state["path"] = next_root
                root_state["chat"] = create_chat_session(next_root)
            return next_root

        def _chat(self):
            with root_lock:
                return root_state["chat"]

        def _inventory(self) -> dict[str, object]:
            return scan_directory(self._root()).to_dict()

        def _plan(self, pack_id: str | None = None) -> dict[str, object]:
            return _build_current_plan(self._root(), config, pack_id=pack_id).to_dict()

        def _dashboard(self) -> dict[str, object]:
            resolved_root = self._root()
            chat_session = self._chat()
            inventory = chat_session.inventory.to_dict() if chat_session.inventory is not None else self._inventory()
            plan = chat_session.plan.to_dict() if chat_session.plan is not None else self._plan()
            librarian = _build_librarian_dashboard(resolved_root)
            store = JobStore(resolved_root)
            jobs = [job.to_dict() for job in store.list()]
            active_job = jobs[0] if jobs else None
            active_policy = None
            active_events: list[dict[str, object]] = []
            active_manifest = None
            if active_job is not None:
                job_id = str(active_job["job_id"])
                active_events = [event.to_dict() for event in store.read_events(job_id)]
                try:
                    active_policy = store.read_json_artifact(job_id, "policy_decision.json")
                except SafetyError:
                    active_policy = None
                manifest_path = active_job.get("manifest_path")
                if isinstance(manifest_path, str) and manifest_path:
                    try:
                        active_manifest = self._read_root_artifact(manifest_path)
                    except SafetyError:
                        active_manifest = None
            return {
                "root": str(resolved_root),
                "config": {
                    "provider": config.provider,
                    "model": config.model,
                    "endpoint": config.endpoint,
                    "privacy_mode": config.privacy_mode,
                },
                "inventory": inventory,
                "plan": plan,
                "jobs": jobs,
                "active_job": active_job,
                "active_policy": active_policy,
                "active_events": active_events,
                "active_manifest": active_manifest,
                "packs": [pack.to_dict() for pack in list_policy_packs()],
                "managed_sessions": [session.to_dict() for session in list_managed_sessions(resolved_root)],
                "providers": _providers_payload(config),
                "chat": chat_session.snapshot(),
                "librarian": librarian,
            }

        def _read_root_artifact(self, artifact_path: str) -> dict[str, object]:
            resolved_root = self._root()
            path = Path(artifact_path).resolve(strict=False)
            try:
                path.relative_to(resolved_root)
            except ValueError as exc:
                raise SafetyError("Artifact path escapes the assigned root.") from exc
            if not path.exists():
                raise SafetyError(f"Missing artifact: {artifact_path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise SafetyError("Artifact is not a JSON object.")
            return payload

        def _read_root_text_file(self, path: Path) -> str:
            resolved_root = self._root()
            resolved_path = path.resolve(strict=False)
            try:
                resolved_path.relative_to(resolved_root)
            except ValueError as exc:
                raise SafetyError("Artifact path escapes the assigned root.") from exc
            if not resolved_path.exists():
                raise SafetyError(f"Missing artifact: {path}")
            return resolved_path.read_text(encoding="utf-8")

        def _job_id_from_path(self, prefix: str, path: str) -> tuple[str, str]:
            remainder = path.removeprefix(prefix).strip("/")
            parts = remainder.split("/")
            if not parts or not parts[0]:
                raise SafetyError("Missing job id.")
            return parts[0], parts[1] if len(parts) > 1 else ""

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._html(200, _page())
                    return
                if parsed.path == "/api/root":
                    self._json(200, {"root": str(self._root())})
                    return
                if parsed.path == "/api/dashboard":
                    self._json(200, self._dashboard())
                    return
                if parsed.path == "/api/librarian/dashboard":
                    self._json(200, _build_librarian_dashboard(self._root()))
                    return
                if parsed.path == "/api/inventory":
                    self._json(200, self._inventory())
                    return
                if parsed.path == "/api/librarian/files":
                    query = parse_qs(parsed.query)
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, {"files": _filter_files(payload["files"], query)})
                    return
                if parsed.path == "/api/librarian/directories":
                    query = parse_qs(parsed.query)
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, {"directories": _filter_directories(payload["directories"], query)})
                    return
                if parsed.path == "/api/librarian/entrypoints":
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, {"entrypoints": payload["code"]["entrypoints"]})
                    return
                if parsed.path == "/api/librarian/scripts":
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, {"scripts": payload["scripts"]})
                    return
                if parsed.path == "/api/librarian/risks":
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, {"risks": payload["risks"]})
                    return
                if parsed.path == "/api/librarian/graph-summary":
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, payload["graph"])
                    return
                if parsed.path == "/api/librarian/agent-brief":
                    payload = _build_librarian_dashboard(self._root())
                    self._json(200, {"brief": payload["agent_brief"]})
                    return
                if parsed.path == "/api/plan":
                    query = parse_qs(parsed.query)
                    pack_id = query.get("pack_id", [""])[0] or None
                    self._json(200, self._plan(pack_id=pack_id))
                    return
                if parsed.path == "/api/packs":
                    self._json(200, {"packs": [pack.to_dict() for pack in list_policy_packs()]})
                    return
                if parsed.path.startswith("/api/packs/recommend"):
                    query = parse_qs(parsed.query)
                    industry = query.get("industry", [""])[0]
                    self._json(200, {"industry": industry, "packs": [pack.to_dict() for pack in recommend_policy_packs(industry)]})
                    return
                if parsed.path.startswith("/api/packs/"):
                    pack_id = parsed.path.removeprefix("/api/packs/").strip("/")
                    self._json(200, get_policy_pack(pack_id).to_dict())
                    return
                if parsed.path == "/api/managed":
                    self._json(200, {"sessions": [session.to_dict() for session in list_managed_sessions(self._root())]})
                    return
                if parsed.path.startswith("/api/managed/"):
                    remainder = parsed.path.removeprefix("/api/managed/").strip("/")
                    parts = remainder.split("/", 1)
                    session_id = parts[0]
                    suffix = parts[1] if len(parts) > 1 else ""
                    session = load_managed_session(self._root(), session_id)
                    if suffix == "report-html":
                        report_path = self._root() / ".thelibrarian" / "managed" / session.session_id / "report.html"
                        self._html(200, self._read_root_text_file(report_path))
                        return
                    if suffix:
                        self._json(404, {"error": "Not found"})
                        return
                    self._json(200, session.to_dict())
                    return
                if parsed.path == "/api/providers":
                    self._json(200, _providers_payload(config))
                    return
                if parsed.path == "/api/chat":
                    self._json(200, self._chat().snapshot())
                    return
                if parsed.path == "/api/providers/doctor":
                    query = parse_qs(parsed.query)
                    provider_name = query.get("provider", [config.provider])[0]
                    context = ProviderContext(model=config.model, endpoint=config.endpoint, privacy_mode=config.privacy_mode)
                    checks = [check.to_dict() for check in diagnose_provider(provider_name, context, required=False)]
                    self._json(200, {"provider": provider_name, "checks": checks})
                    return
                if parsed.path == "/api/jobs":
                    self._json(200, {"jobs": [job.to_dict() for job in JobStore(self._root()).list()]})
                    return
                if parsed.path.startswith("/api/jobs/"):
                    job_id, suffix = self._job_id_from_path("/api/jobs/", parsed.path)
                    store = JobStore(self._root())
                    if suffix == "":
                        self._json(200, store.load(job_id).to_dict())
                        return
                    if suffix == "events":
                        self._json(200, {"events": [event.to_dict() for event in store.read_events(job_id)]})
                        return
                    if suffix == "policy":
                        self._json(200, store.read_json_artifact(job_id, "policy_decision.json"))
                        return
                    if suffix == "manifest":
                        job = store.load(job_id)
                        if not job.manifest_path:
                            self._json(404, {"error": "Job has no manifest."})
                            return
                        self._json(200, self._read_root_artifact(job.manifest_path))
                        return
                self._json(404, {"error": "Not found"})
            except ConfirmationRequired as exc:
                self._json(403, {"error": str(exc)})
            except (SafetyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                body = self._body()

                if parsed.path == "/api/root":
                    self._confirm(query, "Root change")
                    next_root = self._set_root(body.get("root"))
                    self._json(200, {"root": str(next_root)})
                    return
                if parsed.path == "/api/chat":
                    command = body.get("command")
                    if not isinstance(command, str):
                        self._json(400, {"error": "Request body must include command."})
                        return
                    result = execute_chat_command(self._chat(), command)
                    self._json(200, result)
                    return
                if parsed.path == "/api/chat/reset":
                    with root_lock:
                        root_state["chat"] = create_chat_session(self._root())
                        snapshot = root_state["chat"].snapshot()
                    self._json(200, {"message": "Chat reset.", "session": snapshot})
                    return

                if parsed.path == "/api/plan/save":
                    pack_id = body.get("pack_id")
                    active_chat = self._chat()
                    if active_chat.plan is not None:
                        plan = active_chat.plan
                    else:
                        plan = _build_current_plan(
                            self._root(),
                            config,
                            pack_id=str(pack_id) if pack_id else None,
                        )
                    plan_path = write_plan_artifact(self._root(), plan)
                    self._json(200, {"path": str(plan_path), "plan": plan.to_dict()})
                    return

                if parsed.path == "/api/apply":
                    self._confirm(query, "Apply")
                    plan_path = body.get("plan")
                    if not isinstance(plan_path, str):
                        self._json(400, {"error": "Request body must include plan path."})
                        return
                    plan = read_plan(plan_path)
                    execution = execute_plan(self._root(), plan, dry_run=False)
                    self._json(200, execution.to_dict())
                    return

                if parsed.path == "/api/jobs/create":
                    policy = str(body.get("policy", "dry_run_only"))
                    pack_id = body.get("pack")
                    job = JobRunner(self._root(), config=config).create_job(
                        dry_run=True,
                        policy_name=policy,
                        pack_id=str(pack_id) if pack_id else None,
                    )
                    self._json(200, job.to_dict())
                    return

                if parsed.path == "/api/jobs/run":
                    policy = str(body.get("policy", "dry_run_only"))
                    pack_id = body.get("pack")
                    job = JobRunner(self._root(), config=config).run(
                        dry_run=True,
                        policy_name=policy,
                        pack_id=str(pack_id) if pack_id else None,
                    )
                    self._json(200, job.to_dict())
                    return

                if parsed.path == "/api/managed/start":
                    self._confirm(query, "Managed cleanup start")
                    session = start_managed_cleanup(
                        self._root(),
                        client_name=str(body.get("client_name", "Client")),
                        operator_name=str(body.get("operator_name", "Operator")),
                        pack_id=str(body.get("pack_id", "general_office")),
                        config=config,
                    )
                    self._json(200, session.to_dict())
                    return

                if parsed.path == "/api/jobs/delete-all":
                    self._confirm(query, "Delete all jobs")
                    deleted = JobStore(self._root()).delete_all()
                    self._json(200, {"deleted": deleted})
                    return

                if parsed.path.startswith("/api/jobs/"):
                    job_id, suffix = self._job_id_from_path("/api/jobs/", parsed.path)
                    root_path = self._root()
                    runner = JobRunner(root_path, config=config)
                    if suffix == "approve":
                        self._confirm(query, "Job approval")
                        self._json(200, runner.approve(job_id).to_dict())
                        return
                    if suffix == "apply":
                        self._confirm(query, "Job apply")
                        self._json(200, runner.apply(job_id).to_dict())
                        return
                    if suffix == "rollback":
                        self._confirm(query, "Job rollback")
                        self._json(200, runner.rollback(job_id).to_dict())
                        return
                    if suffix == "delete":
                        self._confirm(query, "Job delete")
                        JobStore(root_path).delete(job_id)
                        self._json(200, {"deleted": 1, "job_id": job_id})
                        return

                self._json(404, {"error": "Not found"})
            except ConfirmationRequired as exc:
                self._json(403, {"error": str(exc)})
            except (SafetyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)


def _build_current_plan(root: Path, config: RuntimeConfig, *, pack_id: str | None = None):
    inventory = scan_directory(root)
    provider = get_provider(config.provider)
    context = ProviderContext(
        model=config.model,
        endpoint=config.endpoint,
        privacy_mode=config.privacy_mode,
    )
    policy_pack = get_policy_pack(pack_id, root) if pack_id else None
    return build_plan(inventory, provider=provider, context=context, policy_pack=policy_pack)


def _providers_payload(config: RuntimeConfig) -> dict[str, object]:
    return {
        "active": config.provider,
        "model": config.model,
        "endpoint": config.endpoint,
        "privacy_mode": config.privacy_mode,
        "available": available_providers(),
        "notice": "No file contents are sent. Online providers receive metadata only.",
    }


def serve(root: str | Path, *, host: str, port: int, config: RuntimeConfig) -> None:
    resolved_root = resolve_root(root)
    server = create_server(resolved_root, host=host, port=port, config=config)
    print(f"TheLibrarian web app: http://{host}:{port}")
    print(f"Root: {resolved_root}")
    server.serve_forever()


def _page() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Librarian Dashboard</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #eef2ec;
      --panel: rgba(255,255,255,.94);
      --panel-strong: rgba(255,255,255,.99);
      --line: #d5dbd2;
      --text: #172119;
      --muted: #5b6a60;
      --accent: #12543f;
      --info: #245f73;
      --warn: #946112;
      --danger: #a23c34;
      --ok: #1d6a46;
      --shadow: 0 18px 44px rgba(20,32,24,.12);
      --radius-lg: 18px;
      --radius-md: 12px;
      --font-ui: "Aptos", "Segoe UI", sans-serif;
      --font-display: "Bahnschrift", "Segoe UI Semibold", sans-serif;
      --font-mono: "Cascadia Code", Consolas, monospace;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0f1513;
        --panel: rgba(20,28,24,.92);
        --panel-strong: rgba(21,30,26,.98);
        --line: #25332c;
        --text: #edf3ee;
        --muted: #9aac9f;
        --accent: #5ec59d;
        --info: #86bfcc;
        --warn: #f1c36a;
        --danger: #f08d86;
        --ok: #77d89d;
        --shadow: 0 24px 48px rgba(0,0,0,.28);
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      font-family: var(--font-ui);
      color: var(--text);
      background: linear-gradient(180deg, rgba(18,84,63,.10), transparent 18%), var(--bg);
    }
    button, input, select { font: inherit; }
    button, input, select {
      border: 1px solid var(--line);
      border-radius: 10px;
      min-height: 40px;
      padding: 0 12px;
      background: var(--panel-strong);
      color: var(--text);
    }
    button { cursor: pointer; }
    button:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid rgba(36,95,115,.28); outline-offset: 2px; }
    .button-primary { background: var(--accent); color: #fff; }
    .button-secondary { background: var(--info); color: #fff; }
    .shell { min-height: 100vh; display: grid; grid-template-columns: 260px minmax(0, 1fr) 340px; }
    .sidebar, .details { position: sticky; top: 0; height: 100vh; overflow: auto; padding: 20px; background: rgba(250,252,249,.84); }
    .sidebar { border-right: 1px solid var(--line); }
    .details { border-left: 1px solid var(--line); }
    .content { min-width: 0; padding: 20px; display: grid; gap: 16px; }
    .brand { display: flex; gap: 12px; align-items: center; margin-bottom: 18px; }
    .brand-mark { width: 44px; height: 44px; border-radius: 14px; background: #18362a; color: #fff; display: grid; place-items: center; font-family: var(--font-display); font-weight: 700; box-shadow: var(--shadow); }
    .brand h1 { margin: 0; font-size: 1.1rem; font-family: var(--font-display); }
    .muted { color: var(--muted); }
    .stack { display: grid; gap: 10px; }
    .card, .nav-button, .list-item, .metric-card, .status-line { border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--panel); box-shadow: var(--shadow); }
    .nav-button { width: 100%; text-align: left; padding: 12px; display: flex; justify-content: space-between; gap: 12px; align-items: center; }
    .nav-button.active { background: var(--panel-strong); }
    .nav-left, .toolbar, .badge-row, .action-row, .breadcrumbs { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .nav-icon { width: 28px; height: 28px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; background: rgba(18,84,63,.10); color: var(--accent); font-size: .75rem; font-weight: 700; }
    .topbar, .card { padding: 18px; }
    .topbar { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
    .breadcrumbs { color: var(--muted); font-size: .92rem; }
    .crumb::after { content: '/'; margin-left: 8px; color: var(--muted); }
    .crumb:last-child::after { content: ''; margin: 0; }
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--line); font-size: .83rem; }
    .ok { color: var(--ok); }
    .warn { color: var(--warn); }
    .danger { color: var(--danger); }
    .neutral { color: var(--info); }
    .path-chip, pre { font-family: var(--font-mono); }
    .path-chip { display: inline-flex; padding: 4px 8px; border-radius: 8px; background: rgba(18,84,63,.08); color: var(--accent); word-break: break-all; }
    .hero-grid, .grid-2 { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .metrics { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
    .metric-card { padding: 16px; display: grid; gap: 6px; }
    .metric-value { font-size: 1.9rem; font-weight: 700; }
    .section-page { display: none; gap: 16px; }
    .section-page.active { display: grid; }
    .section-kicker { text-transform: uppercase; letter-spacing: .12em; font-size: .78rem; color: var(--muted); margin-bottom: 8px; }
    .section-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 14px; flex-wrap: wrap; }
    .list-item { padding: 14px; }
    .status-line { padding: 12px 14px; display: flex; gap: 10px; align-items: center; }
    .status-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--info); }
    .table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: var(--radius-lg); }
    table { width: 100%; border-collapse: collapse; min-width: 760px; background: var(--panel-strong); }
    th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { background: rgba(18,84,63,.06); color: var(--muted); font-size: .84rem; text-transform: uppercase; letter-spacing: .04em; }
    .filters { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }
    .filters label { display: grid; gap: 6px; color: var(--muted); font-size: .9rem; }
    .empty-state, .detail-card { border: 1px dashed var(--line); border-radius: var(--radius-lg); padding: 16px; background: var(--panel-strong); }
    pre { margin: 0; padding: 14px; border: 1px solid var(--line); border-radius: var(--radius-lg); background: #13201a; color: #dff3e7; overflow: auto; white-space: pre-wrap; }
    @media (max-width: 1440px) { .shell { grid-template-columns: 250px minmax(0, 1fr); } .details { display: none; } }
    @media (max-width: 1100px) { .shell { grid-template-columns: 1fr; } .sidebar, .details { position: static; height: auto; border: none; } .hero-grid, .grid-2 { grid-template-columns: 1fr; } }
  </style>
</head>
<body data-app="thelibrarian-dashboard" data-shell="librarian-dev-dashboard">
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">TL</div><div><h1>The Librarian</h1><p class="muted">Developer-first workspace dashboard</p></div></div>
      <div class="list-item"><div class="section-kicker">Purpose</div><strong>Understand a workspace before touching it.</strong><p class="muted">Find entrypoints, risky files, generated artifacts, runnable scripts, notes, and graph context in one place.</p></div>
      <nav class="stack" id="sidebarNav" aria-label="Primary"></nav>
      <div class="list-item"><div class="section-kicker">Quick Actions</div><div class="stack"><button id="refreshBtn">Refresh dashboard</button><button id="copyAgentBriefSidebarBtn">Copy Agent Brief</button><button id="savePlanBtn">Save plan artifact</button><button id="downloadPlanBtn">Export plan JSON</button></div></div>
      <p class="muted">The Librarian never edits original source code while indexing this workspace.</p>
    </aside>
    <main class="content">
      <header class="topbar card">
        <div class="stack" style="gap:12px;"><div><div class="section-kicker">Workspace</div><h2 id="workspaceName" style="margin:0;font-family:var(--font-display);">Loading workspace...</h2><p id="workspaceSummary" class="muted">Reading .librarian artifacts and local dashboard state.</p></div><div class="breadcrumbs" id="breadcrumbs" aria-label="Breadcrumb"></div><div class="toolbar"><span id="workspaceStatusBadge" class="badge neutral">Loading</span><span id="workspacePath" class="path-chip">Waiting for root</span><span id="workspaceIndexedAt" class="badge neutral">No index yet</span></div></div>
        <div class="stack" style="gap:12px;"><div class="toolbar"><button id="reindexBtn" class="button-primary">Re-index</button><button id="graphBtn" class="button-secondary">Generate Graph</button><button id="openRunbookBtn">Open Runbook</button><button id="exportDashboardBtn">Export</button><button id="copyAgentBriefBtn">Copy Agent Context</button></div><div class="toolbar"><input id="rootInput" style="min-width:min(420px,70vw);" type="text" placeholder="Switch dashboard to another local root"><button id="setRootBtn">Set root</button></div></div>
      </header>
      <div id="statusLine" class="status-line neutral" role="status" aria-live="polite"><span class="status-dot"></span><strong>Status</strong><span id="statusText">Loading dashboard...</span></div>
      <section id="page-overview" class="section-page active"></section>
      <section id="page-start-here" class="section-page"></section>
      <section id="page-files" class="section-page"></section>
      <section id="page-directories" class="section-page"></section>
      <section id="page-code" class="section-page"></section>
      <section id="page-entrypoints" class="section-page"></section>
      <section id="page-tests" class="section-page"></section>
      <section id="page-graph" class="section-page"></section>
      <section id="page-risks" class="section-page"></section>
      <section id="page-runbooks" class="section-page"></section>
      <section id="page-scripts" class="section-page"></section>
      <section id="page-operations" class="section-page"></section>
      <section id="page-diagnostics" class="section-page"></section>
    </main>
    <aside class="details"><h3 style="margin-top:0;font-family:var(--font-display);">Details</h3><p class="muted">Select a file, risk, script, graph node, or operation to inspect it here.</p><div id="detailPanelBody" class="stack"><div class="empty-state"><h4>No selection yet</h4><p class="muted">Use view-details actions in cards and tables to inspect metadata without losing your place.</p></div></div></aside>
  </div>
  <script>
    const navItems = [
      { id: 'overview', label: 'Overview', icon: 'OV' },
      { id: 'start-here', label: 'Start Here', icon: 'ST' },
      { id: 'files', label: 'Files', icon: 'FI' },
      { id: 'directories', label: 'Directories', icon: 'DI' },
      { id: 'code', label: 'Code', icon: 'CO' },
      { id: 'entrypoints', label: 'Entrypoints', icon: 'EP' },
      { id: 'tests', label: 'Tests', icon: 'TS' },
      { id: 'graph', label: 'Graph', icon: 'GR' },
      { id: 'risks', label: 'Risks', icon: 'RK' },
      { id: 'runbooks', label: 'Runbooks', icon: 'RB' },
      { id: 'scripts', label: 'Scripts', icon: 'SC' },
      { id: 'operations', label: 'Operations', icon: 'OP' },
      { id: 'diagnostics', label: 'Diagnostics', icon: 'DG' },
    ];
    const state = {
      dashboard: null,
      page: 'overview',
      busy: false,
      selectedDetail: null,
      filesView: 'table',
      filters: {
        files: { q: '', kind: '', language: '', risk: '', sort: 'name', desc: false },
        directories: { q: '', role: '', risk: '' },
      },
    };
    const $ = selector => document.querySelector(selector);
    const pageEl = id => document.getElementById(`page-${id}`);
    const esc = value => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    const badge = (text, variant = 'neutral') => `<span class="badge ${variant}">${esc(text)}</span>`;
    const pathChip = value => `<span class="path-chip">${esc(value || '(missing path)')}</span>`;
    const metricCard = metric => `<article class="metric-card">${badge(metric.label, metric.variant || 'neutral')}<div class="metric-value">${new Intl.NumberFormat().format(Number(metric.value || 0))}</div><strong>${esc(metric.label)}</strong></article>`;
    const emptyState = (title, body) => `<div class="empty-state"><h4>${esc(title)}</h4><p class="muted">${esc(body)}</p></div>`;
    const simpleTable = (headers, rows, emptyHtml) => `<div class="table-wrap"><table><thead><tr>${headers.map(h => `<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.length ? rows.map(row => `<tr>${row.join('')}</tr>`).join('') : `<tr><td colspan="${headers.length}">${emptyHtml}</td></tr>`}</tbody></table></div>`;
    const statusVariant = value => {
      const v = String(value || '').toLowerCase();
      if (['error', 'errors', 'high', 'danger', 'missing'].includes(v)) return 'danger';
      if (['warning', 'warnings', 'medium', 'stale', 'needs index'].includes(v)) return 'warn';
      if (['healthy', 'ok', 'safe', 'read-only'].includes(v)) return 'ok';
      return 'neutral';
    };
    const confidenceBadge = value => {
      const n = Number(value || 0);
      return badge(`${Math.round(n * 100)}% confidence`, n >= 0.8 ? 'ok' : n >= 0.6 ? 'neutral' : 'warn');
    };
    const getLibrarian = () => state.dashboard?.librarian || {
      workspace: { name: 'Workspace', path: '', short_path: '', status: 'Needs Index', summary: '' },
      overview: { hero: { description: '', languages: [], frameworks: [], project_type: 'Workspace', confidence: 0 }, metrics: [], do_not_touch: [], health: [], recent_operations: [], status: 'Needs Index' },
      start_here: { recommended_reads: [], recommended_commands: [], runnable_scripts: [], important_files: [], main_entrypoints: [], main_risks: [], agent_instructions: {}, empty_message: '' },
      files: [], directories: [],
      code: { languages: [], frameworks: [], packages: [], modules: [], entrypoints: [], tests: [], config_files: [] },
      graph: { available: false, summary: { nodes: 0, edges: 0, top_connected: [], top_tags: [], top_edge_types: [], isolated_nodes: [] }, nodes: [], edges: [], entrypoint_neighborhood: [], empty_message: 'Graph is missing.' },
      risks: [], runbooks: [], scripts: [], operations: [],
      diagnostics: { items: [], stale_index: false, suggestions: [], warnings: 0, errors: 0 },
      agent_brief: '',
    };
    const getRecommendedFirstReads = () => getLibrarian().start_here?.recommended_reads || [];
    const getEntrypoints = () => getLibrarian().code?.entrypoints || [];
    const getRunnableScripts = () => getLibrarian().scripts || [];
    const setStatus = (message, variant = 'neutral') => { $('#statusLine').className = `status-line ${variant}`; $('#statusText').textContent = message; };
    async function api(path, options = {}) {
      const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Request failed: ${response.status}`);
      }
      const contentType = response.headers.get('content-type') || '';
      return contentType.includes('application/json') ? response.json() : response.text();
    }
    async function copyText(value, message = 'Copied.') {
      try {
        await navigator.clipboard.writeText(String(value || ''));
        setStatus(message, 'ok');
      } catch (error) {
        setStatus('Clipboard access failed. Copy manually from the detail panel.', 'warn');
        setDetail('Clipboard fallback', { value });
      }
    }
    function downloadJson(filename, payload) {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    }
    function setDetail(title, payload, description = 'Structured detail for the selected item.') {
      state.selectedDetail = { title, payload, description };
      renderDetail();
    }
    function renderDetail() {
      const el = $('#detailPanelBody');
      if (!state.selectedDetail) {
        el.innerHTML = emptyState('No selection yet', 'Select an item to inspect its metadata here.');
        return;
      }
      const payload = state.selectedDetail.payload;
      const json = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
      el.innerHTML = `<div class="detail-card"><div class="section-kicker">Selection</div><h4>${esc(state.selectedDetail.title)}</h4><p class="muted">${esc(state.selectedDetail.description)}</p><pre>${esc(json)}</pre><div class="action-row" style="margin-top:10px;"><button data-copy="${esc(typeof payload === 'string' ? payload : json)}">Copy details</button></div></div>`;
      el.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', () => copyText(button.dataset.copy, 'Copied details.')));
    }
    function setPage(page) {
      state.page = page;
      navItems.forEach(item => pageEl(item.id)?.classList.toggle('active', item.id === page));
      document.querySelectorAll('.nav-button').forEach(button => button.classList.toggle('active', button.dataset.page === page));
      renderBreadcrumbs();
    }
    function renderBreadcrumbs() {
      const workspace = getLibrarian().workspace;
      const title = navItems.find(item => item.id === state.page)?.label || 'Overview';
      $('#breadcrumbs').innerHTML = `<span class="crumb">${esc(workspace.name || 'Workspace')}</span><span class="crumb">${esc(title)}</span>${state.selectedDetail?.title ? `<span class="crumb">${esc(state.selectedDetail.title)}</span>` : ''}`;
    }
    function wireSectionActions(root) {
      root.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', () => copyText(button.dataset.copy, 'Copied.')));
      root.querySelectorAll('[data-jump]').forEach(button => button.addEventListener('click', () => setPage(button.dataset.jump)));
      root.querySelectorAll('[data-item]').forEach(button => button.addEventListener('click', () => setDetail(button.dataset.title || 'Details', JSON.parse(button.dataset.item))));
      root.querySelectorAll('[data-graph-file]').forEach(button => button.addEventListener('click', () => { setPage('graph'); $('#graphSearch') && ($('#graphSearch').value = button.dataset.graphFile); renderGraph(button.dataset.graphFile); }));
    }
    function renderSidebar() {
      const librarian = getLibrarian();
      const counts = {
        files: librarian.files.length, directories: librarian.directories.length, code: librarian.code.modules.length,
        entrypoints: librarian.code.entrypoints.length, tests: librarian.code.tests.length, graph: librarian.graph.summary.nodes,
        risks: librarian.risks.length, runbooks: librarian.runbooks.length, scripts: librarian.scripts.length,
        operations: librarian.operations.length, diagnostics: librarian.diagnostics.errors + librarian.diagnostics.warnings,
      };
      $('#sidebarNav').innerHTML = navItems.map(item => `<button class="nav-button ${item.id === state.page ? 'active' : ''}" data-page="${esc(item.id)}"><span class="nav-left"><span class="nav-icon">${esc(item.icon)}</span><span>${esc(item.label)}</span></span>${counts[item.id] ? badge(counts[item.id], 'neutral') : ''}</button>`).join('');
      document.querySelectorAll('.nav-button').forEach(button => button.addEventListener('click', () => setPage(button.dataset.page)));
    }
    function renderTopbar() {
      const workspace = getLibrarian().workspace;
      $('#workspaceName').textContent = workspace.name || 'Workspace';
      $('#workspaceSummary').textContent = workspace.summary || 'Dashboard data not available yet.';
      $('#workspacePath').textContent = workspace.short_path || workspace.path || 'Unknown path';
      $('#workspaceIndexedAt').textContent = workspace.last_indexed ? `Last index: ${new Date(workspace.last_indexed).toLocaleString()}` : 'No index yet';
      $('#workspaceStatusBadge').className = `badge ${statusVariant(workspace.status)}`;
      $('#workspaceStatusBadge').textContent = workspace.status || 'Unknown';
      $('#rootInput').value = state.dashboard?.root || workspace.path || '';
    }
    function renderOverview() {
      const librarian = getLibrarian();
      const overview = librarian.overview;
      const health = overview.health || [];
      pageEl('overview').innerHTML = `
        <div class="hero-grid">
          <article class="card"><div class="section-kicker">Overview</div><h3 id="overviewTitle" style="margin:0 0 10px;font-family:var(--font-display);">${esc(librarian.workspace.name || 'Workspace')}</h3><div class="badge-row">${badge(overview.status || 'Unknown', statusVariant(overview.status))}${confidenceBadge(overview.hero.confidence || 0)}${badge(overview.hero.project_type || 'Workspace', 'neutral')}${(overview.hero.languages || []).slice(0,4).map(item => badge(item, 'neutral')).join('')}${(overview.hero.frameworks || []).slice(0,4).map(item => badge(item, 'ok')).join('')}</div><p class="muted">${esc(overview.hero.description || 'Developer-first workspace dashboard for understanding structure, code intelligence, risk, and runnable context.')}</p><div class="action-row"><button data-jump="start-here" class="button-primary">Open Start Here</button><button data-copy="${esc(librarian.agent_brief || '')}">Copy Agent Brief</button><button data-jump="risks">Review risks</button></div></article>
          <article class="card"><div class="section-kicker">Health</div><h4 style="margin:0 0 10px;">Above the fold checks</h4><div class="metrics">${health.length ? health.map(item => metricCard({ label: item.label, value: item.value, variant: item.variant || 'neutral' })).join('') : emptyState('No health data yet', 'Run librarian mark and librarian dev index to build workspace metadata.')}</div></article>
        </div>
        <div class="metrics">${(overview.metrics || []).map(metricCard).join('')}</div>
        <div class="grid-2">
          <article class="card"><div class="section-header"><div><div class="section-kicker">Start Here</div><h4 style="margin:0;">Recommended first reads</h4></div><button data-jump="start-here">View full guide</button></div><div class="stack">${getRecommendedFirstReads().length ? getRecommendedFirstReads().map(item => `<div class="list-item" data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.label || item.path)}"><strong>${esc(item.label || item.path)}</strong><div class="badge-row">${pathChip(item.path)}${badge('First read','ok')}</div><p class="muted">${esc(item.reason || '')}</p></div>`).join('') : emptyState('No recommended reads yet', 'README files, notes, runbooks, and entrypoints will appear here.')}</div></article>
          <article class="card"><div class="section-header"><div><div class="section-kicker">Do Not Touch</div><h4 style="margin:0;">Protected or risky files</h4></div><button data-jump="risks">Open risks</button></div><div class="stack">${(overview.do_not_touch || []).length ? overview.do_not_touch.map(item => `<div class="list-item" data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.path)}"><strong>${esc(item.name)}</strong><div class="badge-row">${pathChip(item.path)}${badge(item.risk || 'risk', statusVariant(item.risk))}${item.generated ? badge('Generated', 'warn') : ''}${item.vendor ? badge('Vendor', 'warn') : ''}${item.lockfile ? badge('Lockfile', 'warn') : ''}</div><p class="muted">${esc(item.summary || 'Avoid editing unless you know why this file matters.')}</p></div>`).join('') : emptyState('No protected files flagged', 'Generated, vendor, lockfile, and high-risk items will appear here when indexed.')}</div></article>
        </div>
      `;
      wireSectionActions(pageEl('overview'));
    }
    function renderStartHere() {
      const librarian = getLibrarian();
      const start = librarian.start_here;
      pageEl('start-here').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Start Here</div><h3 id="startHereTitle" style="margin:0;">What to read first and what to run next</h3><p class="muted">This page helps a developer or agent get productive in less than 30 seconds.</p></div><button id="copyAgentBriefPageBtn" class="button-primary">Copy Agent Brief</button></div>${start.empty_message ? emptyState('Workspace context is still thin', start.empty_message) : ''}</article><div class="grid-2"><article class="card"><div class="section-header"><div><h4 style="margin:0;">Recommended commands</h4><p class="muted">Copyable CLI commands for the safest next steps.</p></div></div><div class="stack">${(start.recommended_commands || []).length ? start.recommended_commands.map(item => `<div class="list-item"><strong>${esc(item.label)}</strong><p class="muted">${esc(item.description || '')}</p><pre>${esc(item.command)}</pre><div class="action-row"><button data-copy="${esc(item.command)}">Copy command</button></div></div>`).join('') : emptyState('No recommended commands yet', 'Mark, index, status, and inspection commands appear here when metadata exists.')}</div></article><article class="card"><div class="section-header"><div><h4 style="margin:0;">Important files, entrypoints, and risks</h4><p class="muted">Useful context before making changes.</p></div></div><div class="stack">${(start.important_files || []).slice(0,4).map(item => `<div class="list-item" data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.path)}"><strong>${esc(item.name)}</strong><div class="badge-row">${pathChip(item.path)}${item.language ? badge(item.language, 'neutral') : ''}</div></div>`).join('')}${(start.main_entrypoints || []).slice(0,3).map(item => `<div class="list-item" data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.file)}"><strong>${esc(item.file)}</strong><div class="badge-row">${badge(item.symbol, 'ok')}${confidenceBadge(item.confidence)}</div></div>`).join('')}${(start.main_risks || []).slice(0,3).map(item => `<div class="list-item" data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.item)}"><strong>${esc(item.item)}</strong><div class="badge-row">${badge(item.severity, statusVariant(item.severity))}${confidenceBadge(item.confidence)}</div><p class="muted">${esc(item.reason)}</p></div>`).join('') || emptyState('No highlighted items yet', 'Entrypoints and risks will surface here once metadata is available.')}</div></article></div><article class="card"><div class="section-header"><div><h4 style="margin:0;">Agent instructions</h4><p class="muted">Structured context that can be copied into another agent session.</p></div></div><pre>${esc(JSON.stringify(start.agent_instructions || {}, null, 2))}</pre></article>`;
      wireSectionActions(pageEl('start-here'));
      $('#copyAgentBriefPageBtn')?.addEventListener('click', () => copyText(librarian.agent_brief || '', 'Agent brief copied.'));
    }
    function renderFiles() {
      const librarian = getLibrarian();
      const files = librarian.files || [];
      const filters = state.filters.files;
      const filtered = files.filter(item => (!filters.kind || item.kind === filters.kind) && (!filters.language || String(item.language || '') === filters.language) && (!filters.risk || item.risk === filters.risk) && (!filters.q || [item.name, item.path, item.kind, item.language, item.summary].join(' ').toLowerCase().includes(filters.q.toLowerCase())));
      const rows = filtered.map(item => [`<td><strong>${esc(item.name)}</strong><div class="muted">${esc(item.path)}</div></td>`, `<td>${esc(item.kind || 'unknown')}</td>`, `<td>${item.language ? badge(item.language, 'neutral') : badge('Unknown', 'neutral')}</td>`, `<td>${badge(item.risk || 'low', statusVariant(item.risk))}</td>`, `<td>${confidenceBadge(item.confidence)}</td>`, `<td>${esc(item.summary || '')}</td>`, `<td><div class="action-row"><button data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.path)}">View metadata</button><button data-copy="${esc(item.path)}">Copy path</button><button data-graph-file="${esc(item.path)}">Show in graph</button></div></td>`]);
      pageEl('files').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Files & Directories</div><h3 id="filesTitle" style="margin:0;">Files explorer</h3><p class="muted">Searchable and filterable file inventory.</p></div></div><div class="filters"><label>Search<input id="filesSearch" value="${esc(filters.q)}" placeholder="Search path, summary, language"></label><label>File kind<select id="filesKind"><option value="">All kinds</option>${Array.from(new Set(files.map(item => item.kind).filter(Boolean))).sort().map(value => `<option value="${esc(value)}" ${value === filters.kind ? 'selected' : ''}>${esc(value)}</option>`).join('')}</select></label><label>Language<select id="filesLanguage"><option value="">All languages</option>${Array.from(new Set(files.map(item => item.language).filter(Boolean))).sort().map(value => `<option value="${esc(value)}" ${value === filters.language ? 'selected' : ''}>${esc(value)}</option>`).join('')}</select></label><label>Risk<select id="filesRisk"><option value="">All risks</option><option value="low" ${filters.risk === 'low' ? 'selected' : ''}>low</option><option value="medium" ${filters.risk === 'medium' ? 'selected' : ''}>medium</option><option value="high" ${filters.risk === 'high' ? 'selected' : ''}>high</option></select></label></div><p class="muted">${esc(`${filtered.length} of ${files.length} files shown`)}</p>${files.length ? simpleTable(['Name', 'Type', 'Language', 'Risk', 'Confidence', 'Summary', 'Actions'], rows, emptyState('No files match the current filters', 'Try clearing one or more filters.')) : emptyState('No files indexed yet', 'Run librarian mark to create file sidecars and manifest entries.')}</article>`;
      wireSectionActions(pageEl('files'));
      $('#filesSearch')?.addEventListener('input', event => { state.filters.files.q = event.target.value; renderFiles(); });
      $('#filesKind')?.addEventListener('change', event => { state.filters.files.kind = event.target.value; renderFiles(); });
      $('#filesLanguage')?.addEventListener('change', event => { state.filters.files.language = event.target.value; renderFiles(); });
      $('#filesRisk')?.addEventListener('change', event => { state.filters.files.risk = event.target.value; renderFiles(); });
    }
    function renderDirectories() {
      const librarian = getLibrarian();
      const directories = librarian.directories || [];
      const filters = state.filters.directories;
      const filtered = directories.filter(item => (!filters.role || (item.roles || []).includes(filters.role)) && (!filters.risk || item.risk === filters.risk) && (!filters.q || [item.name, item.path, item.description, (item.roles || []).join(' ')].join(' ').toLowerCase().includes(filters.q.toLowerCase())));
      const rows = filtered.map(item => [`<td><strong>${esc(item.name)}</strong><div class="muted">${esc(item.path)}</div></td>`, `<td>${(item.roles || []).map(role => badge(role, 'neutral')).join('')}</td>`, `<td>${esc(item.total_file_count || 0)}</td>`, `<td>${(item.dominant_languages || []).slice(0,3).map(language => badge(language, 'neutral')).join('')}</td>`, `<td>${badge(item.risk || 'low', statusVariant(item.risk))}</td>`, `<td>${confidenceBadge(item.confidence)}</td>`, `<td><button data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.path)}">View details</button></td>`]);
      pageEl('directories').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Files & Directories</div><h3 id="directoriesTitle" style="margin:0;">Directory explorer</h3><p class="muted">Understand the workspace shape before planning any move.</p></div></div><div class="filters"><label>Search<input id="directoriesSearch" value="${esc(filters.q)}" placeholder="Search path, role, description"></label><label>Role<select id="directoriesRole"><option value="">All roles</option>${Array.from(new Set(directories.flatMap(item => item.roles || []))).sort().map(value => `<option value="${esc(value)}" ${value === filters.role ? 'selected' : ''}>${esc(value)}</option>`).join('')}</select></label><label>Risk<select id="directoriesRisk"><option value="">All risks</option><option value="low" ${filters.risk === 'low' ? 'selected' : ''}>low</option><option value="medium" ${filters.risk === 'medium' ? 'selected' : ''}>medium</option><option value="high" ${filters.risk === 'high' ? 'selected' : ''}>high</option></select></label></div>${directories.length ? simpleTable(['Directory', 'Roles', 'Files', 'Languages', 'Risk', 'Confidence', 'Actions'], rows, emptyState('No directories match the current filters', 'Try clearing the search or role filter.')) : emptyState('No directories indexed yet', 'Directory analysis appears after librarian mark.')}</article>`;
      wireSectionActions(pageEl('directories'));
      $('#directoriesSearch')?.addEventListener('input', event => { state.filters.directories.q = event.target.value; renderDirectories(); });
      $('#directoriesRole')?.addEventListener('change', event => { state.filters.directories.role = event.target.value; renderDirectories(); });
      $('#directoriesRisk')?.addEventListener('change', event => { state.filters.directories.risk = event.target.value; renderDirectories(); });
    }
    function renderCode() {
      const code = getLibrarian().code;
      pageEl('code').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Code Intelligence</div><h3 id="codeTitle" style="margin:0;">Languages, frameworks, modules, and config</h3><p class="muted">Static signals only. The Librarian does not execute project code while building this view.</p></div></div><div class="metrics">${code.languages.length ? code.languages.map(item => metricCard({ label: item.name, value: item.count, variant: 'neutral' })).join('') : metricCard({ label: 'Languages', value: 0, variant: 'neutral' })}${code.frameworks.length ? code.frameworks.slice(0,3).map(item => metricCard({ label: item.name, value: item.count, variant: 'ok' })).join('') : ''}</div><div class="grid-2"><div class="card"><div class="section-header"><div><h4 style="margin:0;">Main modules</h4></div></div>${code.modules.length ? simpleTable(['Module', 'File', 'Imports', 'Imported by', 'Risk'], code.modules.slice(0, 25).map(item => [`<td><strong>${esc(item.module)}</strong></td>`, `<td>${pathChip(item.file)}</td>`, `<td>${esc(item.imports_count)}</td>`, `<td>${esc(item.imported_by_count)}</td>`, `<td>${badge(item.risk || 'low', statusVariant(item.risk))}</td>`]), emptyState('No modules found', 'Static code analysis did not detect importable modules yet.')) : emptyState('No modules found', 'Static code analysis did not detect importable modules yet.')}</div><div class="card"><div class="section-header"><div><h4 style="margin:0;">Config files</h4></div></div><div class="stack">${(code.config_files || []).length ? code.config_files.map(path => `<div class="list-item"><strong>${esc(path)}</strong><div class="badge-row">${pathChip(path)}${badge('Configuration', 'neutral')}</div></div>`).join('') : emptyState('No config files detected', 'Configuration files will appear here when classification recognizes them.')}</div></div></div></article>`;
    }
    function renderEntrypoints() {
      const entrypoints = getEntrypoints();
      pageEl('entrypoints').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Code Intelligence</div><h3 id="entrypointsTitle" style="margin:0;">Entrypoints table</h3><p class="muted">Where execution likely starts and the first command worth trying.</p></div></div>${entrypoints.length ? simpleTable(['File', 'Symbol', 'Type', 'Confidence', 'Reason', 'Actions'], entrypoints.map(item => [`<td>${pathChip(item.file)}</td>`, `<td>${badge(item.symbol, 'ok')}</td>`, `<td>${esc(item.type)}</td>`, `<td>${confidenceBadge(item.confidence)}</td>`, `<td>${esc(item.reason || '')}</td>`, `<td><div class="action-row"><button data-copy="${esc(item.command || item.file)}">Copy command</button><button data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.file)}">Open details</button><button data-graph-file="${esc(item.file)}">Show graph</button></div></td>`]), emptyState('No entrypoints detected', 'Run librarian dev index after marking the workspace to strengthen entrypoint detection.')) : emptyState('No entrypoints detected', 'Run librarian dev index after marking the workspace to strengthen entrypoint detection.')}</article>`;
      wireSectionActions(pageEl('entrypoints'));
    }
    function renderTests() {
      const tests = getLibrarian().code.tests || [];
      pageEl('tests').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Code Intelligence</div><h3 id="testsTitle" style="margin:0;">Tests table</h3><p class="muted">Detected test files and their likely targets.</p></div></div>${tests.length ? simpleTable(['Test file', 'Tested target', 'Framework', 'Confidence'], tests.map(item => [`<td>${pathChip(item.file)}</td>`, `<td>${esc(item.tested_target || 'Unknown')}</td>`, `<td>${esc(item.framework || 'Unknown')}</td>`, `<td>${confidenceBadge(item.confidence)}</td>`]), emptyState('No tests detected', 'No test hints were found in the current manifest.')) : emptyState('No tests detected', 'No test hints were found in the current manifest.')}</article>`;
    }
    function renderGraph(focus = '') {
      const graph = getLibrarian().graph;
      const query = (focus || '').toLowerCase();
      const nodes = query ? graph.nodes.filter(node => [node.id, node.label, node.type, node.summary].join(' ').toLowerCase().includes(query)) : graph.nodes;
      const neighborhood = query ? graph.entrypoint_neighborhood.filter(edge => [edge.source, edge.target, edge.type, edge.reason].join(' ').toLowerCase().includes(query)) : graph.entrypoint_neighborhood;
      pageEl('graph').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Knowledge Graph</div><h3 id="graphTitle" style="margin:0;">Relationship view</h3><p class="muted">Summary, top connections, and entrypoint neighborhood without a heavy renderer.</p></div></div>${graph.available ? `<div class="metrics">${metricCard({ label: 'Nodes', value: graph.summary.nodes, variant: 'neutral' })}${metricCard({ label: 'Edges', value: graph.summary.edges, variant: 'neutral' })}${metricCard({ label: 'Connected files', value: graph.summary.top_connected.length, variant: 'ok' })}${metricCard({ label: 'Isolated nodes', value: graph.summary.isolated_nodes.length, variant: 'warn' })}</div><div class="filters"><label>Search node<input id="graphSearch" value="${esc(focus)}" placeholder="Search node label, path, type"></label></div><div class="grid-2"><div class="card"><div class="section-header"><div><h4 style="margin:0;">Graph summary</h4></div></div><div class="stack"><div class="list-item"><strong>Top connected files</strong><div class="badge-row">${graph.summary.top_connected.slice(0, 8).map(item => badge(`${item.label} (${item.degree})`, 'neutral')).join('') || badge('None', 'neutral')}</div></div><div class="list-item"><strong>Top node types</strong><div class="badge-row">${graph.summary.top_tags.map(item => badge(`${item.name} (${item.count})`, 'neutral')).join('') || badge('None', 'neutral')}</div></div><div class="list-item"><strong>Top edge types</strong><div class="badge-row">${graph.summary.top_edge_types.map(item => badge(`${item.name} (${item.count})`, 'neutral')).join('') || badge('None', 'neutral')}</div></div></div></div><div class="card"><div class="section-header"><div><h4 style="margin:0;">Entry point neighborhood</h4></div></div>${neighborhood.length ? simpleTable(['Source', 'Target', 'Type', 'Confidence'], neighborhood.slice(0, 30).map(edge => [`<td>${esc(edge.source)}</td>`, `<td>${esc(edge.target)}</td>`, `<td>${badge(edge.type, 'neutral')}</td>`, `<td>${confidenceBadge(edge.confidence)}</td>`]), emptyState('No neighborhood data', 'No graph edges are connected to the current focus.')) : emptyState('No neighborhood data', 'No graph edges are connected to the current focus.')}</div></div><div class="card"><div class="section-header"><div><h4 style="margin:0;">Nodes</h4></div></div>${nodes.length ? simpleTable(['Node', 'Type', 'Confidence', 'Summary'], nodes.slice(0, 25).map(node => [`<td>${esc(node.label)}</td>`, `<td>${badge(node.type || 'unknown', 'neutral')}</td>`, `<td>${confidenceBadge(node.confidence)}</td>`, `<td>${esc(node.summary || '')}</td>`]), emptyState('No nodes match', 'Try clearing the search box.')) : emptyState('No nodes match', 'Try clearing the search box.')}</div>` : emptyState('Graph is missing', graph.empty_message || 'Generate graph data to unlock relationship views.')}</article>`;
      $('#graphSearch')?.addEventListener('input', event => renderGraph(event.target.value));
    }
    function renderRisks() {
      const risks = getLibrarian().risks || [];
      pageEl('risks').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Risks & Warnings</div><h3 id="risksTitle" style="margin:0;">What to avoid, inspect, or regenerate</h3><p class="muted">Risks are explicit and visible without needing to hunt for them.</p></div></div>${risks.length ? simpleTable(['Severity', 'Item', 'Reason', 'Recommended action', 'Source', 'Confidence'], risks.map(item => [`<td>${badge(item.severity, statusVariant(item.severity))}</td>`, `<td><strong>${esc(item.item)}</strong></td>`, `<td>${esc(item.reason)}</td>`, `<td>${esc(item.recommended_action)}</td>`, `<td>${esc(item.source)}</td>`, `<td>${confidenceBadge(item.confidence)}</td>`]), emptyState('No risks found', 'High-risk files, low-confidence classification, stale graph, unreadable files, and missing sidecars appear here.')) : emptyState('No risks found', 'High-risk files, low-confidence classification, stale graph, unreadable files, and missing sidecars appear here.')}</article>`;
    }
    function renderRunbooks() {
      const runbooks = getLibrarian().runbooks || [];
      pageEl('runbooks').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Runbooks & Scripts</div><h3 id="runbooksTitle" style="margin:0;">Runbooks</h3><p class="muted">Human-readable procedures for inspecting, extending, and operating the workspace safely.</p></div></div><div class="stack">${runbooks.length ? runbooks.map(item => `<div class="list-item" data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.name)}"><strong>${esc(item.name)}</strong><div class="badge-row">${pathChip(item.path)}${badge('Read-only', 'ok')}${item.validated ? badge('Generated', 'ok') : badge('Missing', 'warn')}</div><p class="muted">${esc(item.description)}</p><div class="action-row"><button data-copy="${esc(item.command)}">Copy command</button><button data-copy="${esc(item.path)}">Copy path</button></div></div>`).join('') : emptyState('No runbooks found', 'Run librarian dev runbook to generate step-by-step guides.')}</div></article>`;
      wireSectionActions(pageEl('runbooks'));
    }
    function renderScripts() {
      const scripts = getRunnableScripts();
      pageEl('scripts').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Runbooks & Scripts</div><h3 id="scriptsTitle" style="margin:0;">Runnable scripts</h3><p class="muted">Small Python helpers generated under .librarian/scripts for developers and agents.</p></div></div><div class="stack">${scripts.length ? scripts.map(item => `<div class="list-item"><strong>${esc(item.name)}</strong><div class="badge-row">${pathChip(item.path)}${item.read_only ? badge('Read-only', 'ok') : badge('Modifies files', 'warn')}${item.validated ? badge('Validated', 'ok') : badge('Not validated', 'warn')}</div><p class="muted">${esc(item.description)}</p><pre>${esc(item.command)}</pre><div class="action-row"><button data-copy="${esc(item.command)}">Copy command</button><button data-item='${esc(JSON.stringify(item))}' data-title="${esc(item.name)}">View details</button></div></div>`).join('') : emptyState('No scripts found', 'Run librarian dev init to generate runnable helpers.')}</div></article>`;
      wireSectionActions(pageEl('scripts'));
    }
    function renderOperations() {
      const operations = getLibrarian().operations || [];
      pageEl('operations').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Operations</div><h3 id="operationsTitle" style="margin:0;">Timeline</h3><p class="muted">Append-only operations from logs, including mark, plan, apply, rollback, and export.</p></div></div>${operations.length ? simpleTable(['Timestamp', 'Type', 'Item', 'Result', 'Rollback'], operations.map(item => [`<td>${esc(item.timestamp || 'Unknown time')}</td>`, `<td>${badge(item.type || 'operation', 'neutral')}</td>`, `<td>${esc(item.item || '')}</td>`, `<td>${badge(item.result || 'unknown', statusVariant(item.result))}</td>`, `<td>${item.rollback_available ? badge('Available', 'ok') : badge('No', 'neutral')}</td>`]), emptyState('No operations logged', 'Run mark, plan, apply, rollback, or export commands to build an audit trail.')) : emptyState('No operations logged', 'Run mark, plan, apply, rollback, or export commands to build an audit trail.')}</article>`;
    }
    function renderDiagnostics() {
      const diagnostics = getLibrarian().diagnostics || { items: [], suggestions: [], parsing_errors: [] };
      pageEl('diagnostics').innerHTML = `<article class="card"><div class="section-header"><div><div class="section-kicker">Settings / Diagnostics</div><h3 id="diagnosticsTitle" style="margin:0;">Diagnostics</h3><p class="muted">Artifact presence, parsing errors, stale index detection, and next steps.</p></div></div><div class="grid-2"><div class="card">${(diagnostics.items || []).length ? simpleTable(['Artifact', 'Status', 'Detail'], diagnostics.items.map(item => [`<td>${esc(item.label)}</td>`, `<td>${badge(item.status, statusVariant(item.status))}</td>`, `<td>${esc(item.detail)}</td>`]), emptyState('No diagnostics', 'No diagnostic items were produced.')) : emptyState('No diagnostics', 'No diagnostic items were produced.')}</div><div class="card"><h4 style="margin-top:0;">Suggestions</h4><div class="stack">${(diagnostics.suggestions || []).length ? diagnostics.suggestions.map(item => `<div class="list-item"><strong>${esc(item)}</strong></div>`).join('') : emptyState('No diagnostic suggestions', 'The workspace looks healthy enough to inspect directly.')}</div></div></div></article>`;
    }
    function renderAllSections() { renderSidebar(); renderTopbar(); renderBreadcrumbs(); renderOverview(); renderStartHere(); renderFiles(); renderDirectories(); renderCode(); renderEntrypoints(); renderTests(); renderGraph(); renderRisks(); renderRunbooks(); renderScripts(); renderOperations(); renderDiagnostics(); renderDetail(); setPage(state.page); }
    async function refresh(silent = false) { if (!silent) setStatus('Refreshing dashboard...', 'neutral'); state.dashboard = await api('/api/dashboard'); renderAllSections(); if (!silent) setStatus('Dashboard refreshed.', 'ok'); }
    async function runAction(label, action, refreshAfter = true) { if (state.busy) return; state.busy = true; try { setStatus(`${label} running...`, 'neutral'); await action(); if (refreshAfter) await refresh(true); } catch (error) { setStatus(error.message || `${label} failed.`, 'danger'); } finally { state.busy = false; } }
    $('#refreshBtn').addEventListener('click', () => runAction('Refresh dashboard', () => refresh(true), false));
    $('#copyAgentBriefSidebarBtn').addEventListener('click', () => copyText(getLibrarian().agent_brief || '', 'Agent brief copied.'));
    $('#copyAgentBriefBtn').addEventListener('click', () => copyText(getLibrarian().agent_brief || '', 'Agent context copied.'));
    $('#reindexBtn').addEventListener('click', () => copyText(`librarian dev index "${getLibrarian().workspace.path}"`, 'Re-index command copied.'));
    $('#graphBtn').addEventListener('click', () => { setPage('graph'); if (!getLibrarian().graph.available) { setStatus('Graph data is missing. This build reads graph.json when present, but does not generate it yet.', 'warn'); setDetail('Graph guidance', { expected_path: '.librarian/graph.json', next_step: 'Produce graph.json externally, then refresh the dashboard.' }); } });
    $('#openRunbookBtn').addEventListener('click', () => setPage('runbooks'));
    $('#exportDashboardBtn').addEventListener('click', () => { if (state.dashboard) { downloadJson(`thelibrarian-dashboard-${new Date().toISOString().replace(/[:.]/g, '-')}.json`, state.dashboard); setStatus('Dashboard JSON exported.', 'ok'); } });
    $('#savePlanBtn').addEventListener('click', () => runAction('Save plan artifact', async () => { const saved = await api('/api/plan/save', { method: 'POST', body: '{}' }); setDetail('Saved plan artifact', saved, 'Plan JSON was written to disk without applying any move.'); setStatus(`Saved plan artifact: ${saved.path}`, 'ok'); }, false));
    $('#downloadPlanBtn').addEventListener('click', () => { if (!state.dashboard?.plan) { setStatus('No plan is available to export.', 'warn'); return; } downloadJson(`thelibrarian-plan-${new Date().toISOString().replace(/[:.]/g, '-')}.json`, state.dashboard.plan); setStatus('Plan JSON exported.', 'ok'); });
    $('#setRootBtn').addEventListener('click', () => { const root = $('#rootInput').value.trim(); if (!root) { setStatus('Enter a root path first.', 'warn'); return; } if (!window.confirm('Switch the dashboard to this directory? Existing files will not be moved.')) return; runAction('Switch root', () => api('/api/root?confirm=true', { method: 'POST', body: JSON.stringify({ root }) })); });
    refresh().catch(error => { setStatus(error.message || 'Dashboard failed to load.', 'danger'); pageEl('overview').innerHTML = emptyState('Dashboard failed to load', error.message || 'Unknown error'); });
    window.setInterval(() => { if (!state.busy) refresh(true).catch(error => setStatus(error.message || 'Background refresh failed.', 'danger')); }, 10000);
  </script>
</body>
</html>"""
