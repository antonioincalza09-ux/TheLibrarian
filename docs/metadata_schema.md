# Metadata Schema

The Librarian writes read-only sidecar metadata next to files and directories.

File sidecar path:

- `<filename>.librarian.yaml`

Directory sidecar path:

- `<directory>/.librarian.yaml`

Core fields:

- `librarian_id`: stable hash-like identifier derived from node type and original relative path.
- `type`: `file` or `directory`.
- `original_path`: relative path at first scan/mark time.
- `current_path`: latest known relative path.
- `proposed_path`: current dry-run target or logical target.
- `content_hash`: SHA-256 for readable files.
- `name_hash`: SHA-256 of the basename.
- `mime_type`, `extension`, `size_bytes`, `created_at`, `modified_at`, `indexed_at`.
- `file_kind`: one of `source_code`, `document`, `image`, `audio`, `video`, `archive`, `config`, `data`, `unknown`.
- `detected_language`: language hint when recognized.
- `classification`: `domain`, `category`, `confidence`, `reason`.
- `code_metadata`: present for code files, otherwise `null`.
- `directory_analysis`: present for directory sidecars, otherwise `null`.
- `relations`: outgoing soft links for future graph ingestion.
- `status`: informational state tags.
- `errors`: scan or analysis errors.
- `generated_file`, `vendor_file`, `lock_file`, `should_modify`, `should_move`, `risk_level`.

`code_metadata` contains:

- `language`, `module_name`, `package_name`
- `imports.internal`, `imports.external`, `imports.standard_library`
- `symbols.functions`, `symbols.classes`, `symbols.methods`
- `docstrings.module`, `docstrings.functions`, `docstrings.classes`
- `entrypoints`
- `framework_hints`
- `test_hints`
- `config_hints`
- `risk_level`
- `generated_file`, `vendor_file`, `lock_file`
- `should_modify`, `should_move`
- `reason`

`directory_analysis` contains:

- `direct_file_count`
- `direct_subdirectory_count`
- `total_file_count`
- `dominant_extensions`
- `dominant_languages`
- `recurring_name_tokens`
- `possible_roles`
- `theme`
- `should_reorganize`
- `should_modify`
- `reason`

Global manifest:

- `.librarian/manifest.json`
- machine-readable JSON for files, directories, counts, languages, domains, entrypoints, warnings, and errors

Plan:

- `.librarian/plan.json`
- list of proposed file and directory moves with `node_type`, `safe_to_move`, `logical_only`, `collision`, and `status`

Operation log:

- `.librarian/logs/operations.jsonl`
- append-only move and rollback events
