from __future__ import annotations

from pathlib import Path

from src.config import RuntimeConfig
from src.executor import execute_plan, rollback_manifest
from src.jobs.models import JobConfig, JobPhase, JobRecord, JobStatus
from src.jobs.store import JobStore
from src.jsonio import read_plan, write_inventory, write_plan
from src.models import OrganizationPlan
from src.policy_packs import get_policy_pack
from src.policies import approve_required_decisions, default_policy, evaluate_policy, filter_plan_for_policy
from src.policies.models import PolicyEvaluation
from src.planner import build_plan
from src.providers import ProviderContext, get_provider
from src.reporter import render_plan_report
from src.scanner import scan_directory
from src.security import SafetyError


class JobRunner:
    def __init__(self, root: str | Path, *, config: RuntimeConfig | None = None) -> None:
        self.store = JobStore(root)
        self.config = config or RuntimeConfig()

    def create_job(
        self,
        *,
        dry_run: bool = True,
        policy_name: str | None = None,
        pack_id: str | None = None,
    ) -> JobRecord:
        if pack_id:
            get_policy_pack(pack_id)
        return self.store.create(
            dry_run=dry_run,
            provider=self.config.provider,
            policy_name=policy_name,
            pack_id=pack_id,
        )

    def run(
        self,
        job: JobRecord | None = None,
        *,
        dry_run: bool = True,
        allow_apply: bool = False,
        policy_name: str | None = None,
        pack_id: str | None = None,
    ) -> JobRecord:
        resolved_pack_id = pack_id or (job.pack_id if job else None)
        active_job = job or self.create_job(dry_run=dry_run, policy_name=policy_name, pack_id=resolved_pack_id)
        job_config = JobConfig(
            root=active_job.root,
            dry_run=dry_run,
            provider=self.config.provider,
            model=self.config.model,
            endpoint=self.config.endpoint,
            policy_name=policy_name or active_job.policy_name,
            pack_id=resolved_pack_id,
            privacy_mode=self.config.privacy_mode,
        )
        policy_pack_path = None

        try:
            if job_config.pack_id:
                policy_pack = get_policy_pack(job_config.pack_id)
                policy_pack_path = self.store.write_json_artifact(
                    active_job.job_id,
                    "policy_pack.json",
                    policy_pack.to_dict(),
                )
            self.store.update(
                active_job.job_id,
                status=JobStatus.SCANNING,
                phase=JobPhase.SCANNING,
                message="Scanning root directory.",
                provider=job_config.provider,
                dry_run=job_config.dry_run,
                policy_name=job_config.policy_name,
                pack_id=job_config.pack_id,
            )
            inventory = scan_directory(active_job.root)
            inventory_path = self.store.artifact_path(active_job.job_id, "inventory.json")
            write_inventory(inventory_path, inventory)

            counters = dict(active_job.counters)
            counters.update({"scanned": inventory.total_files})
            self.store.update(
                active_job.job_id,
                status=JobStatus.PLANNING,
                phase=JobPhase.PLANNING,
                message="Building organization plan.",
                inventory_path=str(inventory_path),
                counters=counters,
            )

            provider = get_provider(job_config.provider)
            context = ProviderContext(
                model=job_config.model,
                endpoint=job_config.endpoint,
                privacy_mode=job_config.privacy_mode,
            )
            plan = build_plan(inventory, provider=provider, context=context)
            plan_path = self.store.artifact_path(active_job.job_id, "plan.json")
            write_plan(plan_path, plan)
            policy = default_policy(job_config.policy_name)
            policy_evaluation = evaluate_policy(active_job.root, inventory, plan, policy)
            policy_path = self.store.write_json_artifact(
                active_job.job_id,
                "policy_decision.json",
                policy_evaluation.to_dict(),
            )

            counters.update(
                {
                    "planned": len(plan.planned_entries),
                    "skipped": len(plan.conflict_entries) + len(plan.already_organized_entries),
                }
            )

            if job_config.dry_run:
                execution = execute_plan(active_job.root, plan, dry_run=True)
                report = render_plan_report(inventory, plan, execution)
                report_path = self.store.artifact_path(active_job.job_id, "report.txt")
                report_path.write_text(report, encoding="utf-8")
                return self.store.update(
                    active_job.job_id,
                    status=JobStatus.COMPLETED,
                    phase=JobPhase.COMPLETED,
                    message="Dry-run job completed.",
                    plan_path=str(plan_path),
                    policy_path=str(policy_path),
                    report_path=str(report_path),
                    counters=counters,
                )

            if not allow_apply:
                report = render_plan_report(inventory, plan)
                report_path = self.store.artifact_path(active_job.job_id, "report.txt")
                report_path.write_text(report, encoding="utf-8")
                return self.store.update(
                    active_job.job_id,
                    status=JobStatus.AWAITING_APPROVAL,
                    phase=JobPhase.AWAITING_APPROVAL,
                    message="Plan awaits explicit approval before apply.",
                    plan_path=str(plan_path),
                    policy_path=str(policy_path),
                    report_path=str(report_path),
                    counters=counters,
                )

            self.store.update(
                active_job.job_id,
                status=JobStatus.APPLYING,
                phase=JobPhase.APPLYING,
                message="Applying approved plan.",
                plan_path=str(plan_path),
                policy_path=str(policy_path),
                counters=counters,
            )
            approved_plan = filter_plan_for_policy(plan, policy_evaluation)
            if not approved_plan.entries:
                report = render_plan_report(inventory, plan)
                report_path = self.store.artifact_path(active_job.job_id, "report.txt")
                report_path.write_text(report, encoding="utf-8")
                return self.store.update(
                    active_job.job_id,
                    status=JobStatus.AWAITING_APPROVAL,
                    phase=JobPhase.AWAITING_APPROVAL,
                    message="No policy-approved entries are available to apply.",
                    plan_path=str(plan_path),
                    policy_path=str(policy_path),
                    report_path=str(report_path),
                    counters=counters,
                )
            execution = execute_plan(active_job.root, approved_plan, dry_run=False)
            counters.update({"applied": execution.applied_count, "verified": execution.applied_count})
            report = render_plan_report(inventory, plan, execution)
            report_path = self.store.artifact_path(active_job.job_id, "report.txt")
            report_path.write_text(report, encoding="utf-8")
            verification_path = self.store.write_json_artifact(
                active_job.job_id,
                "verification.json",
                {
                    "job_id": active_job.job_id,
                    "manifest_path": execution.manifest_path,
                    "applied": execution.applied_count,
                    "warnings": list(execution.warnings),
                },
            )
            return self.store.update(
                active_job.job_id,
                status=JobStatus.COMPLETED,
                phase=JobPhase.COMPLETED,
                message="Approved job completed.",
                manifest_path=execution.manifest_path,
                report_path=str(report_path),
                verification_path=str(verification_path),
                counters=counters,
            )
        except Exception as exc:
            return self.store.update(
                active_job.job_id,
                status=JobStatus.FAILED,
                phase=JobPhase.FAILED,
                message="Job failed.",
                error=str(exc),
            )

    def approve(self, job_id: str) -> JobRecord:
        job = self.store.load(job_id)
        evaluation = self._load_policy_evaluation(job)
        approved = approve_required_decisions(evaluation)
        policy_path = self.store.write_json_artifact(job.job_id, "policy_decision.json", approved.to_dict())
        return self.store.update(
            job.job_id,
            status=JobStatus.AWAITING_APPROVAL,
            phase=JobPhase.AWAITING_APPROVAL,
            message="Policy decisions manually approved.",
            policy_path=str(policy_path),
        )

    def apply(self, job_id: str) -> JobRecord:
        job = self.store.load(job_id)
        plan = self._load_plan(job)
        evaluation = self._load_policy_evaluation(job)
        approved_plan = filter_plan_for_policy(plan, evaluation)
        if not approved_plan.entries:
            raise SafetyError("No policy-approved entries are available to apply.")

        self.store.update(
            job.job_id,
            status=JobStatus.APPLYING,
            phase=JobPhase.APPLYING,
            message="Applying policy-approved job entries.",
        )
        execution = execute_plan(job.root, approved_plan, dry_run=False)
        counters = dict(job.counters)
        counters.update({"applied": execution.applied_count, "verified": execution.applied_count})
        verification_path = self.store.write_json_artifact(
            job.job_id,
            "verification.json",
            {
                "job_id": job.job_id,
                "manifest_path": execution.manifest_path,
                "applied": execution.applied_count,
                "warnings": list(execution.warnings),
            },
        )
        return self.store.update(
            job.job_id,
            status=JobStatus.COMPLETED,
            phase=JobPhase.COMPLETED,
            message="Policy-approved job apply completed.",
            manifest_path=execution.manifest_path,
            verification_path=str(verification_path),
            counters=counters,
        )

    def rollback(self, job_id: str) -> JobRecord:
        job = self.store.load(job_id)
        if not job.manifest_path:
            raise SafetyError("Job has no manifest to rollback.")

        self.store.update(
            job.job_id,
            status=JobStatus.APPLYING,
            phase=JobPhase.APPLYING,
            message="Rolling back job manifest.",
        )
        execution = rollback_manifest(job.root, job.manifest_path, confirm=True)
        counters = dict(job.counters)
        counters.update({"applied": max(counters.get("applied", 0) - execution.applied_count, 0)})
        verification_path = self.store.write_json_artifact(
            job.job_id,
            "rollback_verification.json",
            {
                "job_id": job.job_id,
                "rolled_back": execution.applied_count,
                "warnings": list(execution.warnings),
            },
        )
        return self.store.update(
            job.job_id,
            status=JobStatus.ROLLED_BACK,
            phase=JobPhase.ROLLED_BACK,
            message="Job rollback completed.",
            verification_path=str(verification_path),
            counters=counters,
        )

    def _load_plan(self, job: JobRecord) -> OrganizationPlan:
        if not job.plan_path:
            raise SafetyError("Job has no plan artifact.")
        return read_plan(job.plan_path)

    def _load_policy_evaluation(self, job: JobRecord) -> PolicyEvaluation:
        if not job.policy_path:
            raise SafetyError("Job has no policy decision artifact.")
        return PolicyEvaluation.from_dict(self.store.read_json_artifact(job.job_id, "policy_decision.json"))
