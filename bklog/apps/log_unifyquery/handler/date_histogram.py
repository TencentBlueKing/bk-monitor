"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy

from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.utils.thread import MultiExecuteFunc


class UnifyQueryDateHistogramHandler:
    def __init__(self, param):
        self.param = param
        self.index_set_ids = param.pop("index_set_ids", [])

        # 初始化索引集配置
        self.union_config_dict = self._init_union_config_dict(param.pop("union_configs", []))

    def union_search_date_histogram(self):
        # 多线程
        multi_execute_func = MultiExecuteFunc()

        for index_set_id in self.index_set_ids:
            param = copy.deepcopy(self.param)
            param["index_set_ids"] = [index_set_id]

            # 添加相对应索引集配置
            if self.union_config_dict:
                param["custom_indices"] = self.union_config_dict.get(index_set_id, {}).get("custom_indices", "")

            # 多线程
            multi_execute_func_params = {
                "param": param,
            }

            # 多线程请求 unify-query
            multi_execute_func.append(
                result_key=f"union_search_date_histogram_{index_set_id}",
                func=self.date_histogram_unify_query,
                params=multi_execute_func_params,
                multi_func_params=True,
            )

        multi_result = multi_execute_func.run()

        buckets_dict = dict()

        for index_set_id in self.index_set_ids:
            result = multi_result.get(f"union_search_date_histogram_{index_set_id}", {})

            aggs = result.get("aggs", {})
            group_by_histogram = aggs.get("group_by_histogram", {})
            buckets = group_by_histogram.get("buckets", [])

            for bucket in buckets:
                key = bucket.get("key")
                doc_count = bucket.get("doc_count")

                # 合并结果
                if not key:
                    continue
                if key not in buckets_dict:
                    buckets_dict[key] = bucket
                else:
                    buckets_dict[key]["doc_count"] += doc_count

        buckets = sorted(buckets_dict.values(), key=lambda x: x.get("key"), reverse=False)

        return {"aggs": {"group_by_histogram": {"buckets": buckets}}}

    @staticmethod
    def date_histogram_unify_query(param: dict) -> dict:
        """
        unify_query 查询 date_histogram
        """
        if param:
            return UnifyQueryHandler(param).date_histogram()

        return dict()

    @staticmethod
    def _init_union_config_dict(union_configs: list) -> dict:
        """
        初始化索引集配置
        """
        union_config_dict = dict()

        for config in union_configs:
            if not isinstance(config, dict):
                continue

            index_set_id = int(config.get("index_set_id"))
            custom_indices = config.get("custom_indices", "")

            if index_set_id:
                if index_set_id not in union_config_dict:
                    union_config_dict[index_set_id] = {}

                union_config_dict[index_set_id].update({"index_set_id": index_set_id, "custom_indices": custom_indices})

        return union_config_dict
