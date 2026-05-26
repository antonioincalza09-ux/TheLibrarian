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
