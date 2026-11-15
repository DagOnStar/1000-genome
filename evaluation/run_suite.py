#!/usr/bin/env python3
"""Run, validate, and report the DAGonStar workflow evaluation matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def wait_for_files(paths: list[Path], timeout: float = 30.0) -> None:
    """Wait for publish artifacts to become visible on distributed filesystems."""
    deadline = time.monotonic() + timeout
    missing = paths
    while missing and time.monotonic() < deadline:
        missing = [path for path in paths if not path.is_file() or not path.stat().st_size]
        if missing:
            time.sleep(0.25)
    if missing:
        raise AssertionError("missing result after %.1fs: %s" % (timeout, ", ".join(map(str, missing))))


def validate_results(output: Path) -> dict[str, object]:
    expected = {
        "chr1.ALL.summary.json": {"frequency_runs": 100, "individuals": 4, "pairs": 6},
        "chr1.EUR.summary.json": {"frequency_runs": 100, "individuals": 3, "pairs": 3},
    }
    artifact_names = list(expected) + [
        "chr1.ALL.overlap.csv", "chr1.EUR.overlap.csv",
        "chr1.ALL.frequency.json", "chr1.EUR.frequency.json",
    ]
    wait_for_files([output / name for name in artifact_names])
    checks: dict[str, object] = {}
    for filename, wanted in expected.items():
        path = output / filename
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != wanted:
            raise AssertionError(f"{filename}: expected {wanted}, got {actual}")
        checks[filename] = {"sha256": digest(path), "content": actual}
    for filename in ("chr1.ALL.overlap.csv", "chr1.EUR.overlap.csv", "chr1.ALL.frequency.json", "chr1.EUR.frequency.json"):
        path = output / filename
        checks[filename] = {"sha256": digest(path), "bytes": path.stat().st_size}
    return checks


def run(name: str, command: list[str], cwd: Path = ROOT) -> dict[str, object]:
    started = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    result: dict[str, object] = {
        "name": name,
        "command": command,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "seconds": round(elapsed, 3),
        "output_tail": completed.stdout[-8000:],
    }
    if completed.returncode:
        raise RuntimeError(json.dumps(result, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results")
    parser.add_argument("--partition", help="also run the real Slurm workflow")
    parser.add_argument("--docker", action="store_true", help="also execute a real Docker task")
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output.resolve() / f"{socket.gethostname()}-{timestamp}"
    run_dir.mkdir(parents=True)
    report: dict[str, object] = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "hostname": socket.gethostname(), "platform": platform.platform(),
            "python": sys.version, "executable": sys.executable,
        },
        "scenarios": [],
    }
    scenarios: list[dict[str, object]] = report["scenarios"]  # type: ignore[assignment]
    try:
        scenarios.append(run("unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
        scenarios.append(run("dry-run", [
            sys.executable, "workflow.py", "--manifest", "examples/demo/manifest.json",
            "--individual-jobs", "2", "--dry-run",
        ]))
        task_output = run_dir / "task-types"
        command = [
            sys.executable, "evaluation/task_type_smoke.py", "--config", str(args.config.resolve()),
            "--output", str(task_output),
        ]
        if args.docker:
            command.append("--docker")
        scenarios.append(run("task-types", command))

        batch_output = run_dir / "batch"
        scenarios.append(run("batch-workflow", [
            sys.executable, "workflow.py", "--config", str(args.config.resolve()),
            "--manifest", "examples/demo/manifest.json", "--individual-jobs", "2",
            "--frequency-runs", "100", "--seed", "42", "--output", str(batch_output),
        ]))
        report["batch_checks"] = validate_results(batch_output)

        if args.partition:
            slurm_output = run_dir / "slurm"
            scenarios.append(run("slurm-workflow", [
                sys.executable, "workflow.py", "--config", str(args.config.resolve()),
                "--manifest", "examples/demo/manifest.json", "--individual-jobs", "2",
                "--frequency-runs", "100", "--seed", "42", "--output", str(slurm_output),
                "--executor", "slurm", "--partition", args.partition, "--pre-stage",
            ]))
            report["slurm_checks"] = validate_results(slurm_output)
            report["batch_slurm_equal"] = all(
                digest(batch_output / name) == digest(slurm_output / name)
                for name in ("chr1.ALL.overlap.csv", "chr1.EUR.overlap.csv", "chr1.ALL.frequency.json", "chr1.EUR.frequency.json")
            )
            if not report["batch_slurm_equal"]:
                raise AssertionError("batch and Slurm scientific outputs differ")
        else:
            scenarios.append({"name": "slurm-workflow", "status": "skipped", "reason": "no --partition supplied"})
        report["status"] = "passed"
        return_code = 0
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        return_code = 1
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report_path = run_dir / "evaluation.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        latest = args.output.resolve() / "latest.json"
        shutil.copy2(report_path, latest)
        print(report_path)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
