from pathlib import Path

from typer.testing import CliRunner

from bk_monitor_base.cli.app import app


def test_run_script_pass_through_positional_and_options(tmp_path: Path) -> None:
    """
    run-script 应该能透传位置参数与选项参数给脚本（脚本使用 argparse 解析）。
    """

    script = tmp_path / "demo_script.py"
    script.write_text(
        "\n".join(
            [
                "import argparse",
                "",
                "def main():",
                "    p = argparse.ArgumentParser()",
                "    p.add_argument('a')",
                "    p.add_argument('b')",
                "    p.add_argument('--k')",
                "    args = p.parse_args()",
                '    print(f"a={args.a} b={args.b} k={args.k}")',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["run-script", str(script), "x", "y", "--k", "z"])
    assert result.exit_code == 0
    assert "a=x b=y k=z" in result.output
