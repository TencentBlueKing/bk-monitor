"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import string
import time
import random
from core.drf_resource.base import Resource
from monitor_web.incident.metrics.serializers import MetricsSearchSerializer
from monitor_web.incident.metrics.constants import METRIC_NAMES, TIME_SECONDS_INTERVAL, METRIC_ALIAS


class IncidentMetricsSearchResource(Resource):
    """
    故障告警指标查询接口
    """

    def __init__(self):
        super().__init__()

    RequestSerializer = MetricsSearchSerializer

    def perform_request(self, validated_request_data: dict) -> dict:
        metric_type = validated_request_data.get("metric_type")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        mock_response = {}
        mock_response["bk_biz_id"] = bk_biz_id
        mock_response["metrics"] = {}

        random_number = random.randint(2, 5)
        for i in range(random_number):
            random_str = "".join(random.choices(string.ascii_letters, k=5))
            random_label = f"{int(time.time())}_{random_str}"
            origin_metric_name = random.choice(METRIC_NAMES)
            metric_name = f"{origin_metric_name}_{random_label}"
            metric_alias = f"{METRIC_ALIAS[origin_metric_name]}_{random_label}"
            mock_response["metrics"][metric_name] = {
                "metric_name": metric_name,
                "metric_alias": metric_alias,
                "metric_type": metric_type,
                "time_series": [],
            }

            mock_response["metrics"][metric_name]["time_series"] = [
                [
                    (start_time + j * TIME_SECONDS_INTERVAL) * 1000,
                    random.randint(0, 20),
                    # 使用带权重的随机选择，80%概率为0，20%概率为1
                    random.choices([0, 1], weights=[0.8, 0.2], k=1)[0],
                ]
                for j in range((end_time - start_time) // TIME_SECONDS_INTERVAL)
            ]

        return mock_response
