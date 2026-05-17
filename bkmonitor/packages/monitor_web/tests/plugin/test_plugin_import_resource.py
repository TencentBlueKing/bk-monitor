import tarfile
from io import BytesIO
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from pytest_mock import MockerFixture

from bk_monitor_base.metric_plugin import (
    CreatePluginParams,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    VersionTuple,
)
from monitor_web.plugin.constant import ConflictMap
from monitor_web.plugin.resources import PluginImportResource, PluginImportWithoutFrontendResource


def build_package(files: dict[str, str | bytes], file_name: str = "plugin.tgz") -> SimpleUploadedFile:
    package_buffer = BytesIO()
    with tarfile.open(fileobj=package_buffer, mode="w:gz") as tar:
        for path, content in files.items():
            content_bytes = content.encode("utf-8") if isinstance(content, str) else content
            tar_info = tarfile.TarInfo(name=path)
            tar_info.size = len(content_bytes)
            tar.addfile(tar_info, BytesIO(content_bytes))

    package_buffer.seek(0)
    return SimpleUploadedFile(file_name, package_buffer.getvalue(), content_type="application/gzip")


def test_plugin_import_resource_converts_exporter_result(mocker: MockerFixture) -> None:
    request_data = {
        "bk_biz_id": 2,
        "file_data": build_package(
            {
                "external_plugins_linux_x86_64/bkplugin_test/info/meta.yaml": """
plugin_id: bkplugin_test
plugin_display_name: Test Plugin
plugin_type: Exporter
tag: mysql
label: component
is_support_remote: true
""",
                "external_plugins_linux_x86_64/bkplugin_test/info/signature.yaml": """
safety:
  linux: test-signature
""",
            }
        ),
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.resources.resource.plugin.check_plugin_id")
    mock_parse_package = mocker.patch(
        "monitor_web.plugin.resources.parse_metric_plugin_package",
        return_value=CreatePluginParams(
            id="bkplugin_test",
            type="exporter",
            name="Test Plugin",
            description_md="desc",
            label="component",
            logo="data:image/png;base64,bG9nbw==",
            metrics=[
                MetricPluginMetricGroup(
                    table_name="base",
                    table_desc="default",
                    rules=["match_rule"],
                    fields=[
                        MetricPluginMetricField(
                            name="cpu_usage",
                            type="double",
                            description="cpu",
                            monitor_type="metric",
                            unit="%",
                        )
                    ],
                )
            ],
            params=[
                MetricPluginParams(
                    default="127.0.0.1",
                    mode="collector",
                    type="text",
                    name="host",
                    description="host",
                )
            ],
            define={"linux": {"file_token": "token", "file_name": "bkplugin_test"}},
            is_support_remote=True,
            version=VersionTuple(major=1, minor=2),
            version_log="release note",
        ),
    )
    mocker.patch(
        "monitor_web.plugin.resources.get_file",
        return_value=SimpleNamespace(file=ContentFile(b"binary"), filename="bkplugin_test", md5="source-md5"),
    )
    mocker.patch(
        "monitor_web.plugin.resources.PluginFileManager.save_file",
        return_value=SimpleNamespace(
            file_obj=SimpleNamespace(id=12, actual_filename="linux_bkplugin_test", file_md5="legacy-md5")
        ),
    )

    result = PluginImportResource().perform_request(request_data)

    assert result["plugin_id"] == "bkplugin_test"
    assert result["plugin_display_name"] == "Test Plugin"
    assert result["plugin_type"] == "Exporter"
    assert result["tag"] == "mysql"
    assert result["label"] == "component"
    assert result["collector_json"] == {
        "linux": {"file_id": 12, "file_name": "linux_bkplugin_test", "md5": "legacy-md5"}
    }
    assert result["config_json"][0]["name"] == "host"
    assert result["metric_json"][0]["table_name"] == "base"
    assert result["logo"] == b"bG9nbw=="
    assert result["config_version"] == 1
    assert result["info_version"] == 2
    assert result["version_log"] == "release note"
    assert result["is_official"] is True
    assert result["is_safety"] is False
    assert result["related_conf_count"] == 0
    assert b"safety" in result["signature"]
    mock_parse_package.assert_called_once()


def test_plugin_import_resource_reads_jmx_collector_config_from_package(mocker: MockerFixture) -> None:
    request_data = {
        "bk_biz_id": 2,
        "file_data": build_package(
            {
                "external_plugins_linux_x86_64/custom_jmx/info/meta.yaml": """
plugin_id: custom_jmx
plugin_display_name: Custom JMX
plugin_type: JMX
tag:
label: component
is_support_remote: false
""",
                "external_plugins_linux_x86_64/custom_jmx/etc/config.yaml.tpl": "startObjectNames:\n  - java.lang:type=Memory\n",
            }
        ),
    }

    mocker.patch("monitor_web.plugin.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.plugin.resources.get_request_username", return_value="admin")
    mocker.patch("monitor_web.plugin.resources.resource.plugin.check_plugin_id")
    mocker.patch(
        "monitor_web.plugin.resources.parse_metric_plugin_package",
        return_value=CreatePluginParams(
            id="custom_jmx",
            type="jmx",
            name="Custom JMX",
            description_md="desc",
            label="component",
            logo="",
            metrics=[],
            params=[],
            define={},
            is_support_remote=False,
            version=VersionTuple(major=3, minor=4),
            version_log="",
        ),
    )

    result = PluginImportResource().perform_request(request_data)

    assert result["plugin_id"] == "custom_jmx"
    assert result["plugin_type"] == "JMX"
    assert result["collector_json"] == {"config_yaml": "startObjectNames:\n  - java.lang:type=Memory\n"}
    assert result["is_official"] is False
    assert result["is_safety"] is False
    assert result["config_version"] == 3
    assert result["info_version"] == 4


def test_plugin_import_without_frontend_keeps_current_version_for_lower_package(mocker: MockerFixture) -> None:
    create_params = {
        "plugin_id": "test_script",
        "plugin_type": "Script",
        "collector_json": {"linux": {"script_content_base64": b"IyEvYmluL3No"}},
        "logo": b"bG9nbw==",
        "signature": b"",
        "config_version": 1,
        "info_version": 1,
        "duplicate_type": "custom",
        "conflict_detail": "存在冲突",
        "conflict_title": "",
    }
    current_version = SimpleNamespace(
        version="2.3",
        plugin=SimpleNamespace(bk_biz_id=2, plugin_type="Script"),
        config=SimpleNamespace(is_support_remote=False),
    )

    mocker.patch.object(
        PluginImportWithoutFrontendResource,
        "_parse_import_context",
        return_value=SimpleNamespace(
            create_params=create_params,
            current_version=current_version,
            plugin_id="test_script",
            plugin_type="Script",
            imported_version={"config_version": 1, "info_version": 1},
        ),
    )
    mocker.patch(
        "monitor_web.plugin.resources.PluginDataAccessor",
        return_value=SimpleNamespace(contrast_rt=lambda: (None, {"script_test_script.cpu": {}})),
    )
    mock_save_request = mocker.patch(
        "monitor_web.plugin.resources.SaveAndReleasePluginResource.request", return_value=True
    )

    result = PluginImportWithoutFrontendResource().perform_request(
        {
            "bk_biz_id": 2,
            "operator": "admin",
            "metric_json": {},
        }
    )

    assert result is True
    assert create_params["config_version"] == 2
    assert create_params["info_version"] == 3
    saved_params = mock_save_request.call_args.args[0]
    assert saved_params["config_version"] == 2
    assert saved_params["info_version"] == 3
    assert saved_params["logo"] == "data:image/png;base64,bG9nbw=="
    assert saved_params["signature"] == ""
    assert saved_params["collector_json"]["linux"]["script_content_base64"] == "IyEvYmluL3No"


def test_plugin_import_resource_conflict_message_keeps_legacy_behavior() -> None:
    create_params = {
        "duplicate_type": "official",
        "conflict_detail": "",
        "conflict_title": "",
    }
    current_version = SimpleNamespace(
        is_official=True,
        version="2.0",
        plugin=SimpleNamespace(tag="mysql"),
        config=SimpleNamespace(
            config2dict=lambda: {"config_json": [{"name": "host"}], "collector_json": {}, "is_support_remote": False}
        ),
        info=SimpleNamespace(
            info2dict=lambda: {
                "plugin_display_name": "Current",
                "description_md": "old",
                "logo": b"",
                "metric_json": [],
                "enable_field_blacklist": True,
            }
        ),
    )

    PluginImportResource.check_conflict_mes(
        create_params=create_params,
        current_version=current_version,
        imported_meta={"plugin_id": "bkplugin_test", "plugin_type": "Exporter", "tag": "mysql", "label": "component"},
        imported_config={"config_json": [], "collector_json": {}, "is_support_remote": False},
        imported_info={
            "plugin_display_name": "Imported",
            "description_md": "new",
            "logo": b"",
            "metric_json": [],
            "enable_field_blacklist": True,
        },
        imported_version={"config_version": 1, "info_version": 0, "signature": "", "version_log": ""},
    )

    assert "导入插件包版本为：1.0；已有插件版本为：2.0" == create_params["conflict_detail"]
    assert str(ConflictMap.VersionBelow.info) in create_params["conflict_title"]
    assert create_params["conflict_ids"] == [ConflictMap.VersionBelow.id]
