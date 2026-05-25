# Configuration

TheLibrarian uses TOML configuration and CLI flags. Precedence is:

1. Internal defaults.
2. `thelibrarian.toml` in the current working directory.
3. `.thelibrarian/config.toml` under the assigned root.
4. The path passed with `--config`.
5. Environment variables.
6. CLI flags.

## Supported Keys

```toml
[thelibrarian]
provider = "deterministic"
model = ""
endpoint = ""
dry_run = true
output_directory = ".thelibrarian/reports"
privacy_mode = "metadata-only"
```

## Environment Variables

- `THELIBRARIAN_PROVIDER`
- `THELIBRARIAN_MODEL`
- `THELIBRARIAN_ENDPOINT`
- `THELIBRARIAN_DRY_RUN`
- `THELIBRARIAN_OUTPUT_DIRECTORY`
- `THELIBRARIAN_PRIVACY_MODE`
- `OPENAI_API_KEY` for the OpenAI-compatible provider
- `THELIBRARIAN_REMOTE_ENDPOINT`
- `THELIBRARIAN_REMOTE_MODEL`
- `THELIBRARIAN_REMOTE_API_KEY`
- `THELIBRARIAN_REMOTE_API_KEY_ENV`
- `THELIBRARIAN_REMOTE_TIMEOUT_SECONDS`
- `THELIBRARIAN_MANAGED_ENDPOINT`
- `THELIBRARIAN_MANAGED_MODEL`
- `THELIBRARIAN_MANAGED_API_KEY`
- `THELIBRARIAN_MANAGED_API_KEY_ENV`
- `THELIBRARIAN_MANAGED_TIMEOUT_SECONDS`

Only `metadata-only` privacy mode is supported in this version.
