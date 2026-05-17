import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.metric_plugin import MetricPluginNotFoundError, MetricPluginVersionNotFoundError, VersionTuple
from core.errors.plugin import PluginIDNotExist, PluginVersionNotExist, RegisterPackageError
from monitor_web.plugin.resources import PluginRegisterResource


def test_plugin_register_returns_sorted_token_list(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "config_version": 1,
        "info_version": 2,
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mock_get_plugin = mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=object())
    mock_register_plugin = mocker.patch(
        "monitor_web.plugin.resources.register_metric_plugin",
        return_value=["md5_b", "md5_a"],
    )

    result = PluginRegisterResource().perform_request(request_data)

    assert result == {"token": ["md5_a", "md5_b"]}
    mock_get_plugin.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(major=1, minor=2),
    )
    mock_register_plugin.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(major=1, minor=2),
        operator="admin",
    )


def test_plugin_register_raises_plugin_not_exist(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "config_version": 1,
        "info_version": 2,
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.resources.get_metric_plugin",
        side_effect=MetricPluginNotFoundError("plugin not found"),
    )
    mock_register_plugin = mocker.patch("monitor_web.plugin.resources.register_metric_plugin")

    with pytest.raises(PluginIDNotExist):
        PluginRegisterResource().perform_request(request_data)

    mock_register_plugin.assert_not_called()


def test_plugin_register_raises_version_not_exist(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "config_version": 1,
        "info_version": 2,
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.resources.get_metric_plugin",
        side_effect=MetricPluginVersionNotFoundError("version not found"),
    )
    mock_register_plugin = mocker.patch("monitor_web.plugin.resources.register_metric_plugin")

    with pytest.raises(PluginVersionNotExist):
        PluginRegisterResource().perform_request(request_data)

    mock_register_plugin.assert_not_called()


def test_plugin_register_wraps_register_error(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "config_version": 1,
        "info_version": 2,
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=object())
    mocker.patch(
        "monitor_web.plugin.resources.register_metric_plugin",
        side_effect=RuntimeError("register failed"),
    )

    with pytest.raises(RegisterPackageError):
        PluginRegisterResource().perform_request(request_data)
