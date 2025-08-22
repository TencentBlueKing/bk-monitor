"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from ai_agent.services.local_command_handler import local_command_handler, CommandHandler
from bkmonitor.utils.request import get_request
from core.drf_resource import api
from core.errors.api import BKAPIError
from ai_whale.utils import get_nested_value

logger = logging.getLogger("ai_agents")


# TODO:平台暂时不支持MCP，若需要对输入数据进行特殊处理，临时在业务逻辑中实现LocalCommandHandler,实现process_content和get_template方法
@local_command_handler("tracing_analysis")
class TracingAnalysisCommandHandler(CommandHandler):
    keys = ["status", "kind", "elapsed_time", "start_time", "span_name"]

    # 基于 128K 上下文长度设置
    max_character_length = 120_000
    max_span = 50

    def process_content(self, context: list[dict]) -> str:
        template = self.get_template()
        variables = self.extract_context_vars(context)

        req = get_request()
        if not req:
            raise ValueError("TracingAnalysisCommandHandler requires 'local request'")

        try:
            biz_id = req.session["bk_biz_id"]
            resp = api.apm_api.query_trace_detail(
                {
                    "bk_biz_id": biz_id,
                    "app_name": variables["app_name"],
                    "trace_id": variables["trace_id"],
                }
            )
            trace_data = resp["trace_data"]

            processed_trace_data = trace_data
            if len(trace_data) > self.max_span:
                processed_trace_data = [{k: get_nested_value(x, k) for k in self.keys} for x in trace_data]
        except (BKAPIError, KeyError) as e:
            raise ValueError("TracingAnalysis failed to query trace data") from e

        trace_data_lite = str(processed_trace_data)[: self.max_character_length]

        variables["trace_data"] = trace_data_lite

        return self.jinja_env.render(template, variables)

    def get_template(self):
        return """
        请帮助我分析Tracing数据: {{ trace_data }}.
        应用名称: {{ app_name }}
        结果要求: 确保分析准确无误，无需冗余回答内容
        """
