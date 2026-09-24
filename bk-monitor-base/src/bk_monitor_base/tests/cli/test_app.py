"""
CLI 模块的集成测试
"""

from typer.testing import CliRunner

from bk_monitor_base.cli.app import app


class TestCLI:
    """测试命令行接口"""

    def test_cli_app_creation(self) -> None:
        """测试 CLI 应用创建"""
        assert app is not None

    def test_help_command(self) -> None:
        """测试帮助命令"""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "bk-monitor-base" in result.output
