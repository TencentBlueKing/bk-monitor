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


class TendencyDiagrammer:
    def draw(self, c: Converter, **options) -> dict:
        """statistics profile data by time"""

        statistics = defaultdict(int)
        for s in c.raw_data:
            if s["sample_type"].split("/")[1] != DESCRIBING_SAMPLE_UNIT:
                continue
            statistics[s["dtEventTimeStamp"]] += int(s["value"])

        return {
            "series": [
                {
                    "datapoints": [[v, k] for k, v in statistics.items()],
                    "type": "line",
                    "unit": "ns",
                }
            ]
        }

    def diff(self, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> dict:
        raise NotImplementedError
