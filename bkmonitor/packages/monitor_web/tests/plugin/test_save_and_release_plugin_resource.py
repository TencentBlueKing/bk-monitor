from dataclasses import dataclass, field
from typing import Any

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.metric_plugin import VersionTuple
from core.errors.export_import import ExportImportError
from core.errors.plugin import PluginIDExist, UnsupportedPluginTypeError
from monitor_web.plugin.resources import SaveAndReleasePluginResource


@dataclass
class DummyParam:
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return self.payload


@dataclass
class DummyPlugin:
    params: list[DummyParam] = field(default_factory=list)
    define: dict[str, Any] = field(default_factory=dict)
    is_support_remote: bool = False


def build_request_data() -> dict[str, Any]:
    return {
        "bk_biz_id": 2,
        "plugin_id": "test_plugin",
        "plugin_type": "script",
        "plugin_display_name": "Test Plugin",
        "description_md": "desc",
        "label": "os",
        "logo": "logo",
        "config_version": 1,
        "info_version": 2,
        "signature": "",
        "is_support_remote": False,
        "version_log": "release note",
        "enable_field_blacklist": False,
        "config_json": [
            {
                "mode": "param",
                "type": "text",
                "name": "host",
                "description": "host",
                "default": "127.0.0.1",
            }
        ],
        "collector_json": {
            "linux": {
                "filename": "test.sh",
                "type": "shell",
                "script_content_base64": "IyEvYmluL3No",
            }
        },
        "metric_json": [
            {
                "table_name": "cpu",
                "table_desc": "CPU",
                "rule_list": ["cpu"],
                "fields": [
                    {
                        "name": "usage",
                        "type": "double",
                        "description": "usage",
                        "monitor_type": "metric",
                        "unit": "percent",
                        "is_active": True,
                        "source_name": "",
                    }
                ],
            }
        ],
    }


def test_save_and_release_plugin_create_success(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    register_params = {
        **request_data,
        "config_version": 3,
        "info_version": 4,
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mock_create_plugin = mocker.patch(
        "monitor_web.plugin.resources.resource.plugin.create_plugin",
        return_value=register_params,
    )
    mock_register_plugin = mocker.patch(
        "monitor_web.plugin.resources.resource.plugin.plugin_register",
        return_value={"token": ["token_a"]},
    )
    mock_update_version = mocker.patch("monitor_web.plugin.resources.update_metric_plugin_version")
    mock_release_version = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")

    result = SaveAndReleasePluginResource().perform_request(request_data)

    assert result is True
    mock_create_plugin.assert_called_once_with(**request_data)
    mock_register_plugin.assert_called_once_with(**register_params)
    mock_update_version.assert_not_called()
    mock_release_version.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(major=3, minor=4),
        operator="admin",
    )


def test_save_and_release_plugin_update_minor_fields_only(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = DummyPlugin(
        params=[DummyParam(payload=config) for config in request_data["config_json"]],
        define=request_data["collector_json"],
        is_support_remote=request_data["is_support_remote"],
    )

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.resources.resource.plugin.create_plugin",
        side_effect=PluginIDExist({"msg": request_data["plugin_id"]}),
    )
    mock_get_plugin = mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mock_register_plugin = mocker.patch("monitor_web.plugin.resources.resource.plugin.plugin_register")
    mock_update_version = mocker.patch("monitor_web.plugin.resources.update_metric_plugin_version")
    mock_release_version = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")

    result = SaveAndReleasePluginResource().perform_request(request_data)

    assert result is True
    mock_get_plugin.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(major=1, minor=2),
    )
    mock_register_plugin.assert_not_called()
    mock_update_version.assert_called_once()
    update_kwargs = mock_update_version.call_args.kwargs
    assert update_kwargs["bk_tenant_id"] == "tenant"
    assert update_kwargs["plugin_id"] == "test_plugin"
    assert update_kwargs["version"] == VersionTuple(major=1, minor=2)
    assert update_kwargs["operator"] == "admin"
    assert update_kwargs["params"].name == "Test Plugin"
    assert update_kwargs["params"].enable_metric_discovery is False
    assert update_kwargs["params"].version_log == "release note"
    assert update_kwargs["params"].metrics[0].table_name == "cpu"
    mock_release_version.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(major=1, minor=2),
        operator="admin",
    )


def test_save_and_release_plugin_rejects_changed_config_json(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = DummyPlugin(
        params=[DummyParam(payload={"name": "other"})],
        define=request_data["collector_json"],
        is_support_remote=request_data["is_support_remote"],
    )

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.resources.resource.plugin.create_plugin",
        side_effect=PluginIDExist({"msg": request_data["plugin_id"]}),
    )
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mock_register_plugin = mocker.patch("monitor_web.plugin.resources.resource.plugin.plugin_register")
    mock_update_version = mocker.patch("monitor_web.plugin.resources.update_metric_plugin_version")
    mock_release_version = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")

    with pytest.raises(ExportImportError, match="当前仅支持更新次要版本参数"):
        SaveAndReleasePluginResource().perform_request(request_data)

    mock_register_plugin.assert_not_called()
    mock_update_version.assert_not_called()
    mock_release_version.assert_not_called()


def test_save_and_release_plugin_rejects_changed_collector_json(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = DummyPlugin(
        params=[DummyParam(payload=config) for config in request_data["config_json"]],
        define={"linux": {"filename": "other.sh", "type": "shell", "script_content_base64": "abc"}},
        is_support_remote=request_data["is_support_remote"],
    )

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.resources.resource.plugin.create_plugin",
        side_effect=PluginIDExist({"msg": request_data["plugin_id"]}),
    )
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mock_register_plugin = mocker.patch("monitor_web.plugin.resources.resource.plugin.plugin_register")
    mock_update_version = mocker.patch("monitor_web.plugin.resources.update_metric_plugin_version")
    mock_release_version = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")

    with pytest.raises(ExportImportError, match="当前仅支持更新次要版本参数"):
        SaveAndReleasePluginResource().perform_request(request_data)

    mock_register_plugin.assert_not_called()
    mock_update_version.assert_not_called()
    mock_release_version.assert_not_called()


def test_save_and_release_plugin_rejects_changed_remote_support(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = DummyPlugin(
        params=[DummyParam(payload=config) for config in request_data["config_json"]],
        define=request_data["collector_json"],
        is_support_remote=True,
    )

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.resources.resource.plugin.create_plugin",
        side_effect=PluginIDExist({"msg": request_data["plugin_id"]}),
    )
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mock_register_plugin = mocker.patch("monitor_web.plugin.resources.resource.plugin.plugin_register")
    mock_update_version = mocker.patch("monitor_web.plugin.resources.update_metric_plugin_version")
    mock_release_version = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")

    with pytest.raises(ExportImportError, match="当前仅支持更新次要版本参数"):
        SaveAndReleasePluginResource().perform_request(request_data)

    mock_register_plugin.assert_not_called()
    mock_update_version.assert_not_called()
    mock_release_version.assert_not_called()


def test_save_and_release_plugin_rejects_invalid_plugin_type() -> None:
    with pytest.raises(UnsupportedPluginTypeError):
        SaveAndReleasePluginResource().validate_request_data({"plugin_type": "unsupported"})
