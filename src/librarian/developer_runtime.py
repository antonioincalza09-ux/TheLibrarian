from __future__ import annotations

import json
from pathlib import Path

from src.librarian.docs_exporter import explain_workspace, write_markdown_notes, write_runbooks
from src.librarian.rules.schema import Manifest
from src.librarian.storage.sqlite_store import update_sqlite_index


def initialize_runtime(root: str | Path, manifest: Manifest) -> None:
    resolved_root = Path(root).resolve()
    for relative in [
        ".librarian",
        ".librarian/runbooks",
        ".librarian/notes",
        ".librarian/scripts",
        ".librarian/logs",
        ".librarian/cache",
    ]:
        (resolved_root / relative).mkdir(parents=True, exist_ok=True)
    write_markdown_notes(resolved_root, manifest)
    write_runbooks(resolved_root, manifest)
    write_scripts(resolved_root)
    update_sqlite_index(resolved_root, manifest)


def regenerate_runtime(root: str | Path, manifest: Manifest) -> None:
    initialize_runtime(root, manifest)


def write_explanation(root: str | Path, manifest: Manifest) -> Path:
    resolved_root = Path(root).resolve()
    notes_path = resolved_root / ".librarian" / "notes" / "explain.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text("# Workspace Explanation\n\n" + explain_workspace(manifest) + "\n", encoding="utf-8")
    return notes_path


def write_scripts(root: Path) -> None:
    scripts = {
        "inspect_workspace.py": _inspect_workspace_script(),
        "print_manifest_summary.py": _print_manifest_summary_script(),
        "find_entrypoints.py": _find_entrypoints_script(),
        "find_unmarked.py": _find_unmarked_script(),
    }
    scripts_directory = root / ".librarian" / "scripts"
    scripts_directory.mkdir(parents=True, exist_ok=True)
    for name, content in scripts.items():
        (scripts_directory / name).write_text(content, encoding="utf-8")


def _inspect_workspace_script() -> str:
    return _script_prelude() + """
def main() -> int:
    manifest = load_manifest()
    print(f"Workspace: {manifest['workspace_root']}")
    print(f"Files: {manifest['counts']['files']}")
    print(f"Directories: {manifest['counts']['directories']}")
    print(f"Languages: {', '.join(manifest.get('detected_languages', [])) or 'none'}")
    print(f"Entrypoints: {', '.join(manifest.get('entrypoints', [])) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _print_manifest_summary_script() -> str:
    return _script_prelude() + """
def main() -> int:
    manifest = load_manifest()
    counts = manifest['counts']
    print('Manifest summary')
    print(f"- files: {counts['files']}")
    print(f"- directories: {counts['directories']}")
    print(f"- languages: {', '.join(manifest.get('detected_languages', [])) or 'none'}")
    print(f"- domains: {', '.join(manifest.get('detected_domains', [])) or 'none'}")
    print(f"- entrypoints: {', '.join(manifest.get('entrypoints', [])) or 'none'}")
    warnings = manifest.get('warnings', [])
    print(f"- warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _find_entrypoints_script() -> str:
    return _script_prelude() + """
def main() -> int:
    manifest = load_manifest()
    entrypoints = manifest.get('entrypoints', [])
    if not entrypoints:
        print('No entrypoints found.')
        return 0
    for entrypoint in entrypoints:
        print(entrypoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _find_unmarked_script() -> str:
    return _script_prelude() + """
def main() -> int:
    manifest = load_manifest()
    root = workspace_root()
    missing = []
    for file_node in manifest.get('files', []):
        sidecar = root / f"{file_node['current_path']}.librarian.yaml"
        if not sidecar.exists():
            missing.append(file_node['current_path'])
    for directory_node in manifest.get('directories', []):
        if directory_node['current_path'] == '.':
            sidecar = root / '.librarian.yaml'
        else:
            sidecar = root / directory_node['current_path'] / '.librarian.yaml'
        if not sidecar.exists():
            missing.append(directory_node['current_path'])
    if not missing:
        print('All manifest entries have sidecars.')
        return 0
    for item in missing:
        print(item)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _script_prelude() -> str:
    return """from __future__ import annotations

import json
from pathlib import Path


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_manifest() -> dict:
    manifest_path = workspace_root() / '.librarian' / 'manifest.json'
    if not manifest_path.exists():
        raise SystemExit('manifest.json not found. Run librarian mark or librarian dev init first.')
    return json.loads(manifest_path.read_text(encoding='utf-8'))


"""
