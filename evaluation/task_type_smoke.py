#!/usr/bin/env python3
"""Execute credential-free smoke tests for modern DAGonStar task types."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dagon import Workflow
from dagon.task import DagonTask, TaskType


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"received_bytes": len(body)}).encode("utf-8"))

    def log_message(self, *_: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        workflow = Workflow("task-type-smoke", config_file=args.config)
        workflow.add_task(DagonTask(
            TaskType.BATCH,
            "batch-producer",
            "mkdir -p outputs; printf '{\"A\":[1,2],\"B\":[3]}' > outputs/data.json",
        ))
        workflow.add_task(DagonTask(
            TaskType.NATIVE,
            "native-summary",
            "evaluation.native_functions:summarize",
            inputs={"input_file": "workflow:///batch-producer/outputs/data.json"},
            outputs={"output_file": "summary.json"},
            python=sys.executable,
        ))
        workflow.add_task(DagonTask(
            TaskType.WEB,
            "web-report",
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{server.server_port}/report",
                "json": {"summary": {"json_file": "workflow:///native-summary/outputs/summary.json"}},
                "outputs": {"body": "response.json", "metadata": "request.json"},
            },
        ))
        workflow.run()
        native = workflow.find_task_by_name(workflow.name, "native-summary")
        web = workflow.find_task_by_name(workflow.name, "web-report")
        shutil.copy2(Path(native.working_dir, "outputs", "summary.json"), args.output / "native-summary.json")
        shutil.copy2(Path(web.working_dir, "outputs", "response.json"), args.output / "web-response.json")
    finally:
        server.shutdown()

    report: dict[str, object] = {"batch": "passed", "native": "passed", "web": "passed", "docker": "skipped"}
    if args.docker:
        docker_workflow = Workflow("docker-smoke", config_file=args.config)
        docker_workflow.add_task(DagonTask(
            TaskType.DOCKER, "docker-python", "python --version > docker-python.txt",
            image="python:3.11-slim", pull=True, remove=True,
        ))
        docker_workflow.run()
        task = docker_workflow.find_task_by_name(docker_workflow.name, "docker-python")
        if task.status.name != "FINISHED":
            raise RuntimeError(f"Docker task ended in {task.status.name}")
        shutil.copy2(Path(task.working_dir, "docker-python.txt"), args.output / "docker-python.txt")
        report["docker"] = "passed"
    (args.output / "task-types.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
