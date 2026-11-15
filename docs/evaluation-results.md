# Recorded evaluation results

## E4 cluster — 2026-11-15

The suite was executed through SSH on `montella@193.205.230.3`. The login host
reported itself as `fesrv.e4.cluster`, running Linux 4.18 and Python 3.11.7.
DAGonStar 2.9.4 was installed from the commit pinned in `requirements.txt` in
an isolated virtual environment. Slurm 23.11.3 used the `debug` partition and
scheduler-aware pre-staging.

| Scenario | Result | Duration |
|---|---:|---:|
| unit suite | passed | 0.191 s |
| DAG dry-run | passed | 0.059 s |
| Batch → Native → Web task types | passed | 9.652 s |
| complete Batch workflow | passed | 10.773 s |
| complete Slurm workflow | passed | 19.867 s |
| Batch/Slurm deterministic comparison | identical | — |

The Batch and Slurm SHA-256 values matched for all deterministic overlap and
frequency artifacts. Expected summaries were also identical:

| Population | Individuals | Pairs | Frequency runs |
|---|---:|---:|---:|
| ALL | 4 | 6 | 100 |
| EUR | 3 | 3 | 100 |

The host exposes Docker 26.1.3 but the account does not have daemon access, so
the optional live Docker task was skipped. Docker remains represented in the
suite as an opt-in task type and can be enabled with `--docker` on an authorized
runner.

During the first Slurm attempt, the evaluator observed that successful publish
tasks could precede NFS metadata visibility on the login host. The artifacts
became visible shortly afterward. The suite now includes a bounded 30-second
visibility wait; the repeated full evaluation passed. This is recorded as an
evaluation-harness correction, not as a scientific result difference.

The full machine-readable report remains on the evaluation host at:

```text
~/1000-genome-dagonstar-eval/evaluation/results/
fesrv.e4.cluster-20261115T211039Z/evaluation.json
```

Result reports are intentionally not committed because they contain absolute
host paths and runtime details. This page preserves the stable, reviewable
summary.
