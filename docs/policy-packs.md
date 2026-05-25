# Policy Packs

Policy Packs are local reusable templates for policy behavior. They are the foundation for a future template marketplace, but this version has no remote marketplace, authentication, billing, or sync.

## Commands

```bash
thelibrarian policy-packs list
thelibrarian policy-packs show local_safe_review
thelibrarian policy-packs export supervised_documents C:\target
```

## Built-In Packs

- `local_safe_review`: strict dry-run policy where planned moves require explicit approval.
- `supervised_documents`: supervised autonomy for high-confidence `Documents`, `Media`, and `Data` entries.

## Local Registry

Exported packs are written under:

```text
.thelibrarian/policy-packs/<pack_id>.json
```

Local packs override built-in packs with the same id for that root. Pack IDs are validated and cannot include path traversal.

## Safety

Policy Packs configure the policy gate only. They cannot directly create filesystem paths, bypass planner validation, apply moves, or suppress executor safety checks.
