#!/usr/bin/env python3
"""Measure DAGonStar fan-out scalability and verify result equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ("chr1.ALL.overlap.csv", "chr1.ALL.frequency.json", "chr1.ALL.summary.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_for_artifacts(output: Path, timeout: float = 30.0) -> dict[str, str]:
    paths = [output / name for name in ARTIFACTS]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and any(not path.is_file() for path in paths):
        time.sleep(0.25)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError("missing artifacts: " + ", ".join(missing))
    return {path.name: sha256(path) for path in paths}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--levels", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--executor", choices=("batch", "slurm"), default="batch")
    parser.add_argument("--partition")
    args = parser.parse_args()
    if args.repeats < 1 or any(level < 1 for level in args.levels):
        parser.error("levels and repeats must be positive")
    if args.executor == "slurm" and not args.partition:
        parser.error("--partition is required for Slurm")
    args.output.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, object]] = []
    reference_hashes: dict[str, str] | None = None

    # Interleave levels by repeat so filesystem-cache warming is not concentrated
    # entirely on the larger fan-outs.
    for repeat in range(1, args.repeats + 1):
        levels = args.levels if repeat % 2 else list(reversed(args.levels))
        for level in levels:
            run_output = args.output / f"{args.executor}-n{level}-r{repeat}"
            command = [
                sys.executable, str(ROOT / "workflow.py"), "--config", str(args.config.resolve()),
                "--manifest", str((args.fixture / "manifest.json").resolve()),
                "--individual-jobs", str(level), "--frequency-runs", "500", "--seed", "42",
                "--max-individuals", "100", "--output", str(run_output), "--executor", args.executor,
            ]
            if args.executor == "slurm":
                command.extend(("--partition", args.partition, "--pre-stage"))
            started = time.monotonic()
            completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            seconds = time.monotonic() - started
            if completed.returncode:
                raise RuntimeError(f"n={level} repeat={repeat} failed:\n{completed.stdout[-8000:]}")
            hashes = wait_for_artifacts(run_output)
            if reference_hashes is None:
                reference_hashes = hashes
            elif hashes != reference_hashes:
                raise RuntimeError(f"scientific result mismatch at n={level}, repeat={repeat}")
            runs.append({
                "level": level, "repeat": repeat, "seconds": round(seconds, 6),
                "hashes": hashes, "output_tail": completed.stdout[-2000:],
            })

    medians = {
        level: statistics.median(float(run["seconds"]) for run in runs if run["level"] == level)
        for level in args.levels
    }
    baseline = medians[args.levels[0]]
    summary = [
        {
            "level": level,
            "median_seconds": round(medians[level], 6),
            "speedup": round(baseline / medians[level], 6),
            "efficiency": round((baseline / medians[level]) / level, 6),
        }
        for level in args.levels
    ]
    fixture_metadata = json.loads((args.fixture / "fixture.json").read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(), "platform": platform.platform(), "python": sys.version,
        "logical_cpus": os.cpu_count(), "executor": args.executor, "partition": args.partition,
        "fixture": fixture_metadata, "repeats": args.repeats, "runs": runs, "summary": summary,
        "scientific_outputs_identical": True,
    }
    report_path = args.output / f"scalability-{socket.gethostname()}-{args.executor}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = args.output / f"latest-{args.executor}.json"
    shutil.copy2(report_path, latest)
    print(report_path)
    for item in summary:
        print("n={level}: {median_seconds:.3f}s speedup={speedup:.3f} efficiency={efficiency:.3f}".format(**item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
