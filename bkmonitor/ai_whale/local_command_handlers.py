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
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ai_agent.services.local_command_handler import (
    CommandHandler,
    local_command_handler,
)
from ai_whale.utils import get_nested_value
from apm_web.profile.diagrams.dotgraph import DOTDiagrammer
from apm_web.profile.diagrams.tree_converter import TreeConverter
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger("ai_agents")

USER_GUIDE_MSG = "当前页面发起不正确, 礼貌并捎带歉意提示用户前往 '{0}' 使用该功能"


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
        try:
            resp = api.apm_api.query_trace_detail(
                {
                    "bk_biz_id": variables["bk_biz_id"],
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
        if not variables.get("app_name") or not variables.get("bk_biz_id"):
            logger.info("TracingAnalysisCommandHandler: app_name or bk_biz_id is empty,will remind user")
            return """
            当前发起页面不正确,请礼貌并稍带歉意的提示用户前往数据探索->Tracing检索->Trace详情页面使用该功能
            """

        logger.info("TracingAnalysisCommandHandler: all params are valid,will render template")
        return self.jinja_env.render(template, variables)

    def get_template(self):
        return """
        请帮助我分析Tracing数据: {{ trace_data }}.
        应用名称: {{ app_name }}
        业务ID: {{ bk_biz_id }}
        结果要求: 确保分析准确无误，无需冗余回答内容
        如果缺少任意参数,请告知用户前往数据探索->Tracing检索->Trace详情页面使用该功能
        切记不要告诉用户缺少了参数，你需要礼貌的提示用户前往对应页面使用该功能
        """


@local_command_handler("profiling_analysis")
class ProfilingAnalysisCommandHandler(CommandHandler):
    class QueryProfilingParameter(BaseModel):
        data_type: str
        service_name: str
        bk_biz_id: int
        app_name: str
        agg_method: str
        filter_labels: dict[str, str] = Field(default_factory=dict)

        start_time: int | None = Field(default=None, description="second unit")
        start: int | None = Field(default=None, description="microsecond unit")
        end_time: int | None = Field(default=None, description="second unit")
        end: int | None = Field(default=None, description="microsecond unit")

        @field_validator("filter_labels", mode="before")
        def default_on_error(cls, v):
            if not isinstance(v, dict):
                return {}
            return v

        @model_validator(mode="after")
        def check_time_fields(self) -> Self:
            has_seconds = self.start_time and self.end_time
            has_microseconds = self.start and self.end

            if not (has_seconds or has_microseconds):
                raise ValueError("start_time/end_time or start/end must be provided")

            if has_seconds and not has_microseconds:
                self.start = self.start_time * 1_000_000
                self.end = self.end_time * 1_000_000

            if self.start >= self.end:  # type: ignore
                raise ValueError("start must be less than end")

            return self

    def process_content(self, context: list[dict]) -> str:
        from apm_web.profile.views import ProfileQueryViewSet

        template = self.get_template()
        variables = self.extract_context_vars(context)

        try:
            variables = self.QueryProfilingParameter.model_validate(variables)
        except ValueError as e:
            logger.info(f"ProfilingAnalysisCommandHandler: invalid params {e},will remind user")
            return USER_GUIDE_MSG.format("数据探索->Profiling检索->Profiling详情页面")

        # 查询 profiling 数据并取得 TreeConvert 转换器类实例
        validate_data, essentials, extra_params = ProfileQueryViewSet.get_query_params(
            variables.model_dump(exclude={"start_time", "end_time"})
        )
        tree_converter = ProfileQueryViewSet.converter_query(essentials, validate_data, extra_params)

        # 判空
        if not (isinstance(tree_converter, TreeConverter) and getattr(tree_converter, "tree")):
            logger.info("ProfilingAnalysisCommandHandler: tree_converter.tree is empty,will remind user")
            return USER_GUIDE_MSG.format("数据探索->Profiling检索->Profiling详情页面")

        dot_graph = DOTDiagrammer().draw(tree_converter)["dot_graph"]

        logger.info("ProfilingAnalysisCommandHandler: all params are valid,will render template")
        return self.jinja_env.render(
            template, {"profiling_data": dot_graph, "app_name": variables.app_name, "bk_biz_id": variables.bk_biz_id}
        )

    def get_template(self) -> str:
        return """
        请帮助我分析 Profiling 数据(DOT 描述): {{ profiling_data }}.
        应用名称: {{ app_name }}
        业务ID: {{ bk_biz_id }}
        结果要求: 确保分析准确无误，无需冗余回答内容
        """
