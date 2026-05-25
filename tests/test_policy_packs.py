from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cli import main
from src.policy_packs import (
    export_policy_pack,
    get_policy_pack,
    list_policy_packs,
    policy_pack_kpis,
    recommend_policy_packs,
    validate_policy_pack,
)
from src.policy_packs.models import validate_policy_pack_id
from src.policies import default_policy, evaluate_policy
from src.planner import build_plan
from src.scanner import scan_directory


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class PolicyPackTests(unittest.TestCase):
    def test_all_vertical_policy_packs_load_and_validate(self) -> None:
        packs = [pack for pack in list_policy_packs() if pack.industry]
        ids = [pack.id for pack in packs]

        self.assertEqual(len(packs), 25)
        self.assertEqual(len(ids), len(set(ids)))
        for pack in packs:
            self.assertEqual(validate_policy_pack(pack), [])
            self.assertTrue(pack.folder_templates)
            self.assertTrue(pack.managed_service_recommendations)
            self.assertIsNotNone(pack.kpi_profile)

    def test_builtin_policy_templates_are_available(self) -> None:
        pack_ids = {pack.pack_id for pack in list_policy_packs()}

        self.assertIn("local_safe_review", pack_ids)
        self.assertIn("supervised_documents", pack_ids)

    def test_recommend_policy_packs_by_industry(self) -> None:
        healthcare = {pack.id for pack in recommend_policy_packs("healthcare")}
        creative = {pack.id for pack in recommend_policy_packs("creative")}

        self.assertTrue({"medical_clinic", "dental_clinic"} <= healthcare)
        self.assertTrue({"photography_studio", "video_production"} <= creative)

    def test_export_policy_pack_creates_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            output = Path(temp_directory) / "studio_legale.json"

            exported = export_policy_pack("studio_legale", output)
            payload = json.loads(exported.read_text(encoding="utf-8"))

        self.assertEqual(payload["id"], "studio_legale")

    def test_policy_pack_id_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            validate_policy_pack_id("../escape")

    def test_policy_pack_kpis_from_plan_and_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            inventory = scan_directory(root)
            plan = build_plan(inventory)
            evaluation = evaluate_policy(root, inventory, plan, default_policy("supervised_autonomy"))

            kpis = policy_pack_kpis(plan, evaluation).to_dict()

        self.assertEqual(kpis["total_entries"], 1)
        self.assertEqual(kpis["auto_approved"], 1)


class PolicyPackCliTests(unittest.TestCase):
    def test_packs_list_json(self) -> None:
        exit_code, output, _ = run_cli(["packs", "list", "--format", "json"])
        payload = json.loads(output)
        vertical = [pack for pack in payload["packs"] if pack.get("industry")]

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(vertical), 25)

    def test_packs_show_json(self) -> None:
        exit_code, output, _ = run_cli(["packs", "show", "studio_legale", "--format", "json"])
        payload = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["id"], "studio_legale")

    def test_packs_recommend_json(self) -> None:
        exit_code, output, _ = run_cli(["packs", "recommend", "--industry", "healthcare", "--format", "json"])
        payload = json.loads(output)
        ids = {pack["id"] for pack in payload["packs"]}

        self.assertEqual(exit_code, 0)
        self.assertTrue({"medical_clinic", "dental_clinic"} <= ids)

    def test_packs_validate_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            pack_path = export_policy_pack("general_office", Path(temp_directory) / "pack.json")

            exit_code, output, _ = run_cli(["packs", "validate", str(pack_path), "--format", "json"])
            payload = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["valid"])

    def test_policy_pack_cli_export_and_show(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)

            export_exit, export_output, _ = run_cli(
                ["policy-packs", "export", "supervised_documents", str(root), "--format", "json"]
            )
            show_exit, show_output, _ = run_cli(
                ["policy-packs", "show", "supervised_documents", "--root", str(root), "--format", "json"]
            )
            export_payload = json.loads(export_output)
            show_payload = json.loads(show_output)

            self.assertEqual(export_exit, 0)
            self.assertEqual(show_exit, 0)
            self.assertTrue(Path(export_payload["path"]).exists())
            self.assertEqual(show_payload["source"], "local")


if __name__ == "__main__":
    unittest.main()
