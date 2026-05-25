from __future__ import annotations

from src.policies.models import PolicyConfig, PolicyMode
from src.policy_packs.models import PolicyPack, PolicyPackRule


def builtin_policy_packs() -> list[PolicyPack]:
    return [
        PolicyPack(
            pack_id="local_safe_review",
            name="Local Safe Review",
            version="0.1.0",
            description="Strict local pack that keeps all planned moves human-reviewed.",
            policy=PolicyConfig(mode=PolicyMode.DRY_RUN_ONLY, name="dry_run_only"),
            tags=("local", "safe", "review"),
            rules=(
                PolicyPackRule(
                    name="human_review_required",
                    description="Every planned move requires explicit human approval before apply.",
                    severity="required",
                ),
            ),
            kpi_targets={
                "blocked_rate_max": 0.05,
                "review_rate_min": 0.0,
            },
            source="builtin",
            created_at="2026-05-25T00:00:00+00:00",
        ),
        PolicyPack(
            pack_id="supervised_documents",
            name="Supervised Documents",
            version="0.1.0",
            description="Local supervised-autonomy pack for high-confidence Documents, Media, and Data moves.",
            policy=PolicyConfig(
                mode=PolicyMode.SUPERVISED_AUTONOMY,
                name="supervised_autonomy",
                auto_apply_categories=("Documents", "Media", "Data"),
                minimum_confidence=0.92,
            ),
            tags=("local", "supervised", "documents"),
            rules=(
                PolicyPackRule(
                    name="high_confidence_only",
                    description="Only high-confidence low-risk entries can be policy-approved.",
                    severity="required",
                ),
                PolicyPackRule(
                    name="code_requires_review",
                    description="Code, Apps, Archives, and Review entries stay manual.",
                    severity="required",
                ),
            ),
            kpi_targets={
                "auto_approval_rate_min": 0.25,
                "blocked_rate_max": 0.05,
            },
            source="builtin",
            created_at="2026-05-25T00:00:00+00:00",
        ),
    ]
