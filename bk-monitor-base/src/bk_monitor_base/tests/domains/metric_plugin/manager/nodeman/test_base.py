"""
测试 NodemanPluginManager.parse_package 方法
"""

import json
import os
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import NodemanPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)


def create_test_plugin_package(
    plugin_name: str = "test_plugin",
    os_dir: str = "external_plugins_linux_x86_64",
    version: str = "1.0",
    meta_yaml_content: dict[str, Any] | None = None,
    has_version: bool = True,
    has_description_md: bool = True,
    description_md_content: str | None = None,
    has_release_md: bool = True,
    release_md_content: str | None = None,
    has_config_json: bool = True,
    config_json_content: list[dict[str, Any]] | None = None,
    has_metrics_json: bool = True,
    metrics_json_content: list[dict[str, Any]] | None = None,
    has_logo: bool = False,
) -> Path:
    """创建测试用的插件包文件

    Args:
        plugin_name: 插件名称
        os_dir: 操作系统目录名称
        version: 版本号字符串
        meta_yaml_content: meta.yaml 文件内容字典，如果为 None 则使用默认内容
        has_version: 是否包含 VERSION 文件
        has_description_md: 是否包含 description.md 文件
        description_md_content: description.md 文件内容，如果为 None 则使用默认内容
        has_release_md: 是否包含 release.md 文件
        release_md_content: release.md 文件内容，如果为 None 则使用默认内容
        has_config_json: 是否包含 config.json 文件
        config_json_content: config.json 文件内容列表，如果为 None 则使用默认内容
        has_metrics_json: 是否包含 metrics.json 文件
        metrics_json_content: metrics.json 文件内容列表，如果为 None 则使用默认内容
        has_logo: 是否包含 logo.png 文件

    Returns:
        插件包文件路径（临时文件）
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建目录结构: {os_dir}/{plugin_name}/
        plugin_base_dir = os.path.join(temp_dir, os_dir, plugin_name)
        os.makedirs(plugin_base_dir, exist_ok=True)

        # 创建 VERSION 文件
        if has_version:
            version_file = os.path.join(plugin_base_dir, "VERSION")
            with open(version_file, "w", encoding="utf-8") as f:
                f.write(version)

        # 创建 info 目录
        info_dir = os.path.join(plugin_base_dir, "info")
        os.makedirs(info_dir, exist_ok=True)

        # 创建 meta.yaml 文件
        if meta_yaml_content is not False:  # False 表示不创建文件
            if meta_yaml_content is None:
                meta_yaml_content = {
                    "plugin_id": plugin_name,
                    "plugin_display_name": f"{plugin_name} Display Name",
                    "plugin_type": "Script",
                    "tag": "",
                    "label": "component",
                    "is_support_remote": False,
                }
            meta_file = os.path.join(info_dir, "meta.yaml")
            with open(meta_file, "w", encoding="utf-8") as f:
                yaml.dump(meta_yaml_content, f, allow_unicode=True)

        # 创建 description.md 文件
        if has_description_md:
            description_file = os.path.join(info_dir, "description.md")
            content = (
                description_md_content if description_md_content is not None else "# 测试插件描述\n\n这是一个测试插件。"
            )
            with open(description_file, "w", encoding="utf-8") as f:
                f.write(content)

        # 创建 release.md 文件
        if has_release_md:
            release_file = os.path.join(info_dir, "release.md")
            content = release_md_content if release_md_content is not None else "# 版本日志\n\n初始版本"
            with open(release_file, "w", encoding="utf-8") as f:
                f.write(content)

        # 创建 config.json 文件
        if has_config_json:
            config_file = os.path.join(info_dir, "config.json")
            if config_json_content is None:
                config_json_content = [
                    {
                        "name": "test_param",
                        "type": NodemanPluginParamsType.TEXT.value,
                        "mode": NodemanPluginParamsMode.ENV.value,
                        "description": "测试参数",
                        "default": "test",
                        "required": True,
                    }
                ]
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_json_content, f, ensure_ascii=False, indent=4)

        # 创建 metrics.json 文件
        if has_metrics_json:
            metrics_file = os.path.join(info_dir, "metrics.json")
            if metrics_json_content is None:
                metrics_json_content = [
                    {
                        "table_name": "test_metric",
                        "fields": [
                            {
                                "name": "metric1",
                                "type": "double",
                                "monitor_type": "metric",
                            }
                        ],
                    }
                ]
            with open(metrics_file, "w", encoding="utf-8") as f:
                json.dump(metrics_json_content, f, ensure_ascii=False, indent=4)

        # 创建 logo.png 文件（创建一个简单的 PNG 文件头）
        if has_logo:
            logo_file = os.path.join(info_dir, "logo.png")
            # 创建一个最小的有效 PNG 文件（1x1 像素）
            png_data = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x01,
                    0x00,
                    0x00,
                    0x00,
                    0x01,
                    0x08,
                    0x06,
                    0x00,
                    0x00,
                    0x00,
                    0x1F,
                    0x15,
                    0xC4,
                    0x89,
                    0x00,
                    0x00,
                    0x00,
                    0x0A,
                    0x49,
                    0x44,
                    0x41,
                    0x54,
                    0x78,
                    0x9C,
                    0x63,
                    0x00,
                    0x01,
                    0x00,
                    0x00,
                    0x05,
                    0x00,
                    0x01,
                    0x0D,
                    0x0A,
                    0x2D,
                    0xB4,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                    0x49,
                    0x45,
                    0x4E,
                    0x44,
                    0xAE,
                    0x42,
                    0x60,
                    0x82,
                ]
            )
            with open(logo_file, "wb") as f:
                f.write(png_data)

        # 创建 tar.gz 文件
        tar_buffer = BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            tar.add(os.path.join(temp_dir, os_dir), arcname=os_dir)

        tar_buffer.seek(0)

        # 将 tar.gz 内容写入临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tgz")
        temp_file.write(tar_buffer.getvalue())
        temp_file.close()

        return Path(temp_file.name)


class MockNodemanPluginManager(NodemanPluginManager):
    """Mock 的 NodemanPluginManager 类，用于测试 parse_package 方法"""

    @classmethod
    def _parse_define(
        cls, bk_tenant_id: str, operator: str, extract_dir: Path, plugin_id: str, meta_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Mock 的 _parse_define 方法"""
        return {"mock_define": True, "plugin_id": plugin_id}

    def get_supported_os_types(self):
        """Mock 方法"""
        return []

    def make_package(self, is_compress: bool = True) -> Path:
        """Mock 方法"""
        raise NotImplementedError


class TestNodemanPluginManagerParsePackage:
    """测试 NodemanPluginManager.parse_package 方法"""

    def test_parse_package_success(self, tmp_path: Path):
        """测试解析完整插件包 - 成功场景"""
        # 创建完整的测试插件包
        package_file = create_test_plugin_package(
            plugin_name="test_plugin",
            version="2.5",
            meta_yaml_content={
                "plugin_id": "test_plugin",
                "plugin_display_name": "测试插件",
                "plugin_type": "Script",
                "tag": "",
                "label": "component",
                "is_support_remote": True,
            },
            description_md_content="# 测试插件\n\n这是一个完整的测试插件。",
            release_md_content="# 版本日志\n\n版本 2.5",
            has_logo=True,
        )

        try:
            # 执行解析
            result = MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
            )

            # 验证返回结果类型
            assert isinstance(result, CreatePluginParams)

            # 验证各字段值
            assert result.id == "test_plugin"
            assert result.type == "Script".lower()  # 使用 meta.yaml 中的 plugin_type，并转换为小写
            assert result.name == "测试插件"  # 使用 meta.yaml 中的 plugin_display_name
            assert result.description_md == "# 测试插件\n\n这是一个完整的测试插件。"
            assert result.label == "component"
            assert result.logo != ""  # logo 文件路径不为空
            assert result.is_support_remote is True
            assert result.version == VersionTuple(major=2, minor=5)
            assert result.version_log == "# 版本日志\n\n版本 2.5"
            assert result.status == MetricPluginStatus.DEBUG
            assert len(result.params) == 1
            assert result.params[0].name == "test_param"
            assert len(result.metrics) == 1
            assert result.metrics[0].table_name == "test_metric"
            assert result.define == {"mock_define": True, "plugin_id": "test_plugin"}

            # 验证临时目录已被清理（通过检查 package_file 的父目录中不应该有解压目录）
            # 注意：由于解压目录是随机生成的，我们无法直接验证，但可以通过异常来间接验证
        finally:
            # 清理测试文件
            if package_file.exists():
                package_file.unlink()

    @pytest.mark.parametrize(
        "missing_file,expected_error_msg",
        [
            ("VERSION", "插件包缺少 VERSION 文件"),
            ("meta.yaml", "插件包缺少 meta.yaml 文件"),
        ],
    )
    def test_parse_package_missing_required_files(self, missing_file: str, expected_error_msg: str, tmp_path: Path):
        """测试解析插件包 - 缺少必需文件"""
        # 根据缺失的文件创建插件包
        kwargs = {
            "has_version": missing_file != "VERSION",
            "has_description_md": True,
            "has_release_md": True,
            "has_config_json": True,
            "has_metrics_json": True,
        }
        if missing_file == "meta.yaml":
            kwargs["meta_yaml_content"] = False  # False 表示不创建 meta.yaml

        package_file = create_test_plugin_package(**kwargs)

        try:
            # 执行解析，应该抛出异常
            with pytest.raises(ValueError, match=expected_error_msg):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_missing_optional_files(self, tmp_path: Path):
        """测试解析插件包 - 缺少可选文件（应返回默认值）"""
        # 创建不包含可选文件的插件包
        package_file = create_test_plugin_package(
            has_description_md=False,
            has_release_md=False,
            has_config_json=False,
            has_metrics_json=False,
            has_logo=False,
        )

        try:
            # 执行解析
            result = MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
            )

            # 验证可选文件缺失时返回默认值
            assert result.description_md == ""
            assert result.version_log == ""
            assert result.params == []
            assert result.metrics == []
            assert result.logo == ""
        finally:
            if package_file.exists():
                package_file.unlink()

    @pytest.mark.parametrize(
        "file_name,invalid_content,expected_error_msg",
        [
            ("VERSION", "invalid_version", "版本格式错误"),
            ("VERSION", "1", "版本格式错误"),
            ("VERSION", "1.2.3", "版本格式错误"),
            (
                "meta.yaml",
                "not: yaml: format: [",
                "无法确定插件ID|无法确定插件类型",
            ),  # 无效 YAML 会抛出 ScannerError，但会被捕获并转换为 ValueError
        ],
    )
    def test_parse_package_invalid_file_format(
        self, file_name: str, invalid_content: str, expected_error_msg: str, tmp_path: Path
    ):
        """测试解析插件包 - 文件格式错误"""
        # 创建包含格式错误文件的插件包
        if file_name == "VERSION":
            package_file = create_test_plugin_package(version=invalid_content)
        elif file_name == "meta.yaml":
            # 创建一个包含无效 YAML 的插件包
            with tempfile.TemporaryDirectory() as temp_dir:
                os_dir = "external_plugins_linux_x86_64"
                plugin_name = "test_plugin"
                plugin_base_dir = os.path.join(temp_dir, os_dir, plugin_name)
                os.makedirs(plugin_base_dir, exist_ok=True)

                # 创建 VERSION 文件
                version_file = os.path.join(plugin_base_dir, "VERSION")
                with open(version_file, "w", encoding="utf-8") as f:
                    f.write("1.0")

                # 创建 info 目录和无效的 meta.yaml
                info_dir = os.path.join(plugin_base_dir, "info")
                os.makedirs(info_dir, exist_ok=True)
                meta_file = os.path.join(info_dir, "meta.yaml")
                with open(meta_file, "w", encoding="utf-8") as f:
                    f.write(invalid_content)

                # 创建 tar.gz 文件
                tar_buffer = BytesIO()
                with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                    tar.add(os.path.join(temp_dir, os_dir), arcname=os_dir)

                tar_buffer.seek(0)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tgz")
                temp_file.write(tar_buffer.getvalue())
                temp_file.close()
                package_file = Path(temp_file.name)

        try:
            # 执行解析，应该抛出异常（可能是 yaml.scanner.ScannerError 或 ValueError）
            # 无效 YAML 会抛出 yaml.scanner.ScannerError，但代码可能会捕获并转换为其他异常
            with pytest.raises((ValueError, yaml.scanner.ScannerError, yaml.parser.ParserError)):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_missing_meta_fields(self, tmp_path: Path):
        """测试解析插件包 - meta.yaml 缺少必需字段"""
        # 创建缺少必需字段的 meta.yaml
        package_file = create_test_plugin_package(
            meta_yaml_content={
                "plugin_display_name": "测试插件",
                # 缺少 plugin_id 和 plugin_type
            }
        )

        try:
            # 执行解析，应该抛出异常
            with pytest.raises(ValueError, match="无法确定插件ID|无法确定插件类型"):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_invalid_config_json_format(self, tmp_path: Path):
        """测试解析插件包 - config.json 格式错误（不是列表）"""
        # 创建包含无效 config.json 的插件包
        with tempfile.TemporaryDirectory() as temp_dir:
            os_dir = "external_plugins_linux_x86_64"
            plugin_name = "test_plugin"
            plugin_base_dir = os.path.join(temp_dir, os_dir, plugin_name)
            os.makedirs(plugin_base_dir, exist_ok=True)

            # 创建必需文件
            version_file = os.path.join(plugin_base_dir, "VERSION")
            with open(version_file, "w", encoding="utf-8") as f:
                f.write("1.0")

            info_dir = os.path.join(plugin_base_dir, "info")
            os.makedirs(info_dir, exist_ok=True)

            # 创建 meta.yaml
            meta_content = {
                "plugin_id": plugin_name,
                "plugin_display_name": "测试插件",
                "plugin_type": "Script",
                "label": "component",
            }
            meta_file = os.path.join(info_dir, "meta.yaml")
            with open(meta_file, "w", encoding="utf-8") as f:
                yaml.dump(meta_content, f, allow_unicode=True)

            # 创建无效的 config.json（不是列表）
            config_file = os.path.join(info_dir, "config.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"invalid": "format"}, f)

            # 创建 tar.gz 文件
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                tar.add(os.path.join(temp_dir, os_dir), arcname=os_dir)

            tar_buffer.seek(0)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tgz")
            temp_file.write(tar_buffer.getvalue())
            temp_file.close()
            package_file = Path(temp_file.name)

        try:
            # 执行解析，应该抛出异常
            with pytest.raises(ValueError, match="config.json 必须是列表格式"):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_invalid_metrics_json_format(self, tmp_path: Path):
        """测试解析插件包 - metrics.json 格式错误（不是列表）"""
        # 创建包含无效 metrics.json 的插件包
        with tempfile.TemporaryDirectory() as temp_dir:
            os_dir = "external_plugins_linux_x86_64"
            plugin_name = "test_plugin"
            plugin_base_dir = os.path.join(temp_dir, os_dir, plugin_name)
            os.makedirs(plugin_base_dir, exist_ok=True)

            # 创建必需文件
            version_file = os.path.join(plugin_base_dir, "VERSION")
            with open(version_file, "w", encoding="utf-8") as f:
                f.write("1.0")

            info_dir = os.path.join(plugin_base_dir, "info")
            os.makedirs(info_dir, exist_ok=True)

            # 创建 meta.yaml
            meta_content = {
                "plugin_id": plugin_name,
                "plugin_display_name": "测试插件",
                "plugin_type": "Script",
                "label": "component",
            }
            meta_file = os.path.join(info_dir, "meta.yaml")
            with open(meta_file, "w", encoding="utf-8") as f:
                yaml.dump(meta_content, f, allow_unicode=True)

            # 创建无效的 metrics.json（不是列表）
            metrics_file = os.path.join(info_dir, "metrics.json")
            with open(metrics_file, "w", encoding="utf-8") as f:
                json.dump({"invalid": "format"}, f)

            # 创建 tar.gz 文件
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                tar.add(os.path.join(temp_dir, os_dir), arcname=os_dir)

            tar_buffer.seek(0)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tgz")
            temp_file.write(tar_buffer.getvalue())
            temp_file.close()
            package_file = Path(temp_file.name)

        try:
            # 执行解析，应该抛出异常
            with pytest.raises(ValueError, match="metrics.json 必须是列表格式"):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )
        finally:
            if package_file.exists():
                package_file.unlink()

    @pytest.mark.parametrize(
        "os_dir",
        [
            "external_plugins_linux_x86_64",
            "external_plugins_windows_x86_64",
            "external_plugins_linux_aarch64",
        ],
    )
    def test_parse_package_different_os_directories(self, os_dir: str, tmp_path: Path):
        """测试解析插件包 - 不同操作系统目录"""
        package_file = create_test_plugin_package(os_dir=os_dir)

        try:
            # 执行解析
            result = MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
            )

            # 验证解析成功
            assert isinstance(result, CreatePluginParams)
            assert result.id == "test_plugin"
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_multiple_os_directories(self, tmp_path: Path):
        """测试解析插件包 - 多个操作系统目录存在时选择第一个"""
        # 创建包含多个操作系统目录的插件包
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建第一个操作系统目录
            os_dir1 = "external_plugins_linux_x86_64"
            plugin_name1 = "test_plugin_linux"
            plugin_base_dir1 = os.path.join(temp_dir, os_dir1, plugin_name1)
            os.makedirs(plugin_base_dir1, exist_ok=True)

            version_file1 = os.path.join(plugin_base_dir1, "VERSION")
            with open(version_file1, "w", encoding="utf-8") as f:
                f.write("1.0")

            info_dir1 = os.path.join(plugin_base_dir1, "info")
            os.makedirs(info_dir1, exist_ok=True)

            meta_content1 = {
                "plugin_id": "test_plugin_linux",
                "plugin_display_name": "Linux 插件",
                "plugin_type": "Script",
                "label": "component",
            }
            meta_file1 = os.path.join(info_dir1, "meta.yaml")
            with open(meta_file1, "w", encoding="utf-8") as f:
                yaml.dump(meta_content1, f, allow_unicode=True)

            # 创建第二个操作系统目录
            os_dir2 = "external_plugins_windows_x86_64"
            plugin_name2 = "test_plugin_windows"
            plugin_base_dir2 = os.path.join(temp_dir, os_dir2, plugin_name2)
            os.makedirs(plugin_base_dir2, exist_ok=True)

            version_file2 = os.path.join(plugin_base_dir2, "VERSION")
            with open(version_file2, "w", encoding="utf-8") as f:
                f.write("2.0")

            info_dir2 = os.path.join(plugin_base_dir2, "info")
            os.makedirs(info_dir2, exist_ok=True)

            meta_content2 = {
                "plugin_id": "test_plugin_windows",
                "plugin_display_name": "Windows 插件",
                "plugin_type": "Script",
                "label": "component",
            }
            meta_file2 = os.path.join(info_dir2, "meta.yaml")
            with open(meta_file2, "w", encoding="utf-8") as f:
                yaml.dump(meta_content2, f, allow_unicode=True)

            # 创建 tar.gz 文件
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                tar.add(os.path.join(temp_dir, os_dir1), arcname=os_dir1)
                tar.add(os.path.join(temp_dir, os_dir2), arcname=os_dir2)

            tar_buffer.seek(0)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tgz")
            temp_file.write(tar_buffer.getvalue())
            temp_file.close()
            package_file = Path(temp_file.name)

        try:
            # 执行解析
            result = MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
            )

            # 验证选择了第一个找到的插件目录（顺序可能因文件系统而异，但应该能成功解析）
            assert isinstance(result, CreatePluginParams)
            # 由于文件系统顺序不确定，我们只验证能成功解析即可
            assert result.id in ["test_plugin_linux", "test_plugin_windows"]
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_invalid_tar_file(self, tmp_path: Path):
        """测试解析插件包 - 无效的 tar.gz 文件"""
        # 创建一个无效的 tar.gz 文件
        invalid_file = tmp_path / "invalid.tgz"
        invalid_file.write_bytes(b"invalid tar content")

        # 执行解析，应该抛出异常（tarfile 会抛出 tarfile.TarError 或 OSError）
        with pytest.raises((tarfile.TarError, OSError, ValueError)):
            MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=invalid_file, operator="test_user"
            )

    def test_parse_package_no_plugin_directory(self, tmp_path: Path):
        """测试解析插件包 - 找不到有效的插件目录"""
        # 创建一个不包含有效插件目录的 tar.gz 文件
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建一个无效的目录结构
            invalid_dir = os.path.join(temp_dir, "invalid_dir")
            os.makedirs(invalid_dir, exist_ok=True)

            # 创建 tar.gz 文件
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                tar.add(invalid_dir, arcname="invalid_dir")

            tar_buffer.seek(0)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tgz")
            temp_file.write(tar_buffer.getvalue())
            temp_file.close()
            package_file = Path(temp_file.name)

        try:
            # 执行解析，应该抛出异常
            with pytest.raises(ValueError, match="插件包中未找到有效的插件目录"):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_parse_define_called(self, mocker: MockerFixture, tmp_path: Path):
        """测试解析插件包 - 验证 _parse_define 方法被正确调用"""
        package_file = create_test_plugin_package()

        try:
            # Mock _parse_define 方法
            mock_parse_define = mocker.patch.object(
                MockNodemanPluginManager, "_parse_define", return_value={"mock_define": True}
            )

            # 执行解析
            result = MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
            )

            # 验证 _parse_define 被调用
            assert mock_parse_define.called
            call_args = mock_parse_define.call_args
            assert call_args[0][0] == "test_tenant"  # bk_tenant_id
            assert call_args[0][1] == "test_user"  # operator
            assert call_args[0][3] == "test_plugin"  # plugin_id
            assert isinstance(call_args[0][2], Path)  # extract_dir
            assert isinstance(call_args[0][4], dict)  # meta_data

            # 验证返回结果中包含 define
            assert result.define == {"mock_define": True}
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_temp_dir_cleanup(self, mocker: MockerFixture, tmp_path: Path):
        """测试解析插件包 - 验证临时目录被清理"""
        package_file = create_test_plugin_package()

        try:
            # Mock shutil.rmtree 来验证清理操作
            mock_rmtree = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.node_man.base.shutil.rmtree")

            # 执行解析
            result = MockNodemanPluginManager.parse_package(
                bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
            )

            # 验证解析成功
            assert isinstance(result, CreatePluginParams)

            # 验证 shutil.rmtree 被调用（用于清理临时目录）
            assert mock_rmtree.called
        finally:
            if package_file.exists():
                package_file.unlink()

    def test_parse_package_temp_dir_cleanup_on_exception(self, mocker: MockerFixture, tmp_path: Path):
        """测试解析插件包 - 验证异常时临时目录也被清理"""
        # 创建一个缺少必需文件的插件包
        package_file = create_test_plugin_package(has_version=False)

        try:
            # Mock shutil.rmtree 来验证清理操作
            mock_rmtree = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.node_man.base.shutil.rmtree")

            # 执行解析，应该抛出异常
            with pytest.raises(ValueError):
                MockNodemanPluginManager.parse_package(
                    bk_tenant_id="test_tenant", package_file=package_file, operator="test_user"
                )

            # 验证即使发生异常，shutil.rmtree 也被调用（finally 块执行）
            assert mock_rmtree.called
        finally:
            if package_file.exists():
                package_file.unlink()


@pytest.mark.django_db(databases=["default"])
class TestNodemanPluginManagerRelease:
    """测试 NodemanPluginManager.release_plugin_version 方法"""

    def test_release_plugin_version_supports_apply_data_link_flag(self, mocker: MockerFixture):
        """测试发布时可透传 apply_data_link 参数给基类"""
        fake_manager = mocker.MagicMock(spec=NodemanPluginManager)
        fake_manager.config_files = []
        fake_manager.plugin = SimpleNamespace(
            bk_tenant_id="test_tenant",
            id="test_plugin",
            version=VersionTuple(major=1, minor=0),
            version_str=lambda: "1.0.0",
        )
        fake_manager._log = mocker.MagicMock()

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.base.get_plugin_info",
            return_value=[SimpleNamespace(md5="mock_md5")],
        )
        mocker.patch("bk_monitor_base.domains.metric_plugin.manager.node_man.base.release_plugin")
        mock_super_release = mocker.patch.object(BaseMetricPluginManager, "release_plugin_version")

        NodemanPluginManager.release_plugin_version(fake_manager, operator="admin", apply_data_link=False)

        mock_super_release.assert_called_once_with(
            operator="admin",
            apply_data_link=False,
            md5_list=["mock_md5"],
        )
