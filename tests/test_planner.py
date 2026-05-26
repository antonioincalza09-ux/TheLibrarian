from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.planner import build_plan
from src.policy_packs import get_policy_pack
from src.scanner import scan_directory


class PlannerTests(unittest.TestCase):
    def test_planner_routes_known_and_ambiguous_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            (root / "config.json").write_text("{}", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entries = {entry.source: entry for entry in plan.entries}

            self.assertEqual(entries["report.pdf"].destination, "Documents/Reports/report.pdf")
            self.assertEqual(entries["report.pdf"].status, "planned")
            self.assertEqual(entries["config.json"].destination, "Review/config.json")
            self.assertEqual(entries["config.json"].category, "Review")

    def test_planner_marks_conflicts_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "report.pdf").write_text("content", encoding="utf-8")
            (root / "Documents" / "Reports").mkdir(parents=True, exist_ok=True)
            (root / "Documents" / "Reports" / "report.pdf").write_text("existing", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entry = next(item for item in plan.entries if item.source == "report.pdf")

            self.assertEqual(entry.status, "skipped_conflict")
            self.assertIn("Destination already exists", entry.warning or "")

    def test_planner_uses_contextual_skill_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "excel-xlsx").mkdir(parents=True)
            (root / "excel-xlsx" / "SKILL.md").write_text("skill", encoding="utf-8")
            (root / "excel-xlsx" / "Excel_Generator_Agent.md").write_text("agent", encoding="utf-8")
            (root / "excel-xlsx" / "_meta.json").write_text("{}", encoding="utf-8")
            (root / "excel-xlsx" / ".clawhub").mkdir(parents=True)
            (root / "excel-xlsx" / ".clawhub" / "origin.json").write_text("{}", encoding="utf-8")
            (root / "ontology" / "scripts").mkdir(parents=True)
            (root / "ontology" / "scripts" / "ontology.py").write_text("print('ok')", encoding="utf-8")
            (root / "ontology" / "references").mkdir(parents=True)
            (root / "ontology" / "references" / "schema.md").write_text("schema", encoding="utf-8")
            (root / "workflow-sequencer.md").write_text("workflow", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entries = {entry.source: entry for entry in plan.entries}

            self.assertEqual(entries["excel-xlsx/SKILL.md"].destination, "Skills/excel-xlsx/Definition/SKILL.md")
            self.assertEqual(
                entries["excel-xlsx/Excel_Generator_Agent.md"].destination,
                "Skills/excel-xlsx/Documentation/Excel_Generator_Agent.md",
            )
            self.assertEqual(entries["excel-xlsx/_meta.json"].destination, "Skills/excel-xlsx/Metadata/_meta.json")
            self.assertEqual(entries["excel-xlsx/.clawhub/origin.json"].destination, "Skills/excel-xlsx/Metadata/origin.json")
            self.assertEqual(entries["ontology/scripts/ontology.py"].destination, "Skills/ontology/Source/ontology.py")
            self.assertEqual(entries["ontology/references/schema.md"].destination, "Skills/ontology/References/schema.md")
            self.assertEqual(
                entries["workflow-sequencer.md"].destination,
                "Skills/workflow-sequencer/Documentation/workflow-sequencer.md",
            )
            self.assertIn("Contextual skill workspace grouping", entries["excel-xlsx/SKILL.md"].reason)

    def test_planner_can_repair_broad_category_skill_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "Documents" / "excel-xlsx").mkdir(parents=True)
            (root / "Documents" / "excel-xlsx" / "SKILL.md").write_text("skill", encoding="utf-8")
            (root / "Code" / "ontology" / "scripts").mkdir(parents=True)
            (root / "Code" / "ontology" / "scripts" / "ontology.py").write_text("print('ok')", encoding="utf-8")
            (root / "Review" / "excel-xlsx").mkdir(parents=True)
            (root / "Review" / "excel-xlsx" / "_meta.json").write_text("{}", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entries = {entry.source: entry for entry in plan.entries}

            self.assertEqual(
                entries["Documents/excel-xlsx/SKILL.md"].destination,
                "Skills/excel-xlsx/Definition/SKILL.md",
            )
            self.assertEqual(
                entries["Code/ontology/scripts/ontology.py"].destination,
                "Skills/ontology/Source/ontology.py",
            )
            self.assertEqual(
                entries["Review/excel-xlsx/_meta.json"].destination,
                "Skills/excel-xlsx/Metadata/_meta.json",
            )

    def test_regular_markdown_without_skill_context_stays_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "notes.md").write_text("notes", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entry = plan.entries[0]

            self.assertEqual(entry.destination, "Documents/Notes/notes.md")

    def test_documents_are_routed_to_specific_context_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "financial-analysis.pdf").write_text("finance", encoding="utf-8")
            (root / "testing-accessibility-auditor.md").write_text("testing", encoding="utf-8")
            (root / "workflow-sequencer.md").write_text("workflow", encoding="utf-8")
            (root / "presentation.pptx").write_text("slides", encoding="utf-8")
            (root / "memo.txt").write_text("memo", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory)
            entries = {entry.source: entry for entry in plan.entries}

            self.assertEqual(
                entries["financial-analysis.pdf"].destination,
                "Documents/Financial/financial-analysis.pdf",
            )
            self.assertEqual(
                entries["testing-accessibility-auditor.md"].destination,
                "Documents/Testing/testing-accessibility-auditor.md",
            )
            self.assertEqual(
                entries["workflow-sequencer.md"].destination,
                "Documents/Workflows/workflow-sequencer.md",
            )
            self.assertEqual(entries["presentation.pptx"].destination, "Documents/Presentations/presentation.pptx")
            self.assertEqual(entries["memo.txt"].destination, "Documents/Notes/memo.txt")

    def test_policy_pack_templates_refine_matching_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            (root / "client-contract.pdf").write_text("contract", encoding="utf-8")
            (root / "unknown.json").write_text("{}", encoding="utf-8")

            inventory = scan_directory(root)
            plan = build_plan(inventory, policy_pack=get_policy_pack("studio_legale"))
            entries = {entry.source: entry for entry in plan.entries}

            self.assertEqual(entries["client-contract.pdf"].destination, "Documents/Contracts/client-contract.pdf")
            self.assertIn("Policy pack 'Studio Legale'", entries["client-contract.pdf"].reason)
            self.assertEqual(entries["unknown.json"].destination, "Review/NeedsHumanReview/unknown.json")


if __name__ == "__main__":
    unittest.main()
