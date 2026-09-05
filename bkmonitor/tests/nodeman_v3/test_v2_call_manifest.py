import ast
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(__file__).with_name("fixtures") / "v2_call_manifest.yaml"


def _attribute_parts(node: ast.AST) -> list[str] | None:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        value = _attribute_parts(node.value)
        if value:
            return [*value, node.attr]
    return None


def _argument_summary(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return f"${node.id}"
    if isinstance(node, ast.Attribute):
        parts = _attribute_parts(node)
        return f"${'.'.join(parts)}" if parts else "$attribute"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Dict):
        items = []
        for key, value in zip(node.keys, node.values, strict=True):
            key_summary = "**" if key is None else _argument_summary(key)
            items.append(f"{key_summary}:{_argument_summary(value)}")
        return "{" + ",".join(items) + "}"
    if isinstance(node, ast.List):
        return "[" + ",".join(_argument_summary(item) for item in node.elts) + "]"
    if isinstance(node, ast.Tuple):
        return "(" + ",".join(_argument_summary(item) for item in node.elts) + ")"
    if isinstance(node, ast.Set):
        return "set(" + ",".join(_argument_summary(item) for item in node.elts) + ")"
    if isinstance(node, ast.Call):
        parts = _attribute_parts(node.func)
        name = ".".join(parts) if parts else type(node.func).__name__
        args = [_argument_summary(argument) for argument in node.args]
        args.extend(f"{keyword.arg or '**'}={_argument_summary(keyword.value)}" for keyword in node.keywords)
        return f"$call:{name}({','.join(args)})"
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _classify(path: str) -> str:
    if "/migrations/" in f"/{path}":
        return "historical_migration"
    if path.startswith("packages/monitor_web/data_migrate/"):
        return "first_phase_prohibited_v2_migration_tool"
    if "/management/commands/" in f"/{path}" or path.startswith(
        ("kernel_api/rpc/functions/admin/", "kernel_api/rpc/functions/bkm_cli/")
    ):
        return "management_command_or_ops_tool"
    return "production_request_or_async_task"


def _coverage(path: str, category: str) -> list[str]:
    coverage = ["tests/nodeman_v3/test_v2_call_manifest.py::test_v2_call_manifest_matches_baseline"]
    if category == "production_request_or_async_task" and path != "packages/monitor_web/collecting/deploy/__init__.py":
        coverage.append(
            "tests/nodeman_v3/test_v2_call_manifest.py::test_untouched_v2_production_callsite_sources_match_baseline"
        )
    if path == "packages/monitor_web/collecting/deploy/__init__.py":
        coverage.append("tests/nodeman_v3/test_v2_call_manifest.py::test_v2_factory_body_matches_baseline")
    if path == "packages/monitor_web/collecting/deploy/node_man.py":
        coverage.append(
            "packages/monitor_web/tests/collecting/test_node_man_installer.py::"
            "test_stop_uses_existing_subscription_steps_without_deploy_params"
        )
    return coverage


def _call_summary(call: ast.Call) -> dict[str, list[dict[str, str]] | list[str]]:
    return {
        "args": [_argument_summary(argument) for argument in call.args],
        "keywords": [
            {"name": keyword.arg or "**", "value": _argument_summary(keyword.value)} for keyword in call.keywords
        ],
    }


def discover_v2_call_sites() -> list[dict]:
    sites: list[dict] = []
    for source_path in sorted(PROJECT_ROOT.rglob("*.py")):
        relative_path = source_path.relative_to(PROJECT_ROOT).as_posix()
        if "/tests/" in f"/{relative_path}" or relative_path.startswith("tests/"):
            continue

        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=relative_path)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        category = _classify(relative_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                parts = _attribute_parts(node)
                if not parts or parts[:2] != ["api", "node_man"] or len(parts) < 3:
                    continue
                parent = parents.get(node)
                if isinstance(parent, ast.Attribute) and parent.value is node:
                    continue

                call = parent if isinstance(parent, ast.Call) and parent.func is node else None
                sites.append(
                    {
                        "path": relative_path,
                        "line": node.lineno,
                        "category": category,
                        "kind": "call" if call else "resource_reference",
                        "symbol": ".".join(parts),
                        "action": parts[2],
                        "parameters": _call_summary(call) if call else {"args": [], "keywords": []},
                        "coverage": _coverage(relative_path, category),
                    }
                )
                continue

            if isinstance(node, ast.ClassDef) and node.name == "NodeManInstaller":
                sites.append(
                    {
                        "path": relative_path,
                        "line": node.lineno,
                        "category": category,
                        "kind": "class_definition",
                        "symbol": "NodeManInstaller",
                        "action": "installer_definition",
                        "parameters": {"args": [], "keywords": []},
                        "coverage": _coverage(relative_path, category),
                    }
                )
                continue

            if isinstance(node, ast.ImportFrom):
                for imported_name in node.names:
                    if imported_name.name != "NodeManInstaller":
                        continue
                    sites.append(
                        {
                            "path": relative_path,
                            "line": node.lineno,
                            "category": category,
                            "kind": "import",
                            "symbol": "NodeManInstaller",
                            "action": "installer_import",
                            "parameters": {"args": [], "keywords": []},
                            "coverage": _coverage(relative_path, category),
                        }
                    )

            if isinstance(node, ast.Call):
                parts = _attribute_parts(node.func)
                if parts != ["NodeManInstaller"]:
                    continue
                sites.append(
                    {
                        "path": relative_path,
                        "line": node.lineno,
                        "category": category,
                        "kind": "constructor_call",
                        "symbol": "NodeManInstaller",
                        "action": "installer_construct",
                        "parameters": _call_summary(node),
                        "coverage": _coverage(relative_path, category),
                    }
                )

    return sorted(sites, key=lambda item: (item["path"], item["line"], item["kind"], item["symbol"]))


def test_v2_call_manifest_matches_baseline():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = [{key: value for key, value in site.items() if key != "line"} for site in manifest["call_sites"]]
    actual = [{key: value for key, value in site.items() if key != "line"} for site in discover_v2_call_sites()]

    assert manifest["baseline_commit"] == "e4a29134be1c61c3b7a96b57aefdc555b48c7eb7"
    assert expected == actual


def test_v2_call_manifest_has_all_required_classifications():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    classifications = {site["category"] for site in manifest["call_sites"]}

    assert classifications == {
        "production_request_or_async_task",
        "management_command_or_ops_tool",
        "first_phase_prohibited_v2_migration_tool",
        "historical_migration",
    }


def _baseline_source(relative_path: str) -> str:
    import subprocess

    result = subprocess.run(
        [
            "git",
            "-C",
            str(PROJECT_ROOT),
            "show",
            f"e4a29134be1c61c3b7a96b57aefdc555b48c7eb7:bkmonitor/{relative_path}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_untouched_v2_production_callsite_sources_match_baseline():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    modified_routing_files = {
        "api/cmdb/ipchooser.py",
        "bkm_ipchooser/tools/gse_tool.py",
        "packages/monitor_web/cc/resources/cmdb.py",
        "packages/monitor_web/collecting/deploy/__init__.py",
        "packages/monitor_web/plugin/manager/base.py",
        "packages/monitor_web/plugin/resources.py",
        "packages/monitor_web/plugin/views.py",
    }
    production_paths = {
        site["path"] for site in manifest["call_sites"] if site["category"] == "production_request_or_async_task"
    }

    for relative_path in sorted(production_paths - modified_routing_files):
        assert (PROJECT_ROOT / relative_path).read_text(encoding="utf-8") == _baseline_source(relative_path)


def _function_ast(source: str, *, v2_branch: bool) -> str:
    tree = ast.parse(source)
    if v2_branch:
        for node in tree.body:
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            if not any(
                isinstance(comparator, ast.Constant) and comparator.value == "v2"
                for comparator in node.test.comparators
            ):
                continue
            candidates = [item for item in node.body if isinstance(item, ast.FunctionDef)]
            break
        else:
            candidates = []
    else:
        candidates = [item for item in tree.body if isinstance(item, ast.FunctionDef)]
    function = next(item for item in candidates if item.name == "get_collect_installer")
    body = function.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return ast.dump(
        ast.Module(
            body=[
                ast.FunctionDef(
                    name=function.name,
                    args=function.args,
                    body=body,
                    decorator_list=function.decorator_list,
                    returns=function.returns,
                    type_comment=function.type_comment,
                )
            ],
            type_ignores=[],
        ),
        annotate_fields=True,
        include_attributes=False,
    )


def test_v2_factory_body_matches_baseline():
    relative_path = "packages/monitor_web/collecting/deploy/__init__.py"
    current = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    baseline = _baseline_source(relative_path)

    assert _function_ast(current, v2_branch=True) == _function_ast(baseline, v2_branch=False)
