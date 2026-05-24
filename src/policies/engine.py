from __future__ import annotations

from pathlib import Path, PurePosixPath

from src.models import Inventory, OrganizationPlan, PlanEntry
from src.policies.models import PolicyConfig, PolicyDecision, PolicyDecisionStatus, PolicyEvaluation, PolicyMode
from src.security import SafetyError, normalize_relative_path, resolve_relative_path, resolve_root


SENSITIVE_DIRECTORIES = {".git", ".ssh", ".config", ".thelibrarian", ".the_librarian"}
AMBIGUOUS_EXTENSIONS = {"", ".json", ".xml", ".yml", ".yaml"}


def evaluate_policy(root: str | Path, inventory: Inventory, plan: OrganizationPlan, policy: PolicyConfig) -> PolicyEvaluation:
    resolved_root = resolve_root(root)
    decisions = [_evaluate_entry(resolved_root, entry, policy) for entry in plan.entries]
    return PolicyEvaluation(root=str(resolved_root), policy=policy, decisions=decisions)


def filter_plan_for_policy(plan: OrganizationPlan, evaluation: PolicyEvaluation) -> OrganizationPlan:
    allowed_sources = {
        decision.source
        for decision in evaluation.decisions
        if decision.status == PolicyDecisionStatus.AUTO_APPROVED or decision.approved_by_user
    }
    entries = [entry for entry in plan.entries if entry.source in allowed_sources and entry.status == "planned"]
    return OrganizationPlan(
        root=plan.root,
        entries=entries,
        warnings=list(plan.warnings),
        generated_at=plan.generated_at,
        provider=plan.provider,
    )


def approve_required_decisions(evaluation: PolicyEvaluation) -> PolicyEvaluation:
    decisions: list[PolicyDecision] = []
    for decision in evaluation.decisions:
        if decision.status == PolicyDecisionStatus.REQUIRES_APPROVAL:
            decisions.append(
                PolicyDecision(
                    source=decision.source,
                    destination=decision.destination,
                    category=decision.category,
                    confidence=decision.confidence,
                    status=decision.status,
                    reason=f"{decision.reason} Manually approved.",
                    risk_score=decision.risk_score,
                    approved_by_user=True,
                )
            )
        else:
            decisions.append(decision)
    return PolicyEvaluation(
        root=evaluation.root,
        policy=evaluation.policy,
        decisions=decisions,
        generated_at=evaluation.generated_at,
    )


def _evaluate_entry(root: Path, entry: PlanEntry, policy: PolicyConfig) -> PolicyDecision:
    risk_score = _risk_score(entry)

    if entry.status != "planned":
        return _decision(entry, PolicyDecisionStatus.BLOCKED, f"Entry status is '{entry.status}', not planned.", risk_score)

    safety_error = _path_safety_error(root, entry)
    if safety_error:
        return _decision(entry, PolicyDecisionStatus.BLOCKED, safety_error, risk_score)

    if policy.mode == PolicyMode.DRY_RUN_ONLY:
        return _decision(entry, PolicyDecisionStatus.REQUIRES_APPROVAL, "Dry-run policy requires explicit approval.", risk_score)

    if policy.mode == PolicyMode.SUPERVISED_AUTONOMY and _can_auto_approve(root, entry, policy):
        return _decision(entry, PolicyDecisionStatus.AUTO_APPROVED, "Entry satisfies supervised autonomy policy.", risk_score)

    return _decision(entry, PolicyDecisionStatus.REQUIRES_APPROVAL, "Entry requires approval under supervised autonomy policy.", risk_score)


def _can_auto_approve(root: Path, entry: PlanEntry, policy: PolicyConfig) -> bool:
    return (
        entry.status == "planned"
        and entry.confidence >= policy.minimum_confidence
        and entry.category in policy.auto_apply_categories
        and entry.warning is None
        and _path_safety_error(root, entry) is None
    )


def _path_safety_error(root: Path, entry: PlanEntry) -> str | None:
    try:
        source_relative = normalize_relative_path(entry.source)
        destination_relative = normalize_relative_path(entry.destination)
    except SafetyError as exc:
        return str(exc)

    if _has_sensitive_part(source_relative) or _has_sensitive_part(destination_relative):
        return "Source or destination involves a sensitive directory."

    try:
        source_path = resolve_relative_path(root, source_relative, must_exist=True)
        destination_path = resolve_relative_path(root, destination_relative, must_exist=False)
    except SafetyError as exc:
        return str(exc)
    except FileNotFoundError:
        return "Source file does not exist."

    if not source_path.exists():
        return "Source file does not exist."
    if destination_path.exists():
        return "Destination already exists."
    return None


def _risk_score(entry: PlanEntry) -> float:
    score = 0.0
    if entry.confidence < 0.92:
        score += 0.30
    if entry.category in {"Apps", "Code"}:
        score += 0.25
    if entry.category == "Archives":
        score += 0.20
    if entry.category == "Review":
        score += 0.20
    if _has_sensitive_part(entry.source) or _has_sensitive_part(entry.destination):
        score += 0.20
    source_extension = PurePosixPath(entry.source).suffix.lower()
    if source_extension in AMBIGUOUS_EXTENSIONS:
        score += 0.10
    return min(max(score, 0.0), 1.0)


def _has_sensitive_part(path_value: str) -> bool:
    return any(part in SENSITIVE_DIRECTORIES for part in PurePosixPath(path_value.replace("\\", "/")).parts)


def _decision(
    entry: PlanEntry,
    status: PolicyDecisionStatus,
    reason: str,
    risk_score: float,
) -> PolicyDecision:
    return PolicyDecision(
        source=entry.source,
        destination=entry.destination,
        category=entry.category,
        confidence=entry.confidence,
        status=status,
        reason=reason,
        risk_score=risk_score,
    )

