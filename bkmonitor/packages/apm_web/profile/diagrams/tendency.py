"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import ugettext_lazy as _


class TendencyDiagrammer:
    field_key = "(round((cast(dtEventTimeStamp as DOUBLE) / cast(60000 as DOUBLE))) * cast(60 as DOUBLE))"
    field_key1 = "((round((CAST(`dtEventTimeStamp` AS DOUBLE) / 60000)) * 60))"
    value_key = "sum(value)"
    value_key1 = "sum(`value`)"

    def draw(self, c: dict, **options) -> dict:
        """statistics profile data by time"""

        # follow the structure of bk-ui plugin
        if not c.get("list"):
            return {"series": []}

        return {
            "series": [
                {
                    "alias": "_result_",
                    "metric_field": "_result_",
                    "datapoints": [
                        [
                            i.get(self.value_key, i.get(self.value_key1)),
                            int(i.get(self.field_key, i.get(self.field_key1))) * 1000,
                        ]
                        for i in c.get("list", [])
                        if self.field_key in i or self.field_key1 in i
                    ],
                    "target": _("CPU 时间"),
                    "type": "line",
                    "unit": "ns",
                }
            ]
        }

    def diff(self, base_doris_converter: dict, diff_doris_converter: dict, **options) -> dict:
        """diff two profile data by time"""

        # follow the structure of bk-ui plugin
        return {
            "series": [
                {
                    "alias": "_result_",
                    "metric_field": "_result_",
                    "datapoints": [
                        [
                            i.get(self.value_key, i.get(self.value_key1)),
                            int(i.get(self.field_key, i.get(self.field_key1))) * 1000,
                        ]
                        for i in base_doris_converter.get("list", [])
                        if self.field_key in i or self.field_key1 in i
                    ],
                    "target": _("CPU 时间"),
                    "type": "line",
                    "unit": "ns",
                    "dimensions": {"device_name": '查询项'},
                },
                {
                    "alias": "_result_",
                    "metric_field": "_result_",
                    "datapoints": [
                        [
                            i.get(self.value_key, i.get(self.value_key1)),
                            int(i.get(self.field_key, i.get(self.field_key1))) * 1000,
                        ]
                        for i in diff_doris_converter.get("list", [])
                        if self.field_key in i or self.field_key1 in i
                    ],
                    "target": _("CPU 时间"),
                    "type": "line",
                    "unit": "ns",
                    "dimensions": {"device_name": '对比项'},
                },
            ]
        }
