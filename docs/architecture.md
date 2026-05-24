# Architecture

TheLibrarian is organized around a small safety-first core.

## Data Flow

1. `scanner` reads metadata under the assigned root.
2. `providers` optionally classify metadata.
3. `planner` validates classification and builds destinations.
4. `reporter` renders human-readable and JSON artifacts.
5. `executor` applies saved plans and writes rollback manifests.
6. `webapp` exposes local preview endpoints backed by the same core.

## Provider Interface

Providers receive an `Inventory` and `ProviderContext`, then return per-file `source`, `category`, `reason`, and `confidence`.

The planner rejects unknown sources, unknown categories, invalid confidence values, and empty reasons. Invalid provider rows fall back to deterministic classification.

## Artifact Types

- Inventory JSON uses `Inventory.to_dict()`.
- Plan JSON uses `OrganizationPlan.to_dict()` and includes `provider`.
- Execution manifests include app version, root, operations, rollback paths, and skipped entries.
