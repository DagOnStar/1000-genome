# Input and output schemas

## Manifest

The manifest is a UTF-8 JSON object. Relative paths resolve from the manifest's
directory.

```json
{
  "chromosomes": [
    {
      "name": "1",
      "genotypes": "genotypes/ALL.chr1.vcf.gz",
      "annotations": "annotations/ALL.chr1.vep.vcf.gz"
    }
  ],
  "populations": {
    "ALL": "populations/ALL",
    "EUR": "populations/EUR"
  }
}
```

| Field | Type | Constraint |
|---|---|---|
| `chromosomes` | non-empty array | one object per independently processed chromosome |
| `chromosomes[].name` | string | letters, digits, `.`, `_`, or `-` |
| `genotypes` | path | readable VCF or VCF.GZ with a `#CHROM` sample header |
| `annotations` | path | readable VCF or VCF.GZ containing VEP-style SIFT text |
| `populations` | non-empty object | population name to whitespace-delimited sample file |

## Genotypes

The parser uses standard VCF columns and reads the genotype before the first
colon in each sample field. `carrier` includes any called non-reference allele;
`homozygous-alt` requires all called alleles to be non-reference. Records with a
missing ID (`.`) are ignored.

## SIFT annotations

An annotation record contributes when its ID begins with `rs` and its INFO
field contains `deleterious(score)`, `deleterious_low_confidence(score)`,
`tolerated(score)`, or `tolerated_low_confidence(score)`. The lowest score for
each identifier is retained. A score at or below `0.05` is deleterious.

## Published artifacts

`chr<chromosome>.<population>.overlap.csv`:

```csv
sample_a,sample_b,shared_deleterious_variants
HG00096,HG00097,2
```

Each unordered pair appears once.

`chr<chromosome>.<population>.frequency.json`:

```json
{
  "histogram": {"1": 61, "2": 39},
  "individuals": 4,
  "runs": 100,
  "seed": 42
}
```

`chr<chromosome>.<population>.summary.json`:

```json
{
  "frequency_runs": 100,
  "individuals": 4,
  "pairs": 6
}
```

## Evaluation report

`evaluation.json` has `schema_version: 1`, environment metadata, an ordered
`scenarios` array, Batch and optional Slurm artifact checks, timestamps, and a
top-level `passed` or `failed` status. Each executed scenario records command,
return code, duration, and a bounded output tail. `latest.json` is a copy of the
most recent report.
