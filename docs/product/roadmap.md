# Roadmap

## Phase 1: Professionalization And Documentation

Goal: make the product understandable to buyers, operators, and future contributors.

Deliverables:

- Commercial README.
- Product PRD.
- Commercialization plan.
- Security and privacy document.
- Updated architecture document.

Exit criteria:

- The docs clearly explain what exists today.
- Future SaaS, billing, marketplace, and team features are framed as future architecture.
- No runtime behavior changes are introduced.

## Phase 2: Managed Cleanup MVP Sellable

Goal: make `thelibrarian managed` usable as a service workflow.

Deliverables:

- Stronger managed report Markdown and JSON.
- Local HTML report export for client review and printing.
- Example managed reports in `examples/`.
- Clear artifact map for clients.
- Tests for report content, session integrity, and no file movement.
- Dashboard links to managed report artifacts.
- Dashboard visual polish for safe workflow, KPI, and managed report discovery.

Exit criteria:

- An operator can run a dry-run session and hand the report to a client.
- The report explains KPI, risks, review items, and recommended next steps.

## Phase 3: Pro Local Product

Goal: improve the self-service local product.

Deliverables:

- Better dashboard review and pack selection workflows.
- Batch job ergonomics.
- Advanced policy pack validation.
- Local report export improvements.

Exit criteria:

- A non-technical professional can understand the plan, risks, and next action in the local UI.
- Pro-oriented features remain local-first and do not require a cloud account.

## Phase 4: Team/SaaS-Ready Architecture

Goal: design the future hosted and team product without forcing cloud behavior into the local tool.

Deliverables:

- Account and licensing interface design.
- Billing boundary design.
- Remote marketplace design.
- Hosted provider boundary.
- Optional metadata-only sync design.

Exit criteria:

- SaaS components have clear interfaces and privacy constraints.
- Local-first workflows remain fully usable without hosted services.
