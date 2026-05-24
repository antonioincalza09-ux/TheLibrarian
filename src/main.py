from __future__ import annotations

import argparse

from src.orchestrator import organize_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely organize files inside an assigned root directory.")
    parser.add_argument("root", help="Directory to scan and organize.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the plan. Dry-run remains the default when this flag is omitted.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = organize_directory(args.root, dry_run=not args.apply)
    print(result.report)

    if result.execution.manifest_path:
        print(f"Manifest: {result.execution.manifest_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

