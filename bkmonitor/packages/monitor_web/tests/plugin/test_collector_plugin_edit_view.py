from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.metric_plugin import MetricPluginStatus, VersionTuple
from core.errors.plugin import BizChangedError, EditPermissionDenied, RelatedItemsExist
from monitor_web.plugin.views import CollectorPluginViewSet


@dataclass
class DummyDump:
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return self.payload


def build_request_data() -> dict[str, Any]:
    return {
        "bk_biz_id": 2,
        "plugin_id": "test_plugin",
        "plugin_type": "Script",
        "plugin_display_name": "Test Plugin",
        "description_md": "desc",
        "label": "os",
        "logo": "logo",
        "collector_json": {
            "linux": {
                "filename": "test.sh",
                "type": "shell",
                "script_content_base64": "IyEvYmluL3No",
            }
        },
        "config_json": [
            {
                "mode": "param",
                "type": "text",
                "name": "host",
                "description": "host",
                "default": "127.0.0.1",
            }
        ],
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
        "is_support_remote": False,
        "version_log": "release note",
        "signature": "signature: test",
        "enable_field_blacklist": False,
    }


def build_current_plugin(
    *,
    status: MetricPluginStatus = MetricPluginStatus.RELEASE,
    version: VersionTuple = VersionTuple(1, 0),
    bk_biz_id: int = 2,
    plugin_type: str = "Script",
    is_internal: bool = False,
    plugin_display_name: str = "Current Plugin",
    description_md: str = "old desc",
    label: str = "os",
    logo: str = "old-logo",
    collector_json: dict[str, Any] | None = None,
    config_json: list[dict[str, Any]] | None = None,
    metric_json: list[dict[str, Any]] | None = None,
    is_support_remote: bool = False,
    version_log: str = "old release note",
    enable_field_blacklist: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        version=version,
        bk_biz_id=bk_biz_id,
        type=plugin_type,
        is_internal=is_internal,
        name=plugin_display_name,
        description_md=description_md,
        label=label,
        logo=logo,
        define=collector_json
        or {
            "linux": {
                "filename": "current.sh",
                "type": "shell",
                "script_content_base64": "Y3VycmVudA==",
            }
        },
        params=[DummyDump(payload=item) for item in (config_json or [{"name": "host"}])],
        metrics=[DummyDump(payload=item) for item in (metric_json or [])],
        is_support_remote=is_support_remote,
        version_log=version_log,
        enable_metric_discovery=enable_field_blacklist,
    )


def build_base_plugin_model(bk_biz_id: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        bk_biz_id=bk_biz_id,
        is_global=bk_biz_id == 0,
        save=lambda **kwargs: None,
    )


def build_request(data: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(data=data, user=SimpleNamespace(username="admin"))


def build_serializer_class(validated_data: dict[str, Any]):
    class FakeSerializer:
        def __init__(self, *args, **kwargs):
            self.validated_data = dict(validated_data)

        def is_valid(self, raise_exception: bool = False) -> bool:
            return True

    return FakeSerializer


def setup_common_mocks(
    mocker: MockerFixture,
    *,
    request_data: dict[str, Any],
    current_plugin: SimpleNamespace,
    base_plugin_model: SimpleNamespace | None = None,
    validated_data: dict[str, Any] | None = None,
) -> None:
    mocker.patch("monitor_web.plugin.views.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.views.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.views.check_skip_debug", side_effect=lambda need_debug: need_debug)
    mocker.patch("monitor_web.plugin.views.get_metric_plugin_supported_os_types", return_value=["linux"])
    mocker.patch.object(
        CollectorPluginViewSet,
        "_get_edit_serializer_class",
        return_value=build_serializer_class(validated_data or request_data),
    )
    mocker.patch(
        "monitor_web.plugin.views.MetricPluginModel.objects.get",
        return_value=base_plugin_model or build_base_plugin_model(),
    )
    mocker.patch("monitor_web.plugin.views.get_metric_plugin", return_value=current_plugin)


def test_edit_release_plugin_minor_change_uses_release_version(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = build_current_plugin(
        plugin_display_name="Old Plugin",
        description_md="old desc",
        logo="old-logo",
        collector_json=request_data["collector_json"],
        config_json=request_data["config_json"],
        metric_json=[],
        enable_field_blacklist=True,
    )
    setup_common_mocks(mocker, request_data=request_data, current_plugin=current_plugin)
    mock_create_version = mocker.patch(
        "monitor_web.plugin.views.create_metric_plugin_version",
        return_value=(True, VersionTuple(1, 1)),
    )
    mock_release_version = mocker.patch("monitor_web.plugin.views.release_metric_plugin_version")

    response = CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")

    assert response.data["config_version"] == 1
    assert response.data["info_version"] == 1
    assert response.data["stage"] == MetricPluginStatus.RELEASE.value
    assert response.data["need_debug"] is False
    assert response.data["os_type_list"] == ["linux"]
    assert response.data["signature"] == "signature: test"
    mock_create_version.assert_called_once()
    mock_release_version.assert_called_once_with(
        bk_tenant_id="tenant",
        plugin_id="test_plugin",
        version=VersionTuple(1, 1),
        operator="admin",
    )
    create_params = mock_create_version.call_args.kwargs["params"]
    assert create_params.status == MetricPluginStatus.DEBUG
    assert create_params.version is None


def test_edit_release_plugin_major_change_creates_debug_version(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = build_current_plugin(
        plugin_display_name=request_data["plugin_display_name"],
        description_md=request_data["description_md"],
        label=request_data["label"],
        logo=request_data["logo"],
        collector_json={"linux": {"filename": "other.sh", "type": "shell", "script_content_base64": "b3RoZXI="}},
        config_json=request_data["config_json"],
        metric_json=request_data["metric_json"],
        enable_field_blacklist=request_data["enable_field_blacklist"],
    )
    setup_common_mocks(mocker, request_data=request_data, current_plugin=current_plugin)
    mock_create_version = mocker.patch(
        "monitor_web.plugin.views.create_metric_plugin_version",
        return_value=(True, VersionTuple(2, 0)),
    )

    response = CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")

    assert response.data["config_version"] == 2
    assert response.data["info_version"] == 0
    assert response.data["stage"] == MetricPluginStatus.DEBUG.value
    assert response.data["need_debug"] is True
    create_params = mock_create_version.call_args.kwargs["params"]
    assert create_params.status == MetricPluginStatus.DEBUG
    assert create_params.version is None


def test_edit_release_plugin_no_change_updates_current_version(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    request_data["version_log"] = "new release note"
    current_plugin = build_current_plugin(
        plugin_display_name=request_data["plugin_display_name"],
        description_md=request_data["description_md"],
        label=request_data["label"],
        logo=request_data["logo"],
        collector_json=request_data["collector_json"],
        config_json=request_data["config_json"],
        metric_json=request_data["metric_json"],
        enable_field_blacklist=request_data["enable_field_blacklist"],
    )
    setup_common_mocks(mocker, request_data=request_data, current_plugin=current_plugin)
    mock_create_version = mocker.patch(
        "monitor_web.plugin.views.create_metric_plugin_version",
        return_value=(False, VersionTuple(1, 0)),
    )
    mock_release_version = mocker.patch("monitor_web.plugin.views.release_metric_plugin_version")

    response = CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")

    assert response.data["config_version"] == 1
    assert response.data["info_version"] == 0
    assert response.data["stage"] == MetricPluginStatus.RELEASE.value
    assert response.data["need_debug"] is False
    mock_create_version.assert_called_once()
    mock_release_version.assert_not_called()


def test_edit_debug_plugin_overwrites_current_debug_version(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = build_current_plugin(
        status=MetricPluginStatus.DEBUG,
        version=VersionTuple(3, 4),
        collector_json=request_data["collector_json"],
        config_json=request_data["config_json"],
        metric_json=request_data["metric_json"],
        is_support_remote=request_data["is_support_remote"],
        plugin_display_name=request_data["plugin_display_name"],
        description_md=request_data["description_md"],
        label=request_data["label"],
        logo=request_data["logo"],
        enable_field_blacklist=request_data["enable_field_blacklist"],
    )
    setup_common_mocks(mocker, request_data=request_data, current_plugin=current_plugin)
    mock_create_version = mocker.patch(
        "monitor_web.plugin.views.create_metric_plugin_version",
        return_value=(True, VersionTuple(3, 4)),
    )

    response = CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")

    assert response.data["config_version"] == 3
    assert response.data["info_version"] == 4
    assert response.data["stage"] == MetricPluginStatus.DEBUG.value
    assert response.data["need_debug"] is True
    create_params = mock_create_version.call_args.kwargs["params"]
    assert create_params.status == MetricPluginStatus.DEBUG
    assert create_params.version == VersionTuple(3, 4)


def test_edit_imported_plugin_can_skip_debug_when_import_config_matches(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    request_data["import_plugin_config"] = {
        "collector_json": request_data["collector_json"],
        "config_json": request_data["config_json"],
        "is_support_remote": request_data["is_support_remote"],
    }
    current_plugin = build_current_plugin(
        plugin_display_name=request_data["plugin_display_name"],
        description_md=request_data["description_md"],
        label=request_data["label"],
        logo=request_data["logo"],
        collector_json={"linux": {"filename": "other.sh", "type": "shell", "script_content_base64": "b3RoZXI="}},
        config_json=request_data["config_json"],
        metric_json=request_data["metric_json"],
        enable_field_blacklist=request_data["enable_field_blacklist"],
    )
    setup_common_mocks(mocker, request_data=request_data, current_plugin=current_plugin)
    mocker.patch(
        "monitor_web.plugin.views.create_metric_plugin_version",
        return_value=(True, VersionTuple(2, 0)),
    )

    response = CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")

    assert response.data["need_debug"] is False


def test_operator_system_uses_legacy_os_type_ids(mocker: MockerFixture) -> None:
    expected = [
        {"os_type": "linux", "os_type_id": "1"},
        {"os_type": "windows", "os_type_id": "2"},
        {"os_type": "aix", "os_type_id": "3"},
        {"os_type": "linux_aarch64", "os_type_id": "4"},
    ]

    response = CollectorPluginViewSet().operator_system(SimpleNamespace())

    assert response.data == expected


def test_start_debug_defaults_target_nodes_to_empty_list(mocker: MockerFixture) -> None:
    request = SimpleNamespace(
        data={
            "bk_biz_id": 2,
            "config_version": 1,
            "info_version": 1,
            "param": {"collector": {"period": "10"}, "plugin": {}},
            "host_info": {"bk_host_id": 123},
        }
    )
    mocker.patch("monitor_web.plugin.views.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.views.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.views.StartDebugSerializer",
        return_value=SimpleNamespace(
            validated_data={
                "config_version": 1,
                "info_version": 1,
                "param": {"collector": {"period": "10"}, "plugin": {}},
                "host_info": {"bk_host_id": 123},
            },
            is_valid=lambda raise_exception=True: True,
        ),
    )
    mock_debug = mocker.patch("monitor_web.plugin.views.debug_nodeman_plugin", return_value={"task_id": "task-1"})

    response = CollectorPluginViewSet().start_debug(request, plugin_id="test_plugin")

    assert response.data == {"task_id": "task-1"}
    assert mock_debug.call_args.kwargs["target_nodes"] == []


def test_fetch_debug_log_reads_task_id_from_query_params(mocker: MockerFixture) -> None:
    request = SimpleNamespace(data={}, query_params={"task_id": 54313798})
    mocker.patch("monitor_web.plugin.views.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.views.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.views.TaskIdSerializer",
        return_value=SimpleNamespace(
            validated_data={"task_id": 54313798},
            is_valid=lambda raise_exception=True: True,
        ),
    )
    mock_log = mocker.patch(
        "monitor_web.plugin.views.get_nodeman_plugin_debug_log",
        return_value={
            "status": "running",
            "metric_json": [],
            "last_time": "2026-03-21 18:00:00",
            "log": "debugging",
        },
    )

    response = CollectorPluginViewSet().fetch_debug_log(request, plugin_id="test_plugin")

    assert response.data["status"] == "INSTALL"
    assert response.data["log_content"] == "debugging"
    assert mock_log.call_args.kwargs["task_id"] == 54313798


def test_fetch_debug_log_prefers_fetch_data_when_metrics_exist(mocker: MockerFixture) -> None:
    request = SimpleNamespace(data={}, query_params={"task_id": 54314058})
    mocker.patch("monitor_web.plugin.views.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.views.get_request_username", return_value="admin")
    mocker.patch(
        "monitor_web.plugin.views.TaskIdSerializer",
        return_value=SimpleNamespace(
            validated_data={"task_id": 54314058},
            is_valid=lambda raise_exception=True: True,
        ),
    )
    mocker.patch(
        "monitor_web.plugin.views.get_nodeman_plugin_debug_log",
        return_value={
            "status": "running",
            "metric_json": [
                {
                    "metric_name": "disk_usage",
                    "metric_value": 8,
                    "dimensions": [{"dimension_name": "disk_name", "dimension_value": "/data"}],
                }
            ],
            "last_time": "2026-03-21 18:49:50",
            "log": "metric arrived",
        },
    )

    response = CollectorPluginViewSet().fetch_debug_log(request, plugin_id="test_plugin")

    assert response.data["status"] == "FETCH_DATA"
    assert response.data["metric_json"][0]["metric_name"] == "disk_usage"


def test_edit_disallowed_plugin_rejects_version_change(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    current_plugin = build_current_plugin(
        is_internal=True,
        plugin_display_name="Old Plugin",
        collector_json=request_data["collector_json"],
        config_json=request_data["config_json"],
    )
    setup_common_mocks(
        mocker,
        request_data=request_data,
        current_plugin=current_plugin,
    )
    mock_create_version = mocker.patch("monitor_web.plugin.views.create_metric_plugin_version")

    with pytest.raises(EditPermissionDenied):
        CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")

    mock_create_version.assert_not_called()


def test_edit_rejects_single_biz_to_single_biz_switch(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    request_data["bk_biz_id"] = 3
    current_plugin = build_current_plugin()
    setup_common_mocks(mocker, request_data=request_data, current_plugin=current_plugin)

    with pytest.raises(BizChangedError):
        CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")


def test_edit_rejects_global_to_biz_switch_when_other_relations_exist(mocker: MockerFixture) -> None:
    request_data = build_request_data()
    request_data["bk_biz_id"] = 2
    current_plugin = build_current_plugin(bk_biz_id=0)
    setup_common_mocks(
        mocker,
        request_data=request_data,
        current_plugin=current_plugin,
    )
    mocker.patch("monitor_web.plugin.views.assert_manage_pub_plugin_permission")
    mocker.patch(
        "monitor_web.plugin.views.list_metric_plugin_deployments",
        return_value=([SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=3)], 2),
    )

    with pytest.raises(RelatedItemsExist):
        CollectorPluginViewSet().edit(build_request(request_data), plugin_id="test_plugin")
