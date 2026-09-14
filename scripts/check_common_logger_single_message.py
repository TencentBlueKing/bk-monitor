#!/usr/bin/env python3

import ast
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LOGGER_METHODS = {"critical", "debug", "error", "exception", "info", "warning"}


def tracked_python_files():
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / path for path in result.stdout.splitlines()]


def find_imports(tree):
    logger_names = set()
    log_module_names = set()
    common_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "common.log":
            for imported in node.names:
                if imported.name == "logger":
                    logger_names.add(imported.asname or imported.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "common":
            for imported in node.names:
                if imported.name == "log":
                    log_module_names.add(imported.asname or imported.name)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name != "common.log":
                    continue
                if imported.asname:
                    log_module_names.add(imported.asname)
                else:
                    common_names.add("common")

    return logger_names, log_module_names, common_names


def is_logger_expression(node, logger_names, log_module_names, common_names):
    if isinstance(node, ast.Name):
        return node.id in logger_names

    if not isinstance(node, ast.Attribute) or node.attr != "logger":
        return False
    if isinstance(node.value, ast.Name):
        return node.value.id in log_module_names
    return (
        isinstance(node.value, ast.Attribute)
        and node.value.attr == "log"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id in common_names
    )


def add_logger_aliases(tree, logger_names, log_module_names, common_names):
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign | ast.AnnAssign):
                continue
            value = node.value
            if value is None or not is_logger_expression(value, logger_names, log_module_names, common_names):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in logger_names:
                    logger_names.add(target.id)
                    changed = True


def is_logger_call(node, logger_names, log_module_names, common_names):
    function = node.func
    if isinstance(function, ast.Attribute) and function.attr in LOGGER_METHODS:
        return is_logger_expression(function.value, logger_names, log_module_names, common_names)

    if not isinstance(function, ast.Call):
        return False
    if not isinstance(function.func, ast.Name) or function.func.id != "getattr":
        return False
    return bool(function.args) and is_logger_expression(function.args[0], logger_names, log_module_names, common_names)


def main():
    violations = []
    checked_calls = 0

    for path in tracked_python_files():
        source = path.read_text(encoding="utf-8")
        if "common" not in source or "logger" not in source:
            continue

        tree = ast.parse(source, filename=str(path))
        logger_names, log_module_names, common_names = find_imports(tree)
        if not (logger_names or log_module_names or common_names):
            continue
        add_logger_aliases(tree, logger_names, log_module_names, common_names)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not is_logger_call(node, logger_names, log_module_names, common_names):
                continue
            checked_calls += 1
            if len(node.args) > 1 or any(isinstance(arg, ast.Starred) for arg in node.args) or node.keywords:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

    if violations:
        print("common.log.logger calls must pass at most one positional message and no keyword arguments:")
        print("\n".join(violations))
        raise SystemExit(1)

    print(f"common logger single-message self-check passed ({checked_calls} calls checked)")


if __name__ == "__main__":
    main()
