"""Run bkai-init against an explicitly selected deployment space."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from check_package import check_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("action", choices=("validate", "plan", "show", "sync"))
    parser.add_argument("--space", default=os.environ.get("BKAI_SPACE_ID", ""))
    parser.add_argument("--tenant-id", default=os.environ.get("BKAI_TENANT_ID", ""))
    parser.add_argument("--resource", action="append", nargs="+", default=[])
    parser.add_argument("--exclude-resource", action="append", nargs="+", default=[])
    parser.add_argument("--var", action="append", default=[])
    parser.add_argument("--format", choices=("json", "yaml"))
    args = parser.parse_args(argv)
    if not args.space.strip():
        parser.error("set BKAI_SPACE_ID or pass --space explicitly")
    mode = os.environ.get("BKPAAS_MULTI_TENANT_MODE", "false").lower()
    if mode not in {"true", "false"}:
        parser.error("BKPAAS_MULTI_TENANT_MODE must be true or false")
    if mode == "true" and not args.tenant_id.strip():
        parser.error("multi-tenant mode requires BKAI_TENANT_ID or --tenant-id")
    package = Path(__file__).resolve().parents[1] / "package"
    errors = check_directory(package)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    command = [sys.executable, "-m", "bkai_init", args.action, "-f", str(package / "bkai.yaml"), "--space", args.space]
    if mode == "true":
        command += ["--tenant-id", args.tenant_id]
    if args.action == "sync":
        command.append("--confirm")
    for resources in args.resource:
        command += ["--resource", *resources]
    for resources in args.exclude_resource:
        command += ["--exclude-resource", *resources]
    for variable in args.var:
        command += ["--var", variable]
    if args.format:
        command += ["--format", args.format]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
