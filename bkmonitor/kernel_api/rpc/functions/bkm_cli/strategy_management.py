"""Single-strategy query and detection edits through the existing full-save API."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from rest_framework.exceptions import PermissionDenied

from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.strategy.new_strategy import QueryConfig
from bkmonitor.strategy.serializers import allowed_threshold_method
from bkmonitor.utils.request import get_request
from core.drf_resource.exceptions import CustomException
from kernel_api.resource.alert import UpdateAlarmStrategyResource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.management import validate_management_request
from kernel_api.rpc.functions.bkm_cli.platform_catalog.cmdb import _authorize_business

EDITABLE_FIELDS = {
    "items": ["expression"],
    "query_configs": ["query_string", "agg_dimension", "agg_condition"],
    "algorithms": {"type": "Threshold", "fields": ["config"]},
}
ALLOWED_FIELDS = {
    "operation",
    "bk_tenant_id",
    "bk_biz_id",
    "strategy_id",
    "config_version",
    "items",
    "confirmed",
    "operator",
}


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


def _validate_threshold(config):
    if not isinstance(config, list) or not config:
        raise CustomException(message="Threshold config 必须为非空二维数组")
    for group in config:
        if not isinstance(group, list) or not group:
            raise CustomException(message="Threshold config 条件组不能为空")
        for condition in group:
            _strict_object(condition, {"method", "threshold"}, "Threshold config")
            if not isinstance(condition.get("method"), str) or condition["method"] not in allowed_threshold_method:
                raise CustomException(message="不支持的 Threshold method")
            value = condition.get("threshold")
            if not _finite_number(value):
                raise CustomException(message="threshold 必须为有限数值")


def _validate_items(items):
    for item in _patches(items, {"expression", "query_configs", "algorithms"}, "items"):
        if "expression" in item:
            _text(item["expression"], "expression", allow_blank=True)
        if "query_configs" in item:
            for query in _patches(item["query_configs"], EDITABLE_FIELDS["query_configs"], "query_configs"):
                _validate_query_patch(query)
        if "algorithms" in item:
            for algorithm in _patches(item["algorithms"], {"config"}, "algorithms"):
                _validate_threshold(algorithm["config"])


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
            fields = QueryConfig.get_serializer_class(
                query["data_source_label"], query["data_type_label"]
            ).get_config_field_names()
            for field, value in query_patch.items():
                if field == "id":
                    continue
                if field not in fields:
                    raise CustomException(message=f"当前数据源不支持修改 {field}")
                query[field] = deepcopy(value)
        for algorithm_patch in patch.get("algorithms", []):
            algorithm = _target(item["algorithms"], algorithm_patch["id"], "algorithms")
            if algorithm["type"] != "Threshold":
                raise CustomException(message="仅支持修改已有 Threshold 算法配置")
            algorithm["config"] = deepcopy(algorithm_patch["config"])


def manage_strategy_config(params: dict[str, Any]) -> dict[str, Any]:
    operator = validate_management_request(params, allowed_fields=ALLOWED_FIELDS, max_operator_length=128)
    if params.get("operation") != "update":
        raise CustomException(message="operation 仅支持 update")
    _integer(params.get("bk_biz_id"), "bk_biz_id", business=True)
    _integer(params.get("strategy_id"), "strategy_id")
    version = params.get("config_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{64}", version):
        raise CustomException(message="config_version 必须为读取详情时返回的 SHA-256 版本")
    _validate_items(params.get("items"))
    authorize_strategy_business(params)

    def prepare_config(config):
        if config.get("edit_allowed") is False:
            raise CustomException(message="该策略不允许编辑")
        _merge_items(config, params["items"])

    result = UpdateAlarmStrategyResource()._update_config(
        {"bk_biz_id": params["bk_biz_id"], "id": params["strategy_id"], "config_version": version},
        prepare_config=prepare_config,
    )
    return {
        "operation": "update",
        "bk_biz_id": params["bk_biz_id"],
        "strategy_id": params["strategy_id"],
        "requested_operator": operator,
        "result": result,
    }


_PARAMS_SCHEMA = {
    "operation": "update",
    "bk_biz_id": "必填，非零业务或空间 ID",
    "strategy_id": "必填，单个策略 ID",
    "config_version": "必填，inspect-strategy-config detail 返回的原 SHA-256 版本",
    "items": "按已有 ID 匹配的补丁数组；仅 expression、query_configs 和 Threshold algorithms.config",
    "confirmed": "必须为 true，先取得对精确变更的人工确认",
    "operator": "实际执行人，最长 128 字符；不是认证身份",
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
    summary="修改单策略的查询检测配置",
    description="通过原策略保存 API 修改指定字段；保存结果须独立回读，超时禁止自动重发。",
    handler=manage_strategy_config,
    params_schema=_PARAMS_SCHEMA,
    example_params=_EXAMPLE,
)
BkmCliOpRegistry.register(
    op_id="manage-strategy-config",
    func_name="bkm_cli.manage_strategy_config",
    summary="修改单策略的查询检测配置",
    description="只支持已有对象的查询、表达式和静态阈值；先确认精确变更并提供原版本。",
    capability_level="admin",
    risk_level="mutation",
    requires_confirmation=True,
    audit_tags=["strategy", "admin", "mutation", "human-confirmation"],
    params_schema=_PARAMS_SCHEMA,
    example_params=_EXAMPLE,
)
