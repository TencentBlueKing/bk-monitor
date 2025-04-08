# -*- coding: utf-8 -*-
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

from apps.log_desensitize.handlers.desensitize import DesensitizeHandler
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnifyQueryAggHandler(UnifyQueryHandler):

    def search(self, *args, **kwargs):
        """
        agg_search
        仪表盘聚合查询
        """
        desensitize_configs = args
        params = copy.deepcopy(self.base_dict)
        method = self.search_params["method"]
        function = f"{method}_over_time"
        interval = self.search_params["interval"]
        group_by = self.search_params["group_by"]
        # 去重聚合 特殊处理
        if method == "cardinality":
            for q in params["query_list"]:
                q["function"] = [{"method": method, "dimensions": group_by, "window": interval}]
                q["time_aggregation"] = {}
        else:
            # value_count聚合 特殊处理
            if method == "value_count":
                method = "sum"
                function = "count_over_time"
            for q in params["query_list"]:
                q["function"] = [{"method": method, "dimensions": group_by}]
                q["time_aggregation"] = {"function": function, "window": interval}
        params["step"] = interval
        params["order_by"] = []
        # 避免ts接口周期对齐处理导致数据起始周期计算不准确问题
        response = self.query_ts_reference(params)

        # 聚合结果处理
        records = self._format_agg_series(response["series"], desensitize_configs)

        return records

    def _format_agg_series(self, series, desensitize_configs=None):
        records = []
        desensitize_configs = desensitize_configs or []
        desensitize_handler = DesensitizeHandler(desensitize_configs)
        for i in range(len(series)):
            datapoints = [[v[1], v[0]] for v in series[i]["values"] if v[1] != 0]
            dimensions = dict(zip(series[i]["group_keys"], series[i]["group_values"]))
            # 字段脱敏处理
            if desensitize_configs:
                dimensions = desensitize_handler.transform_dict(dimensions)
            target = f"{self.search_params['method']}({self.agg_field})"
            dimension_string = ", ".join("{}={}".format(k, v) for k, v in dimensions.items())
            if dimension_string:
                target += "{{{}}}".format(dimension_string)
            record = {"dimensions": dimensions, "target": target, "datapoints": datapoints}
            records.append(record)

        return records
