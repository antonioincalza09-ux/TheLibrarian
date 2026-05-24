from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.models import Inventory, OrganizationPlan, PlanEntry
from src.policies import PolicyConfig, PolicyDecisionStatus, PolicyMode, default_policy, evaluate_policy


class PolicyEngineTests(unittest.TestCase):
    def test_dry_run_only_requires_approval_for_planned_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            plan = OrganizationPlan(
                root=str(root.resolve()),
                entries=[
                    PlanEntry(
                        source="report.pdf",
                        destination="Documents/report.pdf",
                        reason="test",
                        confidence=0.92,
                        category="Documents",
                    )
                ],
            )
            evaluation = evaluate_policy(root, Inventory(root=str(root.resolve()), files=[]), plan, default_policy())

            self.assertEqual(evaluation.decisions[0].status, PolicyDecisionStatus.REQUIRES_APPROVAL)
            self.assertEqual(evaluation.decisions[0].risk_score, 0.0)

    def test_supervised_autonomy_auto_approves_safe_document_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            plan = OrganizationPlan(
                root=str(root.resolve()),
                entries=[
                    PlanEntry(
                        source="report.pdf",
                        destination="Documents/report.pdf",
                        reason="test",
                        confidence=0.92,
                        category="Documents",
                    )
                ],
            )
            policy = PolicyConfig(mode=PolicyMode.SUPERVISED_AUTONOMY, name="supervised_autonomy")

            evaluation = evaluate_policy(root, Inventory(root=str(root.resolve()), files=[]), plan, policy)

            self.assertEqual(evaluation.decisions[0].status, PolicyDecisionStatus.AUTO_APPROVED)

    def test_supervised_autonomy_requires_approval_for_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "script.py").write_text("print('hello')", encoding="utf-8")
            plan = OrganizationPlan(
                root=str(root.resolve()),
                entries=[
                    PlanEntry(
                        source="script.py",
                        destination="Code/script.py",
                        reason="test",
                        confidence=0.92,
                        category="Code",
                    )
                ],
            )
            policy = PolicyConfig(mode=PolicyMode.SUPERVISED_AUTONOMY, name="supervised_autonomy")

            evaluation = evaluate_policy(root, Inventory(root=str(root.resolve()), files=[]), plan, policy)

            self.assertEqual(evaluation.decisions[0].status, PolicyDecisionStatus.REQUIRES_APPROVAL)
            self.assertGreaterEqual(evaluation.decisions[0].risk_score, 0.25)

    def test_sensitive_directory_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            plan = OrganizationPlan(
                root=str(root.resolve()),
                entries=[
                    PlanEntry(
                        source="report.pdf",
                        destination=".ssh/report.pdf",
                        reason="test",
                        confidence=0.92,
                        category="Documents",
                    )
                ],
            )
            policy = PolicyConfig(mode=PolicyMode.SUPERVISED_AUTONOMY, name="supervised_autonomy")

            evaluation = evaluate_policy(root, Inventory(root=str(root.resolve()), files=[]), plan, policy)

            self.assertEqual(evaluation.decisions[0].status, PolicyDecisionStatus.BLOCKED)
            self.assertIn("sensitive", evaluation.decisions[0].reason)

    def test_missing_or_ambiguous_extension_increases_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "config.json").write_text("{}", encoding="utf-8")
            plan = OrganizationPlan(
                root=str(root.resolve()),
                entries=[
                    PlanEntry(
                        source="config.json",
                        destination="Review/config.json",
                        reason="test",
                        confidence=0.35,
                        category="Review",
                    )
                ],
            )

            evaluation = evaluate_policy(root, Inventory(root=str(root.resolve()), files=[]), plan, default_policy())

            self.assertGreaterEqual(evaluation.decisions[0].risk_score, 0.6)


if __name__ == "__main__":
    unittest.main()

