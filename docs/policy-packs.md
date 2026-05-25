# Policy Packs

Policy packs are JSON files that describe organization and policy preferences without hardcoding industries in Python.

## Vertical Pack Registry

Vertical packs are stored under `data/policy_packs/` and loaded by `src.policy_packs.registry`.

Each vertical pack includes:

- `id`, `name`, `version`, `industry`, `description`, and `tier`.
- `recommended_policy`: `dry_run_only` or `supervised_autonomy`.
- `categories` and `folder_templates`.
- `naming_conventions`.
- `sensitive_directories` and `high_risk_categories`.
- `kpi_profile`.
- `managed_service_recommendations`.

Folder templates must be relative POSIX-style paths. Absolute paths, `..`, and backslashes are rejected.

## Vertical CLI

```powershell
thelibrarian packs list
thelibrarian packs list --format json
thelibrarian packs show studio_legale
thelibrarian packs recommend --industry healthcare
thelibrarian packs export studio_legale --output studio_legale.json
thelibrarian packs validate studio_legale.json
```

## Local Policy Template Compatibility

The earlier local template commands remain available:

```powershell
thelibrarian policy-packs list
thelibrarian policy-packs show local_safe_review
thelibrarian policy-packs export supervised_documents C:\target
```

Exported local packs are written under:

```text
.thelibrarian/policy-packs/<pack_id>.json
```

Local packs override built-in packs with the same id for that root. Pack IDs are validated and cannot include path traversal.

## Tiers

- `free`: safe default packs suitable for general use.
- `premium_stub`: vertical packs prepared for future paid features.
- `managed_stub`: high-touch industries where assisted review and compliance posture matter.

## Current Vertical Packs

The registry currently ships 25 vertical packs: `general_office`, `studio_legale`, `commercialista`, `marketing_agency`, `software_agency`, `real_estate_agency`, `medical_clinic`, `dental_clinic`, `hr_recruiting`, `construction_company`, `architecture_studio`, `ecommerce_business`, `restaurant_hospitality`, `school_training_center`, `photography_studio`, `video_production`, `freelancer_consultant`, `nonprofit_association`, `insurance_broker`, `financial_advisor`, `accounting_firm`, `logistics_company`, `manufacturing_company`, `event_planning`, and `beauty_wellness`.

## Job Integration

`thelibrarian job run ROOT --pack studio_legale` validates the pack, saves it as `.thelibrarian/jobs/<job_id>/policy_pack.json`, and stores `pack_id` in `job.json`. In this version the pack does not yet change classification.

## Safety

Policy packs configure policy and reporting only. They cannot directly bypass planner validation, apply moves, suppress executor safety checks, or move files outside the assigned root.
