"""
每个 Model 提供统一的 get_xxx, list_xxx, save_xxx, delete_xxx 函数，
仅返回 Define 对象（固定结构），职责明确，易于维护和扩展。

1. Task 操作
   - get_task: 获取单个任务 -> UptimeCheckTask
   - list_tasks: 列表查询任务 -> list[UptimeCheckTask]
     * 支持 fields 参数仅加载指定字段，to_define() 自动为 deferred 字段填充默认值
   - save_task: 创建或更新任务
   - delete_task: 删除任务
   - control_task: 部署/启动/停止任务
   - refresh_task_status: 刷新任务状态（从节点管理获取最新状态）

2. Node 操作
   - get_node: 获取单个节点 -> UptimeCheckNode
   - list_nodes: 列表查询节点 -> list[UptimeCheckNode]
   - save_node: 创建或更新节点
   - delete_node: 删除节点

3. Group 操作
   - get_group: 获取单个分组 -> UptimeCheckGroup
   - list_groups: 列表查询分组 -> list[UptimeCheckGroup]
   - save_group: 创建或更新分组
   - delete_group: 删除分组
   - manage_group_tasks: 管理分组与任务的关联

5. CollectorLog 操作
   - create_collector_log: 创建采集日志
"""

import logging
from datetime import datetime
from typing import Any, TypedDict

from bkmonitor.nodeman_integration.backend import node_man_backend
from bkmonitor.nodeman_integration.exceptions import NodeManV3DefiniteFailure
from django.db import transaction
from django.db.models import Prefetch, Q

from bk_monitor_base.config import get_config
from bk_monitor_base.domains.space.cache import bk_biz_id_to_bk_tenant_id
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckGroupModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskCollectorLog,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)
from bk_monitor_base.domains.uptime_check.services.config_generator import ConfigGeneratorService
from bk_monitor_base.domains.uptime_check.services.task_manager import TaskManager
from bk_monitor_base.infras.third_party_api.nodeman import api as node_man_v2_api

from .constants import CollectStatus
from .define import (
    UptimeCheckGroup,
    UptimeCheckNode,
    UptimeCheckNodeIPType,
    UptimeCheckTask,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
)

logger = logging.getLogger(__name__)


def _is_nodeman_v3_enabled() -> bool:
    return node_man_backend.is_v3


def _check_bk_biz_id_tenant_id(bk_biz_id: int | None, bk_tenant_id: str | None) -> None:
    """检查业务ID和租户ID是否匹配

    Args:
        bk_biz_id: 业务ID（可选）
        bk_tenant_id: 租户ID（可选）

    Raises:
        ValueError: 业务ID和租户ID不匹配

    Notes:
        - 如果任一参数为 None，则跳过检查
        - 只有当两个参数都存在时才进行校验
    """
    if bk_biz_id is None or bk_tenant_id is None:
        return

    expected_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
    if expected_tenant_id != bk_tenant_id:
        raise ValueError(
            f"业务ID和租户ID不匹配: bk_biz_id={bk_biz_id}, expected_tenant_id={expected_tenant_id}, bk_tenant_id={bk_tenant_id}"
        )


# ===================== 类型定义 =====================


class TaskQueryParams(TypedDict, total=False):
    """任务查询参数"""

    task_id: int  # 精确查询单个任务
    task_ids: list[int]  # 批量查询多个任务
    name: str  # 模糊搜索任务名称
    protocol: UptimeCheckTaskProtocol  # 协议类型
    status: UptimeCheckTaskStatus  # 任务状态
    node_ids: list[int]  # 关联节点ID列表
    group_ids: list[int]  # 关联分组ID列表


class NodeQueryParams(TypedDict, total=False):
    """节点查询参数"""

    node_id: int  # 精确查询单个节点
    node_ids: list[int]  # 批量查询多个节点
    bk_host_ids: list[int]  # CMDB主机ID列表
    bk_biz_ids: list[int]  # 业务ID列表（过滤多个业务下的节点）
    ip: str  # 精确匹配IP
    plat_id: int  # 云区域ID
    name: str  # 模糊搜索名称
    name_prefix: str  # 名称前缀匹配
    ip_type: UptimeCheckNodeIPType  # IP类型
    is_common: bool  # 是否为公共节点
    include_common: bool  # 是否包含公共节点
    carrieroperator: str  # 运营商
    exclude_carrieroperators: list[str]  # 排除的运营商列表


class GroupQueryParams(TypedDict, total=False):
    """分组查询参数"""

    group_id: int  # 精确查询单个分组
    group_ids: list[int]  # 批量查询多个分组
    name: str  # 模糊搜索名称
    include_global: bool  # 是否包含全局分组（bk_biz_id=0）
    task_id: int  # 关联的任务ID


# 兼容类型别名：允许 TypedDict 或普通 dict 字面量
TaskQueryParamsInput = TaskQueryParams | dict[str, Any]
NodeQueryParamsInput = NodeQueryParams | dict[str, Any]
GroupQueryParamsInput = GroupQueryParams | dict[str, Any]

# ===================== Task 统一操作 =====================

# to_define() 中无 deferred 默认值保护的必要字段（不可被 only() 裁剪掉）
_TASK_REQUIRED_FIELDS: frozenset[str] = frozenset({"id", "bk_biz_id", "name", "protocol", "status"})

# fields 参数中代表 M2M 关联的虚拟字段名（不是真实数据库列，不能传给 only()）
_TASK_VIRTUAL_FIELDS: frozenset[str] = frozenset({"node_ids", "group_ids"})


def get_task(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    task_id: int | None = None,
    name: str | None = None,
) -> UptimeCheckTask:
    """获取单个任务

    Args:
        bk_tenant_id: 租户ID（可选，与 bk_biz_id 配合使用时校验）
        bk_biz_id: 业务ID（可选）
        task_id: 任务ID（与 name 二选一）
        name: 任务名称（与 task_id 二选一，需配合 bk_biz_id）

    Returns:
        UptimeCheckTask 定义对象

    Raises:
        UptimeCheckTaskModel.DoesNotExist: 任务不存在
        ValueError: 参数错误
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    if task_id:
        queryset = UptimeCheckTaskModel.objects.filter(pk=task_id, is_deleted=False)
        if bk_biz_id:
            queryset = queryset.filter(bk_biz_id=bk_biz_id)
    elif name and bk_biz_id:
        queryset = UptimeCheckTaskModel.objects.filter(name=name, bk_biz_id=bk_biz_id, is_deleted=False)
    else:
        raise ValueError("必须提供 task_id 或 (name + bk_biz_id)")

    task_model = queryset.get()
    return task_model.to_define()


def _build_task_queryset(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    query: TaskQueryParamsInput | None = None,
):
    """构建任务 QuerySet（过滤条件部分，供 list_tasks 和 count_tasks 共用）

    Returns:
        QuerySet: 应用业务、删除状态和 query 过滤后的任务 QuerySet。
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    queryset = UptimeCheckTaskModel.objects.filter(is_deleted=False)
    if bk_biz_id:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)

    if not query:
        return queryset

    if task_id := query.get("task_id"):
        queryset = queryset.filter(pk=task_id)
    if task_ids := query.get("task_ids"):
        queryset = queryset.filter(pk__in=task_ids)
    if name := query.get("name"):
        queryset = queryset.filter(name__icontains=name)
    if protocol := query.get("protocol"):
        queryset = queryset.filter(protocol=protocol.value)
    if status := query.get("status"):
        queryset = queryset.filter(status=status.value)
    if node_ids := query.get("node_ids"):
        queryset = queryset.filter(nodes__id__in=node_ids)
    if group_ids := query.get("group_ids"):
        queryset = queryset.filter(groups__id__in=group_ids)

    if query.get("group_ids") or query.get("node_ids"):
        queryset = queryset.distinct()

    return queryset


def _validate_pagination_params(page: int | None, page_size: int | None) -> bool:
    """校验分页参数。

    Args:
        page: 页码，从 1 开始
        page_size: 每页条数

    Returns:
        bool: 是否启用分页

    Raises:
        ValueError: page 和 page_size 未成对提供，或任一参数小于等于 0
    """
    if (page is None) != (page_size is None):
        raise ValueError("page 和 page_size 必须同时提供")

    if page is None and page_size is None:
        return False

    if page is not None and page <= 0:
        raise ValueError("page 必须大于 0")
    if page_size is not None and page_size <= 0:
        raise ValueError("page_size 必须大于 0")

    return True


def list_tasks(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    query: TaskQueryParamsInput | None = None,
    fields: list[str] | None = None,
    order_by: str | list[str] | None = None,
    page: int | None = None,  # 页码
    page_size: int | None = None,  # 每页条数
) -> list[UptimeCheckTask]:
    """列表查询任务

    Args:
        bk_tenant_id: 租户ID（可选，与 bk_biz_id 配合使用时校验）
        bk_biz_id: 业务ID（可选）
        query: 查询过滤参数
        fields: 指定需要加载的字段。数据库列名透传给 only()，未指定的列在 define 中
                返回默认值；虚拟字段 "node_ids"/"group_ids" 控制是否查询 M2M 关联
                （不指定时返回空列表）。核心字段会自动补充，无需手动包含。
        order_by: 排序参数
        page: 页码（可选），与 page_size 配合使用
        page_size: 每页条数（可选），与 page 配合使用

    Returns:
        list[UptimeCheckTask]: 任务 Define 对象列表

    Examples:
        # 获取所有任务（完整字段 + 关联 ID）
        tasks = list_tasks(bk_tenant_id, bk_biz_id)

        # 仅获取轻量字段，跳过大字段 config 和关联查询
        tasks = list_tasks(bk_tenant_id, bk_biz_id, fields=["id", "name", "status"])

        # 跳过 config，但仍需关联节点 ID
        tasks = list_tasks(bk_tenant_id, bk_biz_id, fields=["id", "name", "status", "node_ids"])

        # 分页查询
        tasks = list_tasks(bk_tenant_id, bk_biz_id, page=1, page_size=20)
    """
    queryset = _build_task_queryset(bk_tenant_id, bk_biz_id, query=query)
    has_pagination = _validate_pagination_params(page, page_size)

    # 根据order_by参数排序
    if order_by:
        if isinstance(order_by, str):
            order_by = [order_by]
        queryset = queryset.order_by(*order_by)
    elif has_pagination:
        queryset = queryset.order_by("id")

    if fields:
        fields_set = set(fields)
        # 虚拟字段控制 M2M 关联加载，不能传入 only()
        include_node_ids = "node_ids" in fields_set
        include_group_ids = "group_ids" in fields_set
        # 补充必要字段，确保 to_define() 中无默认值保护的核心字段始终被加载
        db_fields = (fields_set - _TASK_VIRTUAL_FIELDS) | _TASK_REQUIRED_FIELDS
        queryset = queryset.only(*db_fields)
    else:
        # 未指定 fields 时默认加载全部字段和关联
        include_node_ids = True
        include_group_ids = True

    # 按需执行 Prefetch，避免不必要的关联查询
    prefetch_list = []
    if include_node_ids:
        prefetch_list.append(
            Prefetch("nodes", queryset=UptimeCheckNodeModel.objects.only("pk"), to_attr="node_id_list")
        )
    if include_group_ids:
        prefetch_list.append(
            Prefetch("groups", queryset=UptimeCheckGroupModel.objects.only("pk"), to_attr="group_id_list")
        )
    if prefetch_list:
        queryset = queryset.prefetch_related(*prefetch_list)

    # 分页：不传 page/page_size 时行为完全不变（向后兼容）
    if page is not None and page_size is not None:
        offset = (page - 1) * page_size
        queryset = queryset[offset : offset + page_size]

    # 返回 Define 对象列表
    return [task.to_define(include_node_ids=include_node_ids, include_group_ids=include_group_ids) for task in queryset]


def count_tasks(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    query: TaskQueryParamsInput | None = None,
) -> int:
    """查询任务总数，接受和 list_tasks 相同的过滤参数。

    仅执行 COUNT 查询，不加载 M2M 关联、不转换为 Define 对象。
    """
    queryset = _build_task_queryset(bk_tenant_id, bk_biz_id, query=query)
    return queryset.count()


def save_task(
    task: UptimeCheckTask,
    operator: str,
    *,
    node_ids: list[int] | None = None,
    group_ids: list[int] | None = None,
) -> int:
    """创建或更新任务

    Args:
        task: 拨测任务定义（包含 id 时为更新）
        operator: 操作人
        node_ids: 节点ID列表（可选，若指定则覆盖 task.node_ids）
        group_ids: 分组ID列表（可选，若指定则覆盖 task.group_ids）

    Returns:
        int: 任务ID

    Notes:
        部署任务需单独调用 control_task(action="deploy")
    """
    if node_ids is not None:
        task.node_ids = node_ids
    if group_ids is not None:
        task.group_ids = group_ids
    if get_config().metadata.enable_uptimecheck_bkdata:
        task.independent_dataid = True
    _check_bk_biz_id_tenant_id(task.bk_biz_id, task.bk_tenant_id)
    task_model = UptimeCheckTaskModel.create_or_update_from_define(task, operator)

    return task_model.pk


def delete_task(
    bk_tenant_id: str,
    bk_biz_id: int,
    task_id: int,
    operator: str,
) -> None:
    """删除任务

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        task_id: 任务ID
        operator: 操作人
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)
    uptime_check_task = UptimeCheckTaskModel.objects.get(bk_biz_id=bk_biz_id, pk=task_id, is_deleted=False)

    # 检查并删除关联的订阅
    TaskManager(task=uptime_check_task).delete(operator)

    # 执行删除（软删除）
    with transaction.atomic():
        group_list = list(uptime_check_task.groups.all())
        for group in group_list:
            group.tasks.remove(uptime_check_task)
        uptime_check_task.is_deleted = True
        uptime_check_task.update_time = datetime.now()
        uptime_check_task.update_user = operator
        uptime_check_task.save()

    logger.info(f"拨测任务已删除: task_id={uptime_check_task.pk}, name={uptime_check_task.name}")


def control_task(bk_tenant_id: str, bk_biz_id: int, task_id: int, action: str, operator: str | None = None) -> str:
    """控制任务（部署/启动/停止）

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        task_id: 任务ID
        action: 动作类型 (deploy/start/stop)
        operator: 操作人 (start/stop 时必须)

    Returns:
        str: 操作结果

    Examples:
        # 部署任务
        control_task(tenant_id, biz_id, task_id, action="deploy")

        # 启动任务
        control_task(tenant_id, biz_id, task_id, action="start", operator="admin")

        # 停止任务
        control_task(tenant_id, biz_id, task_id, action="stop", operator="admin")
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)
    task = UptimeCheckTaskModel.objects.get(bk_biz_id=bk_biz_id, pk=task_id, is_deleted=False)
    manager = TaskManager(task=task)

    if action == "deploy":
        return manager.deploy()
    elif action == "start":
        if not operator:
            raise ValueError("start 操作需要提供 operator")
        manager.start(operator)
        return "success"
    elif action == "stop":
        if not operator:
            raise ValueError("stop 操作需要提供 operator")
        manager.stop(operator)
        return "success"
    else:
        raise ValueError(f"无效的动作类型: {action}")


def refresh_task_status(
    bk_tenant_id: str,
    bk_biz_id: int,
    task_ids: list[int],
) -> dict[int, str]:
    """刷新任务状态

    从节点管理获取订阅的最新状态，并更新任务状态。
    如果任务失败，会记录详细的错误日志。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        task_ids: 任务ID列表

    Returns:
        dict: {task_id: new_status} 的映射关系，仅包含成功更新的任务

    Examples:
        # 刷新单个任务
        updates = refresh_task_status(tenant_id, biz_id, [123])
        # 返回: {123: "RUNNING"}

        # 刷新多个任务
        updates = refresh_task_status(tenant_id, biz_id, [123, 456, 789])
        # 返回: {123: "RUNNING", 456: "STARTING", 789: "FAILED"}
    """

    # 1. 校验参数
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)
    if not task_ids:
        return {}

    # 2. 查询任务对应的订阅ID映射（一对多关系：含公共节点时一个任务会拆分出多条订阅）
    task_subscription_map = _query_task_subscriptions(task_ids, bk_biz_id)
    if not task_subscription_map:
        return {}

    # 3. 从节点管理批量获取订阅状态
    #    使用 set 去重，避免重复请求节点管理
    all_subscription_ids = sorted({sub_id for sub_ids in task_subscription_map.values() for sub_id in sub_ids})
    subscription_statuses = _fetch_subscription_statuses(bk_tenant_id, all_subscription_ids)
    if not subscription_statuses:
        return {}

    # 4. 根据订阅状态推断任务状态，并批量更新
    task_status_updates = _build_task_status_updates(
        bk_tenant_id,
        task_subscription_map,
        subscription_statuses,
    )

    # 5. 批量更新数据库
    return _batch_update_task_status(task_status_updates)


def _query_task_subscriptions(task_ids: list[int], bk_biz_id: int) -> dict[int, list[int]]:
    """查询任务的订阅ID映射

    存在公共节点的拨测任务会按节点的业务ID拆分出多条订阅，订阅记录上的 ``bk_biz_id``
    是节点所属业务（公共节点为公共业务ID），不等于任务的 ``bk_biz_id``。
    因此业务隔离应通过任务侧（``UptimeCheckTaskModel.bk_biz_id``）来约束，
    而订阅查询不能再用 ``bk_biz_id`` 过滤，否则会漏掉公共节点对应的订阅。

    Args:
        task_ids: 任务ID列表
        bk_biz_id: 业务ID（用于在任务侧做业务隔离校验）

    Returns:
        dict: ``{task_id: [subscription_id, ...]}`` 的映射关系，单任务可能对应多条订阅
    """
    if not task_ids:
        return {}

    # 通过任务模型做业务隔离，避免跨业务读取
    valid_task_ids = list(
        UptimeCheckTaskModel.objects.filter(
            pk__in=task_ids,
            bk_biz_id=bk_biz_id,
            is_deleted=False,
        ).values_list("pk", flat=True)
    )
    if not valid_task_ids:
        return {}

    task_subscription_map: dict[int, list[int]] = {}
    queryset = UptimeCheckTaskSubscription.objects.filter(
        uptimecheck_id__in=valid_task_ids,
        is_deleted=False,
    )
    if _is_nodeman_v3_enabled():
        relation_values = queryset.values_list("uptimecheck_id", "id")
    else:
        relation_values = queryset.filter(node_man_backend="v2").values_list("uptimecheck_id", "subscription_id")

    for task_id, subscription_id in relation_values:
        task_subscription_map.setdefault(task_id, []).append(subscription_id)

    return task_subscription_map


def _fetch_subscription_statuses(bk_tenant_id: str, subscription_ids: list[int]) -> dict[int, str]:
    """从节点管理批量获取订阅状态

    对于以下两种"非完成态"，按照旧版单订阅轮询语义（``check_single_task_status``）
    统一标记为 ``PENDING``，确保任务级聚合时不会被其他已完成订阅误推进到 ``RUNNING``：

    1. 节点管理返回空结果：订阅刚下发、尚未产生执行实例，订阅仍在启用中。
    2. 节点管理接口异常：状态未知，保守视为仍在启用中（避免把任务错误地推进到 RUNNING）。

    Args:
        bk_tenant_id: 租户ID
        subscription_ids: 订阅ID列表

    Returns:
        dict: ``{subscription_id: status}`` 的映射关系，输入的每个订阅都会出现在结果中
    """

    if not subscription_ids:
        return {}

    if _is_nodeman_v3_enabled():
        return _fetch_v3_policy_statuses(subscription_ids)

    subscription_statuses: dict[int, str] = {}

    for sub_id in subscription_ids:
        try:
            tasks, _ = node_man_v2_api.batch_get_subscription_task_result(
                bk_tenant_id=bk_tenant_id, params={"subscription_id": sub_id, "need_aggregate_all_tasks": True}
            )
        except Exception as e:
            logger.exception(e)
            logger.warning(f"获取订阅{sub_id}状态失败，按启用中处理: {e}")
            # 接口异常视为订阅仍在启用中，避免把任务误判为 RUNNING
            subscription_statuses[sub_id] = CollectStatus.PENDING
            continue

        if not tasks:
            # 空结果代表订阅尚未产生执行实例，按启用中处理
            subscription_statuses[sub_id] = CollectStatus.PENDING
            continue

        # 聚合所有实例的状态
        status_list = [task.get("status") for task in tasks]

        # 状态优先级: FAILED > RUNNING/PENDING > 其他
        if any(s == CollectStatus.FAILED for s in status_list):
            subscription_statuses[sub_id] = CollectStatus.FAILED
        elif any(s in [CollectStatus.RUNNING, CollectStatus.PENDING] for s in status_list):
            subscription_statuses[sub_id] = CollectStatus.RUNNING
        else:
            subscription_statuses[sub_id] = status_list[0] if status_list else CollectStatus.RUNNING

    return subscription_statuses


def _fetch_v3_policy_statuses(relation_ids: list[int]) -> dict[int, str]:
    """Fetch statuses for V3 policy relations without treating missing observations as success."""

    from bk_monitor_base.domains.uptime_check.services.nodeman_v3 import UptimeCheckNodeManV3Service

    relations = UptimeCheckTaskSubscription.objects.in_bulk(relation_ids)
    task_ids = {relation.uptimecheck_id for relation in relations.values()}
    tasks = UptimeCheckTaskModel.objects.in_bulk(task_ids)
    service = UptimeCheckNodeManV3Service()
    statuses: dict[int, str] = {}
    for relation_id in relation_ids:
        relation = relations.get(relation_id)
        task = tasks.get(relation.uptimecheck_id) if relation else None
        if relation is None or task is None:
            continue
        if relation.node_man_backend != "v3":
            statuses[relation_id] = CollectStatus.FAILED
            continue
        try:
            remote_status = service.refresh(task, relation)
        except NodeManV3DefiniteFailure as error:
            logger.error(f"NodeMan V3 策略关系{relation_id}存在明确错误: {error}")
            relation.node_man_operation_status = "failed"
            relation.node_man_result_state = getattr(error, "result_state", "")
            relation.node_man_error = str(error)
            relation.save(
                update_fields=[
                    "node_man_operation_status",
                    "node_man_result_state",
                    "node_man_error",
                    "update_time",
                ]
            )
            statuses[relation_id] = CollectStatus.FAILED
            continue
        except Exception as error:
            logger.warning(f"获取 NodeMan V3 策略关系{relation_id}状态失败，按执行中处理: {error}")
            statuses[relation_id] = CollectStatus.PENDING
            continue
        if remote_status == "success":
            statuses[relation_id] = CollectStatus.SUCCESS
        elif remote_status in {"failed", "partial_failed", "cancelled", "unknown"}:
            statuses[relation_id] = CollectStatus.FAILED
        else:
            statuses[relation_id] = CollectStatus.PENDING
    return statuses


def _build_task_status_updates(
    bk_tenant_id: str,
    task_subscription_map: dict[int, list[int]],
    subscription_statuses: dict[int, str],
) -> dict[int, str]:
    """根据订阅状态聚合得到任务状态更新映射

    任务可能对应多条订阅（含公共节点时按节点业务拆分），任务级状态采用以下聚合规则：

    1. 任一订阅为 ``FAILED`` -> 任务 ``START_FAILED``（并对所有失败订阅记录错误日志）
    2. 无失败但任一订阅为 ``RUNNING/PENDING`` -> 任务 ``STARTING``
       （订阅在节点管理返回空结果或调用异常时，``_fetch_subscription_statuses`` 已统一标记为
       ``PENDING``，因此"部分订阅已完成、部分订阅尚未产生结果"的中间态会被聚合为 ``STARTING``，
       不会被其他已完成订阅推进到 ``RUNNING``）
    3. 所有订阅均已完成（非 RUNNING/PENDING/FAILED）-> 任务 ``RUNNING``

    若任务对应的所有订阅在节点管理侧均没有有效状态（理论上不会发生，作为防御性 fallback），
    则跳过该任务的更新。

    Args:
        bk_tenant_id: 租户ID
        task_subscription_map: 任务到订阅的映射 ``{task_id: [subscription_id, ...]}``
        subscription_statuses: 订阅状态映射 ``{subscription_id: status}``

    Returns:
        dict: ``{task_id: new_status}`` 的映射关系
    """
    task_status_updates: dict[int, str] = {}

    for task_id, sub_ids in task_subscription_map.items():
        # 收集该任务下所有订阅的有效状态
        sub_statuses: list[tuple[int, str]] = [
            (sub_id, subscription_statuses[sub_id]) for sub_id in sub_ids if sub_id in subscription_statuses
        ]
        if not sub_statuses:
            continue

        failed_sub_ids = [sub_id for sub_id, status in sub_statuses if status == CollectStatus.FAILED]
        has_in_progress = any(status in (CollectStatus.RUNNING, CollectStatus.PENDING) for _, status in sub_statuses)

        if failed_sub_ids:
            # 任一订阅失败即视为任务启动失败，需要把所有失败订阅的错误日志都记录下来
            task_status_updates[task_id] = UptimeCheckTaskStatus.START_FAILED.value
            for failed_sub_id in failed_sub_ids:
                _record_subscription_error_logs(bk_tenant_id, task_id, failed_sub_id)
        elif has_in_progress:
            task_status_updates[task_id] = UptimeCheckTaskStatus.STARTING.value
        else:
            task_status_updates[task_id] = UptimeCheckTaskStatus.RUNNING.value

    return task_status_updates


def _record_subscription_error_logs(bk_tenant_id: str, task_id: int, subscription_id: int) -> None:
    """记录失败订阅的详细错误日志

    Args:
        bk_tenant_id: 租户ID
        task_id: 拨测任务ID
        subscription_id: 订阅ID
    """
    if _is_nodeman_v3_enabled():
        relation = UptimeCheckTaskSubscription.objects.filter(pk=subscription_id, uptimecheck_id=task_id).first()
        if relation is None:
            return
        UptimeCheckTaskCollectorLog.objects.create(
            task_id=task_id,
            error_log={
                "message": relation.node_man_error or "NodeMan V3 DeployPolicy execution failed",
                "result_state": relation.node_man_result_state,
                "operation_status": relation.node_man_operation_status,
                "trigger_id": relation.node_man_trigger_id,
            },
            subscription_id=relation.subscription_id,
            nodeman_task_id=0,
        )
        return

    from bk_monitor_base.infras.third_party_api.nodeman.api import (
        get_subscription_task_result,
        get_subscription_task_result_detail,
    )

    try:
        # 获取订阅的任务结果列表
        result = get_subscription_task_result(bk_tenant_id=bk_tenant_id, params={"subscription_id": subscription_id})

        failed_tasks = [task for task in result.get("list", []) if task.get("status") == CollectStatus.FAILED]

        # 遍历失败的任务实例，获取详细日志
        for failed_task in failed_tasks:
            instance_id = failed_task.get("instance_id", "")
            nodeman_task_id = failed_task.get("task_id", 0)

            # 获取任务详情
            detail = get_subscription_task_result_detail(
                bk_tenant_id=bk_tenant_id,
                subscription_id=subscription_id,
                instance_id=instance_id,
            )

            # 提取错误日志
            error_logs = _extract_error_logs_from_detail(detail)

            # 批量创建日志记录
            for error_log in error_logs:
                UptimeCheckTaskCollectorLog.objects.create(
                    task_id=task_id,
                    error_log=error_log,
                    subscription_id=subscription_id,
                    nodeman_task_id=nodeman_task_id,
                )

    except Exception as e:
        logger.warning(f"记录订阅{subscription_id}错误日志失败: {e}")


def _extract_error_logs_from_detail(detail: Any) -> list[dict[str, Any]]:
    """从任务详情中提取错误日志

    Args:
        detail: 节点管理返回的任务详情（SubscriptionTaskResult 类型）

    Returns:
        错误日志列表
    """
    error_logs: list[dict[str, Any]] = []

    for step in detail.get("steps", []):
        if step.get("status") != CollectStatus.FAILED:
            continue

        for target_host in step.get("target_hosts", []):
            for sub_step in target_host.get("sub_steps", []):
                ex_data = sub_step.get("ex_data")
                if ex_data:
                    error_logs.append(ex_data)

    return error_logs


def _batch_update_task_status(task_status_updates: dict[int, str]) -> dict[int, str]:
    """批量更新任务状态到数据库

    Args:
        task_status_updates: 任务状态更新映射 {task_id: new_status}

    Returns:
        dict: 实际更新的任务状态映射（过滤掉已删除的任务）
    """
    if not task_status_updates:
        return {}

    # 查询需要更新的任务
    tasks = list(UptimeCheckTaskModel.objects.filter(pk__in=task_status_updates.keys(), is_deleted=False))

    # 批量更新状态
    for task in tasks:
        task.status = task_status_updates[task.pk]

    UptimeCheckTaskModel.objects.bulk_update(tasks, ["status"], batch_size=500)

    # 返回实际更新的任务状态
    updated_task_ids = {task.pk for task in tasks}
    return {task_id: status for task_id, status in task_status_updates.items() if task_id in updated_task_ids}


# ===================== Node 统一操作 =====================


def get_node(
    bk_tenant_id: str,
    bk_biz_id: int | None = None,
    *,
    node_id: int | None = None,
    ip: str | None = None,
) -> UptimeCheckNode:
    """获取单个节点

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID（可选）
        node_id: 节点ID（与 ip 二选一）
        ip: 节点IP（与 node_id 二选一）

    Returns:
        UptimeCheckNode Define 对象

    Examples:
        # 根据ID获取
        node = get_node(tenant_id, node_id=1)

        # 根据IP获取
        node = get_node(tenant_id, ip="192.168.1.1")
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    if node_id:
        queryset = UptimeCheckNodeModel.objects.filter(pk=node_id, bk_tenant_id=bk_tenant_id, is_deleted=False)
        if bk_biz_id:
            queryset = queryset.filter(bk_biz_id=bk_biz_id)
    elif ip:
        queryset = UptimeCheckNodeModel.objects.filter(ip=ip, bk_tenant_id=bk_tenant_id, is_deleted=False)
    else:
        raise ValueError("必须提供 node_id 或 ip")

    node_model = queryset.get()
    return node_model.to_define()


def get_node_with_host_id(bk_tenant_id: str, node_id: int) -> UptimeCheckNode:
    """获取节点并自动回填主机ID

    通过CMDB API查询IP对应的主机ID，并更新到数据库

    Args:
        bk_tenant_id: 租户ID
        node_id: 节点ID

    Returns:
        UptimeCheckNode: 拨测节点定义（包含已回填的 bk_host_id）

    Examples:
        node = get_node_with_host_id(tenant_id="default", node_id=1)
    """
    node_model = UptimeCheckNodeModel.objects.get(pk=node_id, bk_tenant_id=bk_tenant_id, is_deleted=False)

    # 调用 Model 的 set_host_id() 进行回填
    # 这会通过 CMDB API 查询 IP 对应的主机 ID，并更新数据库
    node_model.set_host_id()

    return node_model.to_define()


def list_nodes(
    bk_tenant_id: str,
    bk_biz_id: int | None = None,
    *,
    query: NodeQueryParamsInput | None = None,
    order_by: str | list[str] | None = None,
) -> list[UptimeCheckNode]:
    """列表查询节点

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID（可选）
        query: 查询过滤参数
        order_by: 排序参数

    Returns:
        list[UptimeCheckNode]: 节点 Define 对象列表

    Examples:
        # 获取业务下所有节点
        nodes = list_nodes(tenant_id, biz_id)

        # 按IP过滤
        nodes = list_nodes(tenant_id, biz_id, query={"ip": "192.168.1.1"})
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    include_common = bool(query and query.get("include_common", False))
    queryset = UptimeCheckNodeModel.objects.filter(bk_tenant_id=bk_tenant_id, is_deleted=False)
    if bk_biz_id:
        if include_common:
            queryset = queryset.filter(Q(bk_biz_id=bk_biz_id) | (Q(is_common=True) & ~Q(bk_biz_id=bk_biz_id)))
        else:
            queryset = queryset.filter(bk_biz_id=bk_biz_id)

    # 根据order_by参数排序
    if order_by:
        if isinstance(order_by, str):
            order_by = [order_by]
        queryset = queryset.order_by(*order_by)

    # 应用过滤条件
    if query:
        if node_id := query.get("node_id"):
            queryset = queryset.filter(pk=node_id)
        if node_ids := query.get("node_ids"):
            queryset = queryset.filter(pk__in=node_ids)
        if bk_host_ids := query.get("bk_host_ids"):
            queryset = queryset.filter(bk_host_id__in=bk_host_ids)
        if bk_biz_ids := query.get("bk_biz_ids"):
            queryset = queryset.filter(bk_biz_id__in=bk_biz_ids)
        if ip := query.get("ip"):
            queryset = queryset.filter(ip=ip)
        if plat_id := query.get("plat_id"):
            queryset = queryset.filter(plat_id=plat_id)
        if name := query.get("name"):
            queryset = queryset.filter(name__icontains=name)
        if name_prefix := query.get("name_prefix"):
            queryset = queryset.filter(name__startswith=name_prefix)
        if (ip_type := query.get("ip_type")) is not None:
            queryset = queryset.filter(ip_type=ip_type.value)
        if (is_common := query.get("is_common")) is not None:
            # include_common=True 时，保持“同时返回业务节点与公共节点”的兼容语义，
            # 因此忽略 is_common=False 条件，避免误筛掉公共节点。
            if not (include_common and bk_biz_id and is_common is False):
                queryset = queryset.filter(is_common=is_common)
        if carrieroperator := query.get("carrieroperator"):
            queryset = queryset.filter(carrieroperator=carrieroperator)
        if exclude_carriers := query.get("exclude_carrieroperators"):
            queryset = queryset.exclude(carrieroperator__in=exclude_carriers)

    node_models = list(queryset)
    if include_common and bk_biz_id:
        node_models = [
            node for node in node_models if not node.is_common or not node.biz_scope or bk_biz_id in node.biz_scope
        ]

    return [node.to_define() for node in node_models]


def save_node(node: UptimeCheckNode, operator: str) -> int:
    """创建或更新节点

    Args:
        node: 拨测节点定义（包含 id 时为更新）
        operator: 操作人

    Returns:
        int: 节点ID
    """
    _check_bk_biz_id_tenant_id(node.bk_biz_id, node.bk_tenant_id)
    node_model = UptimeCheckNodeModel.create_or_update_from_define(node=node, operator=operator)
    return node_model.pk


def delete_node(
    bk_tenant_id: str,
    bk_biz_id: int,
    node_id: int,
    operator: str,
) -> None:
    """删除节点

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        node_id: 节点ID
        operator: 操作人

    Raises:
        ValueError: 节点有关联任务时抛出
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    if UptimeCheckTaskModel.objects.filter(nodes__id__exact=node_id, is_deleted=False).exists():
        raise ValueError(f"拨测节点{node_id}有关联的拨测任务，不能删除")

    UptimeCheckNodeModel.objects.filter(bk_biz_id=bk_biz_id, pk=node_id, is_deleted=False).update(
        is_deleted=True, update_user=operator, update_time=datetime.now()
    )


# ===================== Group 统一操作 =====================


def get_group(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    group_id: int | None = None,
) -> UptimeCheckGroup:
    """获取单个分组

    Args:
        bk_tenant_id: 租户ID（可选，与 bk_biz_id 配合使用时校验）
        bk_biz_id: 业务ID（可选）
        group_id: 分组ID（可选但推荐提供）

    Returns:
        UptimeCheckGroup Define 对象

    Raises:
        UptimeCheckGroupModel.DoesNotExist: 分组不存在
        ValueError: 参数错误
    """
    if not group_id:
        raise ValueError("必须提供 group_id")

    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    if bk_biz_id:
        group_model = UptimeCheckGroupModel.objects.get(bk_biz_id=bk_biz_id, pk=group_id, is_deleted=False)
    else:
        # 如果不提供 bk_biz_id，直接按 group_id 查询
        group_model = UptimeCheckGroupModel.objects.get(pk=group_id, is_deleted=False)

    return group_model.to_define()


def _build_group_queryset(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    query: GroupQueryParamsInput | None = None,
):
    """构建分组 QuerySet（过滤条件部分，供 list_groups 和 count_groups 共用）

    Returns:
        QuerySet: 应用业务、删除状态和 query 过滤后的分组 QuerySet。
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    include_global = query.get("include_global", False) if query else False
    if include_global:
        queryset = UptimeCheckGroupModel.objects.filter(bk_biz_id__in=[bk_biz_id, 0], is_deleted=False)
    else:
        queryset = UptimeCheckGroupModel.objects.filter(bk_biz_id=bk_biz_id, is_deleted=False)

    # 应用过滤条件
    if query:
        if group_id := query.get("group_id"):
            queryset = queryset.filter(pk=group_id)
        if group_ids := query.get("group_ids"):
            queryset = queryset.filter(pk__in=group_ids)
        if name := query.get("name"):
            queryset = queryset.filter(name__icontains=name)
        if task_id := query.get("task_id"):
            queryset = queryset.filter(tasks__id=task_id, tasks__is_deleted=False)

    return queryset


def list_groups(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    query: GroupQueryParamsInput | None = None,
    order_by: str | list[str] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[UptimeCheckGroup]:
    """列表查询分组

    Args:
        bk_tenant_id: 租户ID（可选，与 bk_biz_id 配合使用时校验）
        bk_biz_id: 业务ID（可选）
        query: 查询过滤参数
        order_by: 排序参数
        page: 页码（可选），与 page_size 配合使用
        page_size: 每页条数（可选），与 page 配合使用

    Returns:
        list[UptimeCheckGroup]: 分组 Define 对象列表

    Examples:
        # 获取所有分组（向后兼容，不传分页参数返回全量）
        groups = list_groups(tenant_id, biz_id)

        # 包含全局分组
        groups = list_groups(tenant_id, biz_id, query={"include_global": True})

        # 分页查询
        groups = list_groups(tenant_id, biz_id, page=1, page_size=10)
    """
    queryset = _build_group_queryset(bk_tenant_id, bk_biz_id, query=query)
    has_pagination = _validate_pagination_params(page, page_size)

    # 根据order_by参数排序
    if order_by:
        if isinstance(order_by, str):
            order_by = [order_by]
        queryset = queryset.order_by(*order_by)
    elif has_pagination:
        queryset = queryset.order_by("id")

    # 分页：不传 page/page_size 时返回全量（向后兼容）
    if page is not None and page_size is not None:
        offset = (page - 1) * page_size
        queryset = queryset[offset : offset + page_size]

    # 返回 Define 对象列表
    return [group.to_define() for group in queryset]


def count_groups(
    bk_tenant_id: str | None = None,
    bk_biz_id: int | None = None,
    *,
    query: GroupQueryParamsInput | None = None,
) -> int:
    """查询分组总数，接受和 list_groups 相同的过滤参数。

    仅执行 COUNT 查询，不加载 M2M 关联、不转换为 Define 对象。
    """
    queryset = _build_group_queryset(bk_tenant_id, bk_biz_id, query=query)
    return queryset.count()


def save_group(group: UptimeCheckGroup, operator: str) -> int:
    """创建或更新分组

    Args:
        group: 拨测分组定义（包含 id 时为更新）
        operator: 操作人

    Returns:
        int: 分组ID
    """
    _check_bk_biz_id_tenant_id(group.bk_biz_id, group.bk_tenant_id)
    group_model = UptimeCheckGroupModel.create_or_update_from_define(group=group, operator=operator)
    return group_model.pk


def delete_group(
    bk_tenant_id: str,
    bk_biz_id: int,
    group_id: int,
    operator: str,
) -> None:
    """删除分组

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        group_id: 分组ID
        operator: 操作人
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    group_model = UptimeCheckGroupModel.objects.get(bk_biz_id=bk_biz_id, pk=group_id, is_deleted=False)

    with transaction.atomic():
        group_model.tasks.clear()
        group_model.is_deleted = True
        group_model.update_time = datetime.now()
        group_model.update_user = operator
        group_model.save()

    logger.info(f"拨测分组已删除: group_id={group_model.pk}, name={group_model.name}")


def manage_group_tasks(
    bk_tenant_id: str, bk_biz_id: int, group_id: int, task_id: int, action: str, operator: str
) -> None:
    """管理分组与任务的关联

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        group_id: 分组ID
        task_id: 任务ID
        action: 动作类型（add/remove）
        operator: 操作人

    Examples:
        # 添加任务到分组
        manage_group_tasks(tenant_id, biz_id, group_id, task_id, action="add", operator="admin")

        # 从分组移除任务
        manage_group_tasks(tenant_id, biz_id, group_id, task_id, action="remove", operator="admin")
    """
    _check_bk_biz_id_tenant_id(bk_biz_id, bk_tenant_id)

    group_model = UptimeCheckGroupModel.objects.get(bk_biz_id=bk_biz_id, pk=group_id, is_deleted=False)
    task_model = UptimeCheckTaskModel.objects.get(bk_biz_id=bk_biz_id, pk=task_id, is_deleted=False)

    with transaction.atomic():
        if action == "add":
            group_model.tasks.add(task_model)
            logger.info(f"拨测任务已加入分组: group_id={group_model.pk}, task_id={task_model.pk}")
        elif action == "remove":
            group_model.tasks.remove(task_model)
            logger.info(f"拨测任务已从分组移除: group_id={group_model.pk}, task_id={task_model.pk}")
        else:
            raise ValueError(f"未知的动作类型: {action}")
        group_model.update_user = operator
        group_model.save()


def list_collector_logs(task_id: int) -> list[str]:
    """查询采集日志

    Args:
        task_id: 任务ID

    Returns:
        错误日志列表
    """
    return list(
        UptimeCheckTaskCollectorLog.objects.filter(task_id=task_id, is_deleted=False).values_list(
            "error_log", flat=True
        )
    )


def test_uptime_check_task(
    bk_biz_id: int,
    config: dict[str, Any],
    protocol: str,
    node_id_list: list[int],
) -> str:
    """测试拨测任务配置

    下发测试配置，采集器只执行一次数据采集，直接返回采集结果，不经过计算平台。

    Args:
        bk_biz_id: 业务ID
        config: 拨测配置
        protocol: 协议类型 (HTTP/TCP/UDP/ICMP)
        node_id_list: 节点ID列表

    Returns:
        测试结果消息

    Raises:
        TestTaskError: 测试失败时抛出异常
    """
    temp_task = UptimeCheckTaskModel(
        bk_biz_id=bk_biz_id,
        protocol=protocol,
        config=config,
        name="temp_test_task",
    )

    manager = TaskManager(task=temp_task)
    return manager.test(node_id_list=node_id_list)


def generate_task_sub_config(
    protocol: str,
    config: dict[str, Any],
    task_id: int = 0,
    bk_biz_id: int = 0,
    labels: dict[str, Any] | None = None,
    test: bool = False,
) -> list[dict[str, Any]]:
    """生成拨测任务的子配置

    生成 bkmonitorbeat 任务配置，用于下发到采集器。

    Args:
        protocol: 协议类型 (HTTP/TCP/UDP/ICMP)
        config: 拨测任务配置
        task_id: 任务ID，测试时可为 0
        bk_biz_id: 业务ID，测试时可为 0
        labels: 自定义标签
        test: 是否为测试模式

    Returns:
        任务配置列表
    """

    generator = ConfigGeneratorService()
    return generator.generate_sub_config(
        protocol=protocol,
        config=config,
        task_id=task_id,
        bk_biz_id=bk_biz_id,
        labels=labels or {},
        test=test,
    )
