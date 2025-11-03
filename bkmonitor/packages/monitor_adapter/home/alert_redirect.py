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
from urllib.parse import urlencode

from django.conf import settings

from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionInstance
from bkmonitor.utils import time_tools
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource

"""
提供告警详情页面跳转
"""


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
    action = ActionInstanceDocument.get(collect_id)
    if action:
        alert_ids = action.alert_id
    else:
        alert_ids = ActionInstance.objects.get(id=str(collect_id)[10:]).alerts
    if not alert_ids:
        return None

    alert_id = alert_ids[0]
    alert = AlertDocument.get(alert_id)
    if not alert.strategy:
        return []

    item = alert.strategy["items"][0]
    query_config = item["query_configs"][0]

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
            for dimension_field, dimension_value in alert.origin_alarm.get("data", {}).get("dimensions", {}).items()
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
