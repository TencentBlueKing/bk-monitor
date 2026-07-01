"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""


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
        # 容器场景：透传监控侧候选值缓存接口（返回已是 {count, items}）
        result = MonitorApi.list_resource_candidates(
            {
                "bk_biz_id": data["bk_biz_id"],
                "bcs_cluster_ids": data.get("bcs_cluster_ids") or [],
                "resource_type": data["resource_type"],
                "conditions": data.get("conditions") or [],
                "query_string": data.get("query_string") or "",
                "page": data.get("page") or 1,
                "page_size": data.get("page_size") or 500,
            }
        )
        return result or {"count": 0, "items": []}

    # 主机场景：实时入库数据聚合
    return SceneFieldCandidatesHandler(data).list_candidates()
