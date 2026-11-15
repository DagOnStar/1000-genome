#!/usr/bin/env python3
"""Build and run the 1000 Genomes DAG with DAGonStar."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--output", type=Path, default=Path("output"))
    result.add_argument("--individual-jobs", type=int, default=2)
    result.add_argument("--frequency-runs", type=int, default=1000)
    result.add_argument("--seed", type=int, default=42)
    result.add_argument("--max-individuals", type=int, default=0)
    result.add_argument("--genotype-mode", choices=("carrier", "homozygous-alt"), default="carrier")
    result.add_argument("--config", type=Path, default=Path("dagon.ini"))
    result.add_argument("--dry-run", action="store_true")
    return result


def load_manifest(filename: Path) -> dict[str, Any]:
    filename = filename.resolve()
    data = json.loads(filename.read_text(encoding="utf-8"))
    if not isinstance(data.get("chromosomes"), list) or not data["chromosomes"]:
        raise ValueError("manifest.chromosomes must be a non-empty list")
    if not isinstance(data.get("populations"), dict) or not data["populations"]:
        raise ValueError("manifest.populations must be a non-empty object")
    base = filename.parent
    for chromosome in data["chromosomes"]:
        for key in ("name", "genotypes", "annotations"):
            if key not in chromosome:
                raise ValueError(f"chromosome entry is missing {key!r}")
        if not SAFE_NAME.fullmatch(str(chromosome["name"])):
            raise ValueError(f"unsafe chromosome name: {chromosome['name']!r}")
        for key in ("genotypes", "annotations"):
            path = (base / chromosome[key]).resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            chromosome[key] = path
    for name, value in list(data["populations"].items()):
        if not SAFE_NAME.fullmatch(str(name)):
            raise ValueError(f"unsafe population name: {name!r}")
        path = (base / value).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        data["populations"][name] = path
    return data


def task_command(*arguments: object) -> str:
    prefix = f"PYTHONPATH={shlex.quote(str(ROOT))} {shlex.quote(sys.executable)} -m genome_workflow.tasks"
    return prefix + " " + " ".join(shlex.quote(str(argument)) for argument in arguments)


def reference(task: str, filename: str) -> str:
    return f"workflow:///{task}/{filename}"


def describe(data: dict[str, Any], jobs: int) -> list[str]:
    lines: list[str] = []
    for chromosome in data["chromosomes"]:
        chrom = chromosome["name"]
        chunks = [f"chr{chrom}-individuals-{index}" for index in range(jobs)]
        lines.extend(f"{chunk} -> chr{chrom}-individuals-merge" for chunk in chunks)
        lines.append(f"chr{chrom}-sifting -> chr{chrom}-analysis")
        lines.append(f"chr{chrom}-individuals-merge -> chr{chrom}-analysis")
        for population in data["populations"]:
            lines.append(f"chr{chrom}-analysis[{population}] -> chr{chrom}-{population}-publish")
    return lines


def build_workflow(data: dict[str, Any], args: argparse.Namespace):
    from dagon import Workflow
    from dagon.task import DagonTask, TaskType

    config = args.config.resolve() if args.config.is_file() else ROOT / "dagon.ini.sample"
    workflow = Workflow("1000-genomes", config_file=str(config))
    output_dir = args.output.resolve()
    for chromosome in data["chromosomes"]:
        chrom = str(chromosome["name"])
        chunk_tasks: list[str] = []
        for index in range(args.individual_jobs):
            name = f"chr{chrom}-individuals-{index}"
            chunk_tasks.append(name)
            command = task_command(
                "individuals", "--vcf", chromosome["genotypes"], "--output", "individuals.json",
                "--chunk-index", index, "--chunk-count", args.individual_jobs,
                "--genotype-mode", args.genotype_mode,
            )
            workflow.add_task(DagonTask(TaskType.BATCH, name, command))

        merge_name = f"chr{chrom}-individuals-merge"
        merge_args: list[object] = ["merge"]
        for name in chunk_tasks:
            merge_args.extend(("--input", reference(name, "individuals.json")))
        merge_args.extend(("--output", "individuals.json"))
        workflow.add_task(DagonTask(TaskType.BATCH, merge_name, task_command(*merge_args)))

        sift_name = f"chr{chrom}-sifting"
        workflow.add_task(DagonTask(TaskType.BATCH, sift_name, task_command(
            "sift", "--vcf", chromosome["annotations"], "--output", "sift.json"
        )))

        for population, population_path in data["populations"].items():
            stem = f"chr{chrom}-{population}"
            overlap_name = f"{stem}-overlap"
            frequency_name = f"{stem}-frequency"
            common = (
                "--individuals", reference(merge_name, "individuals.json"),
                "--population", population_path, "--max-individuals", args.max_individuals,
            )
            workflow.add_task(DagonTask(TaskType.BATCH, overlap_name, task_command(
                "overlap", *common, "--sift", reference(sift_name, "sift.json"), "--output", "overlap.csv"
            )))
            workflow.add_task(DagonTask(TaskType.BATCH, frequency_name, task_command(
                "frequency", *common, "--runs", args.frequency_runs, "--seed", args.seed,
                "--output", "frequency.json"
            )))
            publish_name = f"{stem}-publish"
            workflow.add_task(DagonTask(TaskType.BATCH, publish_name, task_command(
                "publish", "--overlap", reference(overlap_name, "overlap.csv"),
                "--frequency", reference(frequency_name, "frequency.json"),
                "--output-dir", output_dir, "--prefix", f"chr{chrom}.{population}",
            )))
    workflow.make_dependencies()
    return workflow


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.individual_jobs < 1 or args.frequency_runs < 1 or args.max_individuals < 0:
        raise SystemExit("job and run counts must be positive; max-individuals cannot be negative")
    try:
        data = load_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid manifest: {error}") from error
    if args.dry_run:
        print("1000-genomes DAG")
        print("\n".join(describe(data, args.individual_jobs)))
        return 0
    workflow = build_workflow(data, args)
    workflow.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
