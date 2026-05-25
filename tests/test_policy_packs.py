from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.models import Inventory, OrganizationPlan, PlanEntry
from src.policies import PolicyConfig, PolicyMode, evaluate_policy
from src.policy_packs import export_policy_pack, get_policy_pack, list_policy_packs, policy_pack_kpis


class PolicyPackTests(unittest.TestCase):
    def test_builtin_policy_packs_are_available(self) -> None:
        packs = list_policy_packs()
        pack_ids = {pack.pack_id for pack in packs}

        self.assertIn("local_safe_review", pack_ids)
        self.assertIn("supervised_documents", pack_ids)

    def test_exported_policy_pack_is_loaded_as_local_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)

            path = export_policy_pack("supervised_documents", root)
            pack = get_policy_pack("supervised_documents", root)

            self.assertEqual(path.parent, root / ".thelibrarian" / "policy-packs")
            self.assertEqual(pack.source, "local")
            self.assertEqual(pack.policy.mode, PolicyMode.SUPERVISED_AUTONOMY)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["source"], "local")

    def test_policy_pack_id_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)

            with self.assertRaises(ValueError):
                export_policy_pack("../escape", root)

    def test_policy_pack_kpis_summarize_policy_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            (root / "script.py").write_text("print('hello')", encoding="utf-8")
            plan = OrganizationPlan(
                root=str(root.resolve()),
                entries=[
                    PlanEntry(
                        source="report.pdf",
                        destination="Documents/Reports/report.pdf",
                        reason="document",
                        confidence=0.92,
                        category="Documents",
                    ),
                    PlanEntry(
                        source="script.py",
                        destination="Code/script.py",
                        reason="code",
                        confidence=0.92,
                        category="Code",
                    ),
                ],
            )
            policy = PolicyConfig(mode=PolicyMode.SUPERVISED_AUTONOMY, name="supervised_autonomy")

            evaluation = evaluate_policy(root, Inventory(root=str(root.resolve()), files=[]), plan, policy)
            kpis = policy_pack_kpis(plan, evaluation).to_dict()

            self.assertEqual(kpis["total_entries"], 2)
            self.assertEqual(kpis["auto_approved"], 1)
            self.assertEqual(kpis["requires_approval"], 1)
            self.assertEqual(kpis["auto_approval_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
