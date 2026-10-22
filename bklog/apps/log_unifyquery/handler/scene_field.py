"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy

from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler


class SceneFieldHandler(SceneUnifyQueryHandler):
    """
    Scene-based field analysis handler.
    Inherits SceneUnifyQueryHandler for table_id_conditions routing and reuses
    UnifyQueryFieldHandler's pure computation methods — they only depend on
    self.base_dict / self.result_merge_base_dict / self.search_params which
    SceneUnifyQueryHandler already provides.
    """

    handle_count_data = staticmethod(UnifyQueryFieldHandler.handle_count_data)
    get_total_count = UnifyQueryFieldHandler.get_total_count
    get_field_count = UnifyQueryFieldHandler.get_field_count
    get_bucket_count = UnifyQueryFieldHandler.get_bucket_count
    get_distinct_count = UnifyQueryFieldHandler.get_distinct_count
    get_topk_ts_data = UnifyQueryFieldHandler.get_topk_ts_data
    get_agg_value = UnifyQueryFieldHandler.get_agg_value
    get_topk_data = UnifyQueryFieldHandler.get_topk_data
    get_topk_list = UnifyQueryFieldHandler.get_topk_list
    get_value_list = UnifyQueryFieldHandler.get_value_list
    get_bucket_data = UnifyQueryFieldHandler.get_bucket_data
    get_agg_value_by_agg_method = staticmethod(UnifyQueryFieldHandler.get_agg_value_by_agg_method)
    get_field_value_list = staticmethod(UnifyQueryFieldHandler.get_field_value_list)

    def analyze_field(self, group_by: bool = True, order_by: str = "time", limit: int | None = None) -> dict:
        """适配 MCP 字段分析，Top K 复用页面已有的候选聚合口径。"""
        if group_by and order_by == "value" and limit is not None:
            return self.get_topk_data(limit)

        query_body = copy.deepcopy(self.result_merge_base_dict)
        for query in query_body["query_list"]:
            query["function"] = (
                [{"method": "count", "dimensions": [self.search_params["agg_field"]]}]
                if group_by
                else [{"method": "count"}]
            )
            if limit is not None:
                query["limit"] = limit
        query_body["order_by"] = (
            ["-_value"] if order_by == "value" else ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"]
        )
        result = self.query_ts_reference(query_body)
        if group_by and limit is not None:
            result["series"] = (result.get("series") or [])[:limit]
        return result
