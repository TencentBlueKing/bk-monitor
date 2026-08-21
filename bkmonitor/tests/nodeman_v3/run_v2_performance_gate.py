import argparse
import ast
import json
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path


WORKER = r"""
import json
import sys
import time
from types import SimpleNamespace

import django

django.setup()

import requests
from celery import current_app
from django.db.backends.utils import CursorWrapper
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.plugin.constant import PluginType


def forbidden(name):
    def fail(*args, **kwargs):
        raise AssertionError(f"V2 factory benchmark performed forbidden {name}")
    return fail


CursorWrapper.execute = forbidden("SQL")
CursorWrapper.executemany = forbidden("SQL")
requests.sessions.Session.request = forbidden("remote request")
current_app.send_task = forbidden("Celery send")


class DummyInstaller:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


get_collect_installer.__globals__["NodeManInstaller"] = DummyInstaller
get_collect_installer.__globals__["K8sInstaller"] = DummyInstaller
configs = {
    "node_man": SimpleNamespace(plugin=SimpleNamespace(plugin_type="Script")),
    "k8s": SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.K8S)),
}
v3_modules = sorted(
    name
    for name in sys.modules
    if name.startswith("bkmonitor.nodeman_integration.v3")
    or name.startswith("monitor_web.collecting.deploy.nodeman_v3")
    or name.startswith("monitor_web.nodeman_integration.v3")
)
print("V2_PERF_READY=" + json.dumps({"v3_modules": v3_modules}), flush=True)

for line in sys.stdin:
    request = json.loads(line)
    if request.get("command") == "stop":
        break
    collect_config = configs[request["scenario"]]
    started = time.perf_counter_ns()
    for _ in range(request["iterations"]):
        get_collect_installer(collect_config)
    elapsed = time.perf_counter_ns() - started
    print("V2_PERF_RESULT=" + json.dumps({"elapsed_ns": elapsed}), flush=True)
"""


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def relative_difference(current, baseline):
    return (current - baseline) / baseline


def bootstrap_upper(left, right, metric, *, samples=1000, seed=20260821, absolute=False):
    generator = random.Random(seed)
    values = []
    for _ in range(samples):
        indexes = [generator.randrange(len(left)) for _ in left]
        left_metric = percentile([left[index] for index in indexes], metric)
        right_metric = percentile([right[index] for index in indexes], metric)
        difference = relative_difference(right_metric, left_metric)
        values.append(abs(difference) if absolute else difference)
    return percentile(values, 0.975)


def factory_ast(root):
    path = root / "packages/monitor_web/collecting/deploy/__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "get_collect_installer"
    ]
    if not functions:
        raise RuntimeError(f"get_collect_installer not found in {path}")
    function = functions[0]
    body = function.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    normalized = ast.FunctionDef(
        name=function.name,
        args=function.args,
        body=body,
        decorator_list=function.decorator_list,
        returns=function.returns,
        type_comment=function.type_comment,
    )
    return ast.dump(normalized, annotate_fields=True, include_attributes=False)


class Worker:
    def __init__(self, root, python, database):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "settings",
                "DJANGO_CONF_MODULE": "config.web.development.community",
                "BKAPP_DEPLOY_PLATFORM": "community",
                "USE_DYNAMIC_SETTINGS": "0",
                "BK_MONITOR_APP_CODE": "bk_monitorv3",
                "BK_MONITOR_APP_SECRET": "secret",
                "BKAPP_NODEMAN_INTEGRATION_MODE": "v2",
                "BKM_UNITTEST": "1",
                "BKM_TEST_DB": database,
            }
        )
        self.process = subprocess.Popen(
            [str(python), "-u", "-c", WORKER],
            cwd=root,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        ready = self._read("V2_PERF_READY=")
        self.v3_modules = ready["v3_modules"]

    def _read(self, prefix):
        output = []
        while True:
            line = self.process.stdout.readline()
            if not line:
                detail = "".join(output[-20:])
                raise RuntimeError(f"benchmark worker exited with code {self.process.poll()}:\n{detail}")
            output.append(line)
            if line.startswith(prefix):
                return json.loads(line.removeprefix(prefix))

    def sample(self, scenario, iterations):
        request = {"scenario": scenario, "iterations": iterations}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        return self._read("V2_PERF_RESULT=")["elapsed_ns"] / iterations

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write(json.dumps({"command": "stop"}) + "\n")
            self.process.stdin.flush()
            self.process.wait(timeout=10)


def run_scenario(baseline, current, scenario, *, warmup, samples, iterations):
    for index in range(warmup):
        workers = (baseline, current) if index % 2 == 0 else (current, baseline)
        for worker in workers:
            worker.sample(scenario, iterations)

    baseline_first = []
    baseline_second = []
    current_values = []
    for index in range(samples):
        if index % 2 == 0:
            baseline_first.append(baseline.sample(scenario, iterations))
            current_values.append(current.sample(scenario, iterations))
            baseline_second.append(baseline.sample(scenario, iterations))
        else:
            baseline_second.append(baseline.sample(scenario, iterations))
            current_values.append(current.sample(scenario, iterations))
            baseline_first.append(baseline.sample(scenario, iterations))

    baseline_reference = [statistics.fmean(pair) for pair in zip(baseline_first, baseline_second, strict=True)]
    metrics = {}
    passed = True
    for name, fraction in (("p50", 0.5), ("p95", 0.95)):
        baseline_value = percentile(baseline_reference, fraction)
        current_value = percentile(current_values, fraction)
        noise_upper = bootstrap_upper(
            baseline_first,
            baseline_second,
            fraction,
            absolute=True,
        )
        regression_upper = bootstrap_upper(baseline_reference, current_values, fraction)
        threshold = max(noise_upper, 0.01)
        metric_passed = regression_upper <= threshold
        passed = passed and metric_passed
        metrics[name] = {
            "baseline_ns_per_call": baseline_value,
            "current_ns_per_call": current_value,
            "observed_difference_percent": relative_difference(current_value, baseline_value) * 100,
            "baseline_noise_upper_percent": noise_upper * 100,
            "regression_ci_upper_percent": regression_upper * 100,
            "threshold_percent": threshold * 100,
            "passed": metric_passed,
        }
    return {"metrics": metrics, "passed": passed}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the NodeMan V2 zero-regression performance gate")
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--database", default="bkm_unittest_agent_contract")
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--iterations", type=int, default=10000)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.warmup < 10 or args.samples < 100:
        raise ValueError("performance gate requires warmup >= 10 and samples >= 100")
    exact_gates = {
        "factory_ast_equal": factory_ast(args.baseline_root) == factory_ast(args.current_root),
        "sql_during_benchmark": 0,
        "remote_requests_during_benchmark": 0,
        "celery_messages_during_benchmark": 0,
    }
    baseline = Worker(args.baseline_root, args.python, args.database)
    current = Worker(args.current_root, args.python, args.database)
    try:
        exact_gates["baseline_v3_modules"] = baseline.v3_modules
        exact_gates["current_v3_modules"] = current.v3_modules
        scenarios = {
            scenario: run_scenario(
                baseline,
                current,
                scenario,
                warmup=args.warmup,
                samples=args.samples,
                iterations=args.iterations,
            )
            for scenario in ("node_man", "k8s")
        }
    finally:
        baseline.close()
        current.close()
    exact_passed = exact_gates["factory_ast_equal"] and not baseline.v3_modules and not current.v3_modules
    result = {
        "method": {
            "baseline_root": str(args.baseline_root.resolve()),
            "current_root": str(args.current_root.resolve()),
            "python": str(args.python.resolve()),
            "warmup": args.warmup,
            "samples": args.samples,
            "iterations_per_sample": args.iterations,
            "confidence": 0.95,
            "execution": "alternating baseline/current with paired baseline repeats",
        },
        "exact_gates": exact_gates,
        "scenarios": scenarios,
        "passed": exact_passed and all(scenario["passed"] for scenario in scenarios.values()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
