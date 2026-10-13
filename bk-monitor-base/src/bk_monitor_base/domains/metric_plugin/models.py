import base64
import binascii
from typing import Any, final

from django.db import models, transaction
from typing_extensions import override

from .constants import JobTaskActionEnum, JobTaskStatusEnum, MetricPluginStatus
from .define import (
    CreatePluginParams,
    CreatePluginVersionParams,
    JobTaskInstance,
    JobTaskLogEntry,
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    MetricPluginMetricGroup,
    MetricPluginParams,
    UpdatePluginVersionParams,
    VersionTuple,
    format_version_padded,
    parse_version,
)
from .errors import (
    LogoSizeExceededError,
    MetricPluginRemoteCollectDisableError,
    MetricPluginVersionNotFoundError,
    PluginVersionLessThanReleasedError,
    PluginVersionReleasedError,
)

# 保持向后兼容的别名
JobTaskStatus = JobTaskStatusEnum
JobTaskAction = JobTaskActionEnum

# Logo 图片最大大小限制（2MB）
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024


def _validate_logo_size(content: bytes) -> None:
    """验证 logo 图片大小不超过限制。"""
    if len(content) > MAX_LOGO_SIZE_BYTES:
        size_mb = len(content) / (1024 * 1024)
        max_mb = MAX_LOGO_SIZE_BYTES / (1024 * 1024)
        raise LogoSizeExceededError(f"Logo 图片大小 ({size_mb:.2f}MB) 超过限制 ({max_mb:.0f}MB)")


def _parse_logo_to_base64(logo: str) -> str:
    """验证 base64 logo 字符串并返回，空值返回空字符串。"""
    if not logo:
        return ""

    if ";base64," in logo:
        _, base64_data = logo.split(";base64,", 1)
    elif "," in logo:
        _, base64_data = logo.split(",", 1)
    else:
        return ""

    # 检查 base64 数据是否为空
    if not base64_data:
        return ""

    try:
        content = base64.b64decode(base64_data, validate=True)
        _validate_logo_size(content)
        # 检查解码后的内容是否为空
        if not content:
            return ""
    except (binascii.Error, ValueError, TypeError, LogoSizeExceededError):
        # 无效的 base64 数据或大小超限，返回空字符串
        return ""
    return logo


@final
class MetricPluginModel(models.Model):
    """
    指标插件
    """

    # 基础信息
    bk_tenant_id = models.CharField(max_length=64, verbose_name="租户ID")
    bk_biz_id = models.IntegerField(verbose_name="归属业务ID")
    is_global = models.BooleanField(default=False, verbose_name="是否全局插件")
    is_internal = models.BooleanField(default=False, verbose_name="是否内置插件")
    plugin_id = models.CharField(max_length=64, verbose_name="插件ID")
    type = models.CharField(max_length=32, verbose_name="插件类型")
    related_params: dict[str, Any] = models.JSONField(verbose_name="关联参数", default=dict)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.CharField(max_length=255, default="", verbose_name="创建用户")
    is_deleted = models.BooleanField(default=False, verbose_name="是否删除")
    label = models.CharField(max_length=64, verbose_name="标签")

    @final
    class Meta:
        db_table = "metric_plugin"
        verbose_name = "指标插件"
        verbose_name_plural = "指标插件"
        ordering = ["-created_at"]
        unique_together = ["bk_tenant_id", "plugin_id"]

    @override
    def __str__(self) -> str:
        return f"{self.bk_tenant_id}/{self.bk_biz_id}/{self.plugin_id}({self.type})"

    def _get_version_model(
        self, version: VersionTuple | None = None, status: MetricPluginStatus | None = None
    ) -> "MetricPluginVersionModel | None":
        """
        获取版本模型

        Args:
            version: 版本号，如果为None，则使用插件的最新版本。

        Returns:
            MetricPluginVersionModel: 版本模型
        """
        version_model = MetricPluginVersionModel.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            plugin=self,
        )

        # 过滤状态
        if status is not None:
            version_model = version_model.filter(status=status.value)

        if version is None:
            version_model = version_model.first()
        else:
            version_model = version_model.filter(version=format_version_padded(version)).first()
        return version_model

    def _compare_major_config(
        self, old_version: "MetricPluginVersionModel", new_params: CreatePluginVersionParams
    ) -> bool:
        """
        比较主要配置是否发生变化

        Args:
            old_version: 旧版本模型
            new_params: 新版本参数

        Returns:
            bool: 如果主要配置有变化返回True，否则返回False
        """
        # 比较 params
        old_params = old_version.params
        new_params_list = [param.model_dump() for param in new_params.params]
        if old_params != new_params_list:
            return True

        # 比较 define
        if old_version.define != new_params.define:
            return True

        # 比较 is_support_remote
        if old_version.is_support_remote != new_params.is_support_remote:
            return True

        return False

    def _compare_minor_config(
        self, old_version: "MetricPluginVersionModel", new_params: CreatePluginVersionParams
    ) -> bool:
        """
        比较次要配置是否发生变化

        Args:
            old_version: 旧版本模型
            new_params: 新版本参数

        Returns:
            bool: 如果次要配置有变化返回True，否则返回False
        """
        # 比较 name
        if old_version.name != new_params.name:
            return True

        # 比较 description_md
        if old_version.description_md != new_params.description_md:
            return True

        # 比较 label (注意：label 存储在 MetricPluginModel 中，不在版本模型中)
        if self.label != new_params.label:
            return True

        # 比较 logo
        if old_version.logo != _parse_logo_to_base64(new_params.logo):
            return True

        # 比较 metrics
        old_metrics = old_version.metrics
        new_metrics = [metric.model_dump() for metric in new_params.metrics]
        if old_metrics != new_metrics:
            return True

        # 比较 enable_metric_discovery
        if old_version.enable_metric_discovery != new_params.enable_metric_discovery:
            return True

        return False

    def to_plugin(self, version: VersionTuple | None = None, status: MetricPluginStatus | None = None) -> MetricPlugin:
        """
        转换为插件对象

        Args:
            version: 版本号，如果为None，则使用插件的最新版本。
            status: 状态，如果为None，则使用插件的最新版本。

        Returns:
            MetricPlugin: 插件对象

        Raises:
            MetricPluginVersionNotFoundError: 插件版本不存在
        """
        # 获取版本模型
        version_model = self._get_version_model(version=version, status=status)
        if not version_model:
            raise MetricPluginVersionNotFoundError(f"插件版本不存在: {self.plugin_id} ({version})")

        return MetricPlugin(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            is_global=self.is_global,
            is_internal=self.is_internal,
            id=self.plugin_id,
            type=self.type,
            name=version_model.name,
            description_md=version_model.description_md,
            label=self.label,
            logo=version_model.logo,
            created_at=self.created_at,
            updated_at=version_model.updated_at,
            created_by=self.created_by,
            updated_by=version_model.updated_by,
            status=MetricPluginStatus(version_model.status),
            version=version_model.version_tuple,
            version_log=version_model.version_log,
            metrics=[MetricPluginMetricGroup.model_validate(metric) for metric in version_model.metrics],
            enable_metric_discovery=version_model.enable_metric_discovery,
            params=[MetricPluginParams.model_validate(param) for param in version_model.params],
            define=version_model.define,
            is_support_remote=version_model.is_support_remote,
            related_params=self.related_params,
        )

    @classmethod
    @transaction.atomic
    def create_plugin(
        cls, bk_tenant_id: str, bk_biz_id: int, params: CreatePluginParams, operator: str
    ) -> MetricPlugin:
        """新建插件并创建初始版本

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            operator: 操作者
            params: 创建插件参数
        """
        plugin_model = MetricPluginModel.objects.filter(
            bk_tenant_id=bk_tenant_id,
            plugin_id=params.id,
        ).first()
        if plugin_model:
            raise ValueError(f"插件已存在: {bk_tenant_id}/{params.id}")

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            plugin_id=params.id,
            type=params.type,
            created_by=operator,
            is_global=params.is_global,
            is_internal=params.is_internal,
            label=params.label,
        )

        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            plugin=plugin_model,
            name=params.name,
            description_md=params.description_md,
            metrics=[metric.model_dump() for metric in params.metrics],
            enable_metric_discovery=params.enable_metric_discovery,
            params=[param.model_dump() for param in params.params],
            define=params.define,
            is_support_remote=params.is_support_remote,
            version=format_version_padded(params.version),
            version_log=params.version_log,
            status=params.status.value,
            updated_by=operator,
            logo=_parse_logo_to_base64(params.logo) if params.logo else "",
        )

        return plugin_model.to_plugin(version=params.version)

    @transaction.atomic
    def create_plugin_version(self, params: CreatePluginVersionParams, operator: str) -> tuple[bool, VersionTuple]:
        """创建插件版本

        如果没有指定版本号，则基于最新的release版本生成新的版本（没已发布版本则使用默认版本号 1.0），否则根据配置的变更情况，决定是否变更主版本号或次版本号。如果没有变更，则保持不变。
        如果指定版本号，则需要确认版本号是否已经存在，如果存在的是 DEBUG 版本，则直接覆盖，如果是 RELEASE 版本，则不允许覆盖。

        Args:
            operator: 操作者
            params: 创建插件版本参数

        Returns:
            tuple[bool, VersionTuple]: 是否变更版本号，版本号(主版本号, 次版本号)

        Raises:
            PluginVersionLessThanReleasedError: 版本号小于已发布版本
            PluginVersionReleasedError: 指定的版本号已存在且为 RELEASE 状态
        """
        # 判断是否指定了版本号
        # 如果 params.version 为 None，则未指定版本号，需要自动生成
        # 如果 params.version 不为 None，则是指定了版本号
        if params.version is not None:
            # 情况1: 指定了版本号
            new_version = params.version
            new_version_str = format_version_padded(new_version)

            # 检查该版本是否已存在
            existing_version = MetricPluginVersionModel.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                plugin=self,
                version=new_version_str,
            ).first()

            if existing_version:
                # 如果存在且状态为 RELEASE，不允许覆盖
                if existing_version.status == MetricPluginStatus.RELEASE.value:
                    raise PluginVersionReleasedError(
                        f"插件版本 {new_version.major}.{new_version.minor} 已发布，不允许覆盖。插件: {self.bk_tenant_id}/{self.plugin_id}"
                    )
                # 如果存在且状态为 DEBUG，删除旧版本
                existing_version.delete()

            # 检查版本号是否小于已发布的最大版本号
            max_release_version = (
                MetricPluginVersionModel.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    plugin=self,
                    status=MetricPluginStatus.RELEASE.value,
                )
                .order_by("-version")
                .first()
            )

            if max_release_version:
                if new_version < max_release_version.version_tuple:
                    raise PluginVersionLessThanReleasedError(
                        f"禁止创建小于已发布版本的版本号。已发布最大版本: {max_release_version.version_tuple.major}.{max_release_version.version_tuple.minor}, 当前版本: {new_version.major}.{new_version.minor}"
                    )

            # 创建新版本
            _version_model = MetricPluginVersionModel.objects.create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                plugin=self,
                name=params.name,
                description_md=params.description_md,
                logo=_parse_logo_to_base64(params.logo) if params.logo else "",
                metrics=[metric.model_dump() for metric in params.metrics],
                enable_metric_discovery=params.enable_metric_discovery,
                params=[param.model_dump() for param in params.params],
                define=params.define,
                is_support_remote=params.is_support_remote,
                version=new_version_str,
                version_log=params.version_log,
                status=params.status.value,
                updated_by=operator,
            )

            # 更新 label（如果变化）
            if self.label != params.label:
                self.label = params.label
                self.save(update_fields=["label"])

            return True, new_version

        else:
            # 情况2: 未指定版本号，基于最新 RELEASE 版本生成新版本
            # 获取最新的 RELEASE 版本
            latest_release_version = self._get_version_model(status=MetricPluginStatus.RELEASE)

            # 如果没有 RELEASE 版本，使用默认版本号 1.0
            if not latest_release_version:
                new_version = VersionTuple(major=1, minor=0)
                version_changed = True
            else:
                if latest_release_version.is_support_remote and not params.is_support_remote:
                    raise MetricPluginRemoteCollectDisableError("已开启远程采集的插件无法关闭远程采集")

                # 比较配置变化
                major_changed = self._compare_major_config(latest_release_version, params)
                minor_changed = self._compare_minor_config(latest_release_version, params)

                if major_changed:
                    # 主要配置变化，主版本号 +1，次版本号重置为 0
                    latest_tuple = latest_release_version.version_tuple
                    new_version = VersionTuple(major=latest_tuple.major + 1, minor=0)
                    version_changed = True
                elif minor_changed:
                    # 只有次要配置变化，次版本号 +1
                    latest_tuple = latest_release_version.version_tuple
                    new_version = VersionTuple(
                        major=latest_tuple.major,
                        minor=latest_tuple.minor + 1,
                    )
                    version_changed = True
                else:
                    # 没有变化，版本号保持不变
                    latest_tuple = latest_release_version.version_tuple
                    new_version = VersionTuple(
                        major=latest_tuple.major,
                        minor=latest_tuple.minor,
                    )
                    version_changed = False

                # 编辑场景下，如果自动推导发现配置完全未变更，则沿用当前 release 版本。
                # 同时直接更新当前版本的可编辑字段和 version_log，兼容旧 edit
                # “只改版本日志也算成功”的语义。
                if not version_changed:
                    self.update_plugin_version(
                        version=new_version,
                        params=UpdatePluginVersionParams(
                            name=params.name,
                            description_md=params.description_md,
                            label=params.label,
                            logo=params.logo,
                            metrics=params.metrics,
                            enable_metric_discovery=params.enable_metric_discovery,
                            version_log=params.version_log,
                        ),
                        operator=operator,
                    )
                    return False, new_version

            # 检查新版本是否已存在（可能由于并发或其他原因）
            existing_version = MetricPluginVersionModel.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                plugin=self,
                version=format_version_padded(new_version),
            ).first()

            if existing_version:
                # 如果存在且状态为 RELEASE，不允许覆盖
                if existing_version.status == MetricPluginStatus.RELEASE.value:
                    raise PluginVersionReleasedError(
                        f"插件版本 {new_version.major}.{new_version.minor} 已发布，不允许覆盖。插件: {self.bk_tenant_id}/{self.plugin_id}"
                    )
                # 如果存在且状态为 DEBUG，删除旧版本
                existing_version.delete()

            # 创建新版本
            _version_model = MetricPluginVersionModel.objects.create(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                plugin=self,
                name=params.name,
                description_md=params.description_md,
                logo=_parse_logo_to_base64(params.logo) if params.logo else "",
                metrics=[metric.model_dump() for metric in params.metrics],
                enable_metric_discovery=params.enable_metric_discovery,
                params=[param.model_dump() for param in params.params],
                define=params.define,
                is_support_remote=params.is_support_remote,
                version=format_version_padded(new_version),
                version_log=params.version_log,
                status=params.status.value,
                updated_by=operator,
            )

            # 更新 label（如果变化）
            if self.label != params.label:
                self.label = params.label
                self.save(update_fields=["label"])

            return version_changed, new_version

    @transaction.atomic
    def update_plugin_version(self, version: VersionTuple, params: UpdatePluginVersionParams, operator: str) -> None:
        """更新插件版本配置

        只能更新次要配置，不能更新主要配置

        Args:
            version: 版本号
            params: 更新插件版本参数
            operator: 操作者

        Raises:
            MetricPluginVersionNotFoundError: 插件版本不存在
        """
        # 获取指定版本的版本模型
        version_model = self._get_version_model(version=version)
        if not version_model:
            raise MetricPluginVersionNotFoundError(
                f"插件版本不存在: {self.plugin_id} ({version.major}.{version.minor})"
            )

        # 更新次要配置字段
        version_model.name = params.name
        version_model.description_md = params.description_md
        version_model.metrics = [metric.model_dump() for metric in params.metrics]
        version_model.enable_metric_discovery = params.enable_metric_discovery
        version_model.version_log = params.version_log
        version_model.updated_by = operator

        if params.logo:
            version_model.logo = _parse_logo_to_base64(params.logo)

        # 保存更新
        version_model.save(
            update_fields=[
                "name",
                "description_md",
                "logo",
                "metrics",
                "enable_metric_discovery",
                "version_log",
                "updated_by",
                "updated_at",
            ]
        )

        # 更新 label（如果变化，label 存储在 MetricPluginModel 中）
        if self.label != params.label:
            self.label = params.label
            self.save(update_fields=["label"])

    @transaction.atomic
    def release_plugin_version(self, version: VersionTuple, operator: str) -> None:
        """发布插件版本

        Args:
            version: 版本号
            operator: 操作者
        """

        plugin_version_model = self._get_version_model(version=version)
        if not plugin_version_model:
            raise MetricPluginVersionNotFoundError(
                f"插件版本不存在: {self.bk_tenant_id}/{self.plugin_id} ({version.major}.{version.minor})"
            )

        # 更新版本状态
        if plugin_version_model.status == MetricPluginStatus.DEBUG.value:
            plugin_version_model.updated_by = operator
            plugin_version_model.status = MetricPluginStatus.RELEASE.value
            plugin_version_model.save(update_fields=["updated_by", "status"])


@final
class MetricPluginVersionModel(models.Model):
    """
    指标插件版本
    """

    plugin = models.ForeignKey(
        MetricPluginModel, on_delete=models.PROTECT, related_name="versions", verbose_name="插件"
    )
    bk_tenant_id = models.CharField(max_length=64, verbose_name="租户ID")
    bk_biz_id = models.IntegerField(verbose_name="归属业务ID")

    # 基础信息
    name = models.CharField(max_length=255, verbose_name="插件名称")
    description_md = models.TextField(verbose_name="描述", blank=True)
    logo = models.TextField(verbose_name="logo(base64)", blank=True, default="")

    # 时间信息
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    updated_by = models.CharField(max_length=255, verbose_name="更新用户", blank=True)

    # 指标配置
    metrics: list[dict[str, Any]] = models.JSONField(default=list, verbose_name="指标配置")  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    enable_metric_discovery = models.BooleanField(default=False, verbose_name="自动发现指标开关")

    # 插件配置
    params: list[dict[str, Any]] = models.JSONField(verbose_name="参数配置")  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    define: dict[str, Any] = models.JSONField(verbose_name="插件定义")  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    is_support_remote = models.BooleanField(default=False, verbose_name="是否支持远程采集")

    # 版本信息
    version = models.CharField(max_length=16, verbose_name="版本", help_text="格式为major.minor")
    version_log = models.TextField(verbose_name="版本日志", blank=True)

    # 状态
    status = models.CharField(
        max_length=32, verbose_name="状态", choices=[(status.value, status.name) for status in MetricPluginStatus]
    )

    @property
    def version_tuple(self) -> VersionTuple:
        """将版本字段解析为 VersionTuple。

        Returns:
            版本元组（主版本号、次版本号）。

        Raises:
            ValueError: 当版本字段格式非法时抛出。
        """
        return parse_version(self.version)

    @version_tuple.setter
    def version_tuple(self, value: VersionTuple) -> None:
        """通过 VersionTuple 设置版本字段（会自动零填充以支持排序）。"""
        self.version = format_version_padded(value)

    @override
    def __str__(self) -> str:
        version = self.version_tuple
        return f"{self.plugin} ({version.major}.{version.minor})"

    @final
    class Meta:
        db_table = "metric_plugin_version"
        verbose_name = "指标插件版本"
        verbose_name_plural = "指标插件版本"
        ordering = ["-version"]
        unique_together = ["bk_tenant_id", "bk_biz_id", "plugin", "version"]


@final
class MetricPluginDeploymentModel(models.Model):
    """
    指标插件部署项
    """

    bk_tenant_id = models.CharField(max_length=64, verbose_name="租户ID")
    bk_biz_id = models.IntegerField(verbose_name="归属业务ID")
    plugin = models.ForeignKey(
        MetricPluginModel, on_delete=models.PROTECT, related_name="deployments", verbose_name="插件"
    )
    name = models.CharField(max_length=255, verbose_name="部署名称")
    related_params: dict[str, Any] = models.JSONField(verbose_name="关联参数", default=dict)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    # 仅定义了基础的开始和结束状态，中间状态可以自定义
    status = models.CharField(
        max_length=32, verbose_name="状态", default=MetricPluginDeploymentStatusEnum.INITIALIZING.value
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.CharField(max_length=255, verbose_name="创建用户", blank=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    updated_by = models.CharField(max_length=255, verbose_name="更新用户", blank=True)

    @final
    class Meta:
        db_table = "metric_plugin_deployment"
        verbose_name = "指标插件部署项"
        verbose_name_plural = "指标插件部署项"
        ordering = ["-created_at"]
        unique_together = ["bk_tenant_id", "bk_biz_id", "name"]

    def to_deployment(self) -> MetricPluginDeployment:
        """转换为指标插件部署项定义"""
        return MetricPluginDeployment(
            id=self.pk,
            plugin_id=self.plugin.plugin_id,
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            name=self.name,
            status=MetricPluginDeploymentStatusEnum(self.status),
            created_at=self.created_at,
            created_by=self.created_by,
            updated_at=self.updated_at,
            updated_by=self.updated_by,
            related_params=self.related_params,
        )

    def get_current_version(self) -> MetricPluginDeploymentVersion | None:
        """获取当前版本"""
        version = MetricPluginDeploymentVersionModel.objects.filter(deployment=self, is_current=True).first()
        return version.to_deployment_version() if version else None


@final
class MetricPluginDeploymentVersionModel(models.Model):
    """
    指标插件部署版本
    """

    bk_tenant_id = models.CharField(max_length=64, verbose_name="租户ID")
    bk_biz_id = models.IntegerField(verbose_name="归属业务ID")

    deployment = models.ForeignKey(
        MetricPluginDeploymentModel, on_delete=models.PROTECT, related_name="versions", verbose_name="部署项"
    )
    plugin_version = models.CharField(max_length=16, verbose_name="插件版本", help_text="格式为major.minor")
    version = models.IntegerField(verbose_name="版本号", help_text="从1开始，每次更新递增")
    is_current = models.BooleanField(default=False, verbose_name="是否当前版本")

    params: dict[str, Any] = models.JSONField(verbose_name="参数配置", default=dict)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    target_node_type = models.CharField(max_length=32, verbose_name="目标节点类型")
    target_nodes: list[dict[str, Any]] = models.JSONField(verbose_name="目标节点", default=list)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]

    remote_node_type = models.CharField(max_length=32, verbose_name="远程节点类型", blank=True, default="")
    remote_nodes: list[dict[str, Any]] = models.JSONField(verbose_name="采集节点", default=list)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]

    # 实际下发目标实例，目前仅作为一个记录字段，实际下发目标实例由采集器下发时记录
    target_instances: list[dict[str, Any]] = models.JSONField(verbose_name="目标实例", default=list)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    remote_instances: list[dict[str, Any]] = models.JSONField(verbose_name="远程实例", default=list)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.CharField(max_length=255, verbose_name="创建用户", blank=True)

    @final
    class Meta:
        db_table = "metric_plugin_deployment_version"
        verbose_name = "指标插件部署版本"
        verbose_name_plural = "指标插件部署版本"
        ordering = ["deployment", "-version"]
        unique_together = ["bk_tenant_id", "bk_biz_id", "deployment", "version"]

    def to_deployment_version(self) -> MetricPluginDeploymentVersion:
        """转换为指标插件部署版本定义

        Raises:
            ValueError: 插件版本格式错误
        """
        # 验证插件版本格式
        try:
            version_parts = self.plugin_version.split(".")
            if len(version_parts) != 2:
                raise ValueError(f"插件版本格式错误，应为 major.minor: {self.plugin_version}")
            plugin_major_version, plugin_minor_version = version_parts
        except (ValueError, AttributeError) as e:
            raise ValueError(f"无效的插件版本格式: {self.plugin_version}") from e

        # 判断是否为远程采集：需要同时有 node_type 和 nodes
        remote_scope = None
        if self.remote_node_type and self.remote_node_type.strip() and self.remote_nodes:
            remote_scope = MetricPluginDeploymentScope(node_type=self.remote_node_type, nodes=self.remote_nodes)

        return MetricPluginDeploymentVersion(
            deployment_id=self.deployment.pk,
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            plugin_version=VersionTuple(int(plugin_major_version), int(plugin_minor_version)),
            version=self.version,
            params=self.params,
            target_scope=MetricPluginDeploymentScope(node_type=self.target_node_type, nodes=self.target_nodes),
            remote_scope=remote_scope,
            target_instances=self.target_instances,
            remote_instances=self.remote_instances,
            created_at=self.created_at,
            created_by=self.created_by,
        )


@final
class JobTaskInstanceModel(models.Model):
    """Job 任务实例 ORM 模型

    用于持久化 Job 安装器执行任务的状态和详细信息。
    业务逻辑操作请使用 JobTaskInstance Pydantic 模型，只有需要持久化时才调用本模型。

    Note:
        1. 每个任务实例对应一个目标实例（主机、容器、Pod 等），实现实例级别的任务管理
        2. 使用 to_instance() 转换为 Pydantic 模型进行业务操作
        3. 枚举校验由 Pydantic 模型处理，ORM 层仅存储字符串
    """

    # 基础信息
    bk_tenant_id = models.CharField(max_length=64, verbose_name="租户ID")
    bk_biz_id = models.IntegerField(verbose_name="业务ID")

    # 任务信息 - 直接存储字符串，枚举校验由 Pydantic 处理
    action = models.CharField(
        max_length=32,
        verbose_name="操作类型",
        help_text="install/uninstall/update/retry",
    )
    status = models.CharField(
        max_length=32,
        default=JobTaskStatusEnum.PENDING.value,
        verbose_name="任务状态",
        help_text="pending/running/success/failed/canceled",
    )

    # 目标实例信息（单实例）
    instance_id = models.CharField(
        max_length=255,
        verbose_name="实例标识",
        help_text="目标实例唯一标识，可能是 bk_host_id、ip:bk_cloud_id、container_id、namespace/pod_name 等",
    )
    instance_info: dict[str, Any] = models.JSONField(  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
        verbose_name="实例信息",
        default=dict,
        help_text="目标实例的详细信息，如 bk_host_id, ip, bk_cloud_id,model_id,instance_id 等",
    )
    collect_instance_info: dict[str, Any] = models.JSONField(  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
        verbose_name="采集执行实例信息",
        default=dict,
        help_text="实际执行采集和下发的实例信息，远程采集时为远程采集主机",
    )

    # 任务步骤和日志
    current_step = models.CharField(max_length=64, verbose_name="当前步骤", default="", blank=True)
    task_log: list[dict[str, Any]] = models.JSONField(  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
        verbose_name="任务日志",
        default=list,
        help_text="任务日志列表，每个条目包含 step, status, messages, job_instance_id, timestamp, extra",
    )

    # 执行参数
    execute_params: dict[str, Any] = models.JSONField(  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
        verbose_name="执行参数",
        default=dict,
        help_text="存储执行时的参数，如配置文件路径、采集参数等",
    )

    # 失败原因
    error_message = models.TextField(verbose_name="错误信息", default="", blank=True)

    # 时间信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.CharField(max_length=255, verbose_name="创建用户", default="", blank=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    started_at = models.DateTimeField(verbose_name="开始执行时间", null=True, blank=True)
    finished_at = models.DateTimeField(verbose_name="完成时间", null=True, blank=True)

    @final
    class Meta:
        db_table = "job_task_instance"
        verbose_name = "Job任务实例"
        verbose_name_plural = "Job任务实例"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["bk_tenant_id", "bk_biz_id"]),
            models.Index(fields=["instance_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["action"]),
        ]

    @override
    def __str__(self) -> str:
        return f"JobTask-{self.pk}({self.action}/{self.status})"

    def to_instance(self) -> JobTaskInstance:
        """转换为 Pydantic 模型

        Returns:
            JobTaskInstance: 任务实例 Pydantic 对象
        """
        return JobTaskInstance(
            id=self.pk,
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            action=JobTaskActionEnum(self.action),
            status=JobTaskStatusEnum(self.status),
            instance_id=self.instance_id,
            instance_info=self.instance_info,
            collect_instance_info=self.collect_instance_info,
            current_step=self.current_step,
            task_log=[JobTaskLogEntry.model_validate(log) for log in self.task_log],
            execute_params=self.execute_params,
            error_message=self.error_message,
            created_at=self.created_at,
            created_by=self.created_by,
            updated_at=self.updated_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
        )

    @classmethod
    def save_instance(cls, instance: JobTaskInstance) -> "JobTaskInstanceModel":
        """将 Pydantic 模型保存到数据库

        如果 instance.id 为 None，则创建新记录；否则更新现有记录。

        Args:
            instance: JobTaskInstance Pydantic 对象

        Returns:
            JobTaskInstanceModel: 保存后的 ORM 模型
        """
        task_log_data = [log.model_dump() for log in instance.task_log]

        if instance.id is None:
            # 创建新记录
            model = cls.objects.create(
                bk_tenant_id=instance.bk_tenant_id,
                bk_biz_id=instance.bk_biz_id,
                action=instance.action.value,
                status=instance.status.value,
                instance_id=instance.instance_id,
                instance_info=instance.instance_info,
                collect_instance_info=instance.collect_instance_info,
                current_step=instance.current_step,
                task_log=task_log_data,
                execute_params=instance.execute_params,
                error_message=instance.error_message,
                created_by=instance.created_by,
                started_at=instance.started_at,
                finished_at=instance.finished_at,
            )
            instance.id = model.pk
            instance.created_at = model.created_at
            instance.updated_at = model.updated_at
        else:
            # 更新现有记录
            cls.objects.filter(pk=instance.id).update(
                status=instance.status.value,
                current_step=instance.current_step,
                collect_instance_info=instance.collect_instance_info,
                task_log=task_log_data,
                execute_params=instance.execute_params,
                error_message=instance.error_message,
                started_at=instance.started_at,
                finished_at=instance.finished_at,
            )
            model = cls.objects.get(pk=instance.id)
            instance.updated_at = model.updated_at

        return model

    @classmethod
    def get_by_instance_id(
        cls, instance_id: str, bk_tenant_id: str | None = None, action: str | None = None
    ) -> "JobTaskInstanceModel | None":
        """根据实例标识获取最新的任务实例

        Args:
            instance_id: 实例标识
            bk_tenant_id: 租户ID（可选）
            action: 操作类型（可选，不指定则返回最新的）

        Returns:
            JobTaskInstanceModel | None: 任务实例
        """
        queryset = cls.objects.filter(instance_id=instance_id)
        if bk_tenant_id:
            queryset = queryset.filter(bk_tenant_id=bk_tenant_id)
        if action:
            queryset = queryset.filter(action=action)
        return queryset.order_by("-created_at").first()
