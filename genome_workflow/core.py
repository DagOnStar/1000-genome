"""Streaming parsers and analysis functions used by workflow tasks."""

from __future__ import annotations

import csv
import gzip
import json
import random
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Iterable, TextIO


def open_text(path: str | Path) -> TextIO:
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def atomic_json(path: str | Path, value: object) -> None:
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    temporary.replace(target)


def population_ids(path: str | Path) -> list[str]:
    with open_text(path) as handle:
        return [item for line in handle for item in line.split() if not item.startswith("#")]


def _called_alt(genotype: str, mode: str) -> bool:
    call = genotype.split(":", 1)[0].replace("|", "/")
    alleles = call.split("/")
    called = [allele for allele in alleles if allele != "."]
    if not called:
        return False
    if mode == "homozygous-alt":
        return len(called) == len(alleles) and all(allele != "0" for allele in called)
    return any(allele != "0" for allele in called)


def extract_individuals(
    vcf: str | Path,
    output: str | Path,
    chunk_index: int,
    chunk_count: int,
    genotype_mode: str,
) -> dict[str, int]:
    """Write one VCF shard as a JSON mapping of samples to variant IDs."""
    if chunk_count < 1 or not 0 <= chunk_index < chunk_count:
        raise ValueError("chunk index must be in [0, chunk count)")
    samples: list[str] = []
    mutations: dict[str, list[str]] = {}
    variant_index = 0
    selected = 0
    with open_text(vcf) as handle:
        for line in handle:
            if line.startswith("#CHROM"):
                samples = line.rstrip("\n").split("\t")[9:]
                mutations = {sample: [] for sample in samples}
                continue
            if line.startswith("#"):
                continue
            if not samples:
                raise ValueError(f"{vcf}: missing #CHROM header")
            fields = line.rstrip("\n").split("\t")
            current = variant_index
            variant_index += 1
            if current % chunk_count != chunk_index or len(fields) < 10:
                continue
            variant_id = fields[2]
            if not variant_id or variant_id == ".":
                continue
            selected += 1
            for sample, call in zip(samples, fields[9:]):
                if _called_alt(call, genotype_mode):
                    mutations[sample].append(variant_id)
    atomic_json(output, {sample: sorted(set(ids)) for sample, ids in mutations.items()})
    return {"samples": len(samples), "variants_seen": variant_index, "variants_selected": selected}


def merge_individuals(inputs: Iterable[str | Path], output: str | Path) -> dict[str, int]:
    merged: dict[str, set[str]] = {}
    chunks = 0
    for filename in inputs:
        with open(filename, encoding="utf-8") as handle:
            chunk = json.load(handle)
        chunks += 1
        for sample, variants in chunk.items():
            merged.setdefault(sample, set()).update(variants)
    atomic_json(output, {sample: sorted(variants) for sample, variants in sorted(merged.items())})
    return {"chunks": chunks, "samples": len(merged)}


_SIFT = re.compile(r"(?:deleterious|tolerated)(?:_low_confidence)?\((-?(?:\d+(?:\.\d*)?|\.\d+))\)", re.I)


def extract_sift(vcf: str | Path, output: str | Path) -> dict[str, int]:
    """Extract the lowest numeric SIFT score for every rs identifier."""
    scores: dict[str, float] = {}
    records = 0
    with open_text(vcf) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                continue
            ids = [item for item in fields[2].split(";") if item.lower().startswith("rs")]
            matches = [float(value) for value in _SIFT.findall(fields[7])]
            if not ids or not matches:
                continue
            records += 1
            score = min(matches)
            for variant_id in ids:
                scores[variant_id] = min(score, scores.get(variant_id, score))
    atomic_json(output, scores)
    return {"records": records, "variants": len(scores)}


def load_analysis_inputs(
    individuals_path: str | Path,
    sift_path: str | Path,
    population_path: str | Path,
    max_individuals: int | None,
) -> tuple[list[str], dict[str, set[str]], dict[str, float]]:
    with open(individuals_path, encoding="utf-8") as handle:
        raw_individuals = json.load(handle)
    with open(sift_path, encoding="utf-8") as handle:
        scores = {key: float(value) for key, value in json.load(handle).items()}
    requested = population_ids(population_path)
    ids = [sample for sample in requested if sample in raw_individuals]
    if max_individuals is not None:
        ids = ids[:max_individuals]
    deleterious = {variant for variant, score in scores.items() if score <= 0.05}
    variants = {sample: set(raw_individuals[sample]) & deleterious for sample in ids}
    return ids, variants, scores


def mutation_overlap(
    individuals_path: str | Path,
    sift_path: str | Path,
    population_path: str | Path,
    output: str | Path,
    max_individuals: int | None = None,
) -> dict[str, int]:
    ids, variants, _ = load_analysis_inputs(individuals_path, sift_path, population_path, max_individuals)
    pairs = 0
    with Path(output).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_a", "sample_b", "shared_deleterious_variants"])
        for sample_a, sample_b in combinations(ids, 2):
            writer.writerow([sample_a, sample_b, len(variants[sample_a] & variants[sample_b])])
            pairs += 1
    return {"individuals": len(ids), "pairs": pairs}


def frequency_distribution(
    individuals_path: str | Path,
    population_path: str | Path,
    output: str | Path,
    runs: int,
    seed: int,
    max_individuals: int | None = None,
) -> dict[str, int]:
    if runs < 1:
        raise ValueError("runs must be positive")
    with open(individuals_path, encoding="utf-8") as handle:
        raw = json.load(handle)
    ids = [sample for sample in population_ids(population_path) if sample in raw]
    if max_individuals is not None:
        ids = ids[:max_individuals]
    variants = {sample: set(raw[sample]) for sample in ids}
    rng = random.Random(seed)
    histogram: Counter[int] = Counter()
    if len(ids) >= 2:
        for _ in range(runs):
            sample_a, sample_b = rng.sample(ids, 2)
            histogram[len(variants[sample_a] & variants[sample_b])] += 1
    actual_runs = runs if len(ids) >= 2 else 0
    atomic_json(output, {
        "individuals": len(ids),
        "runs": actual_runs,
        "seed": seed,
        "histogram": {str(key): value for key, value in sorted(histogram.items())},
    })
    return {"individuals": len(ids), "runs": actual_runs}
