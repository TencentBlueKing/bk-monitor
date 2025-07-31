"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import random
import string
import time

from monitor_web.incident.events.constants import (
    EVENT_ALIAS,
    EVENT_NAMES,
    EVENTS_LEVELS,
    EVENTS_SOURCES,
    TIME_SECONDS_INTERVAL,
)


class IncidentEventsSearchMockData:
    @property
    def INCIDENT_EVENTS_SEARCH_MOCK_DATA(self, validated_request_data):
        bk_biz_id = validated_request_data.get("bk_biz_id")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        mock_response = {}
        mock_response["bk_biz_id"] = bk_biz_id
        mock_response["events"] = {}
        mock_response["statistics"] = {"event_source": {}, "event_level": {}}
        random_number = random.randint(2, 5)
        for i in range(random_number):
            random_str = "".join(random.choices(string.ascii_letters, k=5))
            random_label = f"{int(time.time())}_{random_str}"
            origin_events_name = random.choice(EVENT_NAMES)
            event_name = f"{origin_events_name}_{random_label}"
            event_alias = f"{EVENT_ALIAS[origin_events_name]}_{random_label}"
            event_source = random.choice(EVENTS_SOURCES)
            event_level = random.choice(EVENTS_LEVELS)
            statistics = mock_response["statistics"]
            statistics["event_source"][event_source] = statistics["event_source"].get(event_source, 0) + 1
            statistics["event_level"][event_level] = statistics["event_level"].get(event_level, 0) + 1
            mock_response["events"][event_name] = {
                "event_name": event_name,
                "event_alias": event_alias,
                "event_source": event_source,
                "event_level": event_level,
                "series": [],
            }

            datapoint_lists = [
                [
                    (start_time + j * TIME_SECONDS_INTERVAL) * 1000,
                    random.randint(0, 20),
                ]
                for j in range((end_time - start_time) // TIME_SECONDS_INTERVAL)
            ]
            mock_response["events"][event_name]["series"].append(
                {
                    "dimensions": {},
                    "target": "COUNT(_index)",
                    "metric_field": "_result_",
                    "datapoints": random.sample(
                        datapoint_lists, random.randint(1, random.randint(1, len(datapoint_lists)))
                    ),
                    "alias": "_result_",
                    "type": "bar",
                    "dimensions_translation": {},
                    "unit": "",
                }
            )
        return mock_response

    @property
    def INCIDENT_EVENTS_DETAIL_MOCK_DATA(self):
        return {
            "All": {
                "time": 1750316700,
                "total": 2105,
                "topk": [
                    {
                        "domain": {"value": "CICD", "alias": "CICD"},
                        "source": {"value": "BKCI", "alias": "\u84dd\u76fe"},
                        "event_name": {
                            "value": "pipeline_step_status_info",
                            "alias": "pipeline_step_status_info\uff08pipeline_step_status_info\uff09",
                        },
                        "count": 1525,
                        "proportions": 72.45,
                    },
                    {
                        "domain": {"value": "CICD", "alias": "CICD"},
                        "source": {"value": "BKCI", "alias": "\u84dd\u76fe"},
                        "event_name": {
                            "value": "pipeline_status_info",
                            "alias": "\u6d41\u6c34\u7ebf\u6267\u884c\uff08pipeline_status_info\uff09",
                        },
                        "count": 580,
                        "proportions": 27.55,
                    },
                ],
            },
            "Warning": {
                "time": 1750316700,
                "total": 39,
                "topk": [
                    {
                        "domain": {"value": "CICD", "alias": "CICD"},
                        "source": {"value": "BKCI", "alias": "\u84dd\u76fe"},
                        "event_name": {
                            "value": "pipeline_status_info",
                            "alias": "\u6d41\u6c34\u7ebf\u6267\u884c\uff08pipeline_status_info\uff09",
                        },
                        "count": 27,
                        "proportions": 69.23,
                    },
                    {
                        "domain": {"value": "CICD", "alias": "CICD"},
                        "source": {"value": "BKCI", "alias": "\u84dd\u76fe"},
                        "event_name": {
                            "value": "pipeline_step_status_info",
                            "alias": "pipeline_step_status_info\uff08pipeline_step_status_info\uff09",
                        },
                        "count": 12,
                        "proportions": 30.77,
                    },
                ],
            },
        }
