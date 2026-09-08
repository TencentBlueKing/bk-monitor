import base64
import json
import logging
import os
import shutil
import tarfile
import tempfile
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Self, cast

import yaml

from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginMetricGroup,
    MetricPluginParams,
    UpdatePluginVersionParams,
    VersionTuple,
    parse_version,
)
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError
from bk_monitor_base.domains.metric_plugin.models import MAX_LOGO_SIZE_BYTES, MetricPluginModel

logger = logging.getLogger(__name__)


class OSType(StrEnum):
    """
    操作系统类型
    """

    LINUX = "linux"
    WINDOWS = "windows"
    AIX = "aix"
    LINUX_AARCH64 = "linux_aarch64"


class BaseMetricPluginManager(ABC):
    """
    指标插件管理器基类

    要求支持导入的插件必须在os_arch-plugin_name-info-meta.yaml的plugin_type中声明插件类型（与管理器type一致）
    """

    type: ClassVar[str]

    def __init__(self, plugin: MetricPlugin, plugin_model: MetricPluginModel | None = None):
        self.plugin: MetricPlugin = plugin

    def _get_plugin_model(self) -> MetricPluginModel:
        """获取插件数据模型"""
        plugin_model = MetricPluginModel.objects.filter(
            bk_tenant_id=self.plugin.bk_tenant_id, plugin_id=self.plugin.id
        ).first()
        if not plugin_model:
            raise MetricPluginNotFoundError(f"插件不存在: {self.plugin.bk_tenant_id}/{self.plugin.id}")
        return plugin_model

    def apply_data_link(self, operator: str) -> Any:  # pyright: ignore[reportUnusedParameter]
        """申请数据链路

        创建数据ID和结果表, 存入插件的related_params中，函数可重入，多次调用不会重复申请数据链路。

        Args:
            operator: 操作人
        """
        return None

    def apply_data_link_with_deployment(self, deployment: MetricPluginDeployment, operator: str) -> Any:  # pyright: ignore[reportUnusedParameter]
        """申请数据链路(基于插件部署项)

        Args:
            deployment: 插件部署项
            operator: 操作人
        """
        return None

    def delete_data_link(self, operator: str) -> Any:  # pyright: ignore[reportUnusedParameter]
        """删除数据链路

        删除数据ID和结果表相关配置，函数可重入，多次调用不会有影响。

        Args:
            operator: 操作人
        """
        return None

    def delete_data_link_with_deployment(self, deployment: MetricPluginDeployment, operator: str) -> Any:  # pyright: ignore[reportUnusedParameter]
        """删除数据链路(基于插件部署项)

        Args:
            deployment: 插件部署项
            operator: 操作人
        """
        return None

    def refresh_metrics(self, operator: str) -> None:  # pyright: ignore[reportUnusedParameter]
        """刷新插件指标配置。"""
        return None

    @abstractmethod
    def get_supported_os_types(self) -> list[OSType]:
        """
        获取支持的操作系统类型
        """
        pass

    @classmethod
    def create_plugin(
        cls,
        bk_tenant_id: str,
        bk_biz_id: int,
        params: CreatePluginParams,
        operator: str,
    ) -> Self:
        """创建插件"""
        # 创建插件数据模型
        metric_plugin = MetricPluginModel.create_plugin(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            params=params,
            operator=operator,
        )
        return cls(plugin=metric_plugin)

    def create_plugin_version(self, params: CreatePluginVersionParams, operator: str):
        """创建新插件版本

        Args:
            params: 创建插件版本参数
            operator: 操作人
        Returns:
            (版本是否变更, 版本号)

        Raises:
            PluginVersionReleasedError: 插件版本已发布，无法创建新版本
            PluginVersionLessThanReleasedError: 插件版本小于已发布版本，无法创建新版本
        """
        plugin_model = self._get_plugin_model()

        # 创建插件版本数据模型
        version_changed, version = plugin_model.create_plugin_version(params=params, operator=operator)

        # 更新管理器中的插件对象
        self.plugin = plugin_model.to_plugin(version=version)

        return version_changed, version

    def update_plugin_version(self, params: UpdatePluginVersionParams, operator: str):
        """更新插件版本"""
        plugin_model = self._get_plugin_model()

        # 更新插件版本数据模型
        plugin_model.update_plugin_version(version=self.plugin.version, params=params, operator=operator)

        # 更新管理器中的插件对象
        self.plugin = plugin_model.to_plugin(version=self.plugin.version)

    @abstractmethod
    def register(self, operator: str) -> list[str]:
        """注册插件"""
        pass

    def release_plugin_version(
        self, operator: str, apply_data_link: bool = True, md5_list: list[str] | None = None
    ) -> None:
        """发布插件版本

        Args:
            operator: 操作人
            apply_data_link: 是否申请数据链路
            md5_list: 保留给子类发布流程使用的插件包 MD5 列表，基类实现不直接消费
        """
        plugin_model = self._get_plugin_model()
        # 基类保留该参数以兼容不同子类的发布流程和统一调用入口。
        del md5_list

        if apply_data_link:
            # 申请数据链路
            self.apply_data_link(operator=operator)

        # 更新插件版本状态为已发布
        plugin_model.release_plugin_version(version=self.plugin.version, operator=operator)

        # 更新管理器中的插件对象
        self.plugin.status = MetricPluginStatus.RELEASE

    def delete_plugin(self, operator: str) -> None:
        """删除插件"""
        plugin_model = self._get_plugin_model()

        # 删除数据链路
        self.delete_data_link(operator=operator)

        # 删除插件
        plugin_model.is_deleted = True
        plugin_model.save(update_fields=["is_deleted"])

    @staticmethod
    def _safe_tar_extract(tar: tarfile.TarFile, dest: Path) -> None:
        """安全解压 tar 归档，防御 Tar Slip（CVE-2007-4559）路径穿越攻击。

        校验策略：
        1. 对每个成员，检查其解压后的真实路径是否逃逸出目标目录（防御 ``..`` 和绝对路径）。
        2. 对符号链接 / 硬链接成员，额外检查链接目标路径是否指向目标目录之外
           （防御通过符号链接间接穿越的攻击手法）。

        Args:
            tar: 已打开的 TarFile 对象
            dest: 解压目标目录

        Raises:
            ValueError: 归档成员路径穿越到目标目录之外
        """
        abs_dest = os.path.realpath(str(dest))
        abs_dest_prefix = abs_dest + os.sep

        def _is_within_dest(path: str) -> bool:
            return path == abs_dest or path.startswith(abs_dest_prefix)

        for member in tar.getmembers():
            member_path = os.path.join(dest, member.name)
            abs_member_path = os.path.realpath(member_path)
            if not _is_within_dest(abs_member_path):
                raise ValueError(f"检测到路径穿越，拒绝解压恶意成员: {member.name}")

            if member.issym() or member.islnk():
                if os.path.isabs(member.linkname):
                    link_target = os.path.realpath(member.linkname)
                else:
                    link_target = os.path.realpath(os.path.join(os.path.dirname(member_path), member.linkname))
                if not _is_within_dest(link_target):
                    raise ValueError(f"检测到路径穿越，拒绝解压恶意链接成员: {member.name} -> {member.linkname}")

        tar.extractall(dest)  # nosec

    @classmethod
    def _extract_package(cls, package_file: Path) -> Path:
        """解压插件包到临时目录

        Args:
            package_file: 插件包文件路径

        Returns:
            解压后的临时目录路径
        """
        logger.info(f"开始解析插件包: {package_file}")
        extract_dir = Path(tempfile.mkdtemp())
        with tarfile.open(package_file, "r:gz") as tar:
            cls._safe_tar_extract(tar, extract_dir)
        logger.info(f"插件包解压到临时目录: {extract_dir}")
        return extract_dir

    @classmethod
    def extract_package(cls, package_file: Path) -> Path:
        """解压插件包到临时目录。"""
        return cls._extract_package(package_file)

    @classmethod
    def _find_plugin_dir(cls, extract_dir: Path) -> tuple[Path, str]:
        """查找插件目录

        Args:
            extract_dir: 解压后的根目录

        Returns:
            (插件目录路径, 插件名称)

        Raises:
            ValueError: 如果未找到有效的插件目录
        """
        for os_plugin_dir in extract_dir.iterdir():
            if not os_plugin_dir.is_dir() or not os_plugin_dir.name.startswith("external_plugins_"):
                continue

            # 查找该操作系统目录下的插件目录
            for sub_dir in os_plugin_dir.iterdir():
                if sub_dir.is_dir():
                    plugin_dir = sub_dir
                    plugin_name = sub_dir.name
                    logger.info(f"找到插件目录: {plugin_dir}")
                    return plugin_dir, plugin_name
        raise ValueError(f"插件包中未找到有效的插件目录: {extract_dir}")

    @classmethod
    def _find_plugin_type_meta_file(cls, extract_dir: Path) -> Path:
        """查找可用于识别插件类型的 meta.yaml 文件。"""
        plugin_dir, _ = cls._find_plugin_dir(extract_dir)
        meta_file = plugin_dir / "info" / "meta.yaml"
        if not meta_file.exists():
            raise ValueError(f"插件包缺少 meta.yaml 文件: {meta_file}")
        return meta_file

    @classmethod
    def find_plugin_type_meta_file(cls, extract_dir: Path) -> Path:
        """查找可用于识别插件类型的 meta.yaml 文件。"""
        return cls._find_plugin_type_meta_file(extract_dir)

    @classmethod
    def _parse_version_file(cls, plugin_dir: Path) -> VersionTuple:
        """解析 VERSION 文件

        Args:
            plugin_dir: 插件目录路径

        Returns:
            版本号元组

        Raises:
            ValueError: 如果 VERSION 文件不存在或格式错误
        """
        version_file = plugin_dir / "VERSION"
        if not version_file.exists():
            raise ValueError(f"插件包缺少 VERSION 文件: {version_file}")

        version_str = version_file.read_text(encoding="utf-8").strip()
        version = parse_version(version_str)
        logger.info(f"解析版本号: {version_str} -> {version}")
        return version

    @classmethod
    def _parse_description_md(cls, plugin_dir: Path) -> str:
        """解析 description.md 文件

        Args:
            plugin_dir: 插件目录路径

        Returns:
            描述内容，如果文件不存在则返回空字符串
        """
        description_file = plugin_dir / "info" / "description.md"
        if not description_file.exists():
            return ""

        description_md = description_file.read_text(encoding="utf-8")
        logger.info(f"读取 description.md，长度: {len(description_md)} 字符")
        return description_md

    @classmethod
    def _parse_meta_yaml(cls, plugin_dir: Path, plugin_name: str) -> tuple[dict[str, Any], str, str, str, str, bool]:
        """解析 meta.yaml 文件并提取基本信息

        Args:
            plugin_dir: 插件目录路径
            plugin_name: 插件名称（作为后备值）

        Returns:
            (meta_data, plugin_id, plugin_display_name, plugin_type, label, is_support_remote)

        Raises:
            ValueError: 如果 meta.yaml 文件不存在或缺少必要字段
        """
        meta_file = plugin_dir / "info" / "meta.yaml"
        if not meta_file.exists():
            raise ValueError(f"插件包缺少 meta.yaml 文件: {meta_file}")

        with open(meta_file, encoding="utf-8") as f:
            meta_data_raw: Any = yaml.safe_load(f)
        meta_data: dict[str, Any] = cast(dict[str, Any], meta_data_raw) if isinstance(meta_data_raw, dict) else {}
        logger.info(f"解析 meta.yaml: {meta_data}")

        # 从 meta.yaml 中提取基本信息
        plugin_id: str = str(meta_data.get("plugin_id", "")) or plugin_name
        plugin_display_name: str = str(meta_data.get("plugin_display_name", "")) or plugin_name
        plugin_type: str = str(meta_data.get("plugin_type", "")) or ""
        label: str = str(meta_data.get("label", "")) or ""
        is_support_remote: bool = bool(meta_data.get("is_support_remote", False))

        if not plugin_id:
            raise ValueError(f"无法确定插件ID，meta.yaml 中缺少 plugin_id 字段: {meta_file}")
        if not plugin_type:
            raise ValueError(f"无法确定插件类型，meta.yaml 中缺少 plugin_type 字段: {meta_file}")

        return (
            meta_data,
            plugin_id,
            plugin_display_name,
            plugin_type,
            label,
            is_support_remote,
        )

    @classmethod
    def _parse_release_md(cls, plugin_dir: Path) -> str:
        """解析 release.md 文件

        Args:
            plugin_dir: 插件目录路径

        Returns:
            版本日志内容，如果文件不存在则返回空字符串
        """
        release_file = plugin_dir / "info" / "release.md"
        if not release_file.exists():
            return ""

        version_log = release_file.read_text(encoding="utf-8")
        logger.info(f"读取 release.md，长度: {len(version_log)} 字符")
        return version_log

    @classmethod
    def _parse_config_json(cls, plugin_dir: Path) -> list[MetricPluginParams]:
        """解析 config.json 文件

        Args:
            plugin_dir: 插件目录路径

        Returns:
            参数配置列表，如果文件不存在则返回空列表

        Raises:
            ValueError: 如果 config.json 格式不正确（不是列表）
        """
        config_file = plugin_dir / "info" / "config.json"
        if not config_file.exists():
            return []

        with open(config_file, encoding="utf-8") as f:
            config_data: Any = json.load(f)

        # 只允许列表格式，直接交给 pydantic 校验
        if not isinstance(config_data, list):
            raise ValueError(f"config.json 必须是列表格式，当前格式: {type(config_data).__name__}")

        params = [
            MetricPluginParams(**item)  # pyright: ignore[reportUnknownArgumentType]
            for item in config_data  # pyright: ignore[reportUnknownVariableType]
        ]

        logger.info(f"解析 config.json，参数数量: {len(params)}")
        return params

    @classmethod
    def _parse_metrics_json(cls, plugin_dir: Path) -> list[MetricPluginMetricGroup]:
        """解析 metrics.json 文件

        Args:
            plugin_dir: 插件目录路径

        Returns:
            指标配置列表，如果文件不存在则返回空列表

        Raises:
            ValueError: 如果 metrics.json 格式不正确（不是列表）
        """
        metrics_file = plugin_dir / "info" / "metrics.json"
        if not metrics_file.exists():
            return []

        with open(metrics_file, encoding="utf-8") as f:
            metrics_data: Any = json.load(f)

        # 只允许列表格式，直接交给 pydantic 校验
        if not isinstance(metrics_data, list):
            raise ValueError(f"metrics.json 必须是列表格式，当前格式: {type(metrics_data).__name__}")

        metrics = [
            MetricPluginMetricGroup(**item)  # pyright: ignore[reportUnknownArgumentType]
            for item in metrics_data  # pyright: ignore[reportUnknownVariableType]
        ]

        logger.info(f"解析 metrics.json，指标组数量: {len(metrics)}")
        return metrics

    @classmethod
    def _parse_logo_png(cls, plugin_dir: Path, plugin_id: str) -> str:
        """处理 logo.png 文件，转换为 base64 格式

        兼容两种插件包结构：
        - 老插件包：logo.png 在 info 目录下 (plugin_dir/info/logo.png)
        - 新插件包：logo.png 在 plugin_id 目录下 (plugin_dir/logo.png)

        Args:
            plugin_dir: 插件目录路径
            plugin_id: 插件ID

        Returns:
            logo 的 base64 字符串（带 data URI 前缀），如果文件不存在或超过 2MB 则返回空字符串
        """
        # 优先查找老插件包路径 (info 目录下)
        logo_file = plugin_dir / "info" / "logo.png"
        if not logo_file.exists():
            # 兼容新插件包路径 (plugin_id 目录下)
            logo_file = plugin_dir / "logo.png"
        if not logo_file.exists():
            return ""
        try:
            # 读取文件内容并验证大小
            content = logo_file.read_bytes()
            if len(content) > MAX_LOGO_SIZE_BYTES:
                size_mb = len(content) / (1024 * 1024)
                max_mb = MAX_LOGO_SIZE_BYTES / (1024 * 1024)
                logger.warning(f"logo.png 文件大小 ({size_mb:.2f}MB) 超过限制 ({max_mb:.0f}MB)，跳过: {plugin_id}")
                return ""

            # 转换为 base64 格式（带 data URI 前缀）
            base64_data = base64.b64encode(content).decode("utf-8")
            logo_base64 = f"data:image/png;base64,{base64_data}"
            return logo_base64
        except Exception:
            logger.exception(f"处理 logo.png 文件失败，跳过: {plugin_id}")
            return ""

    @classmethod
    @abstractmethod
    def _parse_define(
        cls,
        bk_tenant_id: str,
        operator: str,
        extract_dir: Path,
        plugin_id: str,
        meta_data: dict[str, Any],
    ) -> dict[str, Any]:
        """解析插件定义

        各插件子类需要实现此方法来解析插件特定的 define 字段。

        Args:
            bk_tenant_id: 租户ID
            operator: 操作人
            extract_dir: 解压根目录路径
            plugin_name: 插件名称
            meta_data: meta.yaml 解析后的数据

        Returns:
            插件定义字典，将赋值给 CreatePluginParams.define
        """
        pass

    @classmethod
    def parse_package(cls, bk_tenant_id: str, package_file: Path, operator: str) -> CreatePluginParams:
        """解析插件包

        默认会先将 ``.tgz`` 压缩包解压到临时目录，然后按标准插件包结构解析。
        为了兼容调试、导入复用等场景，``package_file`` 也允许直接传入已经解压好的目录；
        此时会跳过解压步骤，并保留原目录，由调用方自行管理其生命周期。

        支持解析标准的插件包，目录结构如下：
        ├── external_plugins_linux_x86_64
        │   └── bkplugin_mysql
        │       ├── VERSION
        │       ├── info
        │       │   ├── config.json
        │       │   ├── description.md
        │       │   ├── meta.yaml
        |       |   ├── logo.png
        │       │   ├── metrics.json
        │       │   ├── release.md
        │       │   └── signature.yaml
        │       ├── project.yaml
        └── external_plugins_windows_x86_64
            └── bkplugin_mysql
                ├── VERSION
                ├── info
                │   ├── config.json
                │   ├── description.md
                │   ├── meta.yaml
                │   ├── metrics.json
                │   ├── release.md
                │   └── signature.yaml
                ├── project.yaml



        meta.yaml 文件示例如下：
        ```yaml
        plugin_id: bkplugin_mysql
        plugin_display_name: MySQL
        plugin_type: Exporter
        tag: xxx
        is_support_remote: True
        label: component
        ```

        release.md 需要记录在version_log中
        config.json 需要记录在params中
        VERSION 需要记录在version中
        metrics.json 需要记录在metrics中
        description.md 需要记录在description_md中
        logo.png 需要记录在logo中

        Args:
            bk_tenant_id: 租户ID
            package_file: 插件包路径，既支持 tgz 压缩包，也支持已解压目录
            operator: 操作人

        Returns:
            CreatePluginParams: 创建插件参数
        """
        is_dir = package_file.is_dir()
        extract_dir = package_file if is_dir else cls._extract_package(package_file)
        try:
            # 查找插件目录
            plugin_dir, plugin_name = cls._find_plugin_dir(extract_dir)
            # 解析各个文件
            version = cls._parse_version_file(plugin_dir)
            (
                meta_data,
                plugin_id,
                plugin_display_name,
                plugin_type,
                label,
                is_support_remote,
            ) = cls._parse_meta_yaml(plugin_dir, plugin_name)
            description_md = cls._parse_description_md(plugin_dir)
            version_log = cls._parse_release_md(plugin_dir)
            params = cls._parse_config_json(plugin_dir)
            metrics = cls._parse_metrics_json(plugin_dir)
            logo_path = cls._parse_logo_png(plugin_dir, plugin_id)

            # 调用子类实现的 _parse_define 方法解析 define
            define = cls._parse_define(bk_tenant_id, operator, extract_dir, plugin_id, meta_data)

            # 构建 CreatePluginParams
            create_params = CreatePluginParams(
                id=plugin_id,
                type=plugin_type.lower(),
                name=plugin_display_name,
                description_md=description_md,
                label=label,
                logo=logo_path,
                metrics=metrics,
                params=params,
                define=define,
                is_support_remote=is_support_remote,
                version=version,
                version_log=version_log,
                status=MetricPluginStatus.DEBUG,
            )

            logger.info(f"插件包解析完成: {plugin_id} ({plugin_type})")
            return create_params

        finally:
            if not is_dir and extract_dir.exists():
                shutil.rmtree(extract_dir)
                logger.info(f"清理临时目录: {extract_dir}")

    @abstractmethod
    def export_package(self, operator: str) -> str:
        """导出插件包

        各插件子类需要实现此方法来导出插件包。

        Args:
            operator: 操作人

        Returns:
            插件包文件路径

        Raises:
            NotImplementedError: 如果子类未实现此方法
        """
        raise NotImplementedError

    @classmethod
    def get_plugin_type_from_package(cls, package_file: Path) -> str:
        """从插件包中获取插件类型

        获取顺序如下：

        1. 如果文件名符合 ``{plugin_id}__{plugin_type}__{plugin_version}.tgz`` 规范，直接从文件名提取
        2. 如果是 tgz 压缩包，则解压后从 ``meta.yaml`` 读取
        3. 如果传入的是已解压目录，则直接从目录中的 ``meta.yaml`` 读取，并保留原目录

        目录结构至少需要满足 ``external_plugins_xxx/<plugin_name>/info/meta.yaml``，
        且 ``meta.yaml`` 中必须包含 ``plugin_type`` 字段。

        Args:
            package_file: 插件包路径（tgz 文件或已解压目录）

        Returns:
            插件类型(强转小写)
        """
        is_dir = package_file.is_dir()

        if not is_dir:
            filename = package_file.name
            parts = filename.split("__")
            if len(parts) == 3:
                return parts[1].lower()

        extract_dir = package_file if is_dir else cls._extract_package(package_file)
        try:
            meta_file = cls._find_plugin_type_meta_file(extract_dir)
            with meta_file.open("r", encoding="utf-8") as f:
                meta_data = yaml.safe_load(f)
            plugin_type = meta_data.get("plugin_type", "").lower()
            if not plugin_type:
                raise ValueError(f"meta.yaml文件中未找到plugin_type字段: {meta_file}")
            return plugin_type
        except Exception as e:
            raise ValueError("解析插件包获取插件类型失败") from e
        finally:
            if not is_dir:
                shutil.rmtree(extract_dir)
