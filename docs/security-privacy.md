# Security And Privacy

TheLibrarian's commercial advantage is that it treats safety, privacy, reversibility, and auditability as core product requirements.

## Buyer-Readable Guarantees

- Local-first by default: scanning and planning run against a user-selected local root.
- Dry-run first: the default workflow previews a plan without moving files.
- No file deletion: TheLibrarian does not delete user files.
- No content modification: TheLibrarian does not edit file contents.
- Root confinement: operations must stay inside the assigned root.
- No overwrite: destination collisions are skipped instead of overwritten.
- Explicit confirmation: apply and rollback require confirmation.
- Rollback artifacts: every apply writes a rollback manifest.
- Metadata-only remote posture: online providers receive file metadata only, never file contents.

## Threat Model

Primary risks:

- A provider returns malformed, unsafe, or overconfident classifications.
- A path attempts to escape the assigned root.
- A destination already exists.
- A file changes between planning and apply.
- A user applies a plan without understanding ambiguous entries.
- A future remote service could accidentally receive sensitive content.

Current mitigations:

- Provider output is validated and falls back to deterministic classification.
- Paths are normalized and checked against the assigned root.
- Collisions are skipped.
- Apply rechecks source and destination state.
- Low-confidence and ambiguous entries route to `Review/`.
- Remote provider payloads are designed around metadata only.

## Provider Boundary

Remote-capable providers may receive:

- relative path
- file name
- extension
- size in bytes
- modified timestamp
- parent folder

Remote-capable providers must not receive:

- file contents
- snippets or previews
- absolute paths
- local root paths
- usernames
- API keys or secrets
- private hashes intended to identify content

Remote diagnostics avoid mandatory cloud calls where possible. The deterministic provider remains the fallback.

## Auditability

TheLibrarian writes artifacts under `.thelibrarian/` so operators can inspect what happened:

- inventory
- plan
- policy decision
- policy pack snapshot
- job events
- reports
- rollback manifest
- managed session reports

These artifacts support review, client reporting, and rollback workflows.

Managed report HTML is generated as a local static file. It does not load remote scripts, fonts, images, trackers, or provider services.

## Current Limits

- TheLibrarian is not a compliance certification product.
- Policy packs are templates, not legal or regulatory advice.
- No authentication, billing, hosted SaaS dashboard, or remote marketplace exists today.
- Remote provider safety depends on preserving metadata-only payloads in future integrations.
- Users must still review plans before confirmed apply.

See also [safety-model.md](safety-model.md) for implementation-level invariants.
