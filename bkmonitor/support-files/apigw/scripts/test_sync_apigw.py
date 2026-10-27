"""Exercise the deployment command without contacting an API gateway or database."""

import importlib.util
import json
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.management.base import CommandError

_MONITOR_DIR = Path(__file__).resolve().parents[3]
_COMMAND = _MONITOR_DIR / "bkmonitor/management/commands/sync_apigw.py"
_STEPS = [
    "sync_apigw_config",
    "sync_apigw_stage",
    "sync_apigw_resources",
    "sync_resource_docs_by_archive",
    "create_version_and_release_apigw",
    "grant_apigw_permissions",
    "fetch_apigw_public_key",
]


@pytest.fixture
def sync_command(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("sync_apigw_under_test", _COMMAND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "settings", SimpleNamespace(BASE_DIR=str(tmp_path), APIGW_STAGE="prod"))
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="merged", stderr=""))
    remote = Mock()
    monkeypatch.setattr(module.subprocess, "run", runner)
    monkeypatch.setattr(module, "call_command", remote)
    command = module.Command(stdout=StringIO(), stderr=StringIO(), no_color=True)
    return module, command, runner, remote


@pytest.mark.parametrize("stderr", ["duplicate operationId 'example'", None])
def test_merge_failure_aborts_all_gateway_writes(sync_command, stderr):
    _, command, runner, remote = sync_command
    runner.side_effect = subprocess.CalledProcessError(2, ["merge_resources.py"], output="merging", stderr=stderr)

    with pytest.raises(CommandError, match="退出码 2"):
        command.handle()

    remote.assert_not_called()
    assert "merging" in command.stderr.getvalue()
    if stderr:
        assert stderr in command.stderr.getvalue()


def test_merge_cannot_start_is_a_command_failure(sync_command):
    _, command, runner, remote = sync_command
    runner.side_effect = OSError("interpreter unavailable")
    with pytest.raises(CommandError, match="无法启动网关资源合并"):
        command.handle()
    remote.assert_not_called()


def test_disabled_sync_is_explicit_and_does_not_write(sync_command):
    module, command, runner, remote = sync_command
    module.settings.SYNC_APIGATEWAY_ENABLED = False
    command.handle()
    runner.assert_not_called()
    remote.assert_not_called()
    assert "SYNC_APIGATEWAY_ENABLED=False" in command.stdout.getvalue()


def test_success_preserves_gateway_and_release_sequence(sync_command):
    module, command, runner, remote = sync_command
    command.handle()

    runner.assert_called_once_with(
        [sys.executable, f"{module.settings.BASE_DIR}/support-files/apigw/scripts/merge_resources.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert [call.args[0] for call in remote.call_args_list] == _STEPS
    assert all("--gateway-name=bk-monitor" in call.args for call in remote.call_args_list)
    assert "--stage=prod" in remote.call_args_list[4].args
    assert "merged" in command.stdout.getvalue()


@pytest.mark.parametrize("failed_step", _STEPS)
def test_gateway_failure_stops_later_steps(sync_command, failed_step):
    _, command, _, remote = sync_command

    def fail_selected_step(name, *args):
        if name == failed_step:
            raise CommandError(f"{name} failed")

    remote.side_effect = fail_selected_step
    with pytest.raises(CommandError, match=f"{failed_step} failed"):
        command.handle()
    assert [call.args[0] for call in remote.call_args_list] == _STEPS[: _STEPS.index(failed_step) + 1]


def test_duplicate_resources_exit_nonzero_and_leave_stale_output_unused(tmp_path):
    """Run the real merger and Django CLI boundary; no remote command is permitted."""
    gateway_dir = tmp_path / "support-files/apigw"
    script_dir = gateway_dir / "scripts"
    script_dir.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name("merge_resources.py"), script_dir / "merge_resources.py")
    resources_dir = gateway_dir / "resources/external/app"
    resources_dir.mkdir(parents=True)
    for name in ("first", "second"):
        resource = {
            "paths": {f"/app/{name}/": {"get": {"operationId": "duplicate_example", "x-bk-apigateway-resource": {}}}}
        }
        (resources_dir / f"{name}.yaml").write_text(json.dumps(resource))
    stale_output = gateway_dir / "resources.yaml"
    stale_output.write_text("stale resource definition")
    driver = """
import importlib.util
import sys
from django.conf import settings
settings.configure(BASE_DIR=sys.argv[2], APIGW_STAGE='prod', USE_I18N=False, DATABASES={})
spec = importlib.util.spec_from_file_location('sync_apigw_cli', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def reject_remote(*args, **kwargs):
    raise AssertionError('Gateway must not be contacted after merge failure')
module.call_command = reject_remote
command = module.Command()
command.requires_system_checks = []
command.run_from_argv(['manage.py', 'sync_apigw'])
"""
    result = subprocess.run(
        [sys.executable, "-c", driver, str(_COMMAND), str(tmp_path)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert "duplicate operationId 'duplicate_example'" in result.stderr
    assert "CommandError" in result.stderr
    assert "未执行网关同步" in result.stderr
    assert stale_output.read_text() == "stale resource definition"
