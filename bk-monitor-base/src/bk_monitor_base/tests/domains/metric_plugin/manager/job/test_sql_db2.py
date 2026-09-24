from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.errors import ParseOsTypeError
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.base import JobPluginParamsMode, JobPluginParamsType
from bk_monitor_base.domains.metric_plugin.manager.job.db2 import DB2PluginManager
from bk_monitor_base.metric_plugin import (
    MetricPlugin,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)


class TestDB2PluginManager:
    """测试 DB2PluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_db2_plugin",
            type="job_db2",
            name="测试DB2插件",
            description_md="测试DB2插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {},  # 标记支持 linux
                "sql_content": [
                    {
                        "classification_id": "db2_sql1",
                        "classification_name": "DB2-SQL-1",
                        "content": "SELECT 1 FROM SYSIBM.SYSDUMMY1;",
                    }
                ],
            },
            params=[
                MetricPluginParams(
                    name="user",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="用户名",
                    default="db2inst1",
                    required=True,
                ),
                MetricPluginParams(
                    name="password",
                    type=JobPluginParamsType.PASSWORD,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="密码",
                    default="",
                    required=True,
                ),
                MetricPluginParams(
                    name="host",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="服务地址",
                    default="127.0.0.1",
                    required=True,
                ),
                MetricPluginParams(
                    name="port",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="端口",
                    default="50000",
                    required=True,
                ),
            ],
            metrics=[],
        )
        self.plugin_manager = DB2PluginManager(self.plugin)

    def test_get_binary_path_linux(self):
        """测试获取二进制文件路径 - Linux"""
        path = self.plugin_manager.get_binary_path(OSType.LINUX)
        assert path == "job_plugin/job_db2/DB2UniversalPlugin"

    def test_get_binary_path_unsupported_os(self):
        """测试获取二进制文件路径 - 不支持的操作系统"""
        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_binary_path(OSType.WINDOWS)

        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_binary_path(OSType.LINUX_AARCH64)

        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_binary_path(OSType.AIX)

    def test_get_extra_file_source_paths_linux(self):
        """测试获取额外文件路径 - Linux"""
        extra_files = self.plugin_manager.get_extra_file_source_paths(OSType.LINUX)

        assert len(extra_files) == 1
        assert "job_plugin/job_db2/db2_driver/linuxx64_odbc_cli.tar.gz" in extra_files[0]

    def test_get_extra_file_source_paths_unsupported_os(self):
        """测试获取额外文件路径 - 不支持的操作系统"""
        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_extra_file_source_paths(OSType.WINDOWS)

        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_extra_file_source_paths(OSType.LINUX_AARCH64)

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_types = self.plugin_manager.get_supported_os_types()

        assert OSType.LINUX in supported_types
        # DB2 目前仅支持 Linux x86_64
        assert OSType.LINUX_AARCH64 not in supported_types
        assert OSType.WINDOWS not in supported_types
        assert OSType.AIX not in supported_types

    def test_type_class_variable(self):
        """测试类型类变量"""
        assert DB2PluginManager.type == "job_db2"

    def test_start_debug_scripts(self):
        """测试启动调试脚本配置"""
        # 验证 DB2 有自定义的启动调试脚本
        assert OSType.LINUX in DB2PluginManager.START_DEBUG_METRICS_SCRIPTS
        script = DB2PluginManager.START_DEBUG_METRICS_SCRIPTS[OSType.LINUX]

        # 验证脚本包含 DB2 ODBC 驱动安装逻辑
        assert "/data/IBM" in script
        assert "linuxx64_odbc_cli.tar.gz" in script
        assert "chmod +x {file_path}" in script
        assert "{file_path} -f {config_path} -debug true" in script

    def test_make_package(self, mocker: MockerFixture):
        """测试制作插件包"""
        # 模拟 _download_binary
        mock_download_path = Path("/tmp/mock_binary")
        mocker.patch.object(self.plugin_manager, "_download_binary", return_value=mock_download_path)

        # 模拟 _make_package
        mock_make_package = mocker.patch.object(
            self.plugin_manager, "_make_package", return_value=Path("/tmp/mock_pkg.tgz")
        )

        self.plugin_manager.make_package(is_compress=True)

        # 验证 _download_binary 被调用
        assert self.plugin_manager._download_binary.call_count == 1  # 仅支持 linux

        # 验证 _make_package 被调用
        mock_make_package.assert_called_once()
        assert mock_make_package.call_args.kwargs["is_compress"] is True
        assert "extra_files" in mock_make_package.call_args.kwargs

    def test_get_package_context(self):
        """测试获取插件包上下文"""
        context = self.plugin_manager._get_package_context()

        assert "plugin_id" in context
        assert context["plugin_id"] == "test_db2_plugin"
        assert "sql_content" in context
        assert len(context["sql_content"]) == 1

    def test_get_sql_content_json(self):
        """测试获取SQL内容JSON"""
        sql_content = self.plugin_manager.get_sql_content_json()

        assert len(sql_content) == 1
        assert sql_content[0]["classification_id"] == "db2_sql1"
        assert sql_content[0]["content"] == "SELECT 1 FROM SYSIBM.SYSDUMMY1;"

    def test_db2_driver_package_paths(self):
        """测试DB2驱动包路径配置"""
        assert OSType.LINUX in DB2PluginManager.DB2_DRIVER_PACKAGE_PATHS
        driver_path = DB2PluginManager.DB2_DRIVER_PACKAGE_PATHS[OSType.LINUX]
        assert driver_path == "db2_driver/linuxx64_odbc_cli.tar.gz"

    def test_binary_paths(self):
        """测试二进制文件路径配置"""
        assert OSType.LINUX in DB2PluginManager.BINARY_PATHS
        binary_path = DB2PluginManager.BINARY_PATHS[OSType.LINUX]
        assert binary_path == "DB2UniversalPlugin"
