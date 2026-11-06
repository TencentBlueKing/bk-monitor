"""Create and edit standard strategies through the existing save API."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.strategy.new_strategy import Algorithm, Detect, Item, NoticeRelation, QueryConfig, Strategy
from bkmonitor.utils.request import get_request
from core.drf_resource.exceptions import CustomException
from kernel_api.resource.alert import CreateAlarmStrategyResource, UpdateAlarmStrategyResource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.management import validate_management_request
from kernel_api.rpc.functions.bkm_cli.platform_catalog.cmdb import _authorize_business

EDITABLE_FIELDS = {
    "config": ["name", "scenario", "is_enabled", "items", "detects", "notice", "labels"],
    "items": list(Item.Serializer().fields),
    "query_configs": sorted(
        {"data_source_label", "data_type_label", "alias"}
        | {field for serializer in QueryConfig.QueryConfigSerializerMapping.values() for field in serializer().fields}
    ),
    "algorithms": {"fields": list(Algorithm.Serializer().fields)},
    "detects": list(Detect.Serializer().fields),
}
LEGACY_QUERY_FIELDS = {"query_string", "agg_dimension", "agg_condition"}
QUERY_IDENTITY_FIELDS = {"data_source_label", "data_type_label", "alias"}
ALLOWED_FIELDS = {
    "operation",
    "bk_tenant_id",
    "bk_biz_id",
    "strategy_id",
    "config_version",
    "items",
    "config",
    "confirmed",
    "operator",
}
CREATE_ALLOWED_FIELDS = {"operation", "bk_tenant_id", "bk_biz_id", "config", "confirmed", "operator"}
CREATE_CONFIG_FIELDS = {"name", "scenario", "is_enabled", "items", "detects", "notice", "labels"}


def _strict_object(value, allowed_fields, path):
    if not isinstance(value, dict):
        raise CustomException(message=f"{path} 必须为对象")
    unknown = sorted(set(value) - set(allowed_fields))
    if unknown:
        raise CustomException(message=f"{path} 不支持的参数: {unknown}")


def _text(value, path, *, allow_blank=False):
    if not isinstance(value, str) or (not allow_blank and not value.strip()):
        raise CustomException(message=f"{path} 必须为{'非空' if not allow_blank else ''}字符串")


def _integer(value, path, *, business=False):
    if type(value) is not int or (value == 0 if business else value <= 0):
        raise CustomException(message=f"{path} 必须为{'非零' if business else '正'}整数")


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _patches(values, allowed_fields, path):
    if not isinstance(values, list) or not values:
        raise CustomException(message=f"{path} 必须为非空数组")
    seen = set()
    for patch in values:
        _strict_object(patch, {"id", *allowed_fields}, path)
        _integer(patch.get("id"), f"{path}.id")
        if patch["id"] in seen:
            raise CustomException(message=f"{path} 存在重复 ID: {patch['id']}")
        seen.add(patch["id"])
        if len(patch) == 1:
            raise CustomException(message=f"{path} 必须包含至少一个可编辑字段")
    return values


def _validate_query_patch(patch):
    if "query_string" in patch:
        _text(patch["query_string"], "query_string")
    if "agg_dimension" in patch:
        dimensions = patch["agg_dimension"]
        if not isinstance(dimensions, list):
            raise CustomException(message="agg_dimension 必须为字符串数组")
        for dimension in dimensions:
            _text(dimension, "agg_dimension")
        if len(set(dimensions)) != len(dimensions):
            raise CustomException(message="agg_dimension 不能重复")
    if "agg_condition" in patch:
        conditions = patch["agg_condition"]
        if not isinstance(conditions, list):
            raise CustomException(message="agg_condition 必须为数组")
        for condition in conditions:
            _strict_object(condition, {"key", "method", "value", "condition"}, "agg_condition")
            _text(condition.get("key"), "agg_condition.key")
            _text(condition.get("method"), "agg_condition.method")
            if "condition" in condition and condition["condition"] not in ("and", "or"):
                raise CustomException(message="agg_condition.condition 仅支持 and/or")
            values = condition.get("value")
            if not isinstance(values, list) or not values:
                raise CustomException(message="agg_condition.value 必须为非空标量数组")
            for value in values:
                if not isinstance(value, str | bool) and not _finite_number(value):
                    raise CustomException(message="agg_condition.value 仅支持字符串、有限数值和布尔值")


def _validate_items(items):
    for item in _patches(items, {"expression", "query_configs", "algorithms"}, "items"):
        if "expression" in item:
            _text(item["expression"], "expression", allow_blank=True)
        if "query_configs" in item:
            for query in _patches(item["query_configs"], LEGACY_QUERY_FIELDS, "query_configs"):
                _validate_query_patch(query)
        if "algorithms" in item:
            _patches(item["algorithms"], {"config"}, "algorithms")


def authorize_strategy_business(params, action=ActionEnum.MANAGE_RULE):
    """Authenticate the request principal; the declared operator is never an identity."""
    tenant = _authorize_business(params["bk_biz_id"])
    request = get_request(peaceful=True)
    user = getattr(request, "user", None)
    if (
        not getattr(user, "is_authenticated", False)
        or not getattr(user, "username", None)
        or not getattr(user, "tenant_id", None)
    ):
        raise PermissionDenied("策略管理需要已认证的请求用户和租户")
    if params.get("bk_tenant_id", tenant) != tenant:
        raise PermissionDenied("策略业务与请求租户不一致")
    permission = Permission(username=user.username, bk_tenant_id=user.tenant_id)
    permission.skip_check = False
    if (
        permission.is_allowed(
            action,
            [ResourceEnum.BUSINESS.create_simple_instance(params["bk_biz_id"])],
        )
        is not True
    ):
        raise PermissionDenied("没有目标业务的策略管理权限")


def _target(objects, object_id, path):
    for obj in objects:
        if obj["id"] == object_id:
            return obj
    raise CustomException(message=f"{path} ID 不属于目标对象: {object_id}")


def _merge_items(config, patches):
    """Merge only existing objects, preserving their IDs, order and every unedited field."""
    for patch in patches:
        item = _target(config["items"], patch["id"], "items")
        if "expression" in patch:
            item["expression"] = patch["expression"]
        for query_patch in patch.get("query_configs", []):
            query = _target(item["query_configs"], query_patch["id"], "query_configs")
            _merge_query_config(query, query_patch)
        for algorithm_patch in patch.get("algorithms", []):
            algorithm = _target(item["algorithms"], algorithm_patch["id"], "algorithms")
            _merge_algorithm(algorithm, algorithm_patch)


def _query_serializer(query):
    source = query.get("data_source_label")
    data_type = query.get("data_type_label")
    _text(source, "data_source_label")
    _text(data_type, "data_type_label")
    serializer_class = QueryConfig.QueryConfigSerializerMapping.get((source, data_type))
    if serializer_class is None:
        raise CustomException(message=f"不支持的查询数据源类型: {source}/{data_type}")
    return serializer_class()


def _merge_query_config(current, patch):
    """Validate the submitted fields before projecting onto the target source schema."""
    identity = {key: patch.get(key, current.get(key)) for key in QUERY_IDENTITY_FIELDS}
    _text(identity["alias"], "query_configs.alias")
    serializer = _query_serializer(identity)
    _strict_object(patch, {"id", *QUERY_IDENTITY_FIELDS, *serializer.fields}, "query_configs")
    _check_serializer_fields(
        {key: value for key, value in patch.items() if key in serializer.fields}, serializer, "query_configs"
    )
    values = {key: deepcopy(current[key]) for key in serializer.fields if key in current}
    same_source = all(identity[key] == current.get(key) for key in ("data_source_label", "data_type_label"))
    for key, value in patch.items():
        if key not in serializer.fields:
            continue
        if same_source and isinstance(value, dict) and isinstance(values.get(key), dict):
            _merge_config_patch(values[key], value, ())
        else:
            values[key] = deepcopy(value)
    validated = serializer.run_validation(values)
    result = {"id": current["id"], **identity, **validated}
    if "metric_id" in current:
        result["metric_id"] = current["metric_id"]
    current.clear()
    current.update(result)


def _validate_algorithm_config(algorithm, config):
    algorithm_type = Algorithm.Serializer().fields["type"].run_validation(algorithm.get("type"))
    serializer_factory = Algorithm.Serializer.AlgorithmSerializers.get(algorithm_type)
    if serializer_factory:
        _check_serializer_fields(config, serializer_factory(), "algorithms.config")


def _validate_query_output_config(config):
    if config is None:
        return
    _strict_object(config, {"response_contract", "legacy_output_ref", "output_list"}, "query_output_config")
    if isinstance(config.get("output_list"), list):
        for output in config["output_list"]:
            _strict_object(output, {"reference_name", "expression"}, "query_output_config.output_list")
    Item.normalize_query_output_config(config)


def _merge_algorithm(current, patch):
    merged = deepcopy(current)
    if "config" in patch:
        _validate_algorithm_config({**current, **patch}, patch["config"])
    for field, value in patch.items():
        if field == "id":
            continue
        if field == "config" and patch.get("type", current["type"]) == current["type"]:
            if isinstance(value, dict) and isinstance(merged.get(field), dict):
                _merge_config_patch(merged[field], value, ())
                continue
        merged[field] = deepcopy(value)
    validated = Algorithm.Serializer().run_validation(merged)
    current.clear()
    current.update(validated)


def _check_serializer_fields(value, field, path):
    """Reject fields the platform serializer would silently discard."""
    if isinstance(field, serializers.ListSerializer | serializers.ListField) and isinstance(value, list):
        for entry in value:
            _check_serializer_fields(entry, field.child, path)
    elif isinstance(field, serializers.Serializer) and isinstance(value, dict):
        _strict_object(value, set(field.fields), path)
        for key, entry in value.items():
            _check_serializer_fields(entry, field.fields[key], f"{path}.{key}")


def _validate_config_patch(config):
    """Use the creation field scope; the platform validates the merged V2 values."""
    _strict_object(config, CREATE_CONFIG_FIELDS, "config")
    if not config:
        raise CustomException(message="config 不能为空")
    _check_serializer_fields(config, Strategy.Serializer(), "config")
    if "is_enabled" in config and type(config["is_enabled"]) is not bool:
        raise CustomException(message="config.is_enabled 必须为布尔值")
    if "name" in config:
        _text(config["name"], "config.name")
    if "items" in config:
        for item in _patches(config["items"], set(Item.Serializer().fields) - {"id"}, "config.items"):
            if "query_output_config" in item:
                _validate_query_output_config(item["query_output_config"])
            if "query_configs" in item:
                _patches(item["query_configs"], EDITABLE_FIELDS["query_configs"], "query_configs")
            if "algorithms" in item:
                _patches(item["algorithms"], set(Algorithm.Serializer().fields) - {"id"}, "algorithms")
    if "detects" in config:
        _patches(config["detects"], set(Detect.Serializer().fields) - {"id"}, "detects")
    if "notice" in config:
        _strict_object(config["notice"], set(NoticeRelation.Serializer().fields) - {"id", "config_id"}, "notice")
        if "user_groups" in config["notice"] and not config["notice"]["user_groups"]:
            raise CustomException(message="notice.user_groups 必须指定已有通知组")


def _merge_config_patch(current, patch, records=("items", "detects")):
    """Patch owned records by ID; merge dictionaries and replace ordinary arrays."""
    for field, value in patch.items():
        if field in records:
            for record in value:
                target = _target(current[field], record["id"], field)
                if field == "query_configs":
                    _merge_query_config(target, record)
                    continue
                if field == "algorithms":
                    _merge_algorithm(target, record)
                    continue
                nested = ("query_configs", "algorithms") if field == "items" else ()
                _merge_config_patch(target, {key: part for key, part in record.items() if key != "id"}, nested)
        elif field == "query_output_config":
            current[field] = deepcopy(value)
        elif isinstance(value, dict) and isinstance(current.get(field), dict):
            _merge_config_patch(current[field], value, ())
        else:
            current[field] = deepcopy(value)


def _validate_create_config(config):
    _strict_object(config, CREATE_CONFIG_FIELDS, "config")
    _text(config.get("name"), "config.name")
    if len(config["name"].strip()) > 128:
        raise CustomException(message="config.name 最长 128 字符")
    if type(config.get("is_enabled")) is not bool:
        raise CustomException(message="config.is_enabled 必须显式提供布尔值")
    _check_serializer_fields(config, Strategy.Serializer(), "config")
    items = config.get("items")
    if not isinstance(items, list) or not items:
        raise CustomException(message="config.items 必须为非空数组")
    for item in items:
        _strict_object(item, set(Item.Serializer().fields) - {"id"}, "config.items")
        if "query_output_config" in item:
            _validate_query_output_config(item["query_output_config"])
        queries = item.get("query_configs")
        if not isinstance(queries, list) or not queries:
            raise CustomException(message="query_configs 必须为非空数组")
        for query in queries:
            if not isinstance(query, dict):
                raise CustomException(message="query_configs 条目必须为对象")
            serializer = _query_serializer(query)
            _strict_object(query, {*serializer.fields, *QUERY_IDENTITY_FIELDS}, "query_configs")
            _text(query.get("alias"), "query_configs.alias")
            _check_serializer_fields(
                {key: value for key, value in query.items() if key in serializer.fields}, serializer, "query_configs"
            )
            serializer.run_validation(query)
        algorithms = item.get("algorithms")
        if not isinstance(algorithms, list):
            raise CustomException(message="algorithms 必须为数组")
        for algorithm in algorithms:
            _strict_object(algorithm, set(Algorithm.Serializer().fields) - {"id"}, "algorithms")
            _validate_algorithm_config(algorithm, algorithm.get("config"))
            Algorithm.Serializer().run_validation(algorithm)
    detects = config.get("detects")
    if not isinstance(detects, list) or not detects:
        raise CustomException(message="config.detects 必须为非空数组")
    for detect in detects:
        _strict_object(detect, set(Detect.Serializer().fields) - {"id"}, "detects")
    notice = config.get("notice")
    _strict_object(notice, set(NoticeRelation.Serializer().fields) - {"id", "config_id"}, "notice")
    if not notice.get("user_groups"):
        raise CustomException(message="notice.user_groups 必须指定已有通知组")


def manage_strategy_config(params: dict[str, Any]) -> dict[str, Any]:
    operation = params.get("operation")
    if operation not in ("create", "update"):
        raise CustomException(message="operation 仅支持 create/update")
    fields = CREATE_ALLOWED_FIELDS if operation == "create" else ALLOWED_FIELDS
    operator = validate_management_request(params, allowed_fields=fields, max_operator_length=32)
    _integer(params.get("bk_biz_id"), "bk_biz_id", business=True)
    if operation == "create":
        _validate_create_config(params.get("config"))
        authorize_strategy_business(params)
        creator = CreateAlarmStrategyResource()
        config = creator.validate_request_data(
            {**deepcopy(params["config"]), "bk_biz_id": params["bk_biz_id"], "confirm": True}
        )
        result = creator.perform_request(config, audit_operator=operator)
        return {
            "operation": "create",
            "bk_biz_id": params["bk_biz_id"],
            "strategy_id": result["id"],
            "name": result["name"],
            "requested_operator": operator,
            "result": result,
        }
    _integer(params.get("strategy_id"), "strategy_id")
    version = params.get("config_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{64}", version):
        raise CustomException(message="config_version 必须为读取详情时返回的 SHA-256 版本")
    if "items" not in params and "config" not in params:
        raise CustomException(message="update 必须提供 items 或 config")
    if "items" in params:
        _validate_items(params["items"])
    if "config" in params:
        _validate_config_patch(params["config"])
        if "items" in params and "items" in params["config"]:
            raise CustomException(message="items 与 config.items 不能同时提供")
    authorize_strategy_business(params)

    def prepare_config(config):
        if config.get("edit_allowed") is False:
            raise CustomException(message="该策略不允许编辑")
        if "config" in params:
            _merge_config_patch(config, params["config"])
        if "items" in params:
            _merge_items(config, params["items"])

    result = UpdateAlarmStrategyResource()._update_config(
        {"bk_biz_id": params["bk_biz_id"], "id": params["strategy_id"], "config_version": version},
        prepare_config=prepare_config,
        audit_operator=operator,
    )
    return {
        "operation": "update",
        "bk_biz_id": params["bk_biz_id"],
        "strategy_id": params["strategy_id"],
        "requested_operator": operator,
        "result": result,
    }


_PARAMS_SCHEMA = {
    "operation": "create | update",
    "bk_biz_id": "必填，非零业务或空间 ID",
    "strategy_id": "update 必填，单个策略 ID",
    "config_version": "update 必填，inspect-strategy-config detail 返回的原 SHA-256 版本",
    "items": "update 兼容原查询与算法配置补丁；与 config 至少提供一项，不得同时提供 config.items",
    "config": "create 为完整标准 V2 配置；update 为同范围字段补丁；查询按目标来源、算法按类型校验，子记录按已有 ID 修改；query_output_config 对象整体替换、null 清除，省略保留",
    "confirmed": "必须为 true，先取得对精确变更的人工确认",
    "operator": "审计执行人，最长 32 字符；无需已注册用户，不作为认证身份",
}
_EXAMPLE = {
    "operation": "update",
    "bk_biz_id": 2,
    "strategy_id": 1,
    "config_version": "0" * 64,
    "items": [{"id": 10, "expression": "0<a<30"}],
    "confirmed": False,
    "operator": "<actual-implementer>",
}
KernelRPCRegistry.register_function(
    func_name="bkm_cli.manage_strategy_config",
    summary="创建或修改标准策略配置，包括查询、算法、检测窗口、通知和启停",
    description="通过原策略保存 API 创建策略或修改已有子记录，按平台查询和算法类型校验；保存结果须独立回读，超时禁止自动重发。",
    handler=manage_strategy_config,
    params_schema=_PARAMS_SCHEMA,
    example_params=_EXAMPLE,
)
BkmCliOpRegistry.register(
    op_id="manage-strategy-config",
    func_name="bkm_cli.manage_strategy_config",
    summary="创建标准策略或修改单策略查询检测配置",
    description="create/update 对齐标准查询和算法范围，update 按原版本修改已有子记录，复用平台保存校验；结果未知禁止重发。",
    capability_level="admin",
    risk_level="mutation",
    requires_confirmation=True,
    audit_tags=["strategy", "admin", "mutation", "human-confirmation"],
    params_schema=_PARAMS_SCHEMA,
    example_params=_EXAMPLE,
)
