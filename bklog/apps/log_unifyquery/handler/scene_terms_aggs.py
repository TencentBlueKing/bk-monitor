"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy

from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.log_unifyquery.handler.terms_aggs import UnifyQueryTermsAggsHandler


class SceneTermsAggsHandler(SceneUnifyQueryHandler):
    """
    Scene-based multi-field terms aggregation handler.
    Mirrors UnifyQueryTermsAggsHandler but routes via table_id_conditions
    instead of index_set_ids.
    """

    def __init__(self, agg_fields: list, params: dict):
        self.agg_fields = agg_fields
        super().__init__(params)

    def _init_scene_base_dict(self) -> dict:
        base = super()._init_scene_base_dict()
        if self.agg_fields:
            for query in base.get("query_list", []):
                query["field_name"] = self.agg_fields[0]
        return base

    def init_result_merge_base_dict(self, base_dict):
        result_merge_base_dict = super().init_result_merge_base_dict(base_dict)
        terms_result_merge_base_dict = copy.deepcopy(result_merge_base_dict)
        query_list = copy.deepcopy(terms_result_merge_base_dict.get("query_list"))
        reference_name_list = ["a"]

        for index, agg_field in enumerate(self.agg_fields[1:]):
            reference_name = self.generate_reference_name(index + 1)
            reference_name_list.append(reference_name)

            for query in query_list:
                new_query = copy.deepcopy(query)
                new_query["reference_name"] = reference_name
                new_query["field_name"] = agg_field
                terms_result_merge_base_dict["query_list"].append(new_query)

        terms_result_merge_base_dict["metric_merge"] = " or ".join(reference_name_list)
        return terms_result_merge_base_dict

    terms = UnifyQueryTermsAggsHandler.terms
    obtain_agg = staticmethod(UnifyQueryTermsAggsHandler.obtain_agg)
    obtain_agg_items = staticmethod(UnifyQueryTermsAggsHandler.obtain_agg_items)
    _terms_unify_query = UnifyQueryTermsAggsHandler._terms_unify_query
