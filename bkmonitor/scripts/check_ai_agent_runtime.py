"""检查可选 AI 运行时制品，不调用模型、业务服务或上报端点。"""

import argparse
import importlib
import importlib.metadata
import json

from packaging.version import Version


def check_runtime(required=False):
    result = {"available": True, "packages": {}}
    for distribution, module, minimum in (
        ("bkai-hermes-core", "hermes_core", "0.8.1"),
        ("bkai-otel-hermes", "bkai_otel_hermes", "1.3.0"),
    ):
        try:
            result["packages"][distribution] = importlib.metadata.version(distribution)
            if Version(result["packages"][distribution]) < Version(minimum):
                raise ImportError("Unsupported SDK interface version")
            imported = importlib.import_module(module)
            names = (
                ("HermesAgent", "AgentConfig", "HermesTool", "TelemetryConfig")
                if module == "hermes_core"
                else ("instrument_sdk",)
            )
            if not all(hasattr(imported, name) for name in names):
                raise ImportError("Missing SDK interface")
        except (ImportError, importlib.metadata.PackageNotFoundError):
            result["available"] = False
            result["packages"][distribution] = "unavailable"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if required and not result["available"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--required", action="store_true")
    raise SystemExit(check_runtime(parser.parse_args().required))
