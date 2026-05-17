"""采集配置 backend Resource —— 适配 bk-monitor-base 的新实现。

与旧版 ``resources/old/backend.py`` 保持完全相同的入参/出参契约，
内部调用 ``bk_monitor_base.domains.metric_plugin.operation`` 完成核心逻辑。
"""

import logging
from typing import Any

from django.conf import settings
from django.core.paginator import Paginator
from django.utils.translation import gettext as _

from bk_monitor_base.domains.metric_plugin.define import (
    CreateOrUpdateDeploymentParams,
    MetricPluginDeploymentScope,
    RetryDeployPluginParams,
)
from bk_monitor_base.domains.metric_plugin.operation import (
    delete_metric_plugin_deployment,
    get_metric_plugin,
    get_metric_plugin_deployment,
    get_metric_plugin_deployment_status,
    get_nodeman_collect_log_detail,
    list_metric_plugin_deployments,
    retry_metric_plugin_deployment,
    save_and_install_metric_plugin_deployment,
    start_metric_plugin_deployment,
    stop_metric_plugin_deployment,
)
from bkm_space.api import SpaceApi
from bkmonitor.utils.request import get_request, get_request_tenant_id, get_request_username
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.collecting import (
    CollectConfigNotExist,
    CollectConfigParamsError,
    CollectConfigRollbackError,
)
from monitor_web.collecting.compat import (
    convert_deployment_to_legacy,
    convert_deployment_to_legacy_list_item,
    convert_plugin_to_legacy_info,
    convert_save_params_to_base,
    label_to_object_type,
)
from monitor_web.collecting.constant import (
    COLLECT_TYPE_CHOICES,
    CollectStatus,
    OperationResult,
    TaskStatus,
)
from monitor_web.models import CollectConfigMeta
from monitor_web.plugin.constant import PluginType
from monitor_web.strategies.loader.datalink_loader import (
    DatalinkDefaultAlarmStrategyLoader,
)
from monitor_web.tasks import append_metric_list_cache

logger = logging.getLogger(__name__)

_STATUS_TO_DEPLOYMENT_STATUS = {
    "STARTED": "running",
    "STOPPED": "stopped",
    "STARTING": "starting",
    "STOPPING": "stopping",
    "DEPLOYING": "deploying",
    "PREPARING": "initializing",
}

_DIRECT_TASK_STATUS_TO_DEPLOYMENT_STATUS = {
    TaskStatus.PREPARING: "initializing",
    TaskStatus.DEPLOYING: "deploying",
    TaskStatus.STARTING: "starting",
    TaskStatus.STOPPING: "stopping",
    TaskStatus.STOPPED: "stopped",
}

_TERMINAL_TASK_STATUSES = {
    TaskStatus.SUCCESS,
    TaskStatus.WARNING,
    TaskStatus.FAILED,
}

_BASE_ORDER_FIELD_MAP = {
    "id": "id",
    "name": "name",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "update_time": "updated_at",
    "bk_biz_id": "bk_biz_id",
    "status": "status",
    "plugin_id": "plugin_id",
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _ensure_tenant_id() -> str:
    """获取并断言 bk_tenant_id 非空。"""
    bk_tenant_id = get_request_tenant_id()
    assert bk_tenant_id is not None, "bk_tenant_id is required"
    return bk_tenant_id


def _get_deployment_or_raise(bk_tenant_id: str, deployment_id: int, bk_biz_id: int | None = None) -> tuple:
    """获取 base 部署项，不存在时抛出 CollectConfigNotExist。"""
    try:
        return get_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            deployment_id=deployment_id,
            bk_biz_id=bk_biz_id,
        )
    except Exception:
        raise CollectConfigNotExist({"msg": deployment_id})


def _get_plugin(bk_tenant_id: str, plugin_id: str):
    """获取 base 插件信息。"""
    return get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)


def _ensure_operator() -> str:
    """获取当前操作用户并断言非空。"""
    return get_request_username() or get_global_user() or ""


def _intersect_deployment_statuses(
    current_statuses: list[str] | None,
    next_statuses: list[str],
) -> list[str]:
    if current_statuses is None:
        return list(next_statuses)
    next_statuses_set = set(next_statuses)
    return [status for status in current_statuses if status in next_statuses_set]


def _parse_order(order: str | None) -> tuple[str | None, bool]:
    if not order:
        return None, False
    reverse = order.startswith("-")
    return order[1:] if reverse else order, reverse


# ===========================================================================
# CollectConfigListResource
# ===========================================================================


class CollectConfigListResource(Resource):
    """获取采集配置列表信息。

    过滤分层说明：
    - base 的 list_metric_plugin_deployments 已支持 deployment_statuses / fuzzy / 排序 / 分页
    - SaaS 层继续负责旧版 status/task_status 语义翻译，以及 need_upgrade/实例统计补充过滤

    [ISSUE] base 不返回 config_version / info_version，需从 plugin_version 推导。
    """

    def __init__(self):
        super().__init__()
        self.bk_biz_id = None

    @staticmethod
    def _build_base_query_kwargs(
        *,
        bk_biz_ids: list[int] | None,
        search_dict: dict[str, Any],
        order: str | None,
        page: int,
        limit: int,
    ) -> tuple[dict[str, Any], str | None, bool, bool]:
        deployment_statuses: list[str] | None = None
        terminal_task_status: str | None = None

        status = search_dict.get("status")
        if status in _STATUS_TO_DEPLOYMENT_STATUS:
            deployment_statuses = _intersect_deployment_statuses(
                deployment_statuses, [_STATUS_TO_DEPLOYMENT_STATUS[status]]
            )

        task_status = search_dict.get("task_status")
        if task_status in _DIRECT_TASK_STATUS_TO_DEPLOYMENT_STATUS:
            deployment_statuses = _intersect_deployment_statuses(
                deployment_statuses, [_DIRECT_TASK_STATUS_TO_DEPLOYMENT_STATUS[task_status]]
            )
        elif task_status in _TERMINAL_TASK_STATUSES:
            terminal_task_status = str(task_status)

        order_field, order_desc = _parse_order(order)
        base_query_kwargs: dict[str, Any] = {
            "bk_biz_ids": bk_biz_ids,
            "plugin_ids": [str(search_dict["plugin_id"])] if search_dict.get("plugin_id") else None,
            "deployment_statuses": deployment_statuses,
            "fuzzy": search_dict.get("fuzzy"),
            "order_by": _BASE_ORDER_FIELD_MAP.get(order_field or ""),
            "order_desc": order_desc,
        }

        need_memory_filter = (
            any(field in search_dict for field in ("id", "collect_type", "bk_biz_id", "need_upgrade"))
            or terminal_task_status is not None
        )
        need_memory_order = bool(order_field) and order_field not in _BASE_ORDER_FIELD_MAP

        if page != -1 and not need_memory_filter and not need_memory_order:
            base_query_kwargs["limit"] = limit
            base_query_kwargs["offset"] = (page - 1) * limit

        return base_query_kwargs, terminal_task_status, need_memory_filter, need_memory_order

    @staticmethod
    def _apply_memory_order(entries: list[dict[str, Any]], order: str | None) -> list[dict[str, Any]]:
        order_field, reverse = _parse_order(order)
        if not order_field:
            return entries

        try:
            entries.sort(key=lambda entry: entry["item"].get(order_field, ""), reverse=reverse)
        except TypeError:
            pass
        return entries

    @staticmethod
    def _match_terminal_task_status(entry: dict[str, Any], task_status: str) -> bool:
        deployment_status = entry["deployment"].status
        error_count = int(entry["item"].get("error_instance_count", 0))
        total_count = int(entry["item"].get("total_instance_count", 0))

        if task_status == TaskStatus.SUCCESS:
            return deployment_status == "running" and error_count == 0
        if task_status == TaskStatus.WARNING:
            return deployment_status == "running" and 0 < error_count < total_count
        if task_status == TaskStatus.FAILED:
            return deployment_status == "failed" or (
                deployment_status == "running" and total_count > 0 and error_count == total_count
            )
        return False

    @staticmethod
    def _count_k8s_status(result: dict[str, Any]) -> tuple[int, int]:
        instance_status = result.get("instance_status") or {}
        total_count = int(result.get("instance_count") or len(instance_status))
        error_count = 0
        for instance in instance_status.values():
            if instance.get("status") in {"failed", "unknown"}:
                error_count += 1
        return error_count, total_count

    def _enrich_runtime_statistics(self, bk_tenant_id: str, entries: list[dict[str, Any]]) -> None:
        subscription_entry_map: dict[int, dict[str, Any]] = {}
        for entry in entries:
            deployment = entry["deployment"]
            plugin = entry["plugin"]
            subscription_id = deployment.related_params.get("subscription_id")
            if subscription_id and plugin and plugin.type != "k8s":
                try:
                    subscription_id = int(subscription_id)
                except (TypeError, ValueError):
                    continue
                subscription_entry_map[int(subscription_id)] = entry

        if subscription_entry_map:
            statistics_groups = api.node_man.fetch_subscription_statistic.bulk_request(
                [
                    {"subscription_id_list": subscription_ids}
                    for subscription_ids in (
                        list(subscription_entry_map.keys())[index : index + 20]
                        for index in range(0, len(subscription_entry_map), 20)
                    )
                ],
                ignore_exceptions=True,
            )
            for statistics_group in statistics_groups:
                for statistics in statistics_group:
                    entry = subscription_entry_map.get(int(statistics["subscription_id"]))
                    if not entry:
                        continue
                    status_number = {
                        status_item["status"]: status_item["count"] for status_item in statistics.get("status", [])
                    }
                    entry["item"]["error_instance_count"] = status_number.get(CollectStatus.FAILED, 0)
                    entry["item"]["total_instance_count"] = statistics.get("instances", 0)

        for entry in entries:
            if entry["item"].get("total_instance_count"):
                continue
            plugin = entry["plugin"]
            if not plugin or plugin.type != "k8s":
                continue
            try:
                deployment_runtime = get_metric_plugin_deployment_status(
                    bk_tenant_id=bk_tenant_id,
                    deployment_id=entry["deployment"].id,
                    bk_biz_id=entry["deployment"].bk_biz_id,
                )
            except Exception:
                continue
            if not isinstance(deployment_runtime, dict):
                continue
            error_count, total_count = self._count_k8s_status(deployment_runtime)
            entry["item"]["error_instance_count"] = error_count
            entry["item"]["total_instance_count"] = total_count

    @staticmethod
    def _apply_post_filters(entries: list[dict[str, Any]], search_dict: dict[str, Any]) -> list[dict[str, Any]]:
        result = entries
        for field_name, value in search_dict.items():
            if field_name == "task_status" and value in _TERMINAL_TASK_STATUSES:
                result = [
                    entry for entry in result if CollectConfigListResource._match_terminal_task_status(entry, value)
                ]
            elif field_name == "need_upgrade":
                result = [
                    entry
                    for entry in result
                    if str(entry["item"].get("need_upgrade", False)).lower() == str(value).lower()
                ]
            elif field_name in ("id", "plugin_id", "collect_type", "bk_biz_id"):
                result = [entry for entry in result if str(entry["item"].get(field_name, "")) == str(value)]
        return result

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        refresh_status = serializers.BooleanField(required=False, label="是否刷新状态")
        search = serializers.DictField(required=False, label="搜索字段")
        order = serializers.CharField(required=False, label="排序字段")
        disable_service_type = serializers.BooleanField(default=True, label="不需要服务分类")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        limit = serializers.IntegerField(required=False, default=10, label="大小")

    def exists_by_biz(self, bk_biz_id: int) -> bool:
        """检查业务是否有采集配置。"""
        bk_tenant_id = _ensure_tenant_id()
        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=[bk_biz_id],
            limit=1,
        )
        return total > 0

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = _ensure_tenant_id()
        bk_biz_id = validated_request_data.get("bk_biz_id")
        refresh_status = bool(validated_request_data.get("refresh_status"))
        search_dict = validated_request_data.get("search", {})
        order = validated_request_data.get("order")
        page = validated_request_data["page"]
        limit = validated_request_data["limit"]
        self.bk_biz_id = bk_biz_id

        # 确定查询的业务列表
        bk_biz_ids: list[int] | None = None
        if bk_biz_id:
            bk_biz_ids = [bk_biz_id]
        else:
            try:
                req = get_request()
                bk_biz_ids = resource.space.get_bk_biz_ids_by_user(req.user) if req else None
            except Exception:
                bk_biz_ids = None

        base_query_kwargs, terminal_task_status, need_memory_filter, need_memory_order = self._build_base_query_kwargs(
            bk_biz_ids=bk_biz_ids,
            search_dict=search_dict,
            order=order,
            page=page,
            limit=limit,
        )

        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id=bk_tenant_id,
            **base_query_kwargs,
        )

        if total == 0:
            return {"type_list": [], "config_list": [], "total": 0}

        # 获取空间信息
        all_space_list = SpaceApi.list_spaces()
        bk_biz_id_space_dict = {space.bk_biz_id: space for space in all_space_list}

        # 获取每个部署的最新版本（用于转换）
        entries: list[dict[str, Any]] = []
        for deployment in deployments:
            # 获取部署版本
            try:
                _, version = get_metric_plugin_deployment(
                    bk_tenant_id=bk_tenant_id,
                    deployment_id=deployment.id,
                )
            except Exception:
                version = None

            # 构建插件信息对象（简化版）
            plugin_obj = None
            try:
                plugin_obj = _get_plugin(bk_tenant_id, deployment.plugin_id)
            except Exception:
                pass

            # 检查是否需要升级
            need_upgrade = False
            if plugin_obj and version:
                need_upgrade = version.plugin_version < plugin_obj.version

            space = bk_biz_id_space_dict.get(deployment.bk_biz_id)
            space_name = f"{space.space_name}({space.type_name})" if space else ""

            item = (
                convert_deployment_to_legacy_list_item(
                    deployment=deployment,
                    version=version,
                    plugin=plugin_obj,
                    space_name=space_name,
                    need_upgrade=need_upgrade,
                )
                if plugin_obj
                else {
                    "id": deployment.id,
                    "name": deployment.name,
                    "bk_biz_id": deployment.bk_biz_id,
                    "space_name": space_name,
                    "collect_type": "",
                    "status": OperationResult.DEPLOYING,
                    "task_status": TaskStatus.DEPLOYING,
                    "target_object_type": "",
                    "target_node_type": "",
                    "plugin_id": deployment.plugin_id,
                    "target_nodes_count": 0,
                    "need_upgrade": False,
                    "config_version": 0,
                    "info_version": 0,
                    "error_instance_count": 0,
                    "total_instance_count": 0,
                    "running_tasks": [],
                    "label_info": {},
                    "label": "",
                    "update_time": deployment.updated_at,
                    "update_user": deployment.updated_by,
                }
            )
            entries.append(
                {
                    "deployment": deployment,
                    "version": version,
                    "plugin": plugin_obj,
                    "item": item,
                }
            )

        if refresh_status or terminal_task_status is not None:
            self._enrich_runtime_statistics(bk_tenant_id, entries)

        if need_memory_filter:
            entries = self._apply_post_filters(entries, search_dict)

        total = len(entries)

        if need_memory_order:
            entries = self._apply_memory_order(entries, order)

        search_list = [entry["item"] for entry in entries]

        if page != -1 and ("limit" not in base_query_kwargs or need_memory_filter or need_memory_order):
            paginator = Paginator(search_list, limit)
            search_list = list(paginator.page(page))

        type_list = [{"id": item[0], "name": item[1]} for item in COLLECT_TYPE_CHOICES]
        return {"type_list": type_list, "config_list": search_list, "total": total}


# ===========================================================================
# CollectConfigDetailResource
# ===========================================================================


class CollectConfigDetailResource(Resource):
    """获取采集配置详细信息。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    @staticmethod
    def password_convert(config_json: list[dict], params: dict) -> None:
        """将密码类型参数转换为 bool 值，避免 F12 看到明文密码。"""
        for item in config_json:
            if item.get("mode") != "collector":
                item["mode"] = "plugin"
            value = params.get(item.get("mode", ""), {}).get(
                item.get("key", item.get("name", "")),
            ) or item.get("default")
            if item.get("type") in ("password", "encrypt"):
                mode = item.get("mode", "collector")
                name = item.get("name", "")
                if mode in params and name in params[mode]:
                    params[mode][name] = bool(value)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        bk_biz_id = validated_request_data["bk_biz_id"]
        config_id = validated_request_data["id"]

        deployment, version = _get_deployment_or_raise(bk_tenant_id, config_id, bk_biz_id)
        plugin = _get_plugin(bk_tenant_id, deployment.plugin_id)

        # 解析目标节点（与旧版逻辑一致，调用 CMDB API）
        target_result: list = []
        if version and version.target_scope.nodes:
            target_result = self._resolve_targets(
                bk_biz_id=bk_biz_id,
                target_object_type=label_to_object_type(plugin.label),
                target_node_type=version.target_scope.node_type,
                target_nodes=version.target_scope.nodes,
            )

        # 密码脱敏
        plugin_info = convert_plugin_to_legacy_info(plugin)
        params = version.params if version else {}
        self.password_convert(plugin_info.get("config_json", []), params)

        result = convert_deployment_to_legacy(deployment, version, plugin)
        result["target"] = target_result
        result["params"] = params
        return result

    @staticmethod
    def _resolve_targets(
        bk_biz_id: int,
        target_object_type: str,
        target_node_type: str,
        target_nodes: list[dict],
    ) -> list:
        """解析目标节点详情，调用 CMDB API。"""
        if not target_nodes:
            return []

        if target_object_type == TargetObjectType.HOST and target_node_type == TargetNodeType.INSTANCE:
            return resource.commons.get_host_instance_by_ip(
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_biz_ids": [bk_biz_id],
                    "ip_list": target_nodes,
                }
            )
        elif target_object_type == TargetObjectType.HOST and target_node_type == TargetNodeType.TOPO:
            node_list = [{**item, "bk_biz_id": bk_biz_id} for item in target_nodes]
            return resource.commons.get_host_instance_by_node({"bk_biz_id": bk_biz_id, "node_list": node_list})
        elif target_node_type in (
            TargetNodeType.SERVICE_TEMPLATE,
            TargetNodeType.SET_TEMPLATE,
        ):
            templates = {
                template["bk_inst_id"]: template["bk_inst_name"]
                for template in resource.commons.get_template(
                    dict(
                        bk_biz_id=bk_biz_id,
                        bk_obj_id=target_node_type,
                        bk_inst_type=target_object_type,
                    )
                ).get("children", [])
            }
            result = []
            for item in target_nodes:
                item_copy = {**item, "bk_biz_id": bk_biz_id}
                item_copy["bk_inst_name"] = templates.get(item.get("bk_inst_id"))
                result.append(item_copy)
            return result
        elif target_object_type == TargetObjectType.HOST and target_node_type == TargetNodeType.DYNAMIC_GROUP:
            bk_inst_ids = [item["bk_inst_id"] for item in target_nodes]
            return api.cmdb.search_dynamic_group(
                bk_biz_id=bk_biz_id,
                bk_obj_id="host",
                dynamic_group_ids=bk_inst_ids,
                with_count=True,
            )
        else:
            node_list = [{**item, "bk_biz_id": bk_biz_id} for item in target_nodes]
            return resource.commons.get_service_instance_by_node({"bk_biz_id": bk_biz_id, "node_list": node_list})


# ===========================================================================
# RenameCollectConfigResource
# ===========================================================================


class RenameCollectConfigResource(Resource):
    """编辑采集配置的名称。

    [ISSUE] base 没有专门的 rename API，当前通过直接更新 ORM 模型实现。
    如果后续 base 提供了 update_metric_plugin_deployment_name，应该迁移。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        name = serializers.CharField(label="名称")

    def perform_request(self, validated_request_data: dict) -> str:
        # [ISSUE] base 没有单独的 rename operation，暂时直接更新旧 ORM 表
        # 后续需要 base 提供 rename 或 partial update API
        from bk_monitor_base.domains.metric_plugin.models import MetricPluginDeploymentModel

        MetricPluginDeploymentModel.objects.filter(
            id=validated_request_data["id"], bk_biz_id=validated_request_data["bk_biz_id"]
        ).update(name=validated_request_data["name"])
        return "success"


# ===========================================================================
# ToggleCollectConfigStatusResource
# ===========================================================================


class ToggleCollectConfigStatusResource(Resource):
    """启停采集配置。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置ID")
        action = serializers.ChoiceField(required=True, choices=["enable", "disable"], label="启停配置")

    def perform_request(self, validated_request_data: dict) -> str:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()
        config_id = params["id"]
        action = params["action"]

        if action == "enable":
            start_metric_plugin_deployment(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=params["bk_biz_id"],
                deployment_id=config_id,
                operator=operator,
            )
        else:
            stop_metric_plugin_deployment(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=params["bk_biz_id"],
                deployment_id=config_id,
                operator=operator,
            )

        return "success"


# ===========================================================================
# DeleteCollectConfigResource
# ===========================================================================


class DeleteCollectConfigResource(Resource):
    """删除采集配置。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, validated_request_data: dict) -> None:
        data = validated_request_data
        bk_tenant_id = _ensure_tenant_id()

        delete_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=data["bk_biz_id"],
            deployment_id=data["id"],
        )

        # SaaS 层保留的告警策略清理逻辑
        username = _ensure_operator()
        try:
            # [ISSUE] DatalinkDefaultAlarmStrategyLoader 依赖旧 ORM CollectConfigMeta，
            # 但 base 已删除对应记录，这里尝试性调用，失败不影响主流程
            collect_config = CollectConfigMeta.objects.filter(bk_biz_id=data["bk_biz_id"], id=data["id"]).first()
            if collect_config:
                configs_exist = CollectConfigMeta.objects.filter(
                    bk_biz_id=data["bk_biz_id"], create_user=username
                ).exists()
                loader = DatalinkDefaultAlarmStrategyLoader(collect_config=collect_config, user_id=username)
                loader.delete(remove_user_from_group=not configs_exist)
        except Exception as e:
            logger.warning("告警策略清理失败（不影响主流程）: %s", e)


# ===========================================================================
# CloneCollectConfigResource
# ===========================================================================


class CloneCollectConfigResource(Resource):
    """克隆采集配置。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, validated_request_data: dict) -> None:
        data = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()
        bk_biz_id = data["bk_biz_id"]

        # 获取源配置详情
        source_detail = resource.collecting.collect_config_detail(data)

        # 生成不重名的名称
        new_name = base_name = source_detail["name"] + "_copy"
        i = 1
        while self._name_exists(bk_tenant_id, bk_biz_id, new_name):
            new_name = f"{base_name}({i})"
            i += 1

        collect_type = source_detail.get("collect_type", "")
        # 日志 / SNMP Trap 类型走 save_collect_config 重新创建
        if collect_type in (
            CollectConfigMeta.CollectType.LOG,
            CollectConfigMeta.CollectType.SNMP_TRAP,
        ):
            save_data = {**source_detail}
            save_data["name"] = new_name
            save_data.pop("id", None)
            save_data["plugin_id"] = "default_log"
            save_data["target_nodes"] = []
            resource.collecting.save_collect_config(save_data)
            return

        # 其他类型：读出 → 构建新部署参数 → 写入
        deployment, version = _get_deployment_or_raise(bk_tenant_id, data["id"], bk_biz_id)
        plugin = _get_plugin(bk_tenant_id, deployment.plugin_id)

        clone_params = CreateOrUpdateDeploymentParams(
            name=new_name,
            plugin_id=deployment.plugin_id,
            plugin_version=version.plugin_version if version else plugin.version,
            target_scope=MetricPluginDeploymentScope(
                node_type=version.target_scope.node_type if version else "TOPO",
                nodes=[],
            ),
            remote_scope=None,
            params=version.params if version else {},
        )
        save_and_install_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            operator=operator,
            params=clone_params,
        )

    @staticmethod
    def _name_exists(bk_tenant_id: str, bk_biz_id: int, name: str) -> bool:
        """检查名称是否已被使用。"""
        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=[bk_biz_id],
        )
        return any(d.name == name for d in deployments)


# ===========================================================================
# RetryTargetNodesResource
# ===========================================================================


class RetryTargetNodesResource(Resource):
    """重试部分实例或主机。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置ID")
        instance_id = serializers.CharField(required=True, label="需要重试的实例id")

    def perform_request(self, validated_request_data: dict[str, Any]) -> str:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        retry_params = RetryDeployPluginParams(
            deployment_id=params["id"],
            instance_scope=MetricPluginDeploymentScope(
                node_type="INSTANCE",
                nodes=[{"instance_id": params["instance_id"]}],
            ),
        )
        retry_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=params["bk_biz_id"],
            operator=operator,
            params=retry_params,
        )
        return "success"


# ===========================================================================
# RevokeTargetNodesResource
# ===========================================================================


class RevokeTargetNodesResource(Resource):
    """终止部分部署中的实例。

    [ISSUE] base 没有直接的 revoke operation，
    当前通过获取安装器实例调用 revoke 方法实现。
    需要 base 补齐 revoke_metric_plugin_deployment 能力。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        instance_ids = serializers.ListField(label="需要终止的实例ID")

    def perform_request(self, validated_request_data: dict[str, Any]) -> str:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        # [ISSUE] base operation 层没有 revoke 方法，需要直接走 installer
        from bk_monitor_base.domains.metric_plugin.installer.tools import get_installer

        deployment, _version = _get_deployment_or_raise(bk_tenant_id, params["id"], params["bk_biz_id"])
        installer = get_installer(deployment=deployment, operator=operator)
        # [ISSUE] base installer.revoke() 只接受 scope 参数，不支持按 instance_ids 撤销。
        # 原接口支持传入 instance_ids 做部分实例撤销，需 base 补齐此能力。
        installer.revoke()
        return "success"


# ===========================================================================
# RunCollectConfigResource
# ===========================================================================


class RunCollectConfigResource(Resource):
    """主动执行部分实例或节点。

    [ISSUE] base operation 层没有直接的 run 方法，需要通过 installer 调用。
    """

    class RequestSerializer(serializers.Serializer):
        class ScopeParams(serializers.Serializer):
            node_type = serializers.ChoiceField(required=True, label="采集对象类型", choices=["TOPO", "INSTANCE"])
            nodes = serializers.ListField(required=True, label="节点列表")

        scope = ScopeParams(label="事件订阅监听的范围", required=False)
        action = serializers.CharField(label="操作", default="install")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, validated_request_data: dict[str, Any]) -> str:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        from bk_monitor_base.domains.metric_plugin.installer.tools import get_installer

        deployment, _version = _get_deployment_or_raise(bk_tenant_id, params["id"], params["bk_biz_id"])
        installer = get_installer(deployment=deployment, operator=operator)
        installer.run(params["action"], params.get("scope"))
        return "success"


# ===========================================================================
# BatchRevokeTargetNodesResource
# ===========================================================================


class BatchRevokeTargetNodesResource(Resource):
    """批量终止采集配置的部署中的实例。

    [ISSUE] 同 RevokeTargetNodesResource，base 无 revoke operation。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, validated_request_data: dict[str, Any]) -> str:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        from bk_monitor_base.domains.metric_plugin.installer.tools import get_installer

        deployment, _version = _get_deployment_or_raise(bk_tenant_id, params["id"], params["bk_biz_id"])
        installer = get_installer(deployment=deployment, operator=operator)
        installer.revoke()
        return "success"


# ===========================================================================
# GetCollectLogDetailResource
# ===========================================================================


class GetCollectLogDetailResource(Resource):
    """获取采集下发单台主机/实例的详细日志信息。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        instance_id = serializers.CharField(label="主机/实例id")
        task_id = serializers.IntegerField(label="任务id")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        return get_nodeman_collect_log_detail(
            bk_tenant_id=bk_tenant_id,
            deployment_id=params["id"],
            bk_biz_id=params["bk_biz_id"],
            instance_id=params["instance_id"],
            operator=operator,
        )


# ===========================================================================
# BatchRetryConfigResource / BatchRetryResource
# ===========================================================================


class BatchRetryConfigResource(Resource):
    """重试所有失败的实例。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, validated_request_data: dict[str, Any]) -> str:
        params = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        retry_params = RetryDeployPluginParams(
            deployment_id=params["id"],
            instance_scope=None,
        )
        retry_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=params["bk_biz_id"],
            operator=operator,
            params=retry_params,
        )
        return "success"


# ===========================================================================
# SaveCollectConfigResource
# ===========================================================================


class SaveCollectConfigResource(Resource):
    """新增或编辑采集配置。"""

    class RequestSerializer(serializers.Serializer):
        class RemoteCollectingSlz(serializers.Serializer):
            ip = serializers.CharField(required=False)
            bk_cloud_id = serializers.IntegerField(required=False)
            bk_host_id = serializers.IntegerField(required=False)
            bk_supplier_id = serializers.IntegerField(required=False)
            is_collecting_only = serializers.BooleanField(required=True)

            def validate(self, attrs):
                if "bk_host_id" not in attrs and not ("ip" in attrs and "bk_cloud_id" in attrs):
                    raise serializers.ValidationError(_("主机id和ip/bk_cloud_id不能同时为空"))
                return attrs

        class MetricRelabelConfigSerializer(serializers.Serializer):
            source_labels = serializers.ListField(child=serializers.CharField(), label="源标签列表")
            regex = serializers.CharField(label="正则表达式")
            action = serializers.CharField(required=False, label="操作类型")
            target_label = serializers.CharField(required=False, label="目标标签")
            replacement = serializers.CharField(required=False, label="替换内容")

        id = serializers.IntegerField(required=False, label="采集配置ID")
        name = serializers.CharField(required=True, label="采集配置名称")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_type = serializers.ChoiceField(
            required=True, label="采集方式", choices=CollectConfigMeta.COLLECT_TYPE_CHOICES
        )
        target_object_type = serializers.ChoiceField(
            required=True, label="采集对象类型", choices=CollectConfigMeta.TARGET_OBJECT_TYPE_CHOICES
        )
        target_node_type = serializers.ChoiceField(
            required=True,
            label="采集目标类型",
            choices=[
                (TargetNodeType.INSTANCE, "INSTANCE"),
                (TargetNodeType.TOPO, "TOPO"),
                (TargetNodeType.SERVICE_TEMPLATE, "SERVICE_TEMPLATE"),
                (TargetNodeType.SET_TEMPLATE, "SET_TEMPLATE"),
                (TargetNodeType.DYNAMIC_GROUP, "DYNAMIC_GROUP"),
                ("CLUSTER", "CLUSTER"),
            ],
        )
        plugin_id = serializers.CharField(required=True, label="插件ID")
        target_nodes = serializers.ListField(required=True, label="节点列表", allow_empty=True)
        remote_collecting_host = RemoteCollectingSlz(
            required=False, allow_null=True, default=None, label="远程采集配置"
        )
        params = serializers.DictField(required=True, label="采集配置参数")
        label = serializers.CharField(required=True, label="二级标签")
        operation = serializers.ChoiceField(default="EDIT", choices=["EDIT", "ADD_DEL"], label="操作类型")
        metric_relabel_configs = MetricRelabelConfigSerializer(many=True, default=list, label="指标重新标记配置")

        def validate(self, attrs):
            target_type = (attrs["target_object_type"], attrs["target_node_type"])
            if target_type in [
                (TargetObjectType.HOST, TargetNodeType.TOPO),
                (TargetObjectType.SERVICE, TargetNodeType.TOPO),
            ]:
                for node in attrs["target_nodes"]:
                    if not ("bk_inst_id" in node and "bk_obj_id" in node):
                        raise serializers.ValidationError("target_nodes needs bk_inst_id and bk_obj_id")
            elif target_type == (TargetObjectType.HOST, TargetNodeType.INSTANCE):
                for node in attrs["target_nodes"]:
                    if "bk_target_ip" in node and "bk_target_cloud_id" in node:
                        node["ip"] = node.pop("bk_target_ip")
                        node["bk_cloud_id"] = node.pop("bk_target_cloud_id")
                    if not ("ip" in node and "bk_cloud_id" in node) and "bk_host_id" not in node:
                        raise serializers.ValidationError("target_nodes needs ip, bk_cloud_id or bk_host_id")
            elif target_type in [
                (TargetObjectType.HOST, TargetNodeType.SERVICE_TEMPLATE),
                (TargetObjectType.HOST, TargetNodeType.SET_TEMPLATE),
                (TargetObjectType.SERVICE, TargetNodeType.SET_TEMPLATE),
                (TargetObjectType.SERVICE, TargetNodeType.SERVICE_TEMPLATE),
            ]:
                for node in attrs["target_nodes"]:
                    if not ("bk_inst_id" in node and "bk_obj_id" in node):
                        raise serializers.ValidationError("target_nodes needs bk_inst_id, bk_obj_id")
            elif target_type == (TargetObjectType.CLUSTER, "CLUSTER"):
                for node in attrs["target_nodes"]:
                    if "bcs_cluster_id" not in node:
                        raise serializers.ValidationError("target_nodes needs bcs_cluster_id")
            elif attrs["target_node_type"] == TargetNodeType.DYNAMIC_GROUP:
                for node in attrs["target_nodes"]:
                    if not ("bk_inst_id" in node and "bk_obj_id" in node):
                        raise serializers.ValidationError("target_nodes needs bk_inst_id, bk_obj_id")
            else:
                raise serializers.ValidationError(
                    "{} {} is not supported".format(attrs["target_object_type"], attrs["target_node_type"])
                )

            # 目标字段整理
            target_nodes = []
            for node in attrs["target_nodes"]:
                if "bk_host_id" in node:
                    target_nodes.append({"bk_host_id": node["bk_host_id"]})
                elif "bk_inst_id" in node and "bk_obj_id" in node:
                    item = {"bk_inst_id": node["bk_inst_id"], "bk_obj_id": node["bk_obj_id"]}
                    if "bk_biz_id" in node:
                        item["bk_biz_id"] = node["bk_biz_id"]
                    target_nodes.append(item)
                elif "bcs_cluster_id" in node:
                    target_nodes.append({"bcs_cluster_id": node["bcs_cluster_id"]})
                elif "ip" in node and "bk_cloud_id" in node:
                    target_nodes.append({"ip": node["ip"], "bk_cloud_id": node["bk_cloud_id"]})
            attrs["target_nodes"] = target_nodes

            if attrs["collect_type"] == CollectConfigMeta.CollectType.LOG:
                rules = attrs["params"]["log"]["rules"]
                name_set: set[str] = set()
                for rule in rules:
                    rule_name = rule["name"]
                    if rule_name in name_set:
                        raise CollectConfigParamsError(msg=f"Duplicate keyword rule name({rule_name})")
                    name_set.add(rule_name)

            if not attrs.get("id") and attrs["collect_type"] == CollectConfigMeta.CollectType.PUSHGATEWAY:
                password = attrs["params"]["collector"].get("password")
                if password is True:
                    raise serializers.ValidationError("Please reset your password")
                elif password is False:
                    attrs["params"]["collector"]["password"] = ""

            return attrs

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        data = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        # 获取或创建虚拟插件
        plugin_id = self._get_or_create_plugin(data, bk_tenant_id)
        data["plugin_id"] = plugin_id

        data["params"]["target_node_type"] = data["target_node_type"]
        data["params"]["target_object_type"] = data["target_object_type"]
        data["params"]["collector"]["metric_relabel_configs"] = data.pop("metric_relabel_configs")

        # 编辑时处理密码字段
        if data.get("id"):
            self._handle_password_update(data, bk_tenant_id)

        # 转换参数并调用 base
        base_params = convert_save_params_to_base(data, bk_tenant_id)
        result = save_and_install_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=data["bk_biz_id"],
            operator=operator,
            params=base_params,
        )

        # 指标缓存更新
        try:
            plugin = _get_plugin(bk_tenant_id, plugin_id)
            self._update_metric_cache(plugin, bk_tenant_id)
        except Exception as e:
            logger.warning("指标缓存更新失败: %s", e)

        # 告警策略创建
        try:
            # [ISSUE] DatalinkDefaultAlarmStrategyLoader 依赖旧 ORM CollectConfigMeta
            # 新版 base 写入后 CollectConfigMeta 可能不存在对应记录
            # 需要后续适配 DatalinkDefaultAlarmStrategyLoader 支持 base 模型
            collect_config = CollectConfigMeta.objects.filter(bk_biz_id=data["bk_biz_id"], name=data["name"]).first()
            if collect_config:
                DatalinkDefaultAlarmStrategyLoader(collect_config=collect_config, user_id=operator).run()
        except Exception as error:
            logger.error("自动创建默认告警策略 DatalinkDefaultAlarmStrategyLoader error %s", error)

        return result

    def _get_or_create_plugin(self, data: dict, bk_tenant_id: str) -> str:
        """获取或创建虚拟插件，返回 plugin_id。"""
        collect_type = data["collect_type"]
        plugin_id = data["plugin_id"]

        if collect_type == CollectConfigMeta.CollectType.SNMP_TRAP:
            return resource.collecting.get_trap_collector_plugin(data)

        # LOG / PROCESS / K8S 虚拟插件仍使用旧路径
        # [ISSUE] 虚拟插件创建依赖 PluginManagerFactory，
        # 需要确认 plugin 模块是否已适配 base 并统一处理
        from monitor_web.plugin.manager import PluginManagerFactory
        from bkmonitor.utils import shortuuid

        if collect_type == CollectConfigMeta.CollectType.LOG:
            label = data["label"]
            bk_biz_id = data["bk_biz_id"]
            rules = data["params"]["log"]["rules"]
            if "id" not in data:
                plugin_id = "log_" + str(shortuuid.uuid())
                plugin_manager = PluginManagerFactory.get_manager(
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.LOG
                )
                params = plugin_manager.get_params(plugin_id, bk_biz_id, label, rules=rules)
                resource.plugin.create_plugin(params)
            else:
                plugin_manager = PluginManagerFactory.get_manager(
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.LOG
                )
                params = plugin_manager.get_params(plugin_id, bk_biz_id, label, rules=rules)
                plugin_manager.update_version(params)
        elif collect_type == CollectConfigMeta.CollectType.PROCESS:
            plugin_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=bk_tenant_id, plugin="bkprocessbeat", plugin_type=PluginType.PROCESS
            )
            plugin_manager.touch(bk_biz_id=data["bk_biz_id"])
            plugin_id = plugin_manager.plugin.plugin_id
        elif collect_type == CollectConfigMeta.CollectType.K8S:
            qcloud_exporter_plugin_id = f"{settings.TENCENT_CLOUD_METRIC_PLUGIN_ID}_{data['bk_biz_id']}"
            if plugin_id not in [settings.TENCENT_CLOUD_METRIC_PLUGIN_ID, qcloud_exporter_plugin_id]:
                raise ValueError(f"Only support {settings.TENCENT_CLOUD_METRIC_PLUGIN_ID} k8s collector")
            plugin_id = qcloud_exporter_plugin_id
            if not settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG:
                raise ValueError("TENCENT_CLOUD_METRIC_PLUGIN_CONFIG is not set, please contact administrator")
            plugin_config: dict[str, Any] = settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG
            plugin_params = {
                "plugin_id": plugin_id,
                "bk_biz_id": data["bk_biz_id"],
                "plugin_type": PluginType.K8S,
                "label": plugin_config.get("label", "os"),
                "plugin_display_name": _(plugin_config.get("plugin_display_name", "腾讯云指标采集")),
                "description_md": plugin_config.get("description_md", ""),
                "logo": plugin_config.get("logo", ""),
                "version_log": plugin_config.get("version_log", ""),
                "metric_json": [],
                "collector_json": plugin_config["collector_json"],
                "config_json": plugin_config.get("config_json", []),
                "data_label": settings.TENCENT_CLOUD_METRIC_PLUGIN_ID,
            }
            from monitor_web.models import CollectorPluginMeta as OldPluginMeta

            if OldPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id).exists():
                plugin_manager = PluginManagerFactory.get_manager(
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.K8S
                )
                plugin_manager.update_version(plugin_params)
            else:
                resource.plugin.create_plugin(plugin_params)

        return plugin_id

    def _handle_password_update(self, data: dict, bk_tenant_id: str) -> None:
        """编辑时处理密码字段替换。"""
        try:
            deployment, version = _get_deployment_or_raise(bk_tenant_id, data["id"], data["bk_biz_id"])
            plugin = _get_plugin(bk_tenant_id, deployment.plugin_id)
            deployment_params = version.params if version else {}
            for param in plugin.params:
                p = param.model_dump() if hasattr(param, "model_dump") else dict(param)
                if p.get("type") not in ("password", "encrypt"):
                    continue
                param_name = p.get("name", "")
                param_mode = "plugin" if p.get("mode") != "collector" else "collector"
                received = data["params"].get(param_mode, {}).get(param_name)
                if isinstance(received, bool | type(None)):
                    actual = deployment_params.get(param_mode, {}).get(param_name, p.get("default"))
                    if param_mode in data["params"]:
                        data["params"][param_mode][param_name] = actual
        except Exception as e:
            logger.warning("密码字段替换失败: %s", e)

    @staticmethod
    def _update_metric_cache(plugin, bk_tenant_id: str) -> None:
        """更新指标缓存。"""
        metrics = plugin.metrics
        if not metrics:
            return
        result_table_id_list = [f"{plugin.type}_{plugin.id}.{m.table_name}" for m in metrics]
        append_metric_list_cache.delay(bk_tenant_id, result_table_id_list)


# ===========================================================================
# UpgradeCollectPluginResource
# ===========================================================================


class UpgradeCollectPluginResource(Resource):
    """采集配置插件升级。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")
        params = serializers.DictField(required=True, label="采集配置参数")
        realtime = serializers.BooleanField(required=False, default=False, label=_("是否实时刷新缓存"))

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict:
        data = validated_request_data
        bk_tenant_id = _ensure_tenant_id()
        operator = _ensure_operator()

        deployment, version = _get_deployment_or_raise(bk_tenant_id, data["id"], data["bk_biz_id"])
        plugin = _get_plugin(bk_tenant_id, deployment.plugin_id)

        # 用最新插件版本重新安装
        upgrade_params = CreateOrUpdateDeploymentParams(
            id=deployment.id,
            name=deployment.name,
            plugin_id=deployment.plugin_id,
            plugin_version=plugin.version,
            target_scope=version.target_scope if version else MetricPluginDeploymentScope(node_type="TOPO", nodes=[]),
            remote_scope=version.remote_scope if version else None,
            params=data["params"],
        )
        result = save_and_install_metric_plugin_deployment(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=data["bk_biz_id"],
            operator=operator,
            params=upgrade_params,
        )

        # 更新指标缓存
        metrics = plugin.metrics
        if metrics:
            result_table_id_list = [f"{plugin.type}_{plugin.id}.{m.table_name}" for m in metrics]
            append_metric_list_cache.delay(bk_tenant_id, result_table_id_list)

        return result


# ===========================================================================
# RollbackDeploymentConfigResource
# ===========================================================================


class RollbackDeploymentConfigResource(Resource):
    """采集配置回滚。

    [ISSUE] base 没有 rollback operation，通过获取上一版本参数重新 install 模拟。
    需要 base 提供历史版本查询 API 才能准确获取上一版本。
    当前实现暂时使用简化逻辑。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict | None:
        data = validated_request_data
        bk_tenant_id = _ensure_tenant_id()

        _get_deployment_or_raise(bk_tenant_id, data["id"], data["bk_biz_id"])

        # [ISSUE] base 不提供历史版本列表查询 API，
        # 无法获取「上一版本」的完整参数进行回滚。
        # 需要 base 补齐 list_metric_plugin_deployment_versions() 能力。
        # 暂时回退到旧 ORM 实现：
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                bk_biz_id=data["bk_biz_id"], pk=data["id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": data["id"]})

        if not collect_config.allow_rollback:
            raise CollectConfigRollbackError({"msg": _("当前操作不支持回滚，或采集配置正处于执行中")})

        from monitor_web.collecting.deploy import get_collect_installer

        installer = get_collect_installer(collect_config)
        return installer.rollback()


# ===========================================================================
# GetMetricsResource
# ===========================================================================


class GetMetricsResource(Resource):
    """获取对应插件版本的指标参数。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")

    def perform_request(self, validated_request_data: dict[str, Any]) -> list:
        bk_tenant_id = _ensure_tenant_id()

        deployment, version = _get_deployment_or_raise(
            bk_tenant_id,
            validated_request_data["id"],
            validated_request_data["bk_biz_id"],
        )
        plugin = _get_plugin(bk_tenant_id, deployment.plugin_id)

        # 返回插件的指标 JSON（转换为旧格式）
        from monitor_web.plugin.compat import convert_metric_json_to_legacy

        return convert_metric_json_to_legacy(
            [m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in plugin.metrics]
        )


# ===========================================================================
# CollectConfigInfoResource
# ===========================================================================


class CollectConfigInfoResource(Resource):
    """提供给 kernel api 使用，查询采集配置信息。

    [ISSUE] 旧版返回 CollectConfigMeta.objects.all().values() 的原始 dict，
    base 返回的格式与 ORM values() 完全不同。
    为保持对外 API 兼容性，暂时仍使用旧 ORM 查询。
    后续需要所有调用方适配新格式，或提供兼容转换。
    """

    def perform_request(self, validated_request_data: dict) -> list:
        # [ISSUE] 此接口返回 ORM values() 原始格式，
        # base 无法直接提供等价数据。暂时保留旧实现。
        return list(CollectConfigMeta.objects.all().values())


# ===========================================================================
# BatchRetryResource
# ===========================================================================


class BatchRetryResource(BatchRetryConfigResource):
    """详情页批量重试，继承 BatchRetryConfigResource。"""

    pass
