# Product Requirements Document

## Product

TheLibrarian is a privacy-first file organization copilot for professionals and small businesses.

It helps users turn messy local directories into auditable, reversible organization plans, with vertical policy packs for professional workflows and managed cleanup sessions for client-facing service delivery.

## Problem

Small businesses and professional offices accumulate mixed folders containing reports, invoices, scans, client documents, media, archives, exports, and unknown files. Existing cleanup tools are often either manual, opaque, cloud-first, or too risky for sensitive client data.

TheLibrarian solves the trust problem first: preview everything, apply only after confirmation, keep rollback artifacts, and route uncertainty to review.

## Target Personas

- Solo professionals and consultants who want safe local cleanup.
- Small law, accounting, healthcare, real estate, agency, and administrative offices with recurring folder hygiene problems.
- Operators offering cleanup as a managed service.
- Future team administrators who need shared templates and policy governance.

## Jobs To Be Done

- Scan a local folder and understand what is inside.
- Produce a practical organization plan without moving files.
- Use vertical templates for industry-specific folder expectations.
- Identify ambiguous, risky, or conflicting files before apply.
- Generate reports that a client or internal stakeholder can understand.
- Apply approved changes only when explicit confirmation and rollback are available.

## Value Proposition

TheLibrarian combines AI-assisted organization with safety guarantees:

- privacy-first and local-first
- metadata-only provider integrations
- reversible and auditable operations
- vertical policy packs
- managed cleanup reporting

## Current MVP

Implemented:

- CLI and local dashboard.
- Deterministic and optional provider adapters.
- Job engine with filesystem artifacts.
- Policy gate and policy pack attachment.
- Managed cleanup dry-run sessions with KPI and reports.
- Rollback manifests for confirmed apply.

Not implemented:

- billing
- authentication
- hosted SaaS dashboard
- remote marketplace
- team administration
- SSO
- real licensing enforcement

## Success Metrics

Product metrics to track when instrumentation exists:

- number of dry-run plans generated
- plan-to-apply conversion rate
- review queue size by vertical pack
- managed report sessions completed
- estimated minutes saved
- rollback usage rate
- user-reported confidence before apply
- percentage of files routed to `Review/`

No telemetry exists in the current local-first implementation.

## Non-Goals

- Automatically deleting files.
- Modifying file contents.
- Uploading file contents to cloud providers.
- Replacing human review for sensitive or ambiguous files.
- Implementing billing, authentication, or SaaS in Phase 1.
