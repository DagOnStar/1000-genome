# 1000 Genomes on DAGonStar

A local, reproducible DAGonStar implementation of the classic
[1000 Genomes mutational-overlap workflow](https://github.com/pegasus-isi/1000genome-workflow).
It builds this graph for every chromosome and population:

```text
individuals-0 \
individuals-1  +--> individuals-merge --+--> mutation-overlap --> publish
...          /                           +--> frequency --------/
annotations ---------> sifting ---------+
```

The `individuals` stage is a configurable fan-out. DAGonStar discovers all
edges from the `workflow:///task/output` references in task commands and runs
independent branches concurrently.

## Requirements

- Python 3.10+
- A POSIX shell
- DAGonStar (installed by `requirements.txt`)

No scientific Python stack is required; the analysis tasks use the standard
library and stream VCF/VCF.GZ input.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp dagon.ini.sample dagon.ini
python workflow.py --manifest examples/demo/manifest.json --output output
```

The small checked-in fixture finishes in seconds. Results appear in `output/`:

- `chr1.ALL.overlap.csv`: pairwise shared deleterious variants;
- `chr1.ALL.frequency.json`: deterministic random-pair null distribution;
- `chr1.ALL.summary.json`: run metadata and aggregate counts.

DAGonStar task scratch directories are under `.dagon-scratch/`. Set
`remove_dir=True` in `dagon.ini` after debugging if they should be removed.

## Run real data

Create a JSON manifest (paths are resolved relative to the manifest):

```json
{
  "chromosomes": [
    {
      "name": "1",
      "genotypes": "data/ALL.chr1.vcf.gz",
      "annotations": "data/ALL.chr1.vep.vcf.gz"
    }
  ],
  "populations": {
    "ALL": "populations/ALL",
    "EUR": "populations/EUR"
  }
}
```

Population files contain one sample ID per line (whitespace is accepted).
Genotype VCF samples come from the `#CHROM` header. The annotation VCF should
contain VEP-style `CSQ` entries with SIFT predictions such as
`deleterious(0.01)` or `tolerated(0.42)`. Records without an `rs` identifier or
a numeric SIFT score are ignored.

```bash
python workflow.py \
  --manifest manifest.json \
  --individual-jobs 8 \
  --frequency-runs 10000 \
  --seed 42 \
  --output output
```

Useful options:

- `--genotype-mode carrier` includes any non-reference called allele;
- `--genotype-mode homozygous-alt` includes only homozygous alternate calls;
- `--max-individuals N` caps each population deterministically for smoke tests;
- `--dry-run` validates and prints the DAG without executing it.

Input paths and the publication directory must be visible on the execution
host. The current profile uses local `BATCH` tasks; the task graph and commands
can be switched to another DAGonStar task backend without changing the data
formats.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q genome_workflow workflow.py
```

The task CLI can also be run directly with `python -m genome_workflow.tasks
--help`, which makes individual stages easy to test outside DAGonStar.

## Provenance

The graph follows the public Pegasus 1000 Genomes benchmark workflow. The
implementation here is original Python 3 code and uses DAGonStar's documented
Python task API and `workflow://` data references.
