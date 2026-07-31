"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

platform-source catalog domain：nodeman（节点管理 bk-nodeman，只读）。

能力面：采集订阅在各目标主机上的下发/进程态 —— 回答"采集配置是否部署到主机 X、状态如何"。
- get_subscription_summary：订阅基本属性、目标范围计数、插件与模板版本元数据
- fetch_subscription_statistic：订阅实例状态与插件版本分布
- get_subscription_instance_status：按订阅ID列出各实例的部署状态 + 主机归属 + bkmonitorbeat 进程态
- get_subscription_task_instances：分页查询订阅实例任务，不返回步骤与日志
- search_host_plugin_status：按主机ID查询 Agent 与插件状态/版本

典型链路：read-db-model 读 DeploymentConfigVersion 拿 subscription_id → 本接口查该订阅各实例
是否部署成功、主机是否在订阅范围内（区分"配置目标"与"运行时上报"）。

readonly 防线（在 id 前缀白名单 / domain readonly tag 之上叠加 params_guard）：
- 参数 key 白名单：拒绝一切未声明 key，杜绝 RequestSerializer 隐藏参数
  （如 _user_request 切换鉴权方式）经 CLI 整体透传下发
- 固定关闭 show_task_detail，并对响应做字段白名单投影；不向 CLI 返回步骤、日志、inputs
- 不直接开放 task_result_detail / subscription_info：其原始返回含渲染参数或安装凭据

边界：实例状态 SUCCESS 仅表示下发/进程就绪，不代表采集数据合法；数据是否正常另查采集健康指标。
"""

from __future__ import annotations

from typing import Any

from core.drf_resource import api

from ._catalog import OperationSpec, ParamsGuardRejected, PlatformSourceCatalog

SUBSCRIPTION_INSTANCE_STATUS_ALLOWED_KEYS = frozenset({"subscription_id_list"})
SUBSCRIPTION_SUMMARY_ALLOWED_KEYS = frozenset({"subscription_id_list"})
SUBSCRIPTION_STATISTIC_ALLOWED_KEYS = frozenset({"subscription_id_list"})
SUBSCRIPTION_TASK_INSTANCES_ALLOWED_KEYS = frozenset({"subscription_id", "task_id_list", "page", "pagesize"})
HOST_PLUGIN_STATUS_ALLOWED_KEYS = frozenset({"bk_host_id", "page", "pagesize"})

MAX_PAGE_SIZE = 1000

INSTANCE_HOST_FIELDS = (
    "bk_host_innerip_v6",
    "bk_host_innerip",
    "bk_cloud_id",
    "bk_supplier_account",
    "bk_host_name",
    "bk_host_id",
    "bk_biz_id",
    "bk_biz_name",
    "bk_cloud_name",
)
INSTANCE_SERVICE_FIELDS = ("id", "name", "bk_module_id", "bk_host_id")
SUBSCRIPTION_STEP_CONFIG_FIELDS = (
    "job_type",
    "plugin_name",
    "plugin_version",
    "is_version_sensitive",
)
CONFIG_TEMPLATE_FIELDS = ("name", "version", "os", "cpu_arch", "is_main")
TASK_INSTANCE_FIELDS = (
    "task_id",
    "record_id",
    "instance_id",
    "create_time",
    "start_time",
    "finish_time",
    "status",
    "pipeline_id",
)
STATUS_COUNTER_FIELDS = (
    "SUCCESS",
    "PENDING",
    "FAILED",
    "RUNNING",
    "PART_FAILED",
    "TERMINATED",
    "REMOVED",
    "FILTERED",
    "IGNORED",
    "total",
)
HOST_PLUGIN_FIELDS = (
    "bk_biz_id",
    "bk_host_id",
    "bk_cloud_id",
    "bk_host_name",
    "inner_ip",
    "inner_ipv6",
    "os_type",
    "cpu_arch",
    "node_type",
    "node_from",
    "status",
    "version",
    "status_display",
    "bk_cloud_name",
    "bk_biz_name",
)


def _reject_unknown_keys(params: dict[str, Any], allowed: frozenset[str], op_id: str) -> None:
    unknown = sorted(str(k) for k in params if k not in allowed)
    if unknown:
        raise ParamsGuardRejected(f"{op_id} 仅接受参数 {sorted(allowed)}，拒绝未声明参数: {unknown}")


def _project_dict(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {field: value[field] for field in fields if field in value}


def _project_instance_info(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    host = _project_dict(source.get("host"), INSTANCE_HOST_FIELDS)
    bk_cloud_id = host.get("bk_cloud_id")
    if isinstance(bk_cloud_id, list) and bk_cloud_id and isinstance(bk_cloud_id[0], dict):
        host["bk_cloud_id"] = bk_cloud_id[0].get("id")
    return {
        "host": host,
        "service": _project_dict(source.get("service"), INSTANCE_SERVICE_FIELDS),
    }


def _normalize_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ParamsGuardRejected(f"{field} 必须为正整数")
    if isinstance(value, int):
        normalized = value
    elif isinstance(value, str):
        try:
            normalized = int(value)
        except ValueError:
            raise ParamsGuardRejected(f"{field} 必须为正整数: {value!r}")
    else:
        raise ParamsGuardRejected(f"{field} 必须为正整数: {value!r}")
    if normalized <= 0:
        raise ParamsGuardRejected(f"{field} 必须为正整数: {value!r}")
    return normalized


def _normalize_int_list(value: Any, field: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ParamsGuardRejected(f"{field} 必须为非空正整数列表")
    return [_normalize_int(item, field) for item in value]


def _normalize_pagination(params: dict[str, Any]) -> tuple[int, int]:
    page = _normalize_int(params.get("page", 1), "page")
    pagesize = _normalize_int(params.get("pagesize", 100), "pagesize")
    if pagesize > MAX_PAGE_SIZE:
        raise ParamsGuardRejected(f"pagesize 不得超过 {MAX_PAGE_SIZE}")
    return page, pagesize


def _guard_subscription_ids(params: dict[str, Any], allowed: frozenset[str], op_id: str) -> dict[str, Any]:
    _reject_unknown_keys(params, allowed, op_id)
    return {"subscription_id_list": _normalize_int_list(params.get("subscription_id_list"), "subscription_id_list")}


def guard_subscription_summary(params: dict[str, Any]) -> dict[str, Any]:
    return _guard_subscription_ids(params, SUBSCRIPTION_SUMMARY_ALLOWED_KEYS, "get_subscription_summary")


def guard_subscription_statistic(params: dict[str, Any]) -> dict[str, Any]:
    return _guard_subscription_ids(params, SUBSCRIPTION_STATISTIC_ALLOWED_KEYS, "fetch_subscription_statistic")


def project_subscription_summary(raw: Any, _fields: list[str] | None) -> list[dict[str, Any]]:
    """订阅详情安全摘要：不返回目标主机详情、scope instance_info 或 steps.params。"""
    if not isinstance(raw, list):
        return []

    result: list[dict[str, Any]] = []
    for subscription in raw:
        if not isinstance(subscription, dict):
            continue
        projected = _project_dict(
            subscription,
            ("id", "name", "enable", "category", "plugin_name", "bk_biz_scope", "pid"),
        )
        scope = subscription.get("scope") if isinstance(subscription.get("scope"), dict) else {}
        projected_scope = _project_dict(scope, ("bk_biz_id", "object_type", "node_type"))
        projected_scope["node_count"] = len(scope.get("nodes")) if isinstance(scope.get("nodes"), list) else 0
        projected["scope"] = projected_scope
        projected["target_host_count"] = (
            len(subscription["target_hosts"]) if isinstance(subscription.get("target_hosts"), list) else 0
        )

        projected_steps: list[dict[str, Any]] = []
        steps = subscription.get("steps")
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, dict):
                continue
            projected_step = _project_dict(step, ("id", "type"))
            config = step.get("config") if isinstance(step.get("config"), dict) else {}
            projected_config = _project_dict(config, SUBSCRIPTION_STEP_CONFIG_FIELDS)
            templates = config.get("config_templates")
            projected_config["config_templates"] = [
                _project_dict(template, CONFIG_TEMPLATE_FIELDS)
                for template in (templates if isinstance(templates, list) else [])
                if isinstance(template, dict)
            ]
            projected_step["config"] = projected_config
            projected_steps.append(projected_step)
        projected["steps"] = projected_steps
        result.append(projected)
    return result


def project_subscription_statistic(raw: Any, _fields: list[str] | None) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for statistic in raw:
        if not isinstance(statistic, dict):
            continue
        projected = _project_dict(statistic, ("subscription_id", "instances"))
        statuses = statistic.get("status")
        projected["status"] = [
            _project_dict(item, ("status", "count"))
            for item in (statuses if isinstance(statuses, list) else [])
            if isinstance(item, dict)
        ]
        versions = statistic.get("versions")
        projected["versions"] = [
            _project_dict(item, ("name", "version", "count"))
            for item in (versions if isinstance(versions, list) else [])
            if isinstance(item, dict)
        ]
        result.append(projected)
    return result


def guard_subscription_task_instances(params: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(params, SUBSCRIPTION_TASK_INSTANCES_ALLOWED_KEYS, "get_subscription_task_instances")
    page, pagesize = _normalize_pagination(params)
    normalized: dict[str, Any] = {
        "subscription_id": _normalize_int(params.get("subscription_id"), "subscription_id"),
        "need_detail": False,
        "need_aggregate_all_tasks": "task_id_list" not in params,
        "need_out_of_scope_snapshots": False,
        "page": page,
        "pagesize": pagesize,
    }
    if "task_id_list" in params:
        normalized["task_id_list"] = _normalize_int_list(params["task_id_list"], "task_id_list")
    return normalized


def project_subscription_task_instances(raw: Any, _fields: list[str] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"total": 0, "list": [], "status_counter": {}}
    projected = _project_dict(raw, ("total",))
    status_counter = raw.get("status_counter")
    projected["status_counter"] = _project_dict(status_counter, STATUS_COUNTER_FIELDS)
    projected_instances: list[dict[str, Any]] = []
    instances = raw.get("list")
    for instance in instances if isinstance(instances, list) else []:
        if not isinstance(instance, dict):
            continue
        projected_instance = _project_dict(instance, TASK_INSTANCE_FIELDS)
        projected_instance["instance_info"] = _project_instance_info(instance.get("instance_info"))
        projected_instances.append(projected_instance)
    projected["list"] = projected_instances
    return projected


def guard_host_plugin_status(params: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(params, HOST_PLUGIN_STATUS_ALLOWED_KEYS, "search_host_plugin_status")
    page, pagesize = _normalize_pagination(params)
    return {
        "bk_host_id": _normalize_int_list(params.get("bk_host_id"), "bk_host_id"),
        "page": page,
        "pagesize": pagesize,
    }


def project_host_plugin_status(raw: Any, _fields: list[str] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"total": 0, "list": []}
    projected = _project_dict(raw, ("total",))
    projected_hosts: list[dict[str, Any]] = []
    hosts = raw.get("list")
    for host in hosts if isinstance(hosts, list) else []:
        if not isinstance(host, dict):
            continue
        projected_host = _project_dict(host, HOST_PLUGIN_FIELDS)
        plugin_statuses = host.get("plugin_status")
        projected_host["plugin_status"] = [
            _project_dict(item, ("name", "status", "version", "host_id"))
            for item in (plugin_statuses if isinstance(plugin_statuses, list) else [])
            if isinstance(item, dict)
        ]
        projected_hosts.append(projected_host)
    projected["list"] = projected_hosts
    return projected


def project_subscription_instance_status(raw: Any, _fields: list[str] | None) -> list[dict[str, Any]]:
    """实例状态固定投影：即使上游新增详情字段，也不会透传到 bkm-cli。"""
    if not isinstance(raw, list):
        return []

    result: list[dict[str, Any]] = []
    for subscription in raw:
        if not isinstance(subscription, dict):
            continue
        projected_instances: list[dict[str, Any]] = []
        instances = subscription.get("instances")
        for instance in instances if isinstance(instances, list) else []:
            if not isinstance(instance, dict):
                continue
            projected = _project_dict(instance, ("instance_id", "status", "create_time"))
            projected["instance_info"] = _project_instance_info(instance.get("instance_info"))
            projected["running_task"] = (
                _project_dict(instance["running_task"], ("id", "is_auto_trigger"))
                if isinstance(instance.get("running_task"), dict)
                else None
            )
            projected["last_task"] = _project_dict(instance.get("last_task"), ("id",))
            host_statuses = instance.get("host_statuses")
            projected["host_statuses"] = [
                _project_dict(item, ("name", "status", "version"))
                for item in (host_statuses if isinstance(host_statuses, list) else [])
                if isinstance(item, dict)
            ]
            projected_instances.append(projected)
        projected_subscription = _project_dict(subscription, ("subscription_id",))
        projected_subscription["instances"] = projected_instances
        result.append(projected_subscription)
    return result


def guard_subscription_instance_status(params: dict[str, Any]) -> dict[str, Any]:
    """仅接收订阅 ID；任务详情由后端固定关闭，调用方不能覆盖。"""
    _reject_unknown_keys(params, SUBSCRIPTION_INSTANCE_STATUS_ALLOWED_KEYS, "get_subscription_instance_status")

    return {
        "subscription_id_list": _normalize_int_list(params.get("subscription_id_list"), "subscription_id_list"),
        "show_task_detail": False,
    }


def register() -> None:
    """注册 nodeman domain。模块 import 时调用一次；测试 reset() 后可显式重注册。"""
    PlatformSourceCatalog.register_domain(
        id="nodeman",
        summary=(
            "节点管理（bk-nodeman）只读：采集订阅在各目标实例的下发状态，"
            "定位采集配置在主机上的部署/进程态，区分'配置目标'与'运行时上报'"
        ),
        audit_tags=["readonly", "nodeman"],
        operations=[
            OperationSpec(
                id="get_subscription_summary",
                summary="查询订阅安全摘要（基本属性、目标计数、插件与配置模板版本）",
                handler=api.node_man.subscription_info,
                params_guard=guard_subscription_summary,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "subscription_id_list": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "节点管理订阅 ID 列表",
                        }
                    },
                    "required": ["subscription_id_list"],
                },
                example_params={"subscription_id_list": [10001]},
                required_params=["subscription_id_list"],
                response_postprocess=project_subscription_summary,
                audit_tags=["readonly", "nodeman"],
                notes=(
                    "返回订阅基本属性、scope 的类型与目标数量、步骤插件版本和配置模板元数据。"
                    "不返回 scope.nodes、target_hosts、steps.params/context、模板内容或渲染参数；"
                    "因此不能用本接口还原安装凭据或采集端点配置。"
                ),
            ),
            OperationSpec(
                id="fetch_subscription_statistic",
                summary="统计订阅实例状态与节点上报的插件版本分布",
                handler=api.node_man.fetch_subscription_statistic,
                params_guard=guard_subscription_statistic,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "subscription_id_list": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "节点管理订阅 ID 列表",
                        }
                    },
                    "required": ["subscription_id_list"],
                },
                example_params={"subscription_id_list": [10001]},
                required_params=["subscription_id_list"],
                response_postprocess=project_subscription_statistic,
                audit_tags=["readonly", "nodeman"],
                notes=(
                    "status 是订阅实例任务状态计数，versions 来自节点管理 ProcessStatus 上报。"
                    "instances=0 或某版本计数为空不能单独证明未部署，需结合实例状态和 CMDB 目标范围判断。"
                ),
            ),
            OperationSpec(
                id="get_subscription_instance_status",
                summary="查询采集订阅在各目标实例的下发状态（部署成功/失败、主机归属、bkmonitorbeat 进程态）",
                handler=api.node_man.subscription_instance_status,
                params_guard=guard_subscription_instance_status,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "subscription_id_list": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "节点管理订阅ID列表；采集配置的 subscription_id 可经 read-db-model 读 "
                                "DeploymentConfigVersion 获取"
                            ),
                        },
                    },
                    "required": ["subscription_id_list"],
                },
                example_params={"subscription_id_list": [10001]},
                required_params=["subscription_id_list"],
                response_postprocess=project_subscription_instance_status,
                audit_tags=["readonly", "nodeman"],
                notes=(
                    "返回每个订阅下各实例的部署状态与主机信息（bk_host_id / 内网IP / status / host_statuses）。"
                    "实例 status=SUCCESS 仅表示下发/进程就绪，不代表采集数据合法——数据是否正常需另查 "
                    "采集健康指标（gather_up 的 bkm_up_code 等）。后端固定 show_task_detail=false，并对响应做"
                    "字段白名单投影，不返回任务步骤、日志、inputs 或渲染参数。"
                    "注意：subscription_id_list 是 node_man 原生批量接口，其中任一订阅在 node_man 侧异常会让"
                    "整批返回 provider_unavailable（非部分结果）；建议逐订阅查询以隔离失效订阅。"
                ),
            ),
            OperationSpec(
                id="get_subscription_task_instances",
                summary="分页查询订阅实例任务状态（固定无步骤、无日志、无渲染输入）",
                handler=api.node_man.task_result,
                params_guard=guard_subscription_task_instances,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "subscription_id": {"type": "integer", "description": "节点管理订阅 ID"},
                        "task_id_list": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "可选，限定订阅任务 ID",
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "pagesize": {
                            "type": "integer",
                            "default": 100,
                            "minimum": 1,
                            "maximum": MAX_PAGE_SIZE,
                        },
                    },
                    "required": ["subscription_id"],
                },
                example_params={"subscription_id": 10001, "page": 1, "pagesize": 100},
                required_params=["subscription_id"],
                response_postprocess=project_subscription_task_instances,
                audit_tags=["readonly", "nodeman"],
                notes=(
                    "后端固定 need_detail=false、need_out_of_scope_snapshots=false；未指定 task_id_list 时"
                    "聚合全部任务得到当前实例视图，指定 task_id_list 时关闭聚合以确保任务过滤生效。"
                    "响应再次固定投影并丢弃 steps/log/inputs。"
                    "status=SUCCESS 只表示节点管理任务执行成功，不代表采集数据已入库。"
                ),
            ),
            OperationSpec(
                id="search_host_plugin_status",
                summary="按 bk_host_id 查询 Agent 与插件运行状态/版本",
                handler=api.node_man.plugin_search,
                cache_bypass_method="refresh",
                params_guard=guard_host_plugin_status,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "bk_host_id": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "非空主机 ID 列表；不支持不带主机范围的全量查询",
                        },
                        "page": {"type": "integer", "default": 1, "minimum": 1},
                        "pagesize": {
                            "type": "integer",
                            "default": 100,
                            "minimum": 1,
                            "maximum": MAX_PAGE_SIZE,
                        },
                    },
                    "required": ["bk_host_id"],
                },
                example_params={"bk_host_id": [101], "page": 1, "pagesize": 100},
                required_params=["bk_host_id"],
                response_postprocess=project_host_plugin_status,
                audit_tags=["readonly", "nodeman"],
                notes=(
                    "仅允许显式 bk_host_id 范围，返回 Agent status/version 和 plugin_status。"
                    "不返回 job_result、操作权限或其他任务详情；插件 RUNNING 不等价于采集数据有效。"
                ),
            ),
        ],
    )


register()
