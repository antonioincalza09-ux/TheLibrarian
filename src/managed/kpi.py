from __future__ import annotations

from src.jobs.models import JobRecord
from src.managed.models import ManagedCleanupKPI
from src.models import Inventory, OrganizationPlan
from src.policies.models import PolicyEvaluation


def _clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def calculate_kpi(
    *,
    inventory: Inventory,
    plan: OrganizationPlan,
    policy: PolicyEvaluation | None = None,
    job: JobRecord | None = None,
) -> ManagedCleanupKPI:
    files_scanned = inventory.total_files
    planned_moves = len(plan.planned_entries)
    review_category_count = len(plan.review_entries)
    conflict_count = len(plan.conflict_entries)
    already_organized_count = len(plan.already_organized_entries)
    auto_approved_moves = 0
    manual_review_moves = 0
    blocked_moves = 0

    if policy is not None:
        auto_approved_moves = sum(1 for decision in policy.decisions if decision.status.value == "auto_approved")
        manual_review_moves = sum(1 for decision in policy.decisions if decision.status.value == "requires_approval")
        blocked_moves = sum(1 for decision in policy.decisions if decision.status.value == "blocked")
    else:
        manual_review_moves = planned_moves

    applied_moves = job.counters.get("applied", 0) if job else 0
    verified_moves = job.counters.get("verified", 0) if job else 0
    rollback_available = bool(job and job.manifest_path)

    safety_score = 100
    if applied_moves > 0 and not rollback_available:
        safety_score -= 20
    if blocked_moves > 0:
        safety_score -= 15
    if conflict_count > 0:
        safety_score -= 10
    if applied_moves > 0 and verified_moves == 0:
        safety_score -= 10

    if files_scanned:
        organized_ratio = (planned_moves + already_organized_count) / files_scanned
        review_penalty = min(35, (review_category_count / files_scanned) * 35)
        organization_score = _clamp_score(organized_ratio * 100 - review_penalty)
    else:
        organization_score = 100

    if planned_moves:
        automation_score = _clamp_score((auto_approved_moves / planned_moves) * 100 - min(30, manual_review_moves * 4))
    else:
        automation_score = 0

    risk_score = 0
    if files_scanned:
        risk_score += min(35, (blocked_moves / files_scanned) * 100)
        risk_score += min(30, (manual_review_moves / files_scanned) * 70)
        risk_score += min(20, (conflict_count / files_scanned) * 80)
        risk_score += min(20, (review_category_count / files_scanned) * 50)
    if rollback_available:
        risk_score -= 10
    if verified_moves > 0:
        risk_score -= 8

    estimated_minutes_saved = round(planned_moves * 0.5 + manual_review_moves * 1.0, 1)

    return ManagedCleanupKPI(
        files_scanned=files_scanned,
        total_bytes_scanned=inventory.total_bytes,
        planned_moves=planned_moves,
        auto_approved_moves=auto_approved_moves,
        manual_review_moves=manual_review_moves,
        blocked_moves=blocked_moves,
        review_category_count=review_category_count,
        conflict_count=conflict_count,
        already_organized_count=already_organized_count,
        applied_moves=applied_moves,
        verified_moves=verified_moves,
        rollback_available=rollback_available,
        safety_score=_clamp_score(safety_score),
        organization_score=organization_score,
        automation_score=automation_score,
        risk_score=_clamp_score(risk_score),
        estimated_minutes_saved=estimated_minutes_saved,
    )
