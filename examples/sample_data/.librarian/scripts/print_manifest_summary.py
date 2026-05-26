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
