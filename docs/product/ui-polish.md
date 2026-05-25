# UI Polish Plan

## Goal

Make TheLibrarian feel like a professional operations product without weakening the local-first implementation or adding a frontend framework prematurely.

## Product Principles

- Show the safe workflow before showing dangerous actions.
- Prefer compact KPI cards, badges, and filtered tables over raw JSON.
- Make dry-run, review, approval, apply, and rollback states visually distinct.
- Keep visuals sober and operational for professionals and small businesses.
- Do not load remote assets, trackers, or external scripts in the local dashboard or reports.

## Dashboard Improvements

Implemented foundation:

- Brand subtitle aligned to the product positioning.
- Safe workflow strip: scan, plan, review, approve, apply/rollback.
- Before/after two-level tree preview for the current dry-run plan.
- Pack-aware plan preview when a dashboard operator selects a policy pack.
- Pack detail panel with industry, tier, policy, folder templates, and managed recommendations.
- Managed Cleanup table surfaces client report artifact paths.
- Managed KPI cards summarize safety, planned moves, review count, and risk.
- Managed report preview panel for the latest generated local HTML report.

Recommended next improvements:

- Add status-aware row styling for review, blocked, conflict, and auto-approved entries.
- Expand the before/after preview from two-level counts to a collapsible tree.
- Add clearer empty states for no jobs, no review items, and no managed sessions.

## Managed Report Improvements

Implemented foundation:

- Markdown report remains the portable source artifact.
- JSON report remains the structured artifact.
- HTML report provides a browser-viewable, print-friendly client deliverable.

Recommended next improvements:

- Add optional brand fields for operator name, logo path, disclaimer text, and client reference.
- Add a compact appendix with reviewed categories and skipped paths.
- Add a generated sample report command for demos.

## Design Constraints

- Keep HTML/CSS local and dependency-free.
- Keep cards and panels simple, with compact spacing and strong table readability.
- Avoid decorative effects that make file safety harder to scan.
- Preserve accessibility basics: readable contrast, semantic headings, visible focus states, and responsive layout.
