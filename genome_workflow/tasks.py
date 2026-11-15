"""Command-line entry points executed inside DAGonStar task sandboxes."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from .core import extract_individuals, extract_sift, frequency_distribution, merge_individuals, mutation_overlap


def _limit(value: int) -> int | None:
    return value or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    individuals = commands.add_parser("individuals")
    individuals.add_argument("--vcf", required=True)
    individuals.add_argument("--output", required=True)
    individuals.add_argument("--chunk-index", type=int, required=True)
    individuals.add_argument("--chunk-count", type=int, required=True)
    individuals.add_argument("--genotype-mode", choices=("carrier", "homozygous-alt"), default="carrier")
    merge = commands.add_parser("merge")
    merge.add_argument("--input", action="append", required=True)
    merge.add_argument("--output", required=True)
    sift = commands.add_parser("sift")
    sift.add_argument("--vcf", required=True)
    sift.add_argument("--output", required=True)
    overlap = commands.add_parser("overlap")
    overlap.add_argument("--individuals", required=True)
    overlap.add_argument("--sift", required=True)
    overlap.add_argument("--population", required=True)
    overlap.add_argument("--output", required=True)
    overlap.add_argument("--max-individuals", type=int, default=0)
    frequency = commands.add_parser("frequency")
    frequency.add_argument("--individuals", required=True)
    frequency.add_argument("--population", required=True)
    frequency.add_argument("--output", required=True)
    frequency.add_argument("--runs", type=int, default=1000)
    frequency.add_argument("--seed", type=int, default=42)
    frequency.add_argument("--max-individuals", type=int, default=0)
    publish = commands.add_parser("publish")
    publish.add_argument("--overlap", required=True)
    publish.add_argument("--frequency", required=True)
    publish.add_argument("--output-dir", required=True)
    publish.add_argument("--prefix", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "individuals":
        stats = extract_individuals(args.vcf, args.output, args.chunk_index, args.chunk_count, args.genotype_mode)
    elif args.command == "merge":
        stats = merge_individuals(args.input, args.output)
    elif args.command == "sift":
        stats = extract_sift(args.vcf, args.output)
    elif args.command == "overlap":
        stats = mutation_overlap(args.individuals, args.sift, args.population, args.output, _limit(args.max_individuals))
    elif args.command == "frequency":
        stats = frequency_distribution(
            args.individuals, args.population, args.output, args.runs, args.seed, _limit(args.max_individuals)
        )
    else:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        overlap_target = output_dir / f"{args.prefix}.overlap.csv"
        frequency_target = output_dir / f"{args.prefix}.frequency.json"
        shutil.copyfile(args.overlap, overlap_target)
        shutil.copyfile(args.frequency, frequency_target)
        with overlap_target.open(newline="", encoding="utf-8") as handle:
            pairs = max(sum(1 for _ in csv.reader(handle)) - 1, 0)
        frequency_data = json.loads(frequency_target.read_text(encoding="utf-8"))
        stats = {"pairs": pairs, "frequency_runs": frequency_data["runs"], "individuals": frequency_data["individuals"]}
        (output_dir / f"{args.prefix}.summary.json").write_text(
            json.dumps(stats, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    Path("task-stats.json").write_text(json.dumps(stats, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
