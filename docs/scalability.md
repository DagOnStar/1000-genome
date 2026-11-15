# Scalability and speedup

## Workload

`evaluation/generate_scaling_fixture.py` creates a deterministic synthetic
chromosome with 12,000 variants and 400 samples. The genotype VCF is
19,624,655 bytes. Each benchmark run uses the same inputs, caps the overlap
analysis at 100 individuals, performs 500 seeded frequency draws, and verifies
the SHA-256 hashes of all published artifacts.

The benchmark varies `--individual-jobs` over 1, 2, 4, and 8. Each level is run
three times. Odd repeats run in ascending order and even repeats in descending
order to reduce systematic filesystem-cache bias. The reported time is the
median end-to-end wall time, including DAGonStar setup, task staging, merge,
analysis, and publication.

## Metrics

For fan-out level `n`:

```text
speedup(n)    = median_time(1) / median_time(n)
efficiency(n) = speedup(n) / n
```

This is a workflow fan-out experiment, not a CPU-core microbenchmark. The
current `individuals` implementation assigns records by modulo but every shard
still streams and parses the complete VCF before processing its subset. Merge,
SIFT, overlap, frequency, publication, and DAGonStar lifecycle costs are also
serial or fixed. Near-linear speedup is therefore not expected; the experiment
is designed to expose that limit.

## Acceptance criteria

- Every level and repeat must exit successfully.
- All result hashes must match the first run.
- The report must include host, logical CPU count, Python, fixture dimensions,
  raw repeat timings, medians, speedup, and efficiency.
- Runs from overlapping benchmark processes are invalid and must be repeated.

## Commands

```bash
python evaluation/scalability.py \
  --config /absolute/path/dagon.ini \
  --fixture /absolute/path/scaling-fixture \
  --output /absolute/path/scalability-results \
  --levels 1 2 4 8 --repeats 3
```

For a Slurm series, add `--executor slurm --partition <partition>`. Queue wait
is included in wall time, so do not compare a queued Slurm series directly to
an uncontended Batch series without reporting that context.

## Recorded results — 2026-11-15

Both hosts exposed 24 logical CPUs and ran Python 3.12.3. The Batch series was
uncontended at the process level: no overlapping benchmark driver was accepted
as evidence. Every one of the 24 measured workflow runs produced the same
overlap, frequency, and summary hashes.

| Host | Fan-out | Median seconds | Speedup | Efficiency |
|---|---:|---:|---:|---:|
| `sunbow` (`193.205.230.23`) | 1 | 10.903052 | 1.000000 | 1.000000 |
| `sunbow` | 2 | 10.321971 | 1.056296 | 0.528148 |
| `sunbow` | 4 | 10.030604 | 1.086979 | 0.271745 |
| `sunbow` | 8 | 9.916508 | 1.099485 | 0.137436 |
| `rainbow` (`193.205.230.76`) | 1 | 14.407092 | 1.000000 | 1.000000 |
| `rainbow` | 2 | 13.162856 | 1.094526 | 0.547263 |
| `rainbow` | 4 | 12.079398 | 1.192700 | 0.298175 |
| `rainbow` | 8 | 11.767113 | 1.224352 | 0.153044 |

The modest speedup and falling efficiency are consistent across both hosts.
They show that additional extraction tasks overlap some genotype processing,
but duplicated full-file scanning and fixed downstream work dominate by eight
tasks. A future optimization should partition byte ranges or pre-split VCF
records so each extraction task reads only its assigned data.

Machine-readable reports are retained on the hosts as:

```text
# sunbow
~/1000-genome-dagonstar-eval/evaluation/scalability/latest-batch.json

# rainbow (copied out of quota-safe runtime storage)
~/1000-genome-dagonstar-eval/rainbow-scalability.json
```
