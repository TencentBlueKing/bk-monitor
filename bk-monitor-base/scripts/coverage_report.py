#!/usr/bin/env python3
"""
统计模块覆盖率脚本

用法示例：
    python scripts/coverage_report.py
"""

import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import coverage
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()  # 全局 Console 实例，替代 print


PARENT_MODULES: list[str] = ["src/bk_monitor_base/domains", "src/bk_monitor_base/infras"]
SUBMODULES: list[str] = ["src/bk_monitor_base/config", "src/bk_monitor_base/cli"]


def run_pytest() -> int:
    """
    运行pytest
    """
    pytest_cmd = [sys.executable, "-m", "pytest"]
    # 用 rich 输出命令行，突出显示
    console.print(f"[bold cyan]运行命令:[/] {' '.join(pytest_cmd)}")
    result = subprocess.run(pytest_cmd)
    return result.returncode


def calculate_submodule_coverage(submodules: list[str]) -> list[dict[str, Any]]:
    """
    计算每个子模块的覆盖率，返回结构化结果，便于多格式展示。
    返回：
        [
            {
                'name': 'domains/space',
                'covered': 68,
                'statements': 89,
                'percent': 76.40,
            },
            ...
        ]
    """
    cov = coverage.Coverage(data_file=".coverage")
    cov.load()
    results: list[dict[str, Any]] = []
    for sub in submodules:
        sub_path = Path(sub)
        if sub_path.is_dir():
            py_files = [str(p) for p in sub_path.rglob("*.py")]
        elif sub_path.is_file() and sub_path.suffix == ".py":
            py_files = [str(sub_path)]
        else:
            console.print(f"[bold red]无效的子模块路径:[/] {sub}")
            continue
        if not py_files:
            console.print(f"[yellow]{sub} 下没有 .py 文件[/]")
            continue

        sub_covered = 0
        sub_statements = 0
        sub_branch_statements = 0
        sub_branch_covered = 0
        for file in py_files:
            # 行覆盖率
            analysis = cov.analysis2(file)
            executable_lines = analysis[1]
            not_run_lines = analysis[3]
            sub_statements += len(executable_lines)
            sub_covered += len(executable_lines) - len(not_run_lines)
            # 分支覆盖率（累加所有文件）
            branch_stats = cov.branch_stats(file)
            sub_branch_statements += sum(stats[0] for stats in branch_stats.values())  # 总分支数
            sub_branch_covered += sum(stats[1] for stats in branch_stats.values())  # 被覆盖分支数

        # 如果没有代码，则跳过
        if sub_statements == 0:
            continue

        display_sub: str = sub.replace("src/bk_monitor_base/", "")
        percent = 100.0 * sub_covered / sub_statements if sub_statements > 0 else 0.0
        branch_percent = 100.0 * sub_branch_covered / sub_branch_statements if sub_branch_statements > 0 else 0.0
        results.append(
            {
                "name": display_sub,
                "covered": sub_covered,
                "statements": sub_statements,
                "percent": percent,
                "branch_covered": sub_branch_covered,
                "branch_statements": sub_branch_statements,
                "branch_percent": branch_percent,
            }
        )
    return results


def show_submodule_coverage_table(results: list[dict[str, Any]]) -> None:
    """
    rich 表格方式展示覆盖率结果，包含分支覆盖率，子模块列用树形缩进模拟目录结构
    """
    table = Table(title="各模块覆盖率", box=box.SIMPLE_HEAVY)
    table.add_column("子模块", style="bold", justify="left")
    table.add_column("覆盖率", style="green", justify="right")
    table.add_column("覆盖/总行数", style="magenta", justify="right")
    table.add_column("分支覆盖率", style="cyan", justify="right")
    table.add_column("分支覆盖/总分支", style="blue", justify="right")

    # 构建 name 层级树，便于树形缩进
    def tree() -> defaultdict[str, Any]:
        return defaultdict(tree)

    node_map: dict[str, dict[str, Any]] = {}
    root = tree()
    for item in results:
        parts = item["name"].split("/")
        node = root
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]]  # 确保叶子节点存在
        node_map[item["name"]] = item

    def render_table(node: dict[str, Any], prefix: str = "", parent_prefix: str = "") -> None:
        keys = list(node.keys())
        for idx, key in enumerate(keys):
            is_leaf = not node[key]
            is_last_child = idx == len(keys) - 1
            # 生成树形前缀
            if prefix:
                branch = "└── " if is_last_child else "├── "
                display_name = parent_prefix + branch + key
                next_prefix = parent_prefix + ("    " if is_last_child else "│   ")
            else:
                display_name = key + "/" if not is_leaf else key
                next_prefix = ""
            # 查找 item
            full_path = prefix + key if not prefix else prefix + "/" + key
            item = node_map.get(full_path)
            if item:
                covered = item["covered"]
                statements = item["statements"]
                percent = item["percent"]
                branch_covered = item.get("branch_covered", 0)
                branch_statements = item.get("branch_statements", 0)
                branch_percent = item.get("branch_percent", 0.0)
                # 行覆盖率
                if statements > 0:
                    percent_str = f"{percent:.2f}%"
                    if percent < 80:
                        percent_text = Text(percent_str, style="bold red")
                    elif percent < 90:
                        percent_text = Text(percent_str, style="yellow")
                    else:
                        percent_text = Text(percent_str, style="green")
                    covered_str = f"{covered}/{statements}"
                else:
                    continue
                # 分支覆盖率
                if branch_statements > 0:
                    branch_percent_str = f"{branch_percent:.2f}%"
                    if branch_percent < 80:
                        branch_percent_text = Text(branch_percent_str, style="bold red")
                    elif branch_percent < 90:
                        branch_percent_text = Text(branch_percent_str, style="yellow")
                    else:
                        branch_percent_text = Text(branch_percent_str, style="green")
                    branch_covered_str = f"{branch_covered}/{branch_statements}"
                else:
                    branch_percent_text = Text("-", style="dim")
                    branch_covered_str = "0/0"
                table.add_row(display_name, percent_text, covered_str, branch_percent_text, branch_covered_str)
            # 递归子节点
            if node[key]:
                render_table(node[key], full_path, next_prefix)

    render_table(root)
    console.print(table)


def submodule_paths() -> list[str]:
    """
    获取子模块路径
    """
    submodules: list[str] = sorted(SUBMODULES)
    parent_modules: list[str] = sorted(PARENT_MODULES)

    for parent_module in parent_modules:
        submodules.append(parent_module)
        submodules.extend(
            [
                str(submodule)
                for submodule in Path(parent_module).iterdir()
                if submodule.is_dir() and submodule.name not in submodules
            ]
        )
    return submodules


def main() -> None:
    # 先运行pytest收集.coverage
    code = run_pytest()
    if code != 0:
        # pytest 失败高亮输出
        console.print(f"[bold red]pytest 运行失败，退出（code={code}）[/]")
        sys.exit(code)

    # 计算覆盖率
    results = calculate_submodule_coverage(submodule_paths())

    console.print("\n")

    # 输出覆盖率结果
    show_submodule_coverage_table(results)


if __name__ == "__main__":
    main()
