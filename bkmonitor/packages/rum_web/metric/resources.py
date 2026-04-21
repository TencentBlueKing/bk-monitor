"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from common.log import logger
from core.drf_resource import Resource, resource
from rum_web.constants import AlertLevel, AlertStatus
from rum_web.models.application import Application


def get_bar_interval_number(start_time, end_time, size=30):
    """计算柱状图 interval，固定柱子数量"""
    c = (end_time - start_time) / 60
    if c < size:
        return 60
    return int((end_time - start_time) // size)


class RumAlertQueryResource(Resource):
    """
    RUM 告警时间带查询。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        strategy_id = serializers.IntegerField(label="策略ID", required=False)

    def format_alert_data(self, alert_level_result):
        """将多级告警数据格式化为前端所需的时间带数据"""
        all_time_list = {}
        red_time_list = {}
        yellow_time_list = {}
        blue_time_list = {}
        result_time = []

        for level in alert_level_result:
            series_dict = alert_level_result.get(level, {})
            series = series_dict.get("series", [])
            for data_series in series:
                name = data_series.get("name", "")
                data_list = data_series.get("data", [])
                if name == AlertStatus.ABNORMAL:
                    for item_data in data_list:
                        num = item_data[1] if item_data[1] else 0
                        if num > 0:
                            if level == AlertLevel.ERROR:
                                red_time_list[item_data[0]] = num
                            elif level == AlertLevel.WARN:
                                yellow_time_list[item_data[0]] = num
                            else:
                                blue_time_list[item_data[0]] = num
                elif level == AlertLevel.INFO and name == AlertStatus.RECOVERED:
                    for item_data in data_list:
                        all_time_list[item_data[0]] = item_data[1] if item_data[1] else 0

        for time_val, value in all_time_list.items():
            if time_val in red_time_list:
                item = [[1, red_time_list[time_val]], time_val]
            elif time_val in yellow_time_list:
                item = [[2, yellow_time_list[time_val]], time_val]
            elif time_val in blue_time_list:
                item = [[3, blue_time_list[time_val]], time_val]
            else:
                item = [[4, 0], time_val]
            result_time.append(item)

        return result_time

    def get_alert_params(self, application, bk_biz_id, start_time, end_time, level, strategy_id):
        params = {
            "bk_biz_ids": [bk_biz_id],
            "start_time": start_time,
            "end_time": end_time,
            "interval": get_bar_interval_number(start_time, end_time),
            "query_string": f"metric: custom.{application.metric_result_table_id}.*",
            "conditions": [
                {"key": "severity", "value": [level]},
            ],
        }
        if strategy_id is not None:
            params["conditions"].append({"key": "strategy_id", "value": [strategy_id]})
        return params

    def get_alert_data(self, application, bk_biz_id, start_time, end_time, strategy_id):
        alert_level = [AlertLevel.ERROR, AlertLevel.WARN, AlertLevel.INFO]
        alert_level_result = {}
        for level in alert_level:
            params = self.get_alert_params(application, bk_biz_id, start_time, end_time, level, strategy_id)
            response = resource.fta_web.alert.alert_date_histogram(params)
            series = []
            for i in response["series"]:
                series.append({**i, "data": i["data"]})
            alert_level_result[level] = {"series": series, "unit": ""}
        return alert_level_result

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        strategy_id = validated_request_data.get("strategy_id", None)

        try:
            application = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id)
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        series = []
        if application.metric_result_table_id:
            try:
                format_alert_data = self.get_alert_data(application, bk_biz_id, start_time, end_time, strategy_id)
                time_list = self.format_alert_data(format_alert_data)
                if time_list:
                    series = [
                        {
                            "datapoints": time_list[:-1],
                            "dimensions": {},
                            "target": "alert",
                            "type": "bar",
                            "unit": "",
                        }
                    ]
            except Exception as e:
                logger.warning(f"[RumAlertQuery] query alert data failed: {e}")

        return {
            "metrics": [],
            "series": series,
        }
