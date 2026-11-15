# Repository agent guide

## Scope

This repository implements the 1000 Genomes mutational-overlap benchmark as a
DAGonStar workflow. Preserve the scientific stages and their dependency model:

1. shard genotype VCF records across `individuals` tasks;
2. merge per-sample variant sets;
3. extract numeric SIFT annotations independently;
4. calculate population-specific deleterious overlap and null frequencies;
5. publish deterministic CSV/JSON artifacts.

## Engineering rules

- Support Python 3.10 or newer.
- Keep task algorithms in `genome_workflow/core.py` independent of DAGonStar.
- Keep DAG construction in `workflow.py`; infer dependencies with
  `workflow://` references rather than manually ordering tasks.
- Stream VCF and VCF.GZ inputs. Do not load a production VCF into memory.
- Keep fixture data synthetic, tiny, and free of personal or controlled data.
- Never commit credentials, private SSH keys, host-specific `dagon.ini` files,
  scratch directories, or evaluation result directories.
- Pin DAGonStar to a reviewed commit in `requirements.txt`.
- Prefer current task APIs (`TaskType.NATIVE`, `TaskType.WEB`, scheduler-aware
  `TaskType.SLURM`) when they fit; do not introduce an external service merely
  to demonstrate a task type.

## Required verification

Run before committing:

```bash
python -m unittest discover -s tests -v
python -m compileall -q genome_workflow evaluation workflow.py
python workflow.py --manifest examples/demo/manifest.json --individual-jobs 2 --dry-run
git diff --check
```

For execution changes, also run the local evaluation:

```bash
python evaluation/run_suite.py --config dagon.ini
```

On a Slurm system, add `--partition <partition>`. The suite must verify that
local Batch and Slurm results are byte-identical for deterministic artifacts.

## Documentation

Update `README.md` and the relevant file under `docs/` when task topology,
manifest fields, result schemas, execution profiles, or evaluation behavior
changes. Keep diagrams source-controlled as SVG or Mermaid-compatible text.

The main README must retain both:

- the scientific workflow graph (`docs/images/workflow.svg`); and
- the latest measured performance table and chart
  (`docs/images/performance.svg`).

Performance values must come from a completed machine-readable evaluation
report. Keep the host, date, runtime versions, fixture scale, and limitations
beside the numbers; never present fixture timings as production benchmarks.
When results change, update `README.md`, `docs/evaluation-results.md`, and the
performance chart together so they describe the same run.

Scalability claims must use `evaluation/scalability.py`, at least three repeats
per fan-out level, median wall time, and identical scientific output hashes.
Record the baseline, speedup formula, efficiency, host CPU count, workload
dimensions, and whether other benchmark processes overlapped. Update
`docs/scalability.md` and its README table/chart together. Never call task
fan-out a core count unless each task is explicitly allocated one exclusive
core by the executor.
