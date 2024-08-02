"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


class TendencyDiagrammer:
    value_key = "sum(value)"
    value_key1 = "sum(`value`)"

    def draw(self, c: dict, **options) -> dict:
        """statistics profile data by time"""

        # follow the structure of bk-ui plugin
        if not c.get("list"):
            return {"series": []}

        sample_type = (options.get("sample_type") or "samples/count").split("/")
        sample_type_unit = sample_type[-1]
        target = "_".join(sample_type)
        if sample_type_unit == "nanoseconds":
            unit = "ns"
        elif sample_type_unit == "seconds":
            unit = "s"
        elif sample_type_unit == "bytes":
            unit = "bytes"
        else:
            unit = ""

        return {
            "series": [
                {
                    "alias": "_result_",
                    "metric_field": "_result_",
                    "datapoints": [
                        [
                            i.get(self.value_key, i.get(self.value_key1)),
                            int(i.get("time")),
                        ]
                        for i in c.get("list", [])
                        if "time" in i
                    ],
                    "target": target,
                    "type": "bar",
                    "unit": unit,
                }
            ]
        }

    def diff(self, base_doris_converter: dict, diff_doris_converter: dict, **options) -> dict:
        """diff two profile data by time"""
        if not base_doris_converter.get("list", []) or not diff_doris_converter.get("list", []):
            # 如果任一来源没有数据 则页面上需要展示为无数据
            return {"series": []}

        # follow the structure of bk-ui plugin

        sample_type = (options.get("sample_type") or "samples/count").split("/")
        sample_type_unit = sample_type[-1]
        target = "_".join(sample_type)
        if sample_type_unit == "nanoseconds":
            unit = "ns"
        elif sample_type_unit == "seconds":
            unit = "s"
        elif sample_type_unit == "bytes":
            unit = "bytes"
        else:
            unit = ""

        return {
            "series": [
                {
                    "alias": "_result_",
                    "metric_field": "_result_",
                    "datapoints": [
                        [
                            i.get(self.value_key, i.get(self.value_key1)),
                            int(i.get("time")),
                        ]
                        for i in base_doris_converter.get("list", [])
                        if "time" in i
                    ],
                    "target": target,
                    "type": "bar",
                    "unit": unit,
                    "dimensions": {"device_name": '查询项'},
                },
                {
                    "alias": "_result_",
                    "metric_field": "_result_",
                    "datapoints": [
                        [
                            i.get(self.value_key, i.get(self.value_key1)),
                            int(i.get("time")),
                        ]
                        for i in diff_doris_converter.get("list", [])
                        if "time" in i
                    ],
                    "target": target,
                    "type": "bar",
                    "unit": unit,
                    "dimensions": {"device_name": '对比项'},
                },
            ]
        }
