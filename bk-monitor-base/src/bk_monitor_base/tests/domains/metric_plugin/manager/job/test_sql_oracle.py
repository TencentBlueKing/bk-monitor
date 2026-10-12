from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.errors import ParseOsTypeError
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.base import JobPluginParamsMode, JobPluginParamsType
from bk_monitor_base.domains.metric_plugin.manager.job.oracle import OraclePluginManager
from bk_monitor_base.metric_plugin import (
    MetricPlugin,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)


class TestOraclePluginManager:
    """测试 OraclePluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_oracle_plugin",
            type="job_oracle",
            name="测试Oracle插件",
            description_md="测试Oracle插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {},  # 标记支持 linux
                "linux_aarch64": {},  # 标记支持 linux_aarch64
                "sql_content": [
                    {
                        "classification_id": "oracle_sql1",
                        "classification_name": "Oracle-SQL-1",
                        "content": "SELECT 1 FROM DUAL;",
                    }
                ],
            },
            params=[
                MetricPluginParams(
                    name="user",
                    type=JobPluginParamsType.TEXT,
                    mode=JobPluginParamsMode.OPT_CMD,
                    description="用户名",
                    default="oracle",
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
                    default="1521",
                    required=True,
                ),
            ],
            metrics=[],
        )
        self.plugin_manager = OraclePluginManager(self.plugin)

    def test_get_binary_path_linux(self):
        """测试获取二进制文件路径 - Linux"""
        path = self.plugin_manager.get_binary_path(OSType.LINUX)
        assert path == "job_plugin/job_oracle/OracleUniversalPlugin"

    def test_get_binary_path_linux_aarch64(self):
        """测试获取二进制文件路径 - Linux AArch64"""
        path = self.plugin_manager.get_binary_path(OSType.LINUX_AARCH64)
        assert path == "job_plugin/job_oracle/OracleUniversalPlugin_arm"

    def test_get_binary_path_unsupported_os(self):
        """测试获取二进制文件路径 - 不支持的操作系统"""
        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_binary_path(OSType.WINDOWS)

        with pytest.raises(ParseOsTypeError):
            self.plugin_manager.get_binary_path(OSType.AIX)

    def test_get_extra_file_source_paths(self):
        """测试获取额外文件路径 - Oracle不需要额外文件"""
        extra_files = self.plugin_manager.get_extra_file_source_paths(OSType.LINUX)
        assert extra_files == []

        extra_files_arm = self.plugin_manager.get_extra_file_source_paths(OSType.LINUX_AARCH64)
        assert extra_files_arm == []

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_types = self.plugin_manager.get_supported_os_types()

        assert OSType.LINUX in supported_types
        assert OSType.LINUX_AARCH64 in supported_types
        assert OSType.WINDOWS not in supported_types
        assert OSType.AIX not in supported_types

    def test_get_supported_os_types_uses_binary_paths_when_define_only_marks_linux(self):
        """测试支持的操作系统类型由插件二进制能力声明决定"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_oracle_plugin_linux_only",
            type="job_oracle",
            name="测试Oracle插件",
            description_md="测试插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "linux": {},  # 仅支持 linux
                "sql_content": [],
            },
            params=[],
            metrics=[],
        )
        manager = OraclePluginManager(plugin)

        supported_types = manager.get_supported_os_types()
        assert supported_types == list(OraclePluginManager.BINARY_PATHS)

    def test_get_supported_os_types_matches_binary_paths_order(self):
        """测试支持系统列表与二进制路径声明顺序保持一致"""
        assert self.plugin_manager.get_supported_os_types() == list(OraclePluginManager.BINARY_PATHS)

    def test_type_class_variable(self):
        """测试类型类变量"""
        assert OraclePluginManager.type == "job_oracle"

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
        assert self.plugin_manager._download_binary.call_count == 2  # 支持 linux 和 linux_aarch64

        # 验证 _make_package 被调用
        mock_make_package.assert_called_once()
        assert mock_make_package.call_args.kwargs["is_compress"] is True
        assert "extra_files" in mock_make_package.call_args.kwargs

    def test_get_package_context(self):
        """测试获取插件包上下文"""
        context = self.plugin_manager._get_package_context()

        assert "plugin_id" in context
        assert context["plugin_id"] == "test_oracle_plugin"
        assert "sql_content" in context
        assert len(context["sql_content"]) == 1

    def test_get_sql_content_json(self):
        """测试获取SQL内容JSON"""
        sql_content = self.plugin_manager.get_sql_content_json()

        assert len(sql_content) == 1
        assert sql_content[0]["classification_id"] == "oracle_sql1"
        assert sql_content[0]["content"] == "SELECT 1 FROM DUAL;"
