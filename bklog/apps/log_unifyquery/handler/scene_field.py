"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

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
    get_topk_list = UnifyQueryFieldHandler.get_topk_list
    get_value_list = UnifyQueryFieldHandler.get_value_list
    get_bucket_data = UnifyQueryFieldHandler.get_bucket_data
    get_agg_value_by_agg_method = staticmethod(UnifyQueryFieldHandler.get_agg_value_by_agg_method)
    get_field_value_list = staticmethod(UnifyQueryFieldHandler.get_field_value_list)
