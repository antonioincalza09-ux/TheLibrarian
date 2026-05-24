from __future__ import annotations

from pathlib import Path

from src.config import RuntimeConfig
from src.executor import execute_plan
from src.jobs.models import JobConfig, JobPhase, JobRecord, JobStatus
from src.jobs.store import JobStore
from src.jsonio import write_inventory, write_plan
from src.planner import build_plan
from src.providers import ProviderContext, get_provider
from src.reporter import render_plan_report
from src.scanner import scan_directory


class JobRunner:
    def __init__(self, root: str | Path, *, config: RuntimeConfig | None = None) -> None:
        self.store = JobStore(root)
        self.config = config or RuntimeConfig()

    def create_job(self, *, dry_run: bool = True, policy_name: str | None = None) -> JobRecord:
        return self.store.create(dry_run=dry_run, provider=self.config.provider, policy_name=policy_name)

    def run(
        self,
        job: JobRecord | None = None,
        *,
        dry_run: bool = True,
        allow_apply: bool = False,
        policy_name: str | None = None,
    ) -> JobRecord:
        active_job = job or self.create_job(dry_run=dry_run, policy_name=policy_name)
        job_config = JobConfig(
            root=active_job.root,
            dry_run=dry_run,
            provider=self.config.provider,
            model=self.config.model,
            endpoint=self.config.endpoint,
            policy_name=policy_name or active_job.policy_name,
            privacy_mode=self.config.privacy_mode,
        )

        try:
            self.store.update(
                active_job.job_id,
                status=JobStatus.SCANNING,
                phase=JobPhase.SCANNING,
                message="Scanning root directory.",
                provider=job_config.provider,
                dry_run=job_config.dry_run,
                policy_name=job_config.policy_name,
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
                    report_path=str(report_path),
                    counters=counters,
                )

            self.store.update(
                active_job.job_id,
                status=JobStatus.APPLYING,
                phase=JobPhase.APPLYING,
                message="Applying approved plan.",
                plan_path=str(plan_path),
                counters=counters,
            )
            execution = execute_plan(active_job.root, plan, dry_run=False)
            counters.update({"applied": execution.applied_count, "verified": execution.applied_count})
            report = render_plan_report(inventory, plan, execution)
            report_path = self.store.artifact_path(active_job.job_id, "report.txt")
            report_path.write_text(report, encoding="utf-8")
            return self.store.update(
                active_job.job_id,
                status=JobStatus.COMPLETED,
                phase=JobPhase.COMPLETED,
                message="Approved job completed.",
                manifest_path=execution.manifest_path,
                report_path=str(report_path),
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

