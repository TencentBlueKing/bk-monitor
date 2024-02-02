"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict

from apm_web.profile.constants import DESCRIBING_SAMPLE_UNIT
from apm_web.profile.converter import Converter


def get_statistics(c: Converter) -> dict:
    statistics = defaultdict(int)
    for s in c.raw_data:
        if s["sample_type"].split("/")[1] != DESCRIBING_SAMPLE_UNIT:
            continue
        statistics[s["dtEventTimeStamp"]] += int(s["value"])

    return statistics


class TendencyDiagrammer:
    def draw(self, c: Converter, **options) -> dict:
        """statistics profile data by time"""
        statistics = get_statistics(c)

        # follow the structure of bk-ui plugin
        return {
            "series": [
                {
                    "alias": "_result_",
                    "datapoints": [[v, k] for k, v in sorted(statistics.items())],
                    "type": "line",
                    "unit": "",
                }
            ]
        }

    def diff(self, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> dict:
        """diff two profile data by time"""
        base_statistics = get_statistics(base_doris_converter)
        diff_statistics = get_statistics(diff_doris_converter)

        # follow the structure of bk-ui plugin
        return {
            "series": [
                {
                    "alias": "_result_",
                    "datapoints": [[v, k] for k, v in sorted(base_statistics.items())],
                    "type": "line",
                    "unit": "",
                    "dimensions": {"device_name": '查询项'},
                },
                {
                    "alias": "_result_",
                    "datapoints": [[v, k] for k, v in sorted(diff_statistics.items())],
                    "type": "line",
                    "unit": "",
                    "dimensions": {"device_name": '对比项'},
                },
            ]
        }
