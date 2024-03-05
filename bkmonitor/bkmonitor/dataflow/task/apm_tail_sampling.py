# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

from django.conf import settings
from django.utils.translation import ugettext as _

from bkmonitor.dataflow.node.processor import (
    FlinkStreamCodeDefine,
    FlinkStreamCodeOutputField,
    FlinkStreamNode,
    RealTimeNode,
)
from bkmonitor.dataflow.node.source import StreamSourceNode
from bkmonitor.dataflow.node.storage import ElasticsearchStorageNode
from bkmonitor.dataflow.task.base import BaseTask


class EmptyRealTimeNode(RealTimeNode):
    def __init__(self, from_result_table_id, bk_biz_id, app_name, parent):
        self.from_result_table_id = from_result_table_id
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.parent_list = [parent]
        self.node_id = None

    @property
    def config(self):
        return {
            "bk_biz_id": self.bk_biz_id,
            "sql": self._sql,
            "table_name": self.table_name,
            "name": self.name,
            "window_type": "none",
            "output_name": self.table_name,
            "from_result_table_ids": [self.from_result_table_id],
        }

    @property
    def name(self):
        return _("[临时]空计算节点")

    @property
    def table_name(self):
        return f"tail_{self.app_name}_output"

    @property
    def _sql(self):
        return f"SELECT span_id, trace_id, span_info, datetime FROM {self.from_result_table_id}"


class TailSamplingFlinkNode(FlinkStreamNode):
    PROJECT_PREFIX = "bkapm"

    # 会话过期时间
    _TRACE_GAP_MIN = 30
    # 标记状态最大存活时间
    _TRACE_TIMEOUT_MIN = 1440
    # 分析trace中span最大数量
    _MAX_SPAN_COUNT = 10000
    # 采样百分比
    _SAMPLING_RATIO = 100

    def __init__(
        self,
        source_rt_id,
        flink_code,
        conditions=None,
        trace_gap_min=None,
        trace_timeout_min=None,
        max_span_count=None,
        sampling_ratio=None,
        *args,
        **kwargs,
    ):
        super(TailSamplingFlinkNode, self).__init__(source_rt_id, *args, **kwargs)
        self.flink_code = flink_code
        self.conditions = conditions or []
        self.trace_gap_min = self._TRACE_GAP_MIN if trace_gap_min is None else trace_gap_min
        self.trace_timeout_min = self._TRACE_TIMEOUT_MIN if trace_timeout_min is None else trace_timeout_min
        self.max_span_count = self._MAX_SPAN_COUNT if max_span_count is None else max_span_count
        self.sampling_ratio = self._SAMPLING_RATIO if sampling_ratio is None else sampling_ratio

    @property
    def args(self):
        return {
            "input_table_id": self.source_rt_id,
            "output_table_id": self.result_table_id,
            "trace_session_gap_min": self.trace_gap_min,
            "trace_mark_timeout_min": self.trace_timeout_min,
            "sampling_conditions": self.conditions,
            "max_span_count": self.max_span_count,
            "random_sampling_ratio": self.sampling_ratio,
        }

    @property
    def output_fields(self):
        return [
            FlinkStreamCodeOutputField(
                field_name="time",
                field_alias="time",
            ),
            FlinkStreamCodeOutputField(
                field_name="span_name",
                field_alias="span_name",
            ),
            FlinkStreamCodeOutputField(
                field_name="span_id",
                field_alias="span_id",
            ),
            FlinkStreamCodeOutputField(
                field_name="kind",
                field_alias="kind",
                field_type="int",
            ),
            FlinkStreamCodeOutputField(
                field_name="events",
                field_alias="events",
            ),
            FlinkStreamCodeOutputField(
                field_name="parent_span_id",
                field_alias="parent_span_id",
            ),
            FlinkStreamCodeOutputField(
                field_name="end_time",
                field_alias="end_time",
                field_type="long",
            ),
            FlinkStreamCodeOutputField(
                field_name="links",
                field_alias="links",
            ),
            FlinkStreamCodeOutputField(
                field_name="trace_id",
                field_alias="trace_id",
            ),
            FlinkStreamCodeOutputField(
                field_name="elapsed_time",
                field_alias="elapsed_time",
                field_type="long",
            ),
            FlinkStreamCodeOutputField(
                field_name="status",
                field_alias="status",
            ),
            FlinkStreamCodeOutputField(
                field_name="attributes",
                field_alias="attributes",
            ),
            FlinkStreamCodeOutputField(
                field_name="start_time",
                field_alias="start_time",
                field_type="long",
            ),
            FlinkStreamCodeOutputField(
                field_name="trace_state",
                field_alias="trace_state",
            ),
            FlinkStreamCodeOutputField(
                field_name="resource",
                field_alias="resource",
            ),
            FlinkStreamCodeOutputField(field_name="datatime", field_alias="datatime", field_type="long"),
        ]

    @property
    def _code(self):
        return self.flink_code

    @property
    def code(self) -> FlinkStreamCodeDefine:
        return FlinkStreamCodeDefine(
            language="java",
            args=json.dumps(self.args),
            code=self._code.strip(),
            output_fields=self.output_fields,
        )


class APMTailSamplingTask(BaseTask):
    def __init__(self, cleans_result_table_id, bk_biz_id, app_name, config, es_extra_data, flink_code):
        super(APMTailSamplingTask, self).__init__()
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.rt_id = cleans_result_table_id
        self.config = config
        self.es_extra_data = es_extra_data
        self.flink_code = flink_code

        stream_source_node = StreamSourceNode(self.rt_id)

        node_list = [stream_source_node]

        if settings.APM_APP_BKDATA_REQUIRED_TEMP_CONVERT_NODE:
            # Notice: bkbase 对于所有环境还没有全部覆盖 pulsar 作为消息队列 对于没有 pulsar 的环境需要新增一个中转节点 待之后去除
            empty_node = EmptyRealTimeNode(
                from_result_table_id=stream_source_node.output_table_name,
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                parent=stream_source_node,
            )
            flink_node = TailSamplingFlinkNode(
                source_rt_id=empty_node.output_table_name,
                flink_code=self.flink_code,
                conditions=self.config.get("tail_conditions"),
                trace_gap_min=self.config.get("tail_trace_session_gap_min"),
                trace_timeout_min=self.config.get("tail_trace_mark_timeout"),
                sampling_ratio=self.config.get("tail_percentage"),
                name="tail_sampling",
                parent=empty_node,
            )
            node_list.extend([empty_node, flink_node])
        else:
            flink_node = TailSamplingFlinkNode(
                source_rt_id=stream_source_node.output_table_name,
                flink_code=self.flink_code,
                conditions=self.config.get("tail_conditions"),
                trace_gap_min=self.config.get("tail_trace_session_gap_min"),
                trace_timeout_min=self.config.get("tail_trace_mark_timeout"),
                sampling_ratio=self.config.get("tail_percentage"),
                name="tail_sampling",
                parent=stream_source_node,
            )
            node_list.append(flink_node)

        es_storage_node = ElasticsearchStorageNode(
            cluster=self.es_extra_data["cluster_name"],
            storage_keys=["trace_id", "span_id"],
            analyzed_fields=[],
            doc_values_fields=["dtEventTimeStamp", "timestamp"],
            json_fields=["status", "events", "links", "attributes", "resource"],
            storage_expires=self.es_extra_data['retention'],
            source_rt_id=flink_node.result_table_id,
            has_unique_key=True,
            physical_table_name=self.es_extra_data["table_name"],
            parent=flink_node,
        )

        node_list.append(es_storage_node)
        self.node_list = node_list

    @property
    def flow_name(self):
        return f"bkapm_tail_sampling_{self.bk_biz_id}_{self.app_name}"
