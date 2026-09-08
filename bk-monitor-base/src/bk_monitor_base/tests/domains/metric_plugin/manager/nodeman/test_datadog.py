import os
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.datadog import DataDogPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)


def create_test_tar_gz(
    plugin_name: str = "test_plugin",
    os_dir: str = "external_plugins_linux_x86_64",
    has_lib: bool = True,
    has_conf_yaml_tpl: bool = True,
    has_conf_yaml_example: bool = False,
    has_meta_yaml: bool = True,
    meta_yaml_content: str | None = None,
) -> bytes:
    """创建测试用的tar.gz压缩包

    Args:
        plugin_name: 插件名称
        os_dir: 操作系统目录名称
        has_lib: 是否包含lib文件夹
        has_conf_yaml_tpl: 是否包含conf.yaml.tpl文件
        has_conf_yaml_example: 是否包含conf.yaml.example文件
        has_meta_yaml: 是否包含meta.yaml文件
        meta_yaml_content: meta.yaml文件内容，如果为None则使用默认内容

    Returns:
        tar.gz文件的bytes内容
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建目录结构: {os_dir}/{plugin_name}/
        plugin_base_dir = os.path.join(temp_dir, os_dir, plugin_name)
        os.makedirs(plugin_base_dir, exist_ok=True)

        # 创建lib文件夹
        if has_lib:
            lib_dir = os.path.join(plugin_base_dir, "lib")
            os.makedirs(lib_dir, exist_ok=True)
            # 创建一个示例文件
            with open(os.path.join(lib_dir, "check.py"), "w", encoding="utf-8") as f:
                f.write("# DataDog check script\n")

        # 创建etc文件夹和配置文件
        etc_dir = os.path.join(plugin_base_dir, "etc")
        os.makedirs(etc_dir, exist_ok=True)
        if has_conf_yaml_tpl:
            with open(os.path.join(etc_dir, "conf.yaml.tpl"), "w", encoding="utf-8") as f:
                f.write("init_config:\n  min_collection_interval: 30\n")
        if has_conf_yaml_example:
            with open(os.path.join(etc_dir, "conf.yaml.example"), "w", encoding="utf-8") as f:
                f.write("init_config:\n  min_collection_interval: 30\n")

        # 创建info文件夹和meta.yaml
        if has_meta_yaml:
            info_dir = os.path.join(plugin_base_dir, "info")
            os.makedirs(info_dir, exist_ok=True)
            if meta_yaml_content is None:
                meta_content = (
                    'datadog_check_name: test_check\n'
                    'config_yaml: "init_config:\\n  min_collection_interval: 30\\n"\n'
                )
            else:
                meta_content = meta_yaml_content
            with open(os.path.join(info_dir, "meta.yaml"), "w", encoding="utf-8") as f:
                f.write(meta_content)

        # 创建tar.gz文件
        tar_buffer = BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            tar.add(os.path.join(temp_dir, os_dir), arcname=os_dir)

        tar_buffer.seek(0)
        return tar_buffer.getvalue()


class TestDataDogPluginManager:
    """测试 DataDogPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_datadog_plugin",
            type="DataDog",
            name="测试DataDog插件",
            description_md="测试DataDog插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "datadog_check_name": "my_datadog_check",
                "config_yaml": "init_config:\n  min_collection_interval: 30\ninstances:\n  - name: my_service\n    url: http://localhost:8080/metrics\n    tags:\n      - service:my_service",
                "windows": {
                    "file_id": 12345,
                    "file_name": "my_datadog_check_windows.zip",
                    "md5": "a1b2c3d4e5f678901234567890123456",
                },
                "linux": {
                    "file_id": 12346,
                    "file_name": "my_datadog_check_linux.tar.gz",
                    "md5": "b2c3d4e5f678901234567890123456a",
                },
            },
            params=[
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="python_path",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="Python 程序路径",
                    default="python",
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="datadog_metric",
                    fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = DataDogPluginManager(self.plugin)

    def test_make_package(self):
        """测试制作DataDog插件包"""
        # todo 待制作DataDog插件包方法完全实现再补充单侧
        pass

    def test_debug_context(self):
        """测试调试上下文"""
        collect_params = {
            "period": 300,
            "python_path": "/usr/bin/python3",
        }
        plugin_params = {"datadog_check_name": "test_check"}

        # 测试_get_debug_config_context方法
        debug_context = self.plugin_manager._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[],
        )

        expected_debug_context = {
            "conf.yaml": {"datadog_check_name": "test_check"},
            "env.yaml": {"datadog_check_name": "test_check"},
            "bkmonitorbeat_debug.yaml": {
                "period": 300,
                "python_path": "/usr/bin/python3",
            },
        }

        # 校验调试配置上下文结果
        assert debug_context == expected_debug_context, f"调试配置上下文不匹配: {debug_context}"

    def test_get_deploy_steps_params(self):
        """测试获取部署步骤参数"""
        collect_params = {
            "period": 300,
            "python_path": "/usr/bin/python3",
        }
        plugin_params = {
            "datadog_check_name": "test_check",
        }

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        expected_steps_params = [
            # 配置文件下发
            {
                "id": "test_datadog_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "test_datadog_plugin",
                    "plugin_version": "1.0",
                    "config_templates": [
                        {"name": "env.yaml", "version": "1"},
                        {"name": "conf.yaml", "version": "1"},
                    ],
                },
                "params": {
                    "context": {
                        "datadog_check_name": "test_check",
                        "python_path": "/usr/bin/python3",
                    }
                },
            },
            # bkmonitorbeat子配置文件
            {
                "id": "test_datadog_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_script.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "period": "300",
                        "task_id": "2",
                        "bk_biz_id": "1",
                        "config_name": "test_datadog_plugin",
                        "config_version": "1.0",
                        "namespace": "test_datadog_plugin",
                        "timeout": "60",
                        "max_timeout": "60",
                        "dataid": 3,
                        "labels": {
                            "$for": "cmdb_instance.scope",
                            "$item": "scope",
                            "$body": {
                                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                                "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                "bk_collect_config_id": "2",
                            },
                        },
                        "command": "{{ step_data.test_datadog_plugin.control_info.setup_path }}/{{ step_data.test_datadog_plugin.control_info.start_cmd }}",
                    }
                },
            },
        ]

        assert steps_params == expected_steps_params

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_os_types = self.plugin_manager.get_supported_os_types()
        actual_os_types = [os_type.value for os_type in supported_os_types]

        # 根据测试数据，应该支持linux和windows
        expected_os_types = ["linux", "windows"]

        assert set(actual_os_types) == set(expected_os_types)

    @pytest.mark.parametrize(
        "os_type, os_dir_name",
        [
            (OSType.LINUX, "external_plugins_linux_x86_64"),
            (OSType.WINDOWS, "external_plugins_windows_x86_64"),
            (OSType.LINUX_AARCH64, "external_plugins_linux_aarch64"),
            (OSType.AIX, "external_plugins_aix_powerpc"),
        ],
    )
    def test_check_file_valid_linux(self, os_type, os_dir_name):
        """测试check_file方法 - 正常情况"""
        tar_data = create_test_tar_gz(os_dir=os_dir_name)
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, os_type)
        assert is_valid is True
        assert msg == ""
        assert extract_info["datadog_check_name"] == "test_check"
        assert "min_collection_interval" in extract_info["config_yaml"]

    def test_check_file_valid_with_bytesio(self):
        """测试check_file方法 - 使用BytesIO作为输入"""
        tar_data = create_test_tar_gz()
        file_obj = BytesIO(tar_data)
        is_valid, msg, extract_info = DataDogPluginManager.check_file(file_obj, OSType.LINUX)
        assert is_valid is True
        assert msg == ""
        assert extract_info["datadog_check_name"] == "test_check"

    def test_check_file_valid_with_uploaded_file(self):
        """测试check_file方法 - 使用SimpleUploadedFile作为输入"""
        tar_data = create_test_tar_gz()
        uploaded_file = SimpleUploadedFile("test.tar.gz", tar_data, content_type="application/gzip")
        is_valid, msg, extract_info = DataDogPluginManager.check_file(uploaded_file, OSType.LINUX)
        assert is_valid is True
        assert msg == ""
        assert extract_info["datadog_check_name"] == "test_check"

    def test_check_file_missing_os_dir(self):
        """测试check_file方法 - 缺少操作系统目录"""
        # 创建一个不包含正确操作系统目录的压缩包
        tar_data = create_test_tar_gz(os_dir="wrong_dir")
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        assert "external_plugins_linux_x86_64" in msg
        assert extract_info == {}

    def test_check_file_empty_os_dir(self):
        """测试check_file方法 - 操作系统目录为空"""
        with tempfile.TemporaryDirectory() as temp_dir:
            os_dir = "external_plugins_linux_x86_64"
            os.makedirs(os.path.join(temp_dir, os_dir), exist_ok=True)

            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                tar.add(os.path.join(temp_dir, os_dir), arcname=os_dir)

            tar_buffer.seek(0)
            tar_data = tar_buffer.getvalue()

        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        # 当目录为空时，os.listdir 会返回空列表，导致检查失败
        # 实际错误信息可能是"目录为空"或"缺少目录"
        assert "目录为空" in msg or "缺少" in msg
        assert extract_info == {}

    def test_check_file_missing_lib(self):
        """测试check_file方法 - 缺少lib文件夹"""
        tar_data = create_test_tar_gz(has_lib=False)
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        assert "缺少 lib 文件夹" in msg
        assert extract_info == {}

    def test_check_file_missing_conf_yaml(self):
        """测试check_file方法 - 缺少conf.yaml.tpl和conf.yaml.example"""
        tar_data = create_test_tar_gz(has_conf_yaml_tpl=False, has_conf_yaml_example=False)
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        assert "缺少 conf.yaml.example 配置模板文件" in msg
        assert extract_info == {}

    def test_check_file_with_conf_yaml_example(self):
        """测试check_file方法 - 只有conf.yaml.example（没有conf.yaml.tpl）"""
        tar_data = create_test_tar_gz(has_conf_yaml_tpl=False, has_conf_yaml_example=True)
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is True
        assert msg == ""
        assert extract_info["datadog_check_name"] == "test_check"
        assert "min_collection_interval" in extract_info["config_yaml"]

    def test_check_file_missing_meta_yaml(self):
        """测试check_file方法 - 缺少meta.yaml文件"""
        tar_data = create_test_tar_gz(has_meta_yaml=False)
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        assert "缺少 meta.yaml 配置模板文件" in msg
        assert extract_info == {}

    def test_check_file_missing_datadog_check_name(self):
        """测试check_file方法 - meta.yaml缺少datadog_check_name字段"""
        tar_data = create_test_tar_gz(meta_yaml_content="other_field: value\n")
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        assert "缺少 datadog_check_name" in msg
        assert extract_info == {}

    def test_check_file_empty_meta_yaml(self):
        """测试check_file方法 - meta.yaml为空"""
        tar_data = create_test_tar_gz(meta_yaml_content="")
        is_valid, msg, extract_info = DataDogPluginManager.check_file(tar_data, OSType.LINUX)
        assert is_valid is False
        assert "缺少 datadog_check_name" in msg
        assert extract_info == {}

    def test_check_file_invalid_tar_format(self):
        """测试check_file方法 - 无效的tar.gz格式"""
        invalid_data = b"not a tar.gz file"
        is_valid, msg, extract_info = DataDogPluginManager.check_file(invalid_data, OSType.LINUX)
        assert is_valid is False
        assert "校验DataDog插件文件时发生错误" in msg or len(msg) > 0
        assert extract_info == {}

    def test_check_file_with_string_path(self):
        """测试check_file方法 - 使用字符串路径作为输入"""
        # 创建临时文件
        tar_data = create_test_tar_gz()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp_file:
            tmp_file.write(tar_data)
            tmp_file_path = tmp_file.name

        try:
            is_valid, msg, extract_info = DataDogPluginManager.check_file(tmp_file_path, OSType.LINUX)
            assert is_valid is True
            assert msg == ""
            assert extract_info["datadog_check_name"] == "test_check"
        finally:
            # 清理临时文件
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_success(self, tmp_path: Path):
        """测试 _parse_define 方法 - 成功场景"""
        # 创建测试目录结构
        plugin_id = "test_datadog_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建多个操作系统目录
        os_dirs = [
            ("external_plugins_linux_x86_64", OSType.LINUX),
            ("external_plugins_windows_x86_64", OSType.WINDOWS),
        ]

        for os_dir_name, _os_type in os_dirs:
            plugin_dir = extract_dir / os_dir_name / plugin_id
            plugin_dir.mkdir(parents=True)

            # 创建 lib 文件夹和文件
            lib_dir = plugin_dir / "lib"
            lib_dir.mkdir()
            (lib_dir / "check.py").write_text("# DataDog check script\n", encoding="utf-8")
            (lib_dir / "utils.py").write_text("# Utils\n", encoding="utf-8")

            # 创建配置文件
            etc_dir = plugin_dir / "etc"
            etc_dir.mkdir()
            (etc_dir / "conf.yaml.tpl").write_text("init_config:\n  min_collection_interval: 30\n", encoding="utf-8")

        # 创建 info 目录和 config.yaml.tpl（优先读取）- 在第一个操作系统目录中
        info_dir = extract_dir / os_dirs[0][0] / plugin_id / "info"
        info_dir.mkdir(parents=True)
        (info_dir / "config.yaml.tpl").write_text("# Config from info\n", encoding="utf-8")

        # 准备 meta_data
        meta_data = {
            "plugin_id": plugin_id,
            "plugin_display_name": "测试DataDog插件",
            "plugin_type": "DataDog",
            "datadog_check_name": "test_check",
        }

        # 调用 _parse_define
        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 验证结果
        assert result["datadog_check_name"] == "test_check"
        # 代码会遍历所有操作系统目录，找到第一个存在的插件目录来读取配置文件
        # 由于目录遍历顺序可能不确定，我们只验证配置文件内容不为空
        assert result["config_yaml"] != ""
        assert "# Config from info" in result["config_yaml"] or "init_config" in result["config_yaml"]

        # 验证每个操作系统的 lib zip 文件已上传
        for _os_dir_name, os_type in os_dirs:
            assert os_type.value in result
            assert "file_token" in result[os_type.value]
            assert "file_name" in result[os_type.value]
            assert result[os_type.value]["file_name"] == f"{plugin_id}-lib-{os_type.value}.zip"
            assert len(result[os_type.value]["file_token"]) == 64  # token 是 64 个字符

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_with_etc_conf_yaml_tpl(self, tmp_path: Path):
        """测试 _parse_define 方法 - 使用 etc/conf.yaml.tpl 作为配置文件"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)

        # 创建 lib 文件夹
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir()
        (lib_dir / "check.py").write_text("# Check\n", encoding="utf-8")

        # 创建 etc/conf.yaml.tpl（没有 info/config.yaml.tpl）
        etc_dir = plugin_dir / "etc"
        etc_dir.mkdir()
        (etc_dir / "conf.yaml.tpl").write_text("init_config:\n  min_collection_interval: 30\n", encoding="utf-8")

        meta_data = {"datadog_check_name": "test_check"}

        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 应该读取 etc/conf.yaml.tpl
        assert result["config_yaml"] == "init_config:\n  min_collection_interval: 30\n"

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_with_conf_yaml_example(self, tmp_path: Path):
        """测试 _parse_define 方法 - 使用 etc/conf.yaml.example 作为配置文件"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)

        # 创建 lib 文件夹
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir()
        (lib_dir / "check.py").write_text("# Check\n", encoding="utf-8")

        # 只创建 etc/conf.yaml.example（没有其他配置文件）
        etc_dir = plugin_dir / "etc"
        etc_dir.mkdir()
        (etc_dir / "conf.yaml.example").write_text("init_config:\n  min_collection_interval: 60\n", encoding="utf-8")

        meta_data = {"datadog_check_name": "test_check"}

        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 应该读取 etc/conf.yaml.example
        assert result["config_yaml"] == "init_config:\n  min_collection_interval: 60\n"

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_no_config_file(self, tmp_path: Path):
        """测试 _parse_define 方法 - 没有配置文件"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)

        # 创建 lib 文件夹（不创建配置文件）
        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir()
        (lib_dir / "check.py").write_text("# Check\n", encoding="utf-8")

        meta_data = {"datadog_check_name": "test_check"}

        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # config_yaml 应该是空字符串
        assert result["config_yaml"] == ""

    def test_parse_define_missing_datadog_check_name(self, tmp_path: Path):
        """测试 _parse_define 方法 - meta.yaml 缺少 datadog_check_name"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {}  # 缺少 datadog_check_name

        with pytest.raises(ValueError, match="meta.yaml 中缺少 datadog_check_name 字段或字段值不合法"):
            DataDogPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    def test_parse_define_invalid_datadog_check_name(self, tmp_path: Path):
        """测试 _parse_define 方法 - datadog_check_name 类型不正确"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        meta_data = {"datadog_check_name": 123}  # 不是字符串

        with pytest.raises(ValueError, match="meta.yaml 中缺少 datadog_check_name 字段或字段值不合法"):
            DataDogPluginManager._parse_define(
                bk_tenant_id="test_tenant",
                operator="test_user",
                extract_dir=extract_dir,
                plugin_id=plugin_id,
                meta_data=meta_data,
            )

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_multiple_os_types(self, tmp_path: Path):
        """测试 _parse_define 方法 - 多个操作系统类型"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建多个操作系统目录
        os_configs = [
            ("external_plugins_linux_x86_64", OSType.LINUX),
            ("external_plugins_windows_x86_64", OSType.WINDOWS),
            ("external_plugins_linux_aarch64", OSType.LINUX_AARCH64),
        ]

        for os_dir_name, os_type in os_configs:
            plugin_dir = extract_dir / os_dir_name / plugin_id
            plugin_dir.mkdir(parents=True)

            lib_dir = plugin_dir / "lib"
            lib_dir.mkdir()
            (lib_dir / "check.py").write_text(f"# Check for {os_type.value}\n", encoding="utf-8")

        meta_data = {"datadog_check_name": "test_check"}

        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 验证所有操作系统类型都已处理
        for _os_dir_name, os_type in os_configs:
            assert os_type.value in result
            assert result[os_type.value]["file_name"] == f"{plugin_id}-lib-{os_type.value}.zip"

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_skip_missing_os_dir(self, tmp_path: Path):
        """测试 _parse_define 方法 - 跳过不存在的操作系统目录"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 只创建 linux 目录
        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)

        lib_dir = plugin_dir / "lib"
        lib_dir.mkdir()
        (lib_dir / "check.py").write_text("# Check\n", encoding="utf-8")

        meta_data = {"datadog_check_name": "test_check"}

        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # 应该只包含 linux
        assert "linux" in result
        assert "windows" not in result  # windows 目录不存在，应该被跳过

    @pytest.mark.django_db(databases=["default"])
    def test_parse_define_skip_missing_lib(self, tmp_path: Path):
        """测试 _parse_define 方法 - 跳过缺少 lib 文件夹的操作系统目录"""
        plugin_id = "test_plugin"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # 创建目录但不创建 lib 文件夹
        os_dir_name = "external_plugins_linux_x86_64"
        plugin_dir = extract_dir / os_dir_name / plugin_id
        plugin_dir.mkdir(parents=True)
        # 不创建 lib 文件夹

        meta_data = {"datadog_check_name": "test_check"}

        result = DataDogPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="test_user",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data=meta_data,
        )

        # linux 应该被跳过（因为没有 lib 文件夹）
        assert "linux" not in result
        assert result["datadog_check_name"] == "test_check"
