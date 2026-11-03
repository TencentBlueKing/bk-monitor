"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

from apps.api import BcsApi
from apps.exceptions import ApiError
from apps.log_databus.constants import K8S_SCENE_FIELD_TO_MONITOR_RESOURCE_TYPE
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc

_BCS_GET_CLUSTER = BcsApi.get_cluster_by_cluster_id


class AllConditionsBuilder:
    """
    Validate and pass through table_id_conditions in the AllConditions format
    ([][]ConditionField) for unify-query scene-based routing.

    - Inner list: AND group (all conditions must match)
    - Outer list: OR  groups (any group match is sufficient)

    Frontend is responsible for building the conditions structure;
    this class only validates the raw input.
    """

    VALID_OPS = {"eq", "ne", "req", "nreq"}

    @classmethod
    def from_raw(cls, conditions: list[list[dict]]) -> list[list[dict]]:
        """Validate and pass through raw AllConditions provided by the caller."""
        for and_group in conditions:
            for cond in and_group:
                if cond.get("op", "eq") not in cls.VALID_OPS:
                    raise ValueError(f"Invalid op: {cond['op']}")
                if "field_name" not in cond or "value" not in cond:
                    raise ValueError(f"Missing field_name or value in condition: {cond}")
        return conditions


def _get_monitor_k8s_resource_type(resource_type: str) -> str:
    return K8S_SCENE_FIELD_TO_MONITOR_RESOURCE_TYPE.get(resource_type, resource_type)


def _build_monitor_k8s_conditions(conditions: list) -> list:
    mapped_conditions = []
    for condition in conditions:
        mapped_condition = condition.copy()
        mapped_condition["key"] = _get_monitor_k8s_resource_type(mapped_condition.get("key", ""))
        mapped_conditions.append(mapped_condition)
    return mapped_conditions


def get_field_candidates(data: dict) -> dict:
    """
    IaaS 化字段联想候选值统一入口，按 scene 分流：
    - 容器场景（k8s）：转调监控 k8s_resource 候选值缓存接口
    - 主机场景（host/其他）：通过 unify-query ts/reference 聚合实时入库数据

    统一返回 {"count": int, "items": list[str]}。
    """
    from apps.api import MonitorApi
    from apps.log_search.constants import SceneLabelEnum
    from apps.log_unifyquery.handler.scene_field_candidates import (
        SceneFieldCandidatesHandler,
    )

    if data.get("scene") == SceneLabelEnum.K8S.value:
        # 容器场景：适配 bklog 字段 key 后转调监控侧候选值缓存接口（返回已是 {count, items}）
        result = MonitorApi.list_resource_candidates(
            {
                "bk_biz_id": data["bk_biz_id"],
                "bcs_cluster_ids": data.get("bcs_cluster_ids") or [],
                "resource_type": _get_monitor_k8s_resource_type(data["resource_type"]),
                "conditions": _build_monitor_k8s_conditions(data.get("conditions") or []),
                "query_string": data.get("query_string") or "",
                "page": data.get("page") or 1,
                "page_size": data.get("page_size") or 500,
            }
        )
        return result or {"count": 0, "items": []}

    # 主机场景：实时入库数据聚合
    return SceneFieldCandidatesHandler(data).list_candidates()


def resolve_bcs_cluster_names(cluster_ids):
    """并发查询 BCS 集群名称，返回 {cluster_id: cluster_name} 映射。

    复用 BcsApi.get_cluster_by_cluster_id 按 cluster_id 精确查询（自带 5 分钟缓存），
    不依赖业务 ID，关联 BCS 空间的集群也能查到名称。
    单个查询失败降级（该 id 不进入映射，由 build_dimension_options 回退为 id），不中断其他集群。
    """
    def _query_one(cid):
        """查询单个集群名称，失败降级为 cid 本身。

        ApiError（BCS 外部调用失败）为预期降级场景，记 warning 后返回 cid；
        其他异常（编程错误）非预期，记 exception 堆栈便于排查后重新抛出，
        由 MultiExecuteFunc 兜底降级，避免中断其他集群的并发查询。
        """
        try:
            info = _BCS_GET_CLUSTER({"cluster_id": cid.upper()}, timeout=5)
            return info.get("clusterName") or cid
        except ApiError:
            logger.warning("resolve bcs cluster name failed, cluster_id: %s", cid)
            return cid
        except Exception:  # pylint: disable=broad-except
            logger.exception("unexpected error resolving cluster name, cluster_id: %s", cid)
            raise

    multi = MultiExecuteFunc()
    for cid in cluster_ids:
        multi.append(cid, _query_one, params=cid)
    multi.run(return_exception=True)

    # 只把查到名称的（非 Exception、非 cid 本身）放进映射，回退逻辑交给 build_dimension_options
    names = {}
    for cid, res in multi.results.items():
        if isinstance(res, Exception):
            continue
        if res != cid:
            names[cid] = res
    return names


# 按 (scene, dimension_key) 注册名称解析器（直接函数引用，拼错会在导入期 NameError 暴露）；
# 未注册的维度 name 默认等于 id，回退成 id 的逻辑统一在 build_dimension_options 一处做。
DIMENSION_NAME_RESOLVERS = {
    ("k8s", "cluster_id"): resolve_bcs_cluster_names,
}


def build_dimension_options(scene, dimension_key, values):
    """构建维度选项列表 [{id, name}]，name 默认等于 id，命中 resolver 的维度补充名称。

    :param scene: 场景标识（如 k8s / host）
    :param dimension_key: 维度 key（如 cluster_id / stream）
    :param values: 维度值列表（原始字符串）
    :return: [{id, name}] 列表，顺序与 values 一致
    """
    resolver = DIMENSION_NAME_RESOLVERS.get((scene, dimension_key))
    names = resolver(values) if resolver else {}
    return [{"id": v, "name": names.get(v) or v} for v in values]
