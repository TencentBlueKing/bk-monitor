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
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urljoin

from django.conf import settings

from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionInstance
from bkmonitor.utils import time_tools
from bkmonitor.utils.alert_drilling import merge_dimensions_into_conditions
from constants.apm import ApmAlertHelper
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource

"""
提供告警详情页面跳转
"""


@dataclass
class AlertRedirectInfo:
    """告警重定向所需信息数据类"""

    alert: AlertDocument
    origin_dimensions: dict
    query_config: dict
    dimension_fields: list
    duration: int


def _get_alert_redirect_info(action_id: str) -> AlertRedirectInfo | None:
    """获取告警重定向信息数据"""
    action_instance_doc: ActionInstanceDocument = ActionInstanceDocument.get(action_id)
    if action_instance_doc:
        alert_ids: list[str] = action_instance_doc.alert_id
    else:
        try:
            db_action_instance: ActionInstance = ActionInstance.objects.get(id=str(action_id)[10:])
        except ActionInstance.DoesNotExist:
            return None
        alert_ids: list[str] = db_action_instance.alerts

    if not alert_ids:
        return None

    # 根据告警 ID 获取告警文档对象
    alert: AlertDocument = AlertDocument.get(alert_ids[0])
    if not alert.strategy:
        return None

    # 获取告警策略数据查询配置
    try:
        query_config: dict[str, Any] = alert.strategy["items"][0]["query_configs"][0]
    except (KeyError, IndexError, TypeError):
        return None

    alert_data: dict[str, Any] = alert.origin_alarm.get("data", {})
    # 获取原始维度信息
    origin_dimensions: dict[str, str | None] = alert_data.get("dimensions", {})
    # 获取告警策略配置的维度字段
    dimension_fields: list[str] = alert_data.get("dimension_fields", [])

    # 获取持续时间
    duration: int = alert.duration or 60

    return AlertRedirectInfo(
        alert=alert,
        query_config=query_config,
        origin_dimensions=origin_dimensions,
        dimension_fields=dimension_fields,
        duration=duration,
    )


def generate_data_retrieval_url(bk_biz_id, collect_id):
    # 生成基于告警维度的数据检索url
    action = ActionInstanceDocument.get(collect_id)
    if action:
        alert_ids = action.alert_id
    else:
        alert_ids = ActionInstance.objects.get(id=str(collect_id)[10:]).alerts

    # 如果有告警ID，跳转到数据检索页
    if alert_ids:
        params = resource.alert.get_alert_data_retrieval(alert_id=alert_ids[0])
        if params:
            if params["type"] == "metric":
                params_str = urlencode({"targets": json.dumps(params["params"], ensure_ascii=False)})
                query_url = f"/?bizId={bk_biz_id}#/data-retrieval?{params_str}"
                return query_url
    return None


def generate_log_search_url(bk_biz_id, collect_id):
    # 生成跳转日志检索的url
    redirect_info: AlertRedirectInfo | None = _get_alert_redirect_info(collect_id)
    if not redirect_info:
        return None

    alert: AlertDocument = redirect_info.alert
    query_config: dict[str, Any] = redirect_info.query_config

    if (
        query_config["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH
        and query_config["data_type_label"] == DataTypeLabel.LOG
    ):
        index_set_id = query_config["index_set_id"]
        start_time = int(alert.first_anomaly_time) - 5 * 60
        end_time = start_time + 60 * 60
        start_time_str = time_tools.utc2biz_str(start_time)
        end_time_str = time_tools.utc2biz_str(end_time)
        addition = [
            {"field": dimension_field, "operator": "=", "value": dimension_value}
            for dimension_field, dimension_value in redirect_info.origin_dimensions.items()
            if dimension_field in query_config.get("agg_dimension", [])
        ]
        params = {
            "bizId": alert.event.bk_biz_id or bk_biz_id,
            "addition": json.dumps(addition),
            "start_time": start_time_str,
            "end_time": end_time_str,
            "keyword": query_config["query_string"],
        }
        # 如果为指定不截断原始关联信息，则拼接查询链接
        bklog_link = f"{settings.BKLOGSEARCH_HOST}#/retrieve/{index_set_id}?{urlencode(params)}"
        return bklog_link


def generate_apm_rpc_url(bk_biz_id: int, collect_id: str) -> str | None:
    """生成 APM 调用分析跳转链接"""
    redirect_info: AlertRedirectInfo | None = _get_alert_redirect_info(collect_id)
    if not redirect_info:
        return None

    return ApmAlertHelper.get_rpc_url(
        bk_biz_id,
        redirect_info.alert.strategy,
        redirect_info.origin_dimensions,
        redirect_info.alert.event.time,
        redirect_info.duration,
    )


def generate_apm_trace_url(bk_biz_id: int, collect_id: str) -> str | None:
    """生成 APM Tracing 检索跳转链接"""
    redirect_info: AlertRedirectInfo | None = _get_alert_redirect_info(collect_id)
    if not redirect_info:
        return None

    return ApmAlertHelper.get_trace_url(
        bk_biz_id,
        redirect_info.alert.strategy,
        redirect_info.origin_dimensions,
        redirect_info.alert.event.time,
        redirect_info.duration,
    )


def generate_event_explore_url(bk_biz_id: int, collect_id: str) -> str | None:
    """生成事件检索跳转链接"""
    redirect_info: AlertRedirectInfo | None = _get_alert_redirect_info(collect_id)
    if not redirect_info:
        return None

    query_config: dict[str, Any] = redirect_info.query_config
    # 构建事件检索场景的查询过滤条件
    query_filter: dict[str, Any] = {
        "result_table_id": query_config["result_table_id"],
        "data_source_label": query_config["data_source_label"],
        "data_type_label": query_config["data_type_label"],
        "query_string": query_config.get("query_string", ""),
    }

    # 添加 where 过滤条件
    query_filter["where"] = merge_dimensions_into_conditions(
        agg_condition=query_config.get("agg_condition"),
        dimensions=redirect_info.origin_dimensions,
        dimension_fields=redirect_info.dimension_fields,
    )

    offset: int = 5 * 60 * 1000
    create_timestamp: int = redirect_info.alert.event.time
    params: dict[str, Any] = {
        "targets": json.dumps([{"data": {"query_configs": [query_filter]}}]),
        "from": create_timestamp * 1000 - redirect_info.duration * 1000 - offset,
        "to": create_timestamp * 1000 + offset,
    }

    encoded_params: str = urlencode(params)
    return urljoin(settings.BK_MONITOR_HOST, f"/?bizId={bk_biz_id}#/event-explore?{encoded_params}")
