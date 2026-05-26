from __future__ import annotations

import json
from pathlib import Path


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_manifest() -> dict:
    manifest_path = workspace_root() / '.librarian' / 'manifest.json'
    if not manifest_path.exists():
        raise SystemExit('manifest.json not found. Run librarian mark or librarian dev init first.')
    return json.loads(manifest_path.read_text(encoding='utf-8'))



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
