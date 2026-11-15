from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.generate_scaling_fixture import generate
from genome_workflow.core import extract_individuals


class ScalingFixtureTests(unittest.TestCase):
    def test_fixture_is_deterministic_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            metadata = generate(output, variants=12, samples=5)
            self.assertEqual(metadata["variants"], 12)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["populations"], {"ALL": "ALL"})
            extracted = output / "individuals.json"
            stats = extract_individuals(output / "genotypes.vcf", extracted, 0, 1, "carrier")
            self.assertEqual(stats, {"samples": 5, "variants_seen": 12, "variants_selected": 12})

    def test_fixture_rejects_invalid_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generate(Path(directory), variants=0, samples=1)


if __name__ == "__main__":
    unittest.main()
