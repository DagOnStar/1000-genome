#!/usr/bin/env python3
"""Generate a deterministic synthetic VCF workload for scalability tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def generate(output: Path, variants: int, samples: int) -> dict[str, int]:
    """Create the fixture and return its stable size metadata."""
    if variants < 1 or samples < 2:
        raise ValueError("variants must be positive and samples must be at least two")
    output.mkdir(parents=True, exist_ok=True)
    sample_names = [f"S{index:05d}" for index in range(samples)]

    genotype_path = output / "genotypes.vcf"
    with genotype_path.open("w", encoding="utf-8") as handle:
        handle.write("##fileformat=VCFv4.2\n")
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t")
        handle.write("\t".join(sample_names) + "\n")
        for variant in range(variants):
            calls = []
            for sample in range(samples):
                value = (variant * 31 + sample * 17) % 211
                calls.append("1|1" if value == 0 else "0|1" if value < 13 else "0|0")
            handle.write(
                f"1\t{variant + 1}\trs{variant + 1}\tA\tG\t.\tPASS\tAF=0.1\tGT\t"
                + "\t".join(calls) + "\n"
            )

    annotation_path = output / "annotations.vcf"
    with annotation_path.open("w", encoding="utf-8") as handle:
        handle.write("##fileformat=VCFv4.2\n")
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for variant in range(variants):
            score = "0.01" if variant % 3 == 0 else "0.20"
            prediction = "deleterious" if variant % 3 == 0 else "tolerated"
            handle.write(
                f"1\t{variant + 1}\trs{variant + 1}\tA\tG\t.\tPASS\t"
                f"CSQ=G|missense_variant|MODERATE|GENE{variant % 97}|{prediction}({score})\n"
            )

    (output / "ALL").write_text("\n".join(sample_names) + "\n", encoding="utf-8")
    manifest = {
        "chromosomes": [{"name": "1", "genotypes": "genotypes.vcf", "annotations": "annotations.vcf"}],
        "populations": {"ALL": "ALL"},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    metadata = {"variants": variants, "samples": samples, "genotype_bytes": genotype_path.stat().st_size}
    (output / "fixture.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", type=int, default=12000)
    parser.add_argument("--samples", type=int, default=400)
    args = parser.parse_args()
    try:
        metadata = generate(args.output, args.variants, args.samples)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
