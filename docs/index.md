# Documentation

This documentation describes both the scientific workflow and its execution
with DAGonStar.

- [Architecture](architecture.md): graph, stage responsibilities, and execution profiles.
- [Input and output schemas](schemas.md): manifest, VCF assumptions, and result contracts.
- [Evaluation](evaluation.md): test matrix, acceptance criteria, and remote execution.
- [Evaluation results](evaluation-results.md): latest recorded E4 Batch/Slurm run.

The implementation is intentionally split between pure streaming algorithms in
`genome_workflow/core.py` and DAG construction in `workflow.py`. This makes
scientific behavior unit-testable without a scheduler while preserving an
end-to-end DAGonStar evaluation path.
