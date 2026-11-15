from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from genome_workflow.core import extract_individuals, extract_sift, frequency_distribution, merge_individuals, mutation_overlap


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo"


class CoreTests(unittest.TestCase):
    def test_parallel_extraction_merge_and_analyses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            parts = []
            for index in range(2):
                part = work / f"part-{index}.json"
                stats = extract_individuals(DEMO / "genotypes.vcf", part, index, 2, "carrier")
                self.assertEqual(stats["samples"], 4)
                parts.append(part)
            merged = work / "individuals.json"
            merge_individuals(parts, merged)
            data = json.loads(merged.read_text())
            self.assertEqual(data["HG00096"], ["rs100", "rs300"])
            self.assertEqual(data["HG00098"], ["rs200", "rs300"])

            sift = work / "sift.json"
            extract_sift(DEMO / "annotations.vcf", sift)
            self.assertEqual(json.loads(sift.read_text())["rs100"], 0.01)

            overlap = work / "overlap.csv"
            stats = mutation_overlap(merged, sift, DEMO / "populations" / "ALL", overlap)
            self.assertEqual(stats, {"individuals": 4, "pairs": 6})
            with overlap.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            pair = next(row for row in rows if row["sample_a"] == "HG00096" and row["sample_b"] == "HG00097")
            self.assertEqual(pair["shared_deleterious_variants"], "2")

            frequency = work / "frequency.json"
            frequency_distribution(merged, DEMO / "populations" / "ALL", frequency, 20, 7)
            result = json.loads(frequency.read_text())
            self.assertEqual(sum(result["histogram"].values()), 20)

    def test_homozygous_alt_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "individuals.json"
            extract_individuals(DEMO / "genotypes.vcf", output, 0, 1, "homozygous-alt")
            data = json.loads(output.read_text())
            self.assertEqual(data["HG00097"], ["rs100"])
            self.assertEqual(data["HG00098"], ["rs200"])


if __name__ == "__main__":
    unittest.main()
