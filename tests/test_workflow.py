from __future__ import annotations

import unittest
from pathlib import Path

import workflow


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_manifest_and_dry_graph(self) -> None:
        data = workflow.load_manifest(ROOT / "examples" / "demo" / "manifest.json")
        edges = workflow.describe(data, 2)
        self.assertIn("chr1-individuals-0 -> chr1-individuals-merge", edges)
        self.assertIn("chr1-analysis[ALL] -> chr1-ALL-publish", edges)

    def test_slurm_requires_partition(self) -> None:
        with self.assertRaisesRegex(SystemExit, "partition is required"):
            workflow.main([
                "--manifest", str(ROOT / "examples" / "demo" / "manifest.json"),
                "--executor", "slurm", "--dry-run",
            ])


if __name__ == "__main__":
    unittest.main()
