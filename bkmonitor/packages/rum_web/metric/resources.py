"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from core.drf_resource import Resource


class RumAlertQueryResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        strategy_id = serializers.IntegerField(label="策略ID", required=False)

    def perform_request(self, validated_request_data):
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        # 模拟告警时间带
        interval = 60
        datapoints = []
        ts = start_time
        while ts <= end_time:
            # [level, count] — level=4 表示无告警
            datapoints.append([[4, 0], ts * 1000])
            ts += interval
        return {
            "metrics": [],
            "series": [
                {
                    "datapoints": datapoints,
                    "dimensions": {},
                    "target": "alert",
                    "type": "bar",
                    "unit": "",
                }
            ],
        }
