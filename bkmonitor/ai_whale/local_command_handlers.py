"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from math import inf
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ai_agent.services.local_command_handler import (
    CommandHandler,
    local_command_handler,
)
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger("ai_agents")


# TODO:平台暂时不支持MCP，若需要对输入数据进行特殊处理，临时在业务逻辑中实现LocalCommandHandler,实现process_content和get_template方法
@local_command_handler("tracing_analysis")
class TracingAnalysisCommandHandler(CommandHandler):
    keys = ["status", "kind", "elapsed_time", "span_name", "span_id", "parent_span_id", "resource"]
    span_time_fields = ["start_time", "end_time", "elapsed_time"]
    acc_span_step = 10

    # 基于 128K 上下文长度设置
    max_character_length = 120_000
    max_span = 50

    @staticmethod
    def check_span_error(span: dict) -> bool:
        return span.get("status", {}).get("code") == 2

    @staticmethod
    def get_trace_total_time(trace: list[dict]) -> int:
        st, end = inf, 0
        for span in trace:
            st = min(st, span.get("start_time", 0))
            end = max(end, span.get("end_time", 0))
        if st != inf:
            return int(end) - int(st)
        logger.error("get_trace_total_time failed to get valid start_time")
        return end

    @staticmethod
    def us_to_ms(us) -> float:
        try:
            return int(us) / 1000
        except (TypeError, ValueError):
            return 0

    @classmethod
    def convert_timestamp_fields(cls, trace_data: list[dict]) -> list[dict]:
        for span in trace_data:
            for time_field in cls.span_time_fields:
                span[time_field] = f"{cls.us_to_ms(span.get(time_field, 0))}ms"
        return trace_data

    def process_trace_data(self, trace_data):
        #  获取 trace 总耗时, 在 保留必要字段 之前计算
        total_time = f"{self.us_to_ms(self.get_trace_total_time(trace_data))}ms"

        # 长的 trace 数据只保留必要字段
        if len(trace_data) > self.max_span:
            trace_data = [{k: x.get(k, None) for k in self.keys} for x in trace_data]

        # 收集 trace_data_lite 和 error_span_ids, 同时控制长度
        error_span_ids = []
        total_length = 0
        trace_data_lite_parts = []
        for span_idx in range(0, len(trace_data), self.acc_span_step):
            span_group = trace_data[span_idx : span_idx + self.acc_span_step]

            span_group = self.convert_timestamp_fields(span_group)
            json_part = json.dumps(span_group, ensure_ascii=False)
            trace_data_lite_parts.append(json_part)

            # 获取状态码 status.code 异常的 span_id
            error_span_ids_batch = [span.get("span_id") for span in span_group if self.check_span_error(span)]
            error_span_ids.extend(error_span_ids_batch)

            total_length += len(json_part)
            if total_length >= self.max_character_length:
                break

        trace_data_lite = "".join(trace_data_lite_parts)
        return {"trace_data": trace_data_lite, "total_time": total_time, "error_span_ids": error_span_ids}

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
        except (KeyError, BKAPIError) as e:
            raise ValueError(f"TracingAnalysisCommandHandler: fetch trace data failed, error: {e}") from e

        variables.update(self.process_trace_data(trace_data))

        logger.info("TracingAnalysisCommandHandler: all params are valid,will render template")
        return self.jinja_env.render(template, variables)

    def get_template(self):
        # jinja 模板会对一些字符转义, 这种转义我认为会对 llm 推理造成不好的影响:
        # 例如: `可能出错的 span_id: ['123']` 被转义为 `可能出错的 span_id: [&#39;123&#39;]`
        # 故添加 `variable | safe` 取消转义
        return """
        请帮我分析 Tracing:
        应用名称: {{ app_name }}
        trace 总耗时: {{ total_time }}
        可能出错的 span_id: {{ error_span_ids | safe }}
        Tracing 数据(JSON 格式): {{ trace_data | safe }}
        结果要求: 确保分析准确无误，无需冗余回答内容
        """


class QueryProfilingParameter(BaseModel):
    """
    ProfilingAnalysisCommandHandler 的数据模型
    NOTE: convert_json: 把前端的 json 字符串(如果是)转回字典
    """

    data_type: str
    service_name: str
    bk_biz_id: int
    app_name: str
    agg_method: str
    filter_labels: dict[str, str] = Field(default_factory=dict)

    # 前端传了, 但暂时没用的参数, 可能会干扰查出的 profiling 数据, 暂不开启
    # diff_filter_labels: dict

    start_time: int | None = Field(default=None, description="second unit")
    start: int | None = Field(default=None, description="microsecond unit")
    end_time: int | None = Field(default=None, description="second unit")
    end: int | None = Field(default=None, description="microsecond unit")

    @field_validator("filter_labels", mode="before")
    def validate_filter_labels_type(cls, v):
        if not isinstance(v, dict):
            return {}
        return v

    @model_validator(mode="before")
    @classmethod
    def convert_json(cls, data):
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError("invalid JSON string") from e
        return data

    @model_validator(mode="after")
    def check_time_fields(self) -> Self:
        has_seconds = self.start_time is not None and self.end_time is not None
        has_microseconds = self.start is not None and self.end is not None

        if not (has_seconds or has_microseconds):
            raise ValueError("start_time/end_time or start/end must be provided")

        if has_seconds and not has_microseconds:
            self.start = self.start_time * 1_000_000  # type: ignore
            self.end = self.end_time * 1_000_000  # type: ignore

        if self.start >= self.end:  # type: ignore
            raise ValueError("start must be less than end")

        return self


@local_command_handler("profiling_analysis")
class ProfilingAnalysisCommandHandler(CommandHandler):
    class Variables(BaseModel):
        query_params: QueryProfilingParameter

    def process_content(self, context: list[dict]) -> str:
        from apm_web.profile.diagrams.dotgraph import DOTDiagrammer
        from apm_web.profile.diagrams.tree_converter import TreeConverter
        from apm_web.profile.views import ProfileQueryViewSet

        template = self.get_template()

        # variables like: {'query_params': {'bk_biz_id': 0, ... } }
        variables = self.extract_context_vars(context)

        variables = self.Variables.model_validate(variables)
        variables = variables.query_params

        # 查询 profiling 数据并取得 TreeConvert 转换器类实例
        validate_data, essentials, extra_params = ProfileQueryViewSet.get_query_params(
            variables.model_dump(exclude={"start_time", "end_time"})
        )
        tree_converter = ProfileQueryViewSet.converter_query(essentials, validate_data, extra_params)

        # 判空
        if not (isinstance(tree_converter, TreeConverter) and getattr(tree_converter, "tree")):
            raise ValueError("[ProfilingAnalysisCommandHandler] tree_converter is not TreeConverter or is empty")

        dot_graph = DOTDiagrammer().draw(tree_converter)["dot_graph"]

        logger.info("ProfilingAnalysisCommandHandler: all params are valid,will render template")
        return self.jinja_env.render(
            template, {"profiling_data": dot_graph, "app_name": variables.app_name, "bk_biz_id": variables.bk_biz_id}
        )

    def get_template(self) -> str:
        return """
        应用名称: {{ app_name }}
        业务ID: {{ bk_biz_id }}
        请帮助我分析 Profiling 数据(DOT 描述): {{ profiling_data | safe }}
        结果要求: 确保分析准确无误，无需冗余回答内容
        """
