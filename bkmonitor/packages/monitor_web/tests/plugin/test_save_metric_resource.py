from dataclasses import dataclass, field
from typing import Any

from bk_monitor_base.metric_plugin import MetricPluginStatus, VersionTuple
from pytest_mock import MockerFixture

from monitor_web.plugin.resources import SaveMetricResource


@dataclass
class DummyMetric:
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return self.payload


@dataclass
class DummyPlugin:
    name: str = "test plugin"
    description_md: str = "desc"
    label: str = "os"
    logo: str = ""
    enable_metric_discovery: bool = True
    define: dict[str, Any] = field(default_factory=dict)
    params: list[dict[str, Any]] = field(default_factory=list)
    is_support_remote: bool = False
    metrics: list[DummyMetric] = field(default_factory=list)


def test_save_metric_no_change(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "plugin_type": "datadog",
        "config_version": 1,
        "info_version": 1,
        "enable_field_blacklist": True,
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
    current_plugin = DummyPlugin(
        metrics=[
            DummyMetric(
                {
                    "table_name": "cpu",
                    "table_desc": "CPU",
                    "rules": ["cpu"],
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
            )
        ]
    )
    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mocker.patch("monitor_web.plugin.resources.PluginVersionHistory.gen_diff_fields", return_value="")
    mock_create_version = mocker.patch("monitor_web.plugin.resources.create_metric_plugin_version")
    mock_apply_data_link = mocker.patch("monitor_web.plugin.resources.apply_metric_plugin_data_link")
    mock_register = mocker.patch("monitor_web.plugin.resources.register_metric_plugin")
    mock_release = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")
    mock_append_cache = mocker.patch.object(SaveMetricResource, "_append_metric_cache")

    result = SaveMetricResource().perform_request(request_data)

    assert result == {"config_version": 1, "info_version": 1}
    mock_create_version.assert_not_called()
    mock_apply_data_link.assert_not_called()
    mock_register.assert_not_called()
    mock_release.assert_not_called()
    mock_append_cache.assert_not_called()


def test_save_metric_release_with_enable_field_blacklist_mapping(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "plugin_type": "datadog",
        "config_version": 1,
        "info_version": 1,
        "enable_field_blacklist": False,
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
                        "tag_list": ["host"],
                    }
                ],
            }
        ],
    }
    current_plugin = DummyPlugin(
        enable_metric_discovery=True,
        metrics=[
            DummyMetric(
                {
                    "table_name": "cpu",
                    "table_desc": "CPU",
                    "rules": ["cpu"],
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
            )
        ],
    )
    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mocker.patch("monitor_web.plugin.resources.PluginVersionHistory.gen_diff_fields", return_value="")
    mock_create_version = mocker.patch("monitor_web.plugin.resources.create_metric_plugin_version")
    mock_apply_data_link = mocker.patch("monitor_web.plugin.resources.apply_metric_plugin_data_link")
    mock_register = mocker.patch("monitor_web.plugin.resources.register_metric_plugin")
    mock_release = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")
    mock_append_cache = mocker.patch.object(SaveMetricResource, "_append_metric_cache")

    result = SaveMetricResource().perform_request(request_data)

    assert result == {"config_version": 1, "info_version": 2}
    create_kwargs = mock_create_version.call_args.kwargs
    params = create_kwargs["params"]
    assert create_kwargs["version"] == VersionTuple(1, 2)
    assert params.enable_metric_discovery is False
    assert params.version == VersionTuple(1, 2)
    assert params.version_log == "update_metric"
    assert params.status == MetricPluginStatus.RELEASE
    assert params.metrics[0].rules == ["cpu"]
    mock_apply_data_link.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(1, 2),
        operator="admin",
    )
    mock_register.assert_not_called()
    mock_release.assert_not_called()
    append_kwargs = mock_append_cache.call_args.kwargs
    assert append_kwargs["metric_json"][0]["fields"][0]["tag_list"] == []


def test_save_metric_bumps_config_version_when_diff_fields_changed(mocker: MockerFixture) -> None:
    request_data = {
        "plugin_id": "test_plugin",
        "plugin_type": "datadog",
        "config_version": 1,
        "info_version": 1,
        "enable_field_blacklist": True,
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
                        "is_diff_metric": True,
                    }
                ],
            }
        ],
    }
    current_plugin = DummyPlugin(
        enable_metric_discovery=True,
        define={},
        metrics=[
            DummyMetric(
                {
                    "table_name": "cpu",
                    "table_desc": "CPU",
                    "rules": ["cpu"],
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
            )
        ],
    )
    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.resources.get_metric_plugin", return_value=current_plugin)
    mocker.patch("monitor_web.plugin.resources.PluginVersionHistory.gen_diff_fields", return_value="usage")
    mock_create_version = mocker.patch("monitor_web.plugin.resources.create_metric_plugin_version")
    mock_apply_data_link = mocker.patch("monitor_web.plugin.resources.apply_metric_plugin_data_link")
    mock_register = mocker.patch("monitor_web.plugin.resources.register_metric_plugin")
    mock_release = mocker.patch("monitor_web.plugin.resources.release_metric_plugin_version")
    mocker.patch.object(SaveMetricResource, "_append_metric_cache")

    result = SaveMetricResource().perform_request(request_data)

    assert result == {"config_version": 2, "info_version": 2}
    create_kwargs = mock_create_version.call_args.kwargs
    params = create_kwargs["params"]
    assert create_kwargs["version"] == VersionTuple(2, 2)
    assert params.status == MetricPluginStatus.DEBUG
    assert params.define["diff_fields"] == "usage"
    mock_apply_data_link.assert_not_called()
    mock_register.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(2, 2),
        operator="admin",
    )
    mock_release.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(2, 2),
        operator="admin",
    )
