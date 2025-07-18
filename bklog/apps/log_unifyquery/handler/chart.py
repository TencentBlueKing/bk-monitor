"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apps.api import UnifyQueryApi
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from opentelemetry import trace
from apps.utils.local import get_request_username


class UnifyQueryChartHandler(UnifyQueryHandler):
    def add_doris_query_trace(self, trace_id):
        """
        添加unifyquery查询的trace记录
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("unifyquery_doris_query") as span:
            span.set_attribute("trace_id", trace_id)
            span.set_attribute("user.username", get_request_username())
            span.set_attribute("db.system", "doris")

    def get_query_params(self, params):
        # 参数补充
        for q in self.base_dict["query_list"]:
            if sql := params.get("sql"):
                q["sql"] = sql
            if addition := params.get("addition"):
                q["addition"] = addition
        return self.base_dict

    def get_chart_data(self, params):
        search_params = self.get_query_params(params)
        trace_params = {"trace_id": None}
        try:
            data = UnifyQueryApi.query_ts_raw(search_params)
            trace_params.update({"trace_id": data["trace_id"]})
        finally:
            self.add_doris_query_trace(**trace_params)
        # TODO 处理路由，添加别名信息
        # query_alias_settings = params["alias_settings"]
        return data["list"]
