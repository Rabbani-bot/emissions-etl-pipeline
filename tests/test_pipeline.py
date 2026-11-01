import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from make_sources import make_truth, render  # noqa: E402
from pipeline import extract, transform, accuracy, canonical_site  # noqa: E402


class TestETL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.truth = make_truth(); render(cls.truth)
        cls.clean, cls.report = transform(extract())

    def test_site_name_variants(self):
        for v in ["South Plant", "south plant", "S. Plant ", "SOUTH PLANT"]:
            self.assertEqual(canonical_site(v), "South Plant")
        with self.assertRaises(ValueError):
            canonical_site("Unknown Mill")

    def test_all_units_standardised(self):
        self.assertEqual(set(self.clean["unit_std"]), {"kWh", "litre"})

    def test_duplicate_removed_and_gap_reported(self):
        self.assertEqual(self.report["duplicates_removed"], 1)
        self.assertIn(["Depot", "2025-03", "diesel"], self.report["gaps"])

    def test_accuracy_against_truth(self):
        acc = accuracy(self.clean, self.truth)
        self.assertEqual(acc["values_within_0.1pct"], acc["rows_recovered"])
        self.assertEqual(acc["truth_rows"] - acc["rows_recovered"], 3)  # exactly the missing month

    def test_unknown_unit_raises(self):
        raw = extract(); raw.loc[0, "unit"] = "barrel"
        with self.assertRaises(ValueError):
            transform(raw)


if __name__ == "__main__":
    unittest.main()
