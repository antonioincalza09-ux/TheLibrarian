from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from src.librarian.graph._compat import new_digraph
from src.librarian.graph.utils import parent_path, relative_posix, slug, stable_id
from src.librarian.metadata import directory_sidecar_path, file_sidecar_path
from src.librarian.rules.schema import Manifest, WorkspaceNode
from src.librarian.sidecars import read_manifest


def build_graph(root: str | Path):
    resolved_root = Path(root).resolve()
    manifest = read_manifest(resolved_root)
    files, directories = _load_nodes_from_sidecars(resolved_root, manifest)

    graph = new_digraph()
    graph.graph["workspace_root"] = str(resolved_root)
    graph.graph["manifest_generated_at"] = manifest.generated_at

    workspace_id = "workspace"
    project_id = "project:workspace"
    manifest_id = "artifact:manifest"
    graph_artifact_id = "artifact:graph"
    sidecars_id = "artifact:sidecars"
    _add_node(graph, workspace_id, "Workspace", resolved_root.name, {"path": str(resolved_root)})
    _add_node(graph, project_id, "Project", resolved_root.name, {"workspace_root": str(resolved_root)})
    _add_node(graph, manifest_id, "Manifest", "manifest.json", {"path": ".librarian/manifest.json"})
    _add_node(graph, graph_artifact_id, "Graph", "graph.json", {"path": ".librarian/graph.json"})
    _add_node(graph, sidecars_id, "SidecarCollection", "sidecars", {"pattern": "*.librarian.yaml"})
    _add_edge(graph, workspace_id, project_id, "PART_OF_PROJECT", 1.0, "Workspace root is represented as the project.")

    path_to_node_id: dict[str, str] = {}
    id_to_node: dict[str, WorkspaceNode] = {}
    for directory in directories:
        node_type = _filesystem_type(directory)
        _add_workspace_node(graph, directory, node_type)
        path_to_node_id[directory.current_path] = directory.librarian_id
        id_to_node[directory.librarian_id] = directory
        _add_edge(graph, directory.librarian_id, project_id, "PART_OF_PROJECT", 1.0, "Directory belongs to the indexed workspace.")
        _add_path_nodes(graph, directory)

    for file_node in files:
        node_type = _filesystem_type(file_node)
        _add_workspace_node(graph, file_node, node_type)
        path_to_node_id[file_node.current_path] = file_node.librarian_id
        id_to_node[file_node.librarian_id] = file_node
        _add_edge(graph, file_node.librarian_id, project_id, "PART_OF_PROJECT", 1.0, "File belongs to the indexed workspace.")
        if node_type == "ConfigFile":
            _add_edge(graph, project_id, file_node.librarian_id, "HAS_CONFIG", 0.9, "Configuration file detected in the workspace.")
        _add_path_nodes(graph, file_node)

    for node in [*directories, *files]:
        if node.parent_path and node.parent_path in path_to_node_id:
            _add_edge(
                graph,
                path_to_node_id[node.parent_path],
                node.librarian_id,
                "CONTAINS",
                1.0,
                "Parent path comes from manifest metadata.",
            )
            _add_edge(
                graph,
                node.librarian_id,
                path_to_node_id[node.parent_path],
                "CURRENT_PARENT",
                1.0,
                "Current parent path comes from manifest metadata.",
            )
        original_parent = parent_path(node.original_path)
        if original_parent and original_parent in path_to_node_id:
            _add_edge(graph, node.librarian_id, path_to_node_id[original_parent], "ORIGINAL_PARENT", 1.0, "Original parent path is known.")
        proposed_parent = parent_path(node.proposed_path or node.current_path)
        if proposed_parent and proposed_parent in path_to_node_id:
            _add_edge(graph, node.librarian_id, path_to_node_id[proposed_parent], "PROPOSED_PARENT", 0.95, "Proposed parent path is known.")

    for node in [*directories, *files]:
        _add_metadata(graph, node)
        _add_risk(graph, node)
        if node.type == "file":
            _add_file_specific_metadata(graph, node)
        if node.code_metadata is not None:
            _add_code_metadata(graph, node, files)
        if node.directory_analysis is not None:
            _add_directory_metadata(graph, node)
        for relation in node.relations:
            target = _resolve_relation_target(relation.target, path_to_node_id, id_to_node)
            if target:
                _add_edge(
                    graph,
                    node.librarian_id,
                    target,
                    relation.type.upper(),
                    relation.confidence,
                    relation.reason or "Relation declared in sidecar metadata.",
                    {"declared_target": relation.target},
                )

    _add_developer_runtime(graph, resolved_root, workspace_id, project_id, manifest_id, graph_artifact_id, sidecars_id)
    _add_manifest_warnings(graph, manifest, workspace_id)
    _add_inferred_relationships(graph, files, directories, path_to_node_id)
    _add_agent_context(graph, files, directories, workspace_id)
    return graph


def _load_nodes_from_sidecars(root: Path, manifest: Manifest) -> tuple[list[WorkspaceNode], list[WorkspaceNode]]:
    files: list[WorkspaceNode] = []
    directories: list[WorkspaceNode] = []
    for directory in manifest.directories:
        directories.append(_read_sidecar_node(directory_sidecar_path(root, directory), directory))
    for file_node in manifest.files:
        files.append(_read_sidecar_node(file_sidecar_path(root, file_node), file_node))
    return files, directories


def _read_sidecar_node(path: Path, fallback: WorkspaceNode) -> WorkspaceNode:
    if not path.exists():
        return fallback
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return WorkspaceNode.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError):
        return fallback


def _add_node(graph, node_id: str, node_type: str, label: str, properties: dict[str, Any] | None = None) -> None:
    graph.add_node(node_id, id=node_id, type=node_type, label=label, properties=properties or {})


def _add_edge(
    graph,
    source: str,
    target: str,
    edge_type: str,
    confidence: float = 1.0,
    reason: str = "",
    properties: dict[str, Any] | None = None,
) -> None:
    if not graph.has_node(source) or not graph.has_node(target):
        return
    graph.add_edge(
        source,
        target,
        source=source,
        target=target,
        type=edge_type,
        confidence=max(0.0, min(1.0, confidence)),
        reason=reason,
        properties=properties or {},
    )


def _filesystem_type(node: WorkspaceNode) -> str:
    if node.type == "directory":
        return "Directory"
    if node.generated_file:
        return "GeneratedFile"
    if node.vendor_file:
        return "VendorFile"
    if node.lock_file:
        return "LockFile"
    if node.file_kind == "config":
        return "ConfigFile"
    if node.code_metadata is not None:
        return "CodeFile"
    return "File"


def _add_workspace_node(graph, node: WorkspaceNode, node_type: str) -> None:
    properties = node.model_dump(mode="json")
    _add_node(graph, node.librarian_id, node_type, node.name or node.current_path, properties)


def _add_path_nodes(graph, node: WorkspaceNode) -> None:
    original_id = stable_id("original_path", node.original_path)
    current_id = stable_id("current_path", node.current_path)
    proposed_id = stable_id("proposed_path", node.proposed_path or node.current_path)
    _add_node(graph, original_id, "OriginalPath", node.original_path, {"path": node.original_path})
    _add_node(graph, current_id, "CurrentPath", node.current_path, {"path": node.current_path})
    _add_node(graph, proposed_id, "ProposedPath", node.proposed_path or node.current_path, {"path": node.proposed_path or node.current_path})
    _add_edge(graph, original_id, current_id, "MOVED_TO", 1.0 if node.original_path == node.current_path else 0.95, "Original and current path mapping.")


def _add_metadata(graph, node: WorkspaceNode) -> None:
    for tag in node.tags:
        tag_id = stable_id("tag", slug(tag))
        _add_node(graph, tag_id, "Tag", tag, {"value": tag})
        _add_edge(graph, node.librarian_id, tag_id, "HAS_TAG", 1.0, "Tag declared in sidecar or manifest metadata.")

    category_id = stable_id("category", slug(node.classification.category))
    domain_id = stable_id("domain", slug(node.classification.domain))
    _add_node(graph, category_id, "Category", node.classification.category, node.classification.model_dump(mode="json"))
    _add_node(graph, domain_id, "Domain", node.classification.domain, {"domain": node.classification.domain})
    _add_edge(graph, node.librarian_id, category_id, "CLASSIFIED_AS", node.classification.confidence, node.classification.reason)
    _add_edge(graph, category_id, domain_id, "BELONGS_TO_DOMAIN", node.classification.confidence, "Category domain comes from classification metadata.")

    for key, values in node.entities.items():
        entity_type, edge_type = _entity_type_and_edge(key)
        for value in values:
            entity_id = stable_id(entity_type.lower(), slug(value))
            _add_node(graph, entity_id, entity_type, value, {"value": value})
            _add_edge(graph, node.librarian_id, entity_id, edge_type, 1.0, "Entity declared in sidecar or manifest metadata.")


def _entity_type_and_edge(key: str) -> tuple[str, str]:
    mapping = {
        "people": ("Person", "MENTIONS_PERSON"),
        "organizations": ("Organization", "MENTIONS_ORGANIZATION"),
        "places": ("Place", "MENTIONS_PLACE"),
        "dates": ("Date", "MENTIONS_DATE"),
    }
    return mapping.get(key, ("Entity", "MENTIONS_ENTITY"))


def _add_file_specific_metadata(graph, node: WorkspaceNode) -> None:
    if node.mime_type:
        mime_id = stable_id("mime", slug(node.mime_type))
        _add_node(graph, mime_id, "MIMEType", node.mime_type, {"mime_type": node.mime_type})
        _add_edge(graph, node.librarian_id, mime_id, "HAS_MIME_TYPE", 1.0, "MIME type detected during scan.")
    if node.extension:
        extension_id = stable_id("extension", slug(node.extension))
        _add_node(graph, extension_id, "Extension", node.extension, {"extension": node.extension})
        _add_edge(graph, node.librarian_id, extension_id, "HAS_EXTENSION", 1.0, "Extension detected from file name.")


def _add_risk(graph, node: WorkspaceNode) -> None:
    if node.risk_level != "low":
        risk_id = stable_id("risk", node.risk_level)
        _add_node(graph, risk_id, "Risk", f"{node.risk_level} risk", {"risk_level": node.risk_level})
        _add_edge(graph, node.librarian_id, risk_id, "HAS_RISK", 1.0, "Risk level is recorded on the workspace node.")
    if node.type == "file" and (node.code_metadata is not None or node.vendor_file or node.generated_file or node.lock_file) and not node.should_modify:
        risk_id = "risk:should-not-modify"
        _add_node(graph, risk_id, "Risk", "should not modify", {"policy": "read-only unless explicitly requested"})
        _add_edge(graph, node.librarian_id, risk_id, "SHOULD_NOT_MODIFY", 1.0, "Original source and protected files are read-only by default.")


def _add_code_metadata(graph, node: WorkspaceNode, files: list[WorkspaceNode]) -> None:
    metadata = node.code_metadata
    if metadata is None:
        return
    if metadata.module_name:
        module_label = metadata.package_name or metadata.module_name
        module_id = stable_id("module", module_label)
        _add_node(graph, module_id, "Module", module_label, {"module_name": metadata.module_name, "package_name": metadata.package_name})
        _add_edge(graph, node.librarian_id, module_id, "PART_OF_PACKAGE", 1.0, "Code file module metadata was detected statically.")
    package_id = None
    if metadata.package_name:
        package_label = ".".join(metadata.package_name.split(".")[:-1]) or metadata.package_name
        package_id = stable_id("package", package_label)
        _add_node(graph, package_id, "Package", package_label, {"package_name": package_label})
        if metadata.module_name:
            _add_edge(graph, stable_id("module", metadata.package_name), package_id, "PART_OF_PACKAGE", 0.95, "Package inferred from module path.")

    for symbol_type, graph_type in [("functions", "Function"), ("classes", "Class"), ("methods", "Method")]:
        for symbol in metadata.symbols.get(symbol_type, []):
            name = str(symbol.get("name", "unknown"))
            symbol_id = stable_id(graph_type.lower(), f"{node.librarian_id}:{name}")
            _add_node(graph, symbol_id, graph_type, name, {"file": node.current_path, **symbol})
            _add_edge(graph, node.librarian_id, symbol_id, "DEFINES", 1.0, "Symbol found by static code analysis.")

    for entrypoint in metadata.entrypoints:
        entrypoint_id = stable_id("entrypoint", f"{node.librarian_id}:{entrypoint}")
        _add_node(graph, entrypoint_id, "Entrypoint", entrypoint, {"file": node.current_path, "entrypoint": entrypoint})
        _add_edge(graph, node.librarian_id, entrypoint_id, "HAS_ENTRYPOINT", 1.0, "Entrypoint detected by static code analysis.")

    for framework in metadata.framework_hints:
        framework_id = stable_id("framework", slug(framework))
        _add_node(graph, framework_id, "Framework", framework, {"framework": framework})
        _add_edge(graph, node.librarian_id, framework_id, "USES_FRAMEWORK", 0.85, "Framework hint found by static code analysis.")

    for import_kind, imports in metadata.imports.items():
        for module_name in imports:
            import_id, import_type, import_properties = _import_node(module_name, import_kind, node, files)
            _add_node(graph, import_id, import_type, module_name, {"module": module_name, "kind": import_kind})
            _add_edge(
                graph,
                node.librarian_id,
                import_id,
                "IMPORTS",
                0.9,
                f"{import_kind.replace('_', ' ').title()} import detected statically.",
                import_properties,
            )

    if node.classification.category == "Tests" or metadata.test_hints:
        test_id = stable_id("test", node.librarian_id)
        _add_node(graph, test_id, "Test", node.current_path, {"file": node.current_path, "test_hints": metadata.test_hints})
        target = _infer_test_target(node, files)
        if target:
            _add_edge(graph, test_id, target.librarian_id, "TESTS", 0.65, "Test target inferred from nearby source path and filename.")


def _import_node(module_name: str, import_kind: str, source_node: WorkspaceNode, files: list[WorkspaceNode]) -> tuple[str, str, dict[str, Any]]:
    if import_kind == "external":
        return stable_id("dependency", module_name), "ExternalDependency", {"module": module_name, "kind": import_kind}
    if import_kind == "internal":
        resolved = _resolve_internal_module(module_name, source_node, files)
        if resolved and resolved.code_metadata and resolved.code_metadata.package_name:
            return (
                stable_id("module", resolved.code_metadata.package_name),
                "Module",
                {"module": module_name, "kind": import_kind, "resolved_path": resolved.current_path},
            )
        return stable_id("module", module_name), "Module", {"module": module_name, "kind": import_kind}
    return stable_id("import", module_name), "Import", {"module": module_name, "kind": import_kind}


def _resolve_internal_module(module_name: str, source_node: WorkspaceNode, files: list[WorkspaceNode]) -> WorkspaceNode | None:
    module_map = {
        file_node.code_metadata.package_name: file_node
        for file_node in files
        if file_node.code_metadata and file_node.code_metadata.package_name
    }
    candidates = [module_name]
    if source_node.code_metadata and source_node.code_metadata.package_name:
        package_parts = source_node.code_metadata.package_name.split(".")
        if len(package_parts) > 1:
            candidates.append(".".join([*package_parts[:-1], module_name]))
        if len(package_parts) > 2:
            candidates.append(".".join([*package_parts[:-2], module_name]))
    for candidate in candidates:
        if candidate in module_map:
            return module_map[candidate]
    module_leaf = module_name.split(".")[-1]
    same_name = [
        file_node
        for file_node in files
        if file_node.code_metadata
        and file_node.code_metadata.module_name == module_leaf
        and file_node.current_path != source_node.current_path
    ]
    return same_name[0] if same_name else None


def _infer_test_target(test_node: WorkspaceNode, files: list[WorkspaceNode]) -> WorkspaceNode | None:
    test_name = test_node.name.removeprefix("test_")
    candidates = [
        file_node
        for file_node in files
        if file_node.librarian_id != test_node.librarian_id
        and file_node.code_metadata is not None
        and file_node.classification.category != "Tests"
    ]
    for candidate in candidates:
        if candidate.name == test_name or candidate.name == test_node.name.replace("test_", ""):
            return candidate
    if candidates:
        return max(candidates, key=lambda item: SequenceMatcher(None, test_node.current_path, item.current_path).ratio())
    return None


def _add_directory_metadata(graph, node: WorkspaceNode) -> None:
    analysis = node.directory_analysis
    if analysis is None:
        return
    for role in analysis.possible_roles:
        component_id = stable_id("component", slug(role))
        _add_node(graph, component_id, "Component", role, {"role": role})
        _add_edge(graph, node.librarian_id, component_id, "CLASSIFIED_AS", 0.75, "Directory role inferred by offline analysis.")


def _add_developer_runtime(
    graph,
    root: Path,
    workspace_id: str,
    project_id: str,
    manifest_id: str,
    graph_artifact_id: str,
    sidecars_id: str,
) -> None:
    librarian_root = root / ".librarian"
    for note_path in sorted((librarian_root / "notes").glob("*.md")) if (librarian_root / "notes").exists() else []:
        note_id = stable_id("note", relative_posix(note_path, root))
        _add_node(graph, note_id, "MarkdownNote", note_path.name, {"path": relative_posix(note_path, root)})
        _add_edge(graph, project_id, note_id, "DOCUMENTED_BY", 1.0, "Markdown note generated by The Librarian runtime.")
    readme = librarian_root / "README.librarian.md"
    if readme.exists():
        readme_id = stable_id("note", ".librarian/README.librarian.md")
        _add_node(graph, readme_id, "MarkdownNote", "README.librarian.md", {"path": ".librarian/README.librarian.md"})
        _add_edge(graph, project_id, readme_id, "DOCUMENTED_BY", 1.0, "Runtime README documents the indexed workspace.")
    for runbook_path in sorted((librarian_root / "runbooks").glob("*.md")) if (librarian_root / "runbooks").exists() else []:
        runbook_id = stable_id("runbook", relative_posix(runbook_path, root))
        _add_node(graph, runbook_id, "Runbook", runbook_path.name, {"path": relative_posix(runbook_path, root)})
        _add_edge(graph, project_id, runbook_id, "HAS_RUNBOOK", 1.0, "Runbook exists in the developer runtime.")
    for scripts_dir in [librarian_root / "scripts", librarian_root / "graph_scripts"]:
        for script_path in sorted(scripts_dir.glob("*.py")) if scripts_dir.exists() else []:
            script_id = stable_id("script", relative_posix(script_path, root))
            _add_node(graph, script_id, "RunnableScript", script_path.name, {"path": relative_posix(script_path, root), "read_only": True})
            _add_edge(graph, workspace_id, script_id, "HAS_RUNNABLE_HELPER", 1.0, "Runnable helper script exists under .librarian.")
            _add_edge(graph, script_id, manifest_id, "SCRIPT_READS", 0.85, "Helper scripts read Librarian runtime artifacts.")
            _add_edge(graph, script_id, graph_artifact_id, "SCRIPT_READS", 0.85, "Graph helper scripts read graph.json when present.")
            _add_edge(graph, script_id, sidecars_id, "SCRIPT_READS", 0.6, "Some helpers inspect sidecar coverage.")


def _add_manifest_warnings(graph, manifest: Manifest, workspace_id: str) -> None:
    for index, warning in enumerate(manifest.warnings):
        warning_id = stable_id("warning", f"{index}:{warning}")
        _add_node(graph, warning_id, "Warning", warning, {"message": warning, "source": "manifest"})
        _add_edge(graph, workspace_id, warning_id, "HAS_RISK", 0.6, "Manifest warning should be reviewed before relying on graph output.")


def _add_inferred_relationships(graph, files: list[WorkspaceNode], directories: list[WorkspaceNode], path_to_node_id: dict[str, str]) -> None:
    files_by_hash: dict[str, list[WorkspaceNode]] = defaultdict(list)
    files_by_tag: dict[str, list[WorkspaceNode]] = defaultdict(list)
    files_by_org: dict[str, list[WorkspaceNode]] = defaultdict(list)
    files_by_original_parent: dict[str, list[WorkspaceNode]] = defaultdict(list)
    files_by_proposed_parent: dict[str, list[WorkspaceNode]] = defaultdict(list)

    for file_node in files:
        if file_node.content_hash:
            files_by_hash[file_node.content_hash].append(file_node)
        for tag in file_node.tags:
            files_by_tag[tag].append(file_node)
        for organization in file_node.entities.get("organizations", []):
            files_by_org[organization].append(file_node)
        if parent := parent_path(file_node.original_path):
            files_by_original_parent[parent].append(file_node)
        if parent := parent_path(file_node.proposed_path or file_node.current_path):
            files_by_proposed_parent[parent].append(file_node)

    for tag, nodes in files_by_tag.items():
        if 1 < len(nodes) <= 12:
            _pairwise_edges(graph, nodes, "SIMILAR_TO", 0.45, f"Files share tag {tag}.", {"shared_tag": tag})
    for organization, nodes in files_by_org.items():
        if 1 < len(nodes) <= 12:
            _pairwise_edges(graph, nodes, "SIMILAR_TO", 0.55, f"Files mention organization {organization}.", {"organization": organization})
    for parent, nodes in files_by_original_parent.items():
        if 1 < len(nodes) <= 15:
            _pairwise_edges(graph, nodes, "SIMILAR_TO", 0.35, f"Files share original parent {parent}.", {"original_parent": parent})
    for parent, nodes in files_by_proposed_parent.items():
        if len(nodes) > 1:
            cluster_id = stable_id("cluster", parent)
            _add_node(graph, cluster_id, "Cluster", parent, {"proposed_parent": parent})
            for node in nodes:
                _add_edge(graph, node.librarian_id, cluster_id, "PROPOSED_PARENT", 0.65, "Files cluster under the same proposed parent.")

    for left in files:
        for right in files:
            if left.librarian_id >= right.librarian_id:
                continue
            score = SequenceMatcher(None, left.name.lower(), right.name.lower()).ratio()
            if score >= 0.88 and left.content_hash != right.content_hash:
                _add_edge(graph, left.librarian_id, right.librarian_id, "SIMILAR_TO", score * 0.7, "File names are highly similar.", {"name_similarity": score})

    for nodes in files_by_hash.values():
        if len(nodes) > 1:
            _pairwise_edges(graph, nodes, "SIMILAR_TO", 1.0, "Files share the same content hash.", {"duplicate": True})

    for file_node in files:
        if file_node.name.lower().startswith("readme") or file_node.current_path.startswith("docs/"):
            target_parent = parent_path(file_node.current_path) or "."
            target_id = path_to_node_id.get(target_parent)
            if target_id:
                _add_edge(graph, target_id, file_node.librarian_id, "DOCUMENTED_BY", 0.7, "README/docs file is near the directory it documents.")

    for directory in directories:
        if directory.directory_analysis and "project_root" in directory.directory_analysis.possible_roles:
            project_marker_id = stable_id("feature", directory.current_path)
            _add_node(graph, project_marker_id, "Feature", directory.current_path, {"directory": directory.current_path})
            _add_edge(graph, directory.librarian_id, project_marker_id, "PART_OF_PROJECT", 0.75, "Project root role inferred from directory contents.")


def _pairwise_edges(graph, nodes: list[WorkspaceNode], edge_type: str, confidence: float, reason: str, properties: dict[str, Any]) -> None:
    for index, left in enumerate(nodes):
        for right in nodes[index + 1 :]:
            _add_edge(graph, left.librarian_id, right.librarian_id, edge_type, confidence, reason, properties)


def _add_agent_context(graph, files: list[WorkspaceNode], directories: list[WorkspaceNode], workspace_id: str) -> None:
    agent_id = "agent_context:default"
    prompt_pack_id = "prompt_pack:default"
    _add_node(graph, agent_id, "AgentContext", "agent context", {"purpose": "recommended first reads for agents"})
    _add_node(graph, prompt_pack_id, "PromptPack", "default prompt pack", {"purpose": "agent navigation prompts and runbooks"})
    starts = [file_node for file_node in files if file_node.code_metadata and file_node.code_metadata.entrypoints]
    starts.extend(file_node for file_node in files if file_node.name.lower().startswith("readme"))
    starts.extend(directory for directory in directories if directory.current_path in {".", "src", "docs", "tests"})
    for node in starts[:10]:
        _add_edge(graph, agent_id, node.librarian_id, "AGENT_SHOULD_START_FROM", 0.9, "Recommended first read for fast workspace orientation.")
    _add_edge(graph, workspace_id, agent_id, "DOCUMENTED_BY", 0.8, "Agent context summarizes the graph and runtime artifacts.")
    _add_edge(graph, agent_id, prompt_pack_id, "EXPLAINED_IN", 0.75, "Prompt pack documents how an agent should use the graph.")


def _resolve_relation_target(target: str, path_to_node_id: dict[str, str], id_to_node: dict[str, WorkspaceNode]) -> str | None:
    if target in id_to_node:
        return target
    if target in path_to_node_id:
        return path_to_node_id[target]
    return None
