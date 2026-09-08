import io
from datetime import datetime
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.exporter import ExporterPluginManager
from bk_monitor_base.domains.uploaded_file.operation import FileInfo


class TestExporterPluginManager:
    @pytest.mark.parametrize(
        "file_or_content, os_type, expected_bool, expected_msg_part",
        [
            # Windows Valid (bytes)
            (b"MZ\x90\x00", OSType.WINDOWS, True, ""),
            # Windows Invalid (bytes, header)
            (b"EL\x00\x00", OSType.WINDOWS, False, "文件不是windows下的可执行文件"),
            # Windows Invalid (bytes, length)
            (b"M", OSType.WINDOWS, False, "文件不是有效的可执行文件"),
            # Windows Valid (SimpleUploadedFile, .exe, header MZ)
            (SimpleUploadedFile("test.exe", b"MZ\x00\x00"), OSType.WINDOWS, True, ""),
            # Windows Invalid (SimpleUploadedFile, .txt)
            (SimpleUploadedFile("test.txt", b"MZ\x00\x00"), OSType.WINDOWS, False, "不是windows下的可执行文件"),
            # Windows Invalid (SimpleUploadedFile, .exe, wrong header)
            (SimpleUploadedFile("test.exe", b"EL\x00\x00"), OSType.WINDOWS, False, "文件不是windows下的可执行文件"),
            # Windows Invalid (SimpleUploadedFile, .exe, short header)
            # SimpleUploadedFile might return empty bytes if seeked or not handled right?
            # It wraps bytes.
            (SimpleUploadedFile("test.exe", b"M"), OSType.WINDOWS, False, "文件不是有效的可执行文件"),
            # Linux Valid (bytes)
            (b"\x7fELF\x00", OSType.LINUX, True, ""),
            # Linux Invalid (bytes, header)
            (b"MZ\x00\x00", OSType.LINUX, False, "文件不是linux下的可执行文件"),
            # Linux Valid (SimpleUploadedFile, no .exe, header ELF)
            (SimpleUploadedFile("test_linux", b"\x7fELF\x00"), OSType.LINUX, True, ""),
            # Linux Invalid (SimpleUploadedFile, .exe)
            (SimpleUploadedFile("test.exe", b"\x7fELF\x00"), OSType.LINUX, False, "不是linux下的可执行文件"),
            # Linux Invalid (SimpleUploadedFile, wrong header)
            (SimpleUploadedFile("test_linux", b"MZ\x00\x00"), OSType.LINUX, False, "文件不是linux下的可执行文件"),
            # AIX (Always valid)
            (b"Any content", OSType.AIX, True, ""),
            # BytesIO Case
            (io.BytesIO(b"MZ\x00\x00"), OSType.WINDOWS, True, ""),
            (io.BytesIO(b"\x7fELF\x00"), OSType.LINUX, True, ""),
        ],
    )
    def test_check_file(self, file_or_content, os_type, expected_bool, expected_msg_part):
        is_valid, msg, extract_info = ExporterPluginManager.check_file(file_or_content, os_type)
        assert is_valid == expected_bool
        assert extract_info == {}
        if not is_valid:
            assert expected_msg_part in msg

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_exporter_plugin",
            type="Exporter",
            name="测试Exporter插件",
            description_md="测试Exporter插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "windows": {
                    "file_token": "test_windows_token",
                    "file_name": "test_exporter_plugin.exe",
                },
                "linux": {
                    "file_token": "test_linux_token",
                    "file_name": "test_exporter_plugin",
                },
                "diff_fields": "metric1,metric2",
            },
            params=[
                MetricPluginParams(
                    name="port",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="端口",
                    default="8080",
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="exporter_metric",
                    fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = ExporterPluginManager(self.plugin)

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_os_types = self.plugin_manager.get_supported_os_types()
        actual_os_types = [os_type.value for os_type in supported_os_types]

        # 根据测试数据，应该支持linux和windows
        expected_os_types = ["linux", "windows"]

        assert set(actual_os_types) == set(expected_os_types)

    def test_get_supported_os_types_empty(self):
        """测试获取支持的操作系统类型 - 空define"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="Exporter",
            name="测试插件",
            description_md="测试",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={},
        )
        plugin_manager = ExporterPluginManager(plugin)
        supported_os_types = plugin_manager.get_supported_os_types()
        assert len(supported_os_types) == 0

    @pytest.mark.django_db(databases=["default"])
    def test_make_package_success(self, mocker: MockerFixture, tmp_path: Path):
        """测试制作插件包 - 成功场景"""
        # Mock get_file 返回文件信息
        mock_file_info = FileInfo(
            id=1,
            file=ContentFile(b"MZ\x00\x00fake_binary_content", name="test_exporter_plugin.exe"),
            filename="test_exporter_plugin.exe",
            usage="exporter_plugin",
            token="test_windows_token",
            md5="d41d8cd98f00b204e9800998ecf8427e",
            created_by="admin",
            description="",
            created_at=datetime.now(),
        )

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.exporter.get_file",
            side_effect=[mock_file_info, mock_file_info],  # 为两个操作系统各返回一次
        )

        # Mock _make_package
        mock_package_path = tmp_path / "test_plugin.tgz"
        mock_package_path.touch()
        mocker.patch.object(
            self.plugin_manager,
            "_make_package",
            return_value=mock_package_path,
        )

        # 调用 make_package
        result = self.plugin_manager.make_package(is_compress=True)

        # 验证结果
        assert result == mock_package_path

    @pytest.mark.django_db(databases=["default"])
    def test_make_package_missing_file_token(self, mocker: MockerFixture):
        """测试制作插件包 - 缺少file_token"""
        # 创建一个只有windows的plugin，但windows的define中没有file_token
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="Exporter",
            name="测试插件",
            description_md="测试",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "windows": {},  # 没有file_token
            },
        )
        plugin_manager = ExporterPluginManager(plugin)

        # 调用 make_package，应该跳过缺少file_token的操作系统
        mocker.patch.object(
            plugin_manager,
            "_make_package",
            return_value=Path("/tmp/test.tgz"),
        )

        result = plugin_manager.make_package(is_compress=True)
        assert result is not None

    @pytest.mark.django_db(databases=["default"])
    def test_make_package_get_file_failed(self, mocker: MockerFixture):
        """测试制作插件包 - get_file失败"""
        # Mock get_file 抛出异常
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.exporter.get_file",
            side_effect=Exception("File not found"),
        )

        # 调用 make_package 应该抛出 ValueError
        with pytest.raises(ValueError, match="获取插件.*的二进制文件失败"):
            self.plugin_manager.make_package(is_compress=True)

    def test_get_deploy_steps_params_with_port(self):
        """测试获取部署步骤参数 - 有port参数"""
        collect_params = {
            "period": 300,
            "timeout": 60,
            "host": "localhost",
            "port": "9090",
        }
        plugin_params = {}

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        # 验证步骤参数
        assert len(steps_params) == 2
        assert steps_params[0]["id"] == "test_exporter_plugin"
        assert steps_params[1]["id"] == "bkmonitorbeat"

        # 验证plugin_params中有port
        assert plugin_params["port"] == "9090"
        assert collect_params["port"] == "9090"

        # 验证extra_collect_context
        bkmonitorbeat_context = steps_params[1]["params"]["context"]
        assert bkmonitorbeat_context["metric_url"] == "localhost:9090/metrics"
        assert bkmonitorbeat_context["diff_metrics"] == ["metric1", "metric2"]

    def test_get_deploy_steps_params_without_port(self):
        """测试获取部署步骤参数 - 没有port参数"""
        collect_params = {
            "period": 300,
            "timeout": 60,
            "host": "localhost",
        }
        plugin_params = {}

        self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        # 验证plugin_params中有port模板
        assert plugin_params["port"] == "{{ control_info.listen_port }}"
        assert "port" in collect_params
        assert "listen_port" in collect_params["port"]

    def test_get_deploy_steps_params_no_diff_fields(self):
        """测试获取部署步骤参数 - 没有diff_fields"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="Exporter",
            name="测试插件",
            description_md="测试",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {
                    "file_token": "test_token",
                    "file_name": "test_plugin",
                },
            },
        )
        plugin_manager = ExporterPluginManager(plugin)

        collect_params = {"host": "localhost", "port": "9090"}
        plugin_params = {}

        steps_params = plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[],
        )

        # 验证diff_metrics为空列表
        bkmonitorbeat_context = steps_params[1]["params"]["context"]
        assert bkmonitorbeat_context["diff_metrics"] == []

    def test_get_debug_config_context(self):
        """测试获取调试配置上下文"""
        collect_params = {
            "period": 300,
            "host": "localhost",
            "port": "9090",
        }
        plugin_params = {"custom_param": "value"}

        debug_context = self.plugin_manager._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[],
        )

        # 验证metric_url已添加到collect_params
        assert collect_params["metric_url"] == "localhost:9090/metrics"

        # 验证返回的上下文结构
        assert "env.yaml" in debug_context
        assert "bkmonitorbeat_debug.yaml" in debug_context

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_success(self, tmp_path: Path):
        """测试 _parse_define 方法 - 成功场景"""
        plugin_id = "test_exporter_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建所有支持的操作系统目录和二进制文件（_parse_define 会遍历所有 OSType）
        os_configs = [
            ("external_plugins_linux_x86_64", OSType.LINUX, plugin_id),
            ("external_plugins_windows_x86_64", OSType.WINDOWS, f"{plugin_id}.exe"),
            ("external_plugins_linux_aarch64", OSType.LINUX_AARCH64, plugin_id),
            ("external_plugins_aix_powerpc", OSType.AIX, plugin_id),
        ]

        for os_dir_name, os_type, binary_filename in os_configs:
            plugin_dir = extract_dir / os_dir_name / plugin_id
            plugin_dir.mkdir(parents=True)

            # 创建二进制文件
            binary_file = plugin_dir / binary_filename
            if os_type == OSType.WINDOWS:
                binary_file.write_bytes(b"MZ\x00\x00fake_windows_binary")
            else:
                binary_file.write_bytes(b"\x7fELF\x00fake_linux_binary")

        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试Exporter插件",
            "plugin_type": "Exporter",
        }

        # 调用 _parse_define
        result = ExporterPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 验证结果（只验证我们创建的操作系统）
        for _os_dir_name, os_type, binary_filename in os_configs:
            assert os_type.value in result
            assert "file_token" in result[os_type.value]
            assert "file_name" in result[os_type.value]
            assert result[os_type.value]["file_name"] == binary_filename
            assert len(result[os_type.value]["file_token"]) == 64  # token 是 64 个字符

    def test_parse_define_missing_binary_file(self, tmp_path: Path):
        """测试 _parse_define 方法 - 二进制文件不存在"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建目录但不创建二进制文件
        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)
        # 不创建二进制文件

        meta_data = {}

        with pytest.raises(ValueError, match="二进制文件不存在"):
            ExporterPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_all_os_types(self, tmp_path: Path):
        """测试 _parse_define 方法 - 所有操作系统类型"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建所有支持的操作系统目录
        os_configs = [
            ("external_plugins_linux_x86_64", OSType.LINUX, plugin_id),
            ("external_plugins_windows_x86_64", OSType.WINDOWS, f"{plugin_id}.exe"),
            ("external_plugins_linux_aarch64", OSType.LINUX_AARCH64, plugin_id),
            ("external_plugins_aix_powerpc", OSType.AIX, plugin_id),
        ]

        for os_dir_name, os_type, binary_filename in os_configs:
            plugin_dir = extract_dir / os_dir_name / plugin_id
            plugin_dir.mkdir(parents=True)

            binary_file = plugin_dir / binary_filename
            if os_type == OSType.WINDOWS:
                binary_file.write_bytes(b"MZ\x00\x00")
            else:
                binary_file.write_bytes(b"\x7fELF\x00")

        meta_data = {}

        result = ExporterPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 验证所有操作系统类型都已处理
        for _os_dir_name, os_type, binary_filename in os_configs:
            assert os_type.value in result
            assert result[os_type.value]["file_name"] == binary_filename
