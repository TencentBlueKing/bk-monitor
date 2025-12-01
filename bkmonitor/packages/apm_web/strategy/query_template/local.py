"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property
from typing import Any

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.query_template.constants import VariableType, Namespace
from constants.apm import CachedEnum
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.query_template import GLOBAL_BIZ_ID
from bkmonitor.query_template.builtin import utils
from bkmonitor.query_template.builtin import QueryTemplateSet

from django.utils.translation import gettext_lazy as _


def _qs_to_query_params(qs: UnifyQuerySet) -> dict[str, Any]:
    return utils.format_query_params(qs.config)


class LocalQueryTemplateName(CachedEnum):
    RPC_PANIC_LOG = "apm_rpc_panic_log"
    TRACE_SPAN_TOTAL = "apm_trace_span_total"
    LOG_TOTAL = "apm_log_total"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.RPC_PANIC_LOG: _("服务 Panic 日志数"),
                self.TRACE_SPAN_TOTAL: _("调用链 Span 数"),
                self.LOG_TOTAL: _("日志数"),
            }.get(self, self.value)
        )


RPC_PANIC_LOG_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.RPC_PANIC_LOG.value,
    "alias": LocalQueryTemplateName.RPC_PANIC_LOG.label,
    "description": str(_("服务 Panic 日志是指当前服务在运行过程中发生的 Panic 所记录的堆栈日志。")),
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_LOG_SEARCH))
            .table("${INDEX_SET_ID}")
            .index_set_id("${INDEX_SET_ID}")
            .interval(60)
            .group_by("resource.server", "resource.env", "resource.instance")
            .metric(field="_index", method="COUNT", alias="a")
            .conditions([{"key": "resource.server", "method": "eq", "value": ["${SERVICE_NAME}"], "condition": "and"}])
            .query_string("${QUERY_STRING}")
        )
        .expression("a")
    ),
    "variables": [
        {
            "name": "INDEX_SET_ID",
            "alias": str(_("日志索引集 ID")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("日志索引集 ID")),
        },
        {
            "name": "SERVICE_NAME",
            "alias": str(_("服务名称")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("服务名")),
        },
        {
            "name": "QUERY_STRING",
            "alias": str(_("日志关键字")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "\\\\[PANIC\\\\]"},
            "description": str(_("用于检索 Panic 的日志关键字。")),
        },
    ],
}

TRACE_SPAN_TOTAL_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.TRACE_SPAN_TOTAL.value,
    "alias": LocalQueryTemplateName.TRACE_SPAN_TOTAL.label,
    "description": str(_("调用链 Span 数是指在指定时间范围内所上报的 Span 总数。")),
    "table": "",
    "query_configs": [
        {
            "table": "",
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": "a",
            "interval": 60,
            "promql": "sum(count_over_time(bklog:bklog_index_set_${INDEX_SET_ID}:"
            '_index{resource__bk_46__service__bk_46__name="${SERVICE_NAME}"}[1m])) or vector(0)',
        }
    ],
    "variables": [
        {
            "name": "INDEX_SET_ID",
            "alias": str(_("日志索引集 ID")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("日志索引集 ID")),
        },
        {
            "name": "SERVICE_NAME",
            "alias": str(_("服务名称")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("服务名")),
        },
    ],
}

LOG_TOTAL_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.LOG_TOTAL.value,
    "alias": LocalQueryTemplateName.LOG_TOTAL.label,
    "description": str(_("日志数是指在指定时间范围内所上报的日志总数。")),
    "query_configs": [
        {
            "table": "",
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": "a",
            "interval": 60,
            # 为什么用 PromQL？
            # 目前日志数据源不支持 or vector(0) 的补 0 写法，暂时通过 PromQL 直接复用 UnifyQuery 的能力。
            # 等后续 SaaS 数据源统一切换到 UnifyQuery 时，改回结构体。
            "promql": "sum(count_over_time(bklog:bklog_index_set_${INDEX_SET_ID}:"
            '_index{resource__bk_46__service__bk_46__name="${SERVICE_NAME}"}[1m])) or vector(0)',
        }
    ],
    "variables": [
        {
            "name": "INDEX_SET_ID",
            "alias": str(_("日志索引集 ID")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("日志索引集 ID")),
        },
        {
            "name": "SERVICE_NAME",
            "alias": str(_("服务名称")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("服务名")),
        },
    ],
}


class LocalQueryTemplateSet(QueryTemplateSet):
    NAMESPACE: str = Namespace.DEFAULT

    QUERY_TEMPLATES = [
        RPC_PANIC_LOG_QUERY_TEMPLATE,
        TRACE_SPAN_TOTAL_QUERY_TEMPLATE,
        LOG_TOTAL_QUERY_TEMPLATE,
    ]
