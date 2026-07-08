"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy

from apps.log_unifyquery.handler.scene_terms_aggs import SceneTermsAggsHandler

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 500
MAX_PAGE_SIZE = 1000
# 聚合取数上限，分页越界时返回空，避免大基数维度拖垮 unify-query
MAX_FETCH_SIZE = 10000


class SceneFieldCandidatesHandler(SceneTermsAggsHandler):
    """
    主机场景字段联想候选值检索（通过 unify-query ts/reference 聚合实时入库数据）。

    在 SceneTermsAggsHandler 的 terms 聚合基础上补三件事：
    - 目标维度自排除：conditions 中 key == resource_type 的项不参与过滤
      （多选取候选时忽略本维度已选值，对齐容器侧 list_resource_candidates 语义）
    - query_string 包含匹配：下推为目标字段的 contains 条件
    - 分页：对去重有序的候选值列表做内存分页，返回 {count, items}
    """

    def __init__(self, params: dict):
        params = copy.deepcopy(params)
        self.resource_type: str = params["resource_type"]
        self.page: int = max(int(params.get("page") or DEFAULT_PAGE), 1)
        self.page_size: int = min(int(params.get("page_size") or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
        self.candidate_query_string: str = (params.get("query_string") or "").strip()

        # 由 conditions 构造 addition（目标维度自排除 + query_string 包含匹配下推）
        params["addition"] = self._build_addition(params.get("conditions") or [])
        params["agg_field"] = self.resource_type
        # 候选值检索不接受全局 keyword，避免污染聚合范围
        params["keyword"] = params.get("keyword") or ""
        # 取足够多以支撑分页（上限保护）
        params["size"] = min(max(self.page * self.page_size, self.page_size), MAX_FETCH_SIZE)

        super().__init__(agg_fields=[self.resource_type], params=params)

    def _build_addition(self, conditions: list) -> list:
        addition = []
        for cond in conditions:
            key = cond.get("key") or cond.get("field")
            # 目标维度自身的已选条件不参与过滤
            if not key or key == self.resource_type:
                continue
            method = cond.get("method") or cond.get("operator") or "eq"
            value = cond.get("value", [])
            if not isinstance(value, list):
                value = [value] if value not in ("", None) else []
            # eq -> 精确多选(IN/OR)；include -> 包含匹配
            operator = "contains" if method == "include" else "="
            addition.append({"field": key, "operator": operator, "value": value})

        # query_string 包含匹配下推到目标字段
        if self.candidate_query_string:
            addition.append(
                {"field": self.resource_type, "operator": "contains", "value": [self.candidate_query_string]}
            )
        return addition

    def list_candidates(self) -> dict:
        result = self.terms()
        # aggs_items 已按 doc_count 降序去重
        items = result.get("aggs_items", {}).get(self.resource_type, [])
        count = len(items)
        start = (self.page - 1) * self.page_size
        end = start + self.page_size
        return {"count": count, "items": items[start:end]}
