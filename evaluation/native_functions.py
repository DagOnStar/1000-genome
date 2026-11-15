"""Importable functions used to evaluate DAGonStar Native tasks."""

from __future__ import annotations

import json


def summarize(input_file: str, output_file: str) -> dict[str, int]:
    """Summarize a JSON mapping while exercising staged Native I/O."""
    with open(input_file, encoding="utf-8") as source:
        data = json.load(source)
    summary = {"keys": len(data), "values": sum(len(value) for value in data.values())}
    with open(output_file, "w", encoding="utf-8") as destination:
        json.dump(summary, destination, sort_keys=True)
        destination.write("\n")
    return summary
