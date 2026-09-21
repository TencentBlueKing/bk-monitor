import re
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, cast

from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    DateTimeField,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)

from bk_monitor_base.domains.metric_plugin.installer.job import JobInstaller
from bk_monitor_base.domains.metric_plugin.installer.nodeman import NodemanInstaller
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.define import JobMetricPluginDebugInst, JobStatus
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import DebugStatus, NodemanPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.snmp_trap import SNMPTrapPluginManager
from bk_monitor_base.domains.uploaded_file.operation import FileInfo, save_file
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.nodeman import api as nodeman_api
from bk_monitor_base.infras.types import FILE_OR_CONTENT_TYPE

from .constants import MetricPluginStatus
from .define import (
    CreateOrUpdateDeploymentParams,
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    RetryDeployPluginParams,
    UpdatePluginVersionParams,
    VersionTuple,
)
from .errors import (
    MetricPluginDeploymentExistsError,
    MetricPluginDeploymentNotFoundError,
    MetricPluginDeploymentOperationError,
    MetricPluginDeploymentStatusError,
    MetricPluginNotFoundError,
    PluginFileUploadError,
    PluginIDExistsError,
    PluginIDInvalidError,
)
from .installer.tools import get_installer
from .manager.tools import (
    get_job_plugin_manager,
    get_nodeman_plugin_manager,
    get_plugin_manager,
    get_plugin_manager_class,
    get_plugin_type_from_package,
)
from .models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
)


class MetricPluginInfo(TypedDict):
    """指标插件基础信息

    Attributes:
        bk_tenant_id: 租户ID
        bk_biz_id: 归属业务ID
        is_global: 是否全局插件
        is_internal: 是否内置插件
        id: 插件ID
        type: 插件类型
        name: 插件名称
        logo: logo
        label: 标签
        release_version: 已发布版本
        debug_version: 调试版本
        created_at: 创建时间
        updated_at: 更新时间
        created_by: 创建用户
        updated_by: 更新用户
    """

    bk_tenant_id: str
    bk_biz_id: int
    is_global: bool
    is_internal: bool
    id: str
    type: str
    name: str
    logo: str
    label: str
    release_version: VersionTuple | None
    debug_version: VersionTuple | None
    deployment_count: int | None
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class DebugNodemanPluginResult(TypedDict):
    """调试 nodeman 插件结果

    Attributes:
        task_id: 调试任务ID，用于后续查询调试日志或停止调试
    """

    task_id: int


class DebugMetricInfo(TypedDict):
    """调试指标信息

    Attributes:
        metric_name: 指标名称
        metric_value: 指标值
        dimensions: 维度列表，包含 dimension_name 和 dimension_value
    """

    metric_name: str
    metric_value: Any
    dimensions: list[dict[str, str]]


class GetNodemanPluginDebugLogResult(TypedDict):
    """获取 nodeman 插件调试日志结果

    Attributes:
        status: 调试状态 (running/success/failed)
        metric_json: 解析后的指标信息列表
        last_time: 最新采集时间（格式：YYYY-MM-DD HH:MM:SS）
        error_message: 错误信息（如果存在）
        log: 原始日志内容，用于前端展示
    """

    status: DebugStatus
    metric_json: list[DebugMetricInfo]
    last_time: str
    error_message: str
    log: str


def count_metric_plugin_type(
    bk_tenant_id: str | None = None,
    bk_biz_ids: list[int] | None = None,
    bk_biz_id_with_global: bool | None = None,
    labels: list[str] | None = None,
    plugin_types: list[str] | None = None,
    search: str | None = None,
) -> dict[str, int]:
    """统计插件类型数量

    Args:
        bk_tenant_id: 租户ID，用于过滤指定租户的插件。
        bk_biz_ids: 业务ID列表，用于过滤指定业务的插件。
        bk_biz_id_with_global: 在查询业务ID列表时，是否包含非当前业务ID的全局插件。
        labels: 标签列表，用于过滤包含指定标签的插件。
        plugin_types: 插件类型列表，用于过滤指定类型的插件。
        search: 搜索关键词，用于搜索插件ID或插件名称（不区分大小写）。插件名称搜索会优先匹配已发布版本的名称，如果没有已发布版本则匹配调试版本的名称。

    Returns:
        dict[str, int]: 插件类型数量
    """
    plugin_models = MetricPluginModel.objects.filter(is_deleted=False)

    # 预先注解每个插件的最新 release/debug 版本信息，避免后续过滤出现额外查询。
    latest_release_versions = MetricPluginVersionModel.objects.filter(
        plugin=OuterRef("pk"),
        bk_tenant_id=OuterRef("bk_tenant_id"),
        status=MetricPluginStatus.RELEASE.value,
    ).order_by("-version")
    latest_debug_versions = MetricPluginVersionModel.objects.filter(
        plugin=OuterRef("pk"),
        bk_tenant_id=OuterRef("bk_tenant_id"),
        status=MetricPluginStatus.DEBUG.value,
    ).order_by("-version")

    plugin_models = plugin_models.annotate(
        latest_release_id=Subquery(latest_release_versions.values("id")[:1], output_field=IntegerField()),
        latest_debug_id=Subquery(latest_debug_versions.values("id")[:1], output_field=IntegerField()),
    )

    # 过滤租户ID
    if bk_tenant_id is not None:
        plugin_models = plugin_models.filter(bk_tenant_id=bk_tenant_id)

    # 过滤业务ID
    if bk_biz_ids is not None:
        if bk_biz_id_with_global:
            plugin_models = plugin_models.filter(Q(bk_biz_id__in=bk_biz_ids) | Q(is_global=True))
        else:
            plugin_models = plugin_models.filter(bk_biz_id__in=bk_biz_ids)

    # 过滤标签
    if labels is not None:
        plugin_models = plugin_models.filter(label__in=labels)

    # 搜索插件ID或插件名，插件名是记录在 MetricPluginVersionModel 中的 name 字段
    if search is not None:
        plugin_models = plugin_models.annotate(
            latest_release_name=Subquery(latest_release_versions.values("name")[:1], output_field=CharField()),
            latest_debug_name=Subquery(latest_debug_versions.values("name")[:1], output_field=CharField()),
        )
        plugin_models = plugin_models.filter(
            Q(plugin_id__icontains=search)
            | Q(latest_release_name__icontains=search)
            | (Q(latest_release_id__isnull=True) & Q(latest_debug_name__icontains=search))
        )

    # 过滤类型
    if plugin_types is not None:
        if not plugin_types:
            return {}
        plugin_models = plugin_models.filter(type__in=plugin_types)

    # 仅统计有有效版本（release/debug）的插件，和列表口径保持一致
    plugin_models = plugin_models.filter(Q(latest_release_id__isnull=False) | Q(latest_debug_id__isnull=False))

    type_counts = plugin_models.values("type").annotate(count=Count("id"))
    return {str(item["type"]): int(item["count"]) for item in type_counts}


def _build_metric_plugin_ordering(
    plugin_models: QuerySet[MetricPluginModel],
    latest_release_versions: QuerySet[MetricPluginVersionModel],
    latest_debug_versions: QuerySet[MetricPluginVersionModel],
    order: str | None,
) -> QuerySet[MetricPluginModel]:
    """为指标插件列表构建数据库排序。

    仅支持有限排序字段，并将排序下推到数据库层执行，以降低内存排序开销。
    默认排序为 `-updated_at`（即 `-display_updated_at`）。
    """
    normalized_order = (order or "").strip()
    is_desc = True
    raw_field = "updated_at"
    if normalized_order:
        is_desc = normalized_order.startswith("-")
        raw_field = normalized_order[1:] if is_desc else normalized_order

    # API 字段到 DB 字段（或注解字段）映射，仅保留有限字段。
    order_field_map: dict[str, str] = {
        "created_at": "created_at",
        "updated_at": "display_updated_at",
        "status": "display_status",
    }

    mapped_field = order_field_map.get(raw_field, "display_updated_at")
    if raw_field not in order_field_map:
        is_desc = True

    # 仅在需要时增加注解，避免无关排序带来的额外开销
    if mapped_field == "display_updated_at":
        plugin_models = plugin_models.annotate(
            display_updated_at=Case(
                When(
                    latest_release_id__isnull=False,
                    then=Subquery(
                        latest_release_versions.values("updated_at")[:1],
                        output_field=DateTimeField(),
                    ),
                ),
                default=Subquery(
                    latest_debug_versions.values("updated_at")[:1],
                    output_field=DateTimeField(),
                ),
                output_field=DateTimeField(),
            )
        )
    elif mapped_field == "display_status":
        plugin_models = plugin_models.annotate(
            display_status=Case(
                When(latest_release_id__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

    direction_prefix = "-" if is_desc else ""
    order_by_field = f"{direction_prefix}{mapped_field}"
    return plugin_models.order_by(order_by_field, "-plugin_id")


def get_virtual_metric_plugin(bk_tenant_id: str, plugin_id: str) -> MetricPlugin:
    """获取虚拟插件

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID

    Returns:
        MetricPlugin: 虚拟插件
    """

    if plugin_id.startswith("snmp_"):
        return SNMPTrapPluginManager.get_virtual_plugins(bk_tenant_id=bk_tenant_id, plugin_ids=[plugin_id])[0]
    else:
        raise ValueError(f"Invalid plugin id: {plugin_id}")


class DebugJobPluginResult(TypedDict):
    """调试 Job 插件结果

    Attributes:
        task_id: 调试任务ID，用于后续查询调试日志或停止调试
    """

    task_id: int


class GetJobPluginDebugLogResult(TypedDict):
    """获取 Job 插件调试日志结果

    Attributes:
        task_log: 调试日志条目列表
        debug_status: 调试状态
        metric_json: 调试成功时返回的指标数据
    """

    task_log: list[dict[str, Any]]
    debug_status: JobStatus
    metric_json: list[dict[str, Any]]


def list_metric_plugins(
    bk_tenant_id: str | None = None,
    bk_biz_ids: list[int] | None = None,
    labels: list[str] | None = None,
    is_global: bool | None = None,
    bk_biz_id_with_global: bool | None = None,
    is_internal: bool | None = None,
    plugin_ids: list[str] | None = None,
    plugin_types: list[str] | None = None,
    search: str | None = None,
    with_deployment_count: bool = False,
    limit: int | None = None,
    offset: int | None = None,
    order: str | None = None,
) -> tuple[list[MetricPluginInfo], int]:
    """获取插件列表

    插件的信息使用最新已发布版本，除非没有已发布版本，则显示最新调试版本。

    Args:
        bk_tenant_id: 租户ID，用于过滤指定租户的插件。
        bk_biz_ids: 业务ID列表，用于过滤指定业务的插件。
        labels: 标签列表，用于过滤包含指定标签的插件。
        is_global: 是否全局插件，True表示只查询全局插件，False表示只查询非全局插件。
        bk_biz_id_with_global: 在查询业务ID列表时，是否包含非当前业务ID的全局插件。
        is_internal: 是否内置插件，True表示只查询内置插件，False表示只查询非内置插件。
        search: 搜索关键词，用于搜索插件ID或插件名称（不区分大小写）。插件名称搜索会优先匹配已发布版本的名称，如果没有已发布版本则匹配调试版本的名称。
        stage: 插件版本发布状态，用于过滤指定状态的插件。
        plugin_ids: 插件ID列表，用于过滤指定ID的插件。
        plugin_types: 插件类型列表，用于过滤指定类型的插件。
        with_deployment_count: 是否包含部署项数量，如果为True，则返回每个插件的部署项数量。
        limit: 分页大小，限制返回的插件数量。
        offset: 分页偏移量，用于分页查询。
        order: 排序字段。仅支持 `updated_at`、`created_at`、`status`（支持前缀 `-` 表示降序）。

    Returns:
        符合条件的插件列表和总数。
    """
    plugin_models = MetricPluginModel.objects.filter(is_deleted=False)

    # 预先注解每个插件的最新 release/debug 版本信息，避免后续循环查询导致 N+1。
    # 同时也用于 search 分支：有 release 时仅匹配最新 release 的 name；无 release 时匹配最新 debug 的 name。
    latest_release_versions = MetricPluginVersionModel.objects.filter(
        plugin=OuterRef("pk"),
        bk_tenant_id=OuterRef("bk_tenant_id"),
        status=MetricPluginStatus.RELEASE.value,
    ).order_by("-version")
    latest_debug_versions = MetricPluginVersionModel.objects.filter(
        plugin=OuterRef("pk"),
        bk_tenant_id=OuterRef("bk_tenant_id"),
        status=MetricPluginStatus.DEBUG.value,
    ).order_by("-version")

    plugin_models = plugin_models.annotate(
        latest_release_id=Subquery(latest_release_versions.values("id")[:1], output_field=IntegerField()),
        latest_debug_id=Subquery(latest_debug_versions.values("id")[:1], output_field=IntegerField()),
    )

    # 过滤租户ID
    if bk_tenant_id is not None:
        plugin_models = plugin_models.filter(bk_tenant_id=bk_tenant_id)

    # 过滤业务ID
    if bk_biz_ids is not None:
        # 是否包含非当前业务ID的全局插件
        if bk_biz_id_with_global:
            plugin_models = plugin_models.filter(Q(bk_biz_id__in=bk_biz_ids) | Q(is_global=True))
        else:
            plugin_models = plugin_models.filter(bk_biz_id__in=bk_biz_ids)

    # 过滤标签
    if labels is not None:
        plugin_models = plugin_models.filter(label__in=labels)

    # 过滤是否全局
    if is_global is not None:
        plugin_models = plugin_models.filter(is_global=is_global)

    # 过滤是否内置
    if is_internal is not None:
        plugin_models = plugin_models.filter(is_internal=is_internal)

    # 搜索插件ID或插件名，插件名是记录在MetricPluginVersionModel中的name字段
    if search:
        # 只有 search 分支才需要 name 注解，避免无 search 时额外的子查询开销。
        plugin_models = plugin_models.annotate(
            latest_release_name=Subquery(latest_release_versions.values("name")[:1], output_field=CharField()),
            latest_debug_name=Subquery(latest_debug_versions.values("name")[:1], output_field=CharField()),
        )
        plugin_models = plugin_models.filter(
            Q(plugin_id__icontains=search)
            | Q(latest_release_name__icontains=search)
            | (Q(latest_release_id__isnull=True) & Q(latest_debug_name__icontains=search))
        )

    # 过滤插件ID
    if plugin_ids is not None:
        if not plugin_ids:
            return [], 0
        plugin_models = plugin_models.filter(plugin_id__in=plugin_ids)

    # 过滤类型
    if plugin_types is not None:
        plugin_models = plugin_models.filter(type__in=plugin_types)

    # 先获取所有插件，然后过滤掉没有版本的插件，计算实际可返回的插件数量
    # 复用注解的 latest_release_id/latest_debug_id 来过滤掉没有版本的插件，避免额外 Exists 子查询。
    plugin_models = plugin_models.filter(Q(latest_release_id__isnull=False) | Q(latest_debug_id__isnull=False))

    # 排序：仅支持有限字段，默认 -update_time
    plugin_models = _build_metric_plugin_ordering(
        plugin_models=plugin_models,
        latest_release_versions=latest_release_versions,
        latest_debug_versions=latest_debug_versions,
        order=order,
    )

    # 获取插件总数（只计算有版本的插件）
    total = plugin_models.count()

    # 分页（在数据库层分页，避免先拉全量数据）
    if limit is not None or offset is not None:
        start = offset or 0
        end = start + limit if limit is not None else None
        plugin_models = plugin_models[start:end]

    # 转换为列表以便后续使用
    plugin_models_list = list(plugin_models)

    if not plugin_models_list:
        return [], total

    # 批量拉取分页结果中每个插件的最新 release/debug 版本，避免循环查询导致 N+1。
    version_ids: set[int] = set()
    for plugin_model in plugin_models_list:
        latest_release_id = getattr(plugin_model, "latest_release_id", None)
        latest_debug_id = getattr(plugin_model, "latest_debug_id", None)

        if latest_release_id is not None:
            version_ids.add(int(latest_release_id))
        if latest_debug_id is not None:
            version_ids.add(int(latest_debug_id))

    version_model_by_id: dict[int, MetricPluginVersionModel] = {
        int(version_model.pk): version_model
        for version_model in MetricPluginVersionModel.objects.filter(id__in=version_ids)
    }

    # 批量聚合统计每个插件的部署项数量
    if with_deployment_count:
        deployment_counts = (
            MetricPluginDeploymentModel.objects.filter(plugin__in=plugin_models_list)
            .values("plugin_id")
            .annotate(deployment_count=Count("id"))
        )
        deployment_count_by_plugin_pk: dict[int, int] = {
            int(deployment_count["plugin_id"]): int(deployment_count["deployment_count"])
            for deployment_count in deployment_counts
        }
    else:
        deployment_count_by_plugin_pk = {}

    plugins: list[MetricPluginInfo] = []
    for plugin_model in plugin_models_list:
        latest_release_id = getattr(plugin_model, "latest_release_id", None)
        latest_debug_id = getattr(plugin_model, "latest_debug_id", None)

        release_version_model = (
            version_model_by_id.get(int(latest_release_id)) if latest_release_id is not None else None
        )
        debug_version_model = version_model_by_id.get(int(latest_debug_id)) if latest_debug_id is not None else None
        display_version_model = release_version_model or debug_version_model

        if not display_version_model:
            continue

        # 构造 MetricPluginInfo 对象
        plugin_info: MetricPluginInfo = {
            "bk_tenant_id": plugin_model.bk_tenant_id,
            "bk_biz_id": plugin_model.bk_biz_id,
            "is_global": plugin_model.is_global,
            "is_internal": plugin_model.is_internal,
            "id": plugin_model.plugin_id,
            "type": plugin_model.type,
            "name": display_version_model.name,
            "logo": display_version_model.logo,
            "label": plugin_model.label,
            "release_version": release_version_model.version_tuple if release_version_model else None,
            "debug_version": debug_version_model.version_tuple if debug_version_model else None,
            "deployment_count": (
                deployment_count_by_plugin_pk.get(int(plugin_model.pk), 0) if with_deployment_count else None
            ),
            "created_at": plugin_model.created_at,
            "updated_at": display_version_model.updated_at,
            "created_by": plugin_model.created_by,
            "updated_by": display_version_model.updated_by,
        }
        plugins.append(plugin_info)

    return plugins, total


def get_metric_plugin(
    bk_tenant_id: str,
    plugin_id: str,
    version: VersionTuple | None = None,
    status: MetricPluginStatus | None = None,
) -> MetricPlugin:
    """获取插件

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        plugin_id: 插件ID
        version: 版本号，如果为None，则使用插件的最新版本。
        status: 状态，如果为None，则使用插件的最新版本。

    Returns:
        MetricPlugin: 插件

    Raises:
        MetricPluginVersionNotFoundError: 插件版本不存在
    """
    plugin_model = MetricPluginModel.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False
    ).first()
    if not plugin_model:
        raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}")

    return plugin_model.to_plugin(version=version, status=status)


class VersionLogTypedDict(TypedDict):
    """
    版本日志 类型定义
    """

    version: VersionTuple
    version_log: str
    status: MetricPluginStatus
    updated_at: datetime
    updated_by: str


def get_metric_plugin_versions(
    bk_tenant_id: str,
    plugin_id: str,
    status: MetricPluginStatus | None = MetricPluginStatus.RELEASE,
) -> list[VersionLogTypedDict]:
    """获取插件版本日志

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        plugin_id: 插件ID
        status: 状态，默认只获取已发布的版本日志

    Returns:
        list[VersionLogTypedDict]: 版本日志

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    plugin_model = MetricPluginModel.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False
    ).first()
    if not plugin_model:
        raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}")

    versions = MetricPluginVersionModel.objects.filter(bk_tenant_id=bk_tenant_id, plugin=plugin_model)

    if status is not None:
        versions = versions.filter(status=status.value)

    return [
        {
            "version": version.version_tuple,
            "version_log": version.version_log,
            "status": MetricPluginStatus(version.status),
            "updated_at": version.updated_at,
            "updated_by": version.updated_by,
        }
        for version in versions
    ]


def create_metric_plugin(bk_tenant_id: str, bk_biz_id: int, operator: str, params: CreatePluginParams) -> MetricPlugin:
    """创建插件

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        operator: 操作者
        params: 创建插件参数

    Returns:
        MetricPlugin: 创建的插件对象

    Raises:
        ValueError: 插件ID已存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    # 校验插件ID是否已存在
    check_metric_plugin_id(bk_tenant_id=bk_tenant_id, plugin_id=params.id)

    plugin_manager_class = get_plugin_manager_class(plugin_type=params.type)
    metric_plugin = plugin_manager_class.create_plugin(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, operator=operator, params=params
    )
    return metric_plugin.plugin


def create_metric_plugin_version(
    bk_tenant_id: str, plugin_id: str, operator: str, params: CreatePluginVersionParams
) -> tuple[bool, VersionTuple]:
    """创建插件版本

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        operator: 操作者
        params: 创建插件版本参数

    Returns:
        tuple[bool, VersionTuple]: 是否创建成功，版本号

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
        PluginVersionReleasedError: 插件版本已发布，无法创建新版本
        PluginVersionLessThanReleasedError: 插件版本小于已发布版本，无法创建新版本
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
    return plugin_manager.create_plugin_version(params=params, operator=operator)


def update_metric_plugin_version(
    bk_tenant_id: str,
    plugin_id: str,
    version: VersionTuple,
    operator: str,
    params: UpdatePluginVersionParams,
) -> None:
    """更新插件版本配置

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 版本号
        operator: 操作者
        params: 更新插件版本参数

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager.update_plugin_version(params=params, operator=operator)


def export_metric_plugin_package(
    bk_tenant_id: str,
    plugin_id: str,
    operator: str,
    version: VersionTuple | None = None,
) -> str:
    """导出插件包

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 版本号
        operator: 操作者

    Returns:
        str: 插件包下载链接

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
        NotImplementedError: 插件管理器不支持导出插件包
    """
    if version is None:
        plugin_model = MetricPluginModel.objects.filter(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            is_deleted=False,
        ).first()
        if not plugin_model:
            raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}")

        plugin_manager_class = get_plugin_manager_class(plugin_model.type)
        plugin_manager = plugin_manager_class(
            plugin=plugin_model.to_plugin(status=MetricPluginStatus.RELEASE),
            plugin_model=plugin_model,
        )
    else:
        plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    return plugin_manager.export_package(operator=operator)


def register_metric_plugin(bk_tenant_id: str, plugin_id: str, version: VersionTuple, operator: str) -> list[str]:
    """注册插件

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 版本号
        operator: 操作者

    Returns:
        list[str]: 注册成功的md5列表

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    return plugin_manager.register(operator=operator)


def apply_metric_plugin_data_link(bk_tenant_id: str, plugin_id: str, version: VersionTuple, operator: str) -> None:
    """申请插件数据链路

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 版本号
        operator: 操作者

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager.apply_data_link(operator=operator)


def refresh_metric_plugin_metrics(bk_tenant_id: str, plugin_id: str, version: VersionTuple, operator: str) -> None:
    """刷新插件指标配置。

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 版本号
        operator: 操作者
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager.refresh_metrics(operator=operator)


def release_metric_plugin_version(
    bk_tenant_id: str,
    plugin_id: str,
    version: VersionTuple,
    operator: str,
    apply_data_link: bool = True,
    md5_list: list[str] | None = None,
) -> None:
    """发布插件版本

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 版本号
        operator: 操作者

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager.release_plugin_version(operator=operator, apply_data_link=apply_data_link, md5_list=md5_list)


def delete_metric_plugin(bk_tenant_id: str, plugin_id: str, operator: str):
    """
    删除插件

    由于插件的背后存在数据链路接入及相关存储配置，目前仅支持软删除，插件ID仍然会被占用。
    删除插件前，需要先删除所有的插件部署项。

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """

    # 检查是否存在部署项
    if MetricPluginDeploymentModel.objects.filter(bk_tenant_id=bk_tenant_id, plugin__plugin_id=plugin_id).exists():
        raise MetricPluginDeploymentExistsError(f"插件({bk_tenant_id}/{plugin_id})存在部署项，无法删除")

    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
    plugin_manager.delete_plugin(operator=operator)


def check_metric_plugin_id(bk_tenant_id: str, plugin_id: str):
    """检查新建插件ID是否合法

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID

    Raises:
        PluginIDFormatError: 插件ID长度超过限制
        PluginIDFormatError: 插件ID格式错误
        PluginIDExistsError: 插件ID已存在
        PluginIDExistsError: 插件ID已经在节点管理被占用
    """

    plugin_id = plugin_id.strip()

    # 检查插件ID长度
    if len(plugin_id) > 30:
        raise PluginIDInvalidError(f"插件ID长度超过限制: {plugin_id}")

    # 检查插件ID格式
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", plugin_id):
        raise PluginIDInvalidError(f"插件ID仅允许包含字母、数字、下划线，且必须以字母开头: {plugin_id}")

    # 检查插件ID是否已存在
    if MetricPluginModel.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False).exists():
        raise PluginIDExistsError(f"插件ID已存在: {bk_tenant_id}/{plugin_id}")

    # 检查插件ID是否在节点管理被占用
    try:
        nodeman_api.get_plugin_info(bk_tenant_id=bk_tenant_id, name=plugin_id)
    except BkApiError as e:
        if e.third_api_error_code == "3800100":
            return
        else:
            raise e
    else:
        raise PluginIDExistsError(f"插件ID已经在节点管理被占用: {bk_tenant_id}/{plugin_id}")


def parse_metric_plugin_package(bk_tenant_id: str, package_file: Path, operator: str) -> CreatePluginParams:
    """解析插件包

    该函数会先识别插件类型，再路由到对应的插件管理器执行解析。
    ``package_file`` 可以是 tgz 压缩包，也可以是已经解压好的目录；传入目录时会跳过解压，
    并保留该目录，便于上层在导入链路中复用同一份临时产物。

    Args:
        bk_tenant_id: 租户ID
        package_file: 插件包路径，支持 tgz 压缩包或已解压目录
        operator: 操作者

    Returns:
        CreatePluginParams: 解析结果
    """
    plugin_type = get_plugin_type_from_package(package_file=package_file)
    plugin_manager = get_plugin_manager_class(plugin_type=plugin_type)
    return plugin_manager.parse_package(bk_tenant_id=bk_tenant_id, package_file=package_file, operator=operator)


def list_metric_plugin_deployments(
    bk_tenant_id: str,
    bk_biz_ids: list[int] | None,
    plugin_types: list[str] | None = None,
    plugin_ids: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[list[MetricPluginDeployment], int]:
    """获取插件部署项列表

    Args:
        bk_tenant_id: 租户ID
        bk_biz_ids: 业务ID列表
        plugin_types: 插件类型列表
        plugin_ids: 插件ID列表
        limit: 分页大小
        offset: 分页偏移量

    Returns:
        插件部署项列表和总数
    """

    deployments = MetricPluginDeploymentModel.objects.filter(bk_tenant_id=bk_tenant_id)

    # 过滤业务ID
    if bk_biz_ids:
        deployments = deployments.filter(bk_biz_id__in=bk_biz_ids)

    # 过滤插件类型
    if plugin_types:
        deployments = deployments.filter(plugin__type__in=plugin_types)

    # 过滤插件ID
    if plugin_ids:
        deployments = deployments.filter(plugin__plugin_id__in=plugin_ids)

    total = deployments.count()

    # 分页
    if limit is not None and offset is not None:
        deployments = deployments[offset : offset + limit]

    return [deployment.to_deployment() for deployment in deployments], total


def get_metric_plugin_deployment(
    bk_tenant_id: str, deployment_id: int, bk_biz_id: int | None = None
) -> tuple[MetricPluginDeployment, MetricPluginDeploymentVersion | None]:
    """获取插件部署项详情

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        deployment_id: 部署项ID

    Returns:
        插件部署项信息及当前版本信息
    """
    query_set = MetricPluginDeploymentModel.objects.filter(bk_tenant_id=bk_tenant_id, id=deployment_id)
    if bk_biz_id is not None:
        query_set = query_set.filter(bk_biz_id=bk_biz_id)

    deployment = query_set.first()
    if not deployment:
        raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")

    return deployment.to_deployment(), deployment.get_current_version()


def save_and_install_metric_plugin_deployment(
    bk_tenant_id: str,
    bk_biz_id: int,
    operator: str,
    params: CreateOrUpdateDeploymentParams,
) -> Any:
    """保存并安装插件部署项

    Note:
        1. 当id为空时，表示创建部署项，否则表示更新部署项。
        2. 如果版本相关参数未变化，则不变更版本号，仅重新触发一次install。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        operator: 操作者
        params: 部署参数

    Returns:
        Any: 安装结果
    """
    # 1. 预检查
    plugin_model = None
    if params.id:
        deployment_model = MetricPluginDeploymentModel.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=params.id
        ).first()
        if not deployment_model:
            raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{params.id}")
    else:
        plugin_model = MetricPluginModel.objects.filter(
            bk_tenant_id=bk_tenant_id, plugin_id=params.plugin_id, is_deleted=False
        ).first()
        if not plugin_model:
            raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{params.plugin_id}")

    # 2. 数据库变更原子操作块
    with transaction.atomic():
        if params.id:
            # 锁定部署项进行更新
            deployment_model = MetricPluginDeploymentModel.objects.select_for_update().get(id=params.id)
            deployment_model.name = params.name
            deployment_model.updated_by = operator
            deployment_model.save(update_fields=["name", "updated_by"])
        else:
            # 创建部署项 (此时 plugin_model 必定已定义)
            deployment_model = MetricPluginDeploymentModel.objects.create(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                plugin=plugin_model,
                name=params.name,
                status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
                created_by=operator,
                updated_by=operator,
            )

        deployment = deployment_model.to_deployment()

        # 获取当前最大版本号记录
        last_version_model: MetricPluginDeploymentVersionModel | None = (
            MetricPluginDeploymentVersionModel.objects.filter(deployment=deployment_model).order_by("-version").first()
        )
        last_version: int = last_version_model.version if last_version_model else 0
        # 构造新的部署版本对象（暂定版本号为 last_version + 1）
        next_version: int = last_version + 1
        deployment_version = MetricPluginDeploymentVersion(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            deployment_id=deployment_model.pk,
            plugin_version=params.plugin_version,
            version=next_version,
            target_scope=params.target_scope,
            remote_scope=params.remote_scope,
            params=params.params,
            created_by=operator,
        )

        installer = get_installer(deployment, operator)
        # 3. 执行安装（放到事务内部，避免实际操作失败，仍然创建了部署项）
        return installer.install(deployment_version)


def delete_metric_plugin_deployment(bk_tenant_id: str, bk_biz_id: int, deployment_id: int):
    """删除插件部署项

    Note:
        仅在部署项为stopped状态时，才允许删除。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        deployment_id: 部署项ID
    """

    deployment = MetricPluginDeploymentModel.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=deployment_id
    ).first()
    if not deployment:
        raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")

    # 检查部署项状态，只有stopped状态才能删除
    if deployment.status != MetricPluginDeploymentStatusEnum.STOPPED.value:
        raise MetricPluginDeploymentStatusError(f"部署项状态不为stopped: {deployment.status}, 不允许删除")

    # 删除部署项及对应版本
    with transaction.atomic():
        MetricPluginDeploymentVersionModel.objects.filter(deployment=deployment).delete()
        deployment.delete()


def start_metric_plugin_deployment(
    bk_tenant_id: str,
    bk_biz_id: int,
    deployment_id: int,
    operator: str,
) -> Any:
    """启动插件部署项

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        deployment_id: 部署项ID
        operator: 操作者
    """
    with transaction.atomic():
        deployment_model = (
            MetricPluginDeploymentModel.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=deployment_id)
            .select_for_update()
            .first()
        )

        if not deployment_model:
            raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")

        if deployment_model.status != MetricPluginDeploymentStatusEnum.STOPPED.value:
            raise MetricPluginDeploymentOperationError(f"部署状态为{deployment_model.status}，无法启动")

        deployment_model.status = MetricPluginDeploymentStatusEnum.STARTING.value
        deployment_model.save(update_fields=["status"])
        deployment = deployment_model.to_deployment()

    installer = get_installer(deployment, operator)
    return installer.start()


def stop_metric_plugin_deployment(
    bk_tenant_id: str,
    bk_biz_id: int,
    deployment_id: int,
    operator: str,
) -> Any:
    """停止插件部署项

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        deployment_id: 部署项ID
        operator: 操作者
    """
    with transaction.atomic():
        deployment_model = (
            MetricPluginDeploymentModel.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=deployment_id)
            .select_for_update()
            .first()
        )

        if not deployment_model:
            raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")

        if deployment_model.status != MetricPluginDeploymentStatusEnum.RUNNING.value:
            raise MetricPluginDeploymentOperationError(f"部署状态为{deployment_model.status}，无法停止")

        deployment_model.status = MetricPluginDeploymentStatusEnum.STOPPING.value
        deployment_model.save(update_fields=["status"])
        deployment = deployment_model.to_deployment()

    installer = get_installer(deployment, operator)
    return installer.stop()


def retry_metric_plugin_deployment(
    bk_tenant_id: str,
    bk_biz_id: int,
    operator: str,
    params: RetryDeployPluginParams,
) -> Any:
    """重试插件部署项

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        operator: 操作者
        params: 重试部署参数
    """
    deployment_model = MetricPluginDeploymentModel.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=params.deployment_id
    ).first()
    if not deployment_model:
        raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{params.deployment_id}")
    deployment = deployment_model.to_deployment()
    installer = get_installer(deployment, operator)
    return installer.retry(params.instance_scope)


def get_metric_plugin_deployment_status(
    bk_tenant_id: str,
    deployment_id: int,
    bk_biz_id: int | None = None,
) -> Any:
    """获取插件部署项状态

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        deployment_id: 部署项ID

    Returns:
        Any: 状态信息
    """
    query_set = MetricPluginDeploymentModel.objects.filter(bk_tenant_id=bk_tenant_id, id=deployment_id)
    if bk_biz_id is not None:
        query_set = query_set.filter(bk_biz_id=bk_biz_id)

    deployment_model = query_set.first()
    if not deployment_model:
        raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")
    deployment = deployment_model.to_deployment()

    # 获取 installer，operator 传空即可，仅查询状态不需要 operator
    installer = get_installer(deployment, operator="")
    return installer.status()


def get_metric_plugin_supported_os_types(bk_tenant_id: str, plugin_id: str) -> list[str]:
    """获取插件支持的操作系统类型

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID

    Returns:
        list[str]: 支持的操作系统类型列表

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
    """
    plugin_manager = get_plugin_manager(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
    return [os_type.value for os_type in plugin_manager.get_supported_os_types()]


def debug_nodeman_plugin(
    bk_tenant_id: str,
    plugin_id: str,
    version: VersionTuple,
    collect_params: dict[str, Any],
    plugin_params: dict[str, Any],
    collect_host: dict[str, Any],
    target_nodes: list[dict[str, Any]],
    operator: str,
) -> DebugNodemanPluginResult:
    """启动 nodeman 类型插件调试

    通过节点管理启动插件调试任务，在指定主机上执行插件并采集调试数据。

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 插件版本，格式为 (major, minor)
        collect_params: 采集参数，如采集周期、超时时间等内置参数
        plugin_params: 插件定义参数，用户自定义的参数
        collect_host: 采集主机信息，如 {"bk_host_id": 1}
        target_nodes: 采集目标节点列表
        operator: 操作人

    Returns:
        DebugNodemanPluginResult: 包含调试任务 task_id

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 非 nodeman 类型插件，不支持调试
    """
    plugin_model = MetricPluginModel.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False
    ).first()
    if not plugin_model:
        raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}")

    plugin = plugin_model.to_plugin(version=version)
    manager = get_nodeman_plugin_manager(plugin)

    task_id = manager.start_debug(
        collect_params=collect_params,
        plugin_params=plugin_params,
        collect_host=collect_host,
        target_nodes=target_nodes,
        operator=operator,
    )
    return {"task_id": task_id}


def get_nodeman_collect_log_detail(
    bk_tenant_id: str,
    deployment_id: int,
    bk_biz_id: int,
    instance_id: str,
    operator: str,
) -> dict[str, Any]:
    """获取节点管理采集日志详情
    Args:
        bk_tenant_id: 租户ID
        deployment_id: 部署项ID
        bk_biz_id: 业务ID
        instance_id: 采集实例ID
        operator: 操作者

    Returns:
        dict[str,Any]: 采集日志详情
    Raises:
        MetricPluginDeploymentNotFoundError: 部署项不存在
        MetricPluginDeploymentOperationError: 部署项非节点管理类型，无法获取采集日志详情
    """
    deployment_model = MetricPluginDeploymentModel.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=deployment_id
    ).first()
    if not deployment_model:
        raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")
    deployment = deployment_model.to_deployment()
    installer = get_installer(deployment, operator=operator)
    if not isinstance(installer, NodemanInstaller):
        raise MetricPluginDeploymentOperationError(f"部署项({deployment_id})非节点管理类型，无法获取采集日志详情")
    collect_log_detail = installer.instance_status(
        instance_id=instance_id,
    )

    return collect_log_detail


def get_job_collect_log_detail(
    bk_tenant_id: str,
    deployment_id: int,
    bk_biz_id: int,
    instance_id: str,
    operator: str,
) -> dict[str, Any]:
    """获取作业平台采集日志详情
    Args:
        bk_tenant_id: 租户ID
        deployment_id: 部署项ID
        bk_biz_id: 业务ID
        instance_id: 采集实例ID
        operator: 操作者

    Returns:
        dict[str,Any]: Job 采集日志详情，当前结构参考 installer.define.JobCollectLogDetail，保留 dict 便于后续扩展
    Raises:
        MetricPluginDeploymentNotFoundError: 部署项不存在
        MetricPluginDeploymentOperationError: 部署项非作业平台类型，无法获取采集日志详情
    """
    deployment_model = MetricPluginDeploymentModel.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=deployment_id
    ).first()
    if not deployment_model:
        raise MetricPluginDeploymentNotFoundError(f"部署项不存在: {bk_tenant_id}/{bk_biz_id}/{deployment_id}")
    deployment = deployment_model.to_deployment()
    installer = get_installer(deployment, operator=operator)
    if not isinstance(installer, JobInstaller):
        raise MetricPluginDeploymentOperationError(f"部署项({deployment_id})非作业平台类型，无法获取采集日志详情")
    collect_log_detail = installer.instance_status(
        instance_id=instance_id,
    )

    return collect_log_detail


def get_nodeman_plugin_debug_log(
    bk_tenant_id: str,
    plugin_id: str,
    task_id: int,
    operator: str,
    version: VersionTuple | None = None,
) -> GetNodemanPluginDebugLogResult:
    """获取 nodeman 类型插件调试日志

    查询指定调试任务的执行结果，返回解析后的指标信息。

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 插件版本，格式为 (major, minor)
        task_id: 调试任务ID，由 debug_nodeman_plugin 返回
        operator: 操作人

    Returns:
        GetNodemanPluginDebugLogResult: 包含 metric_json, last_time, error_message

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 非 nodeman 类型插件
        ParsePluginDebugContentError: 调试日志解析失败
    """
    plugin_model = MetricPluginModel.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False
    ).first()
    if not plugin_model:
        raise MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}")

    plugin = plugin_model.to_plugin(version=version)
    manager = get_nodeman_plugin_manager(plugin)

    result = manager.get_debug_log(task_id=task_id, operator=operator)

    # Normalize and validate metric_json to match DebugMetricInfo structure
    raw_metric_json: list[dict[str, Any]] = result.get("metric_json", [])
    normalized_metric_json: list[DebugMetricInfo] = []
    for item in raw_metric_json:
        # Ensure required keys exist; skip malformed entries
        if not all(k in item for k in ("metric_name", "metric_value", "dimensions")):
            continue
        metric_name = str(item["metric_name"])
        metric_value = item["metric_value"]
        dimensions: list[dict[str, str]] = item.get("dimensions", [])
        normalized_metric_json.append(
            {
                "metric_name": metric_name,
                "metric_value": metric_value,
                "dimensions": dimensions,
            }
        )

    return {
        "status": result["status"],
        "metric_json": normalized_metric_json,
        "last_time": result["last_time"],
        "error_message": result["error_message"],
        "log": result["log"],
    }


def stop_nodeman_plugin_debug(
    bk_tenant_id: str,
    plugin_id: str,
    task_id: int,
    operator: str,
    version: VersionTuple | None = None,
) -> None:
    """停止节点管理插件调试

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        version: 插件版本
        task_id: 调试任务ID
        operator: 操作人

    Raises:
        MetricPluginNotFoundError: 插件不存在
        MetricPluginManagerNotFoundError: 插件管理器不存在
        BkApiError: 接口调用失败
    """
    plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager = get_nodeman_plugin_manager(plugin)
    plugin_manager.stop_debug(task_id=task_id, operator=operator)


def upload_plugin_file(
    bk_tenant_id: str,
    plugin_type: str,
    file_or_content: FILE_OR_CONTENT_TYPE,
    os_type: OSType,
    operator: str,
) -> tuple[FileInfo, dict[str, Any]]:
    """上传插件文件

    Args:
        bk_tenant_id: 租户ID
        plugin_id: 插件ID
        file_or_content: 文件或内容
        os_type: 操作系统类型
        operator: 操作者

    Returns:
        FileInfo: 文件信息
        dict[str, Any]: 提取信息

    Raises:
        PluginFileUploadError: 文件上传失败
    """
    plugin_manager = cast(NodemanPluginManager, get_plugin_manager_class(plugin_type=plugin_type))
    is_valid, msg, extract_info = plugin_manager.check_file(file_or_content=file_or_content, os_type=os_type)
    if not is_valid:
        raise PluginFileUploadError(msg)

    file_info = save_file(
        bk_tenant_id=bk_tenant_id,
        usage="metric_plugin",
        description=f"plugin_type: {plugin_type}, os_type: {os_type}",
        created_by=operator,
        file_or_content=file_or_content,
    )
    return file_info, extract_info


def debug_job_plugin(
    bk_tenant_id: str,
    plugin_id: str,
    collect_params: dict[str, Any],
    plugin_params: dict[str, Any],
    collect_host: dict[str, Any],
    operator: str,
    version: VersionTuple | None = None,
    plugin: MetricPlugin | None = None,
) -> DebugJobPluginResult:
    """启动 Job 类型插件调试"""

    plugin = plugin or get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager = get_job_plugin_manager(plugin)
    task_id = plugin_manager.start_debug(
        collect_params=collect_params,
        plugin_params=plugin_params,
        collect_host=collect_host,
        operator=operator,
    )
    return {"task_id": task_id}


def get_job_plugin_debug_log(
    bk_tenant_id: str,
    plugin_id: str | None,
    task_id: int,
    version: VersionTuple | None = None,
) -> GetJobPluginDebugLogResult:
    """获取 Job 类型插件调试日志"""

    if plugin_id is None:
        debug_task = JobMetricPluginDebugInst.get(task_id)
        if debug_task is None:
            raise ValueError(f"调试任务 {task_id} 不存在")
        plugin_id = debug_task.job_plugin_id

    plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager = get_job_plugin_manager(plugin)
    task_log, debug_status, metric_json = plugin_manager.get_debug_log(task_id=task_id)
    return {
        "task_log": task_log,
        "debug_status": debug_status,
        "metric_json": metric_json,
    }


def stop_job_plugin_debug(
    bk_tenant_id: str,
    plugin_id: str,
    task_id: int,
    operator: str,
    version: VersionTuple | None = None,
) -> None:
    """停止 Job 类型插件调试"""

    plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
    plugin_manager = get_job_plugin_manager(plugin)
    plugin_manager.stop_debug(task_id=task_id, operator=operator)
