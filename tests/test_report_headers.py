import unittest
from pathlib import Path


REPORTS = Path(__file__).resolve().parents[1] / "reports"
REQUIRED_LABELS = ("Contexte", "Problème", "Méthode", "Modifications", "Résultats")


class ReportHeaderTests(unittest.TestCase):
    def test_every_markdown_report_starts_with_a_complete_quick_summary(self):
        reports = sorted(REPORTS.glob("*.md"))
        self.assertGreater(len(reports), 0)
        for report in reports:
            with self.subTest(report=report.name):
                text = report.read_text(encoding="utf-8")
                first_part = "\n".join(text.splitlines()[:20])
                self.assertIn("## Résumé rapide", first_part)
                for label in REQUIRED_LABELS:
                    self.assertIn(f"**{label}**", first_part)


if __name__ == "__main__":
    unittest.main()
