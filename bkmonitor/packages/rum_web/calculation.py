"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict

from opentelemetry.trace import StatusCode

from rum_web.constants import Apdex


class Calculation:
    @classmethod
    def instance_cal(cls, metric_result):
        if not metric_result:
            return 0

        return metric_result[0]["_result_"]

    @classmethod
    def range_cal(cls, metric_result):
        return metric_result

    @classmethod
    def common_unify_result_cal_serie(cls, serie):
        return serie["datapoints"][0][0]

    @classmethod
    def calculate(cls, *data):
        return data[0]


class ApdexCalculation(Calculation):
    SATISFIED_RATE = 0.75
    TOLERATING_RATE = 0.5
    FRUSTRATING_RATE = 0.25

    @classmethod
    def instance_cal(cls, metric_result):
        return cls.common_unify_result_cal(metric_result)

    @classmethod
    def range_cal(cls, metric_result):
        """
        Apdex: (满意数 + 可容忍 / 2) / 总样本量
        """
        if not metric_result:
            return {"metrics": [], "series": []}
        datapoint_map = defaultdict(lambda: {"satisfied": 0, "tolerating": 0, "frustrated": 0})
        for item in metric_result.get("series", []):
            if Apdex.DIMENSION_KEY not in item["dimensions"]:
                continue
            apdex_type = item["dimensions"][Apdex.DIMENSION_KEY]
            for point in item.get("datapoints"):
                if not point[0]:
                    continue
                datapoint_map[point[1]][apdex_type] += point[0]

        res = []
        for timestamp in sorted(datapoint_map.keys()):
            info = datapoint_map[timestamp]

            satisfied_count = info["satisfied"]
            tolerating_count = info["tolerating"]
            frustrated_count = info["frustrated"]

            total = satisfied_count + tolerating_count + frustrated_count
            if not total:
                # 无数据不显示此柱
                res.append((None, timestamp))
            else:
                res.append((round((satisfied_count + tolerating_count) / total, 2), timestamp))

        return {
            "metrics": [],
            "series": [{"datapoints": res, "dimensions": {}, "target": "apdex", "type": "bar", "unit": ""}],
        }

    @classmethod
    def common_unify_result_cal(cls, metric_result):
        if not metric_result:
            return None

        error_count = sum(i["_result_"] for i in metric_result if i.get("status_code") == str(StatusCode.ERROR.value))
        total_count = 0
        satisfied_count = 0
        tolerating_count = 0
        frustrated_count = 0
        for serie in metric_result:
            if Apdex.DIMENSION_KEY not in serie:
                continue
            total_count += serie["_result_"]
            if serie[Apdex.DIMENSION_KEY] == Apdex.SATISFIED:
                satisfied_count += serie["_result_"]
            if serie[Apdex.DIMENSION_KEY] == Apdex.TOLERATING:
                tolerating_count += serie["_result_"]
            if serie[Apdex.DIMENSION_KEY] == Apdex.FRUSTRATED:
                frustrated_count += serie["_result_"]
        return cls.calculate(satisfied_count, tolerating_count, frustrated_count, error_count, total_count)

    @classmethod
    def calculate(cls, *data):
        satisfied_count, tolerating_count, frustrated_count, error_count, total_count = data
        if not total_count:
            return None

        apdex_rate = (satisfied_count * 1 + tolerating_count * 0.5 + (tolerating_count + error_count) * 0) / total_count
        if apdex_rate > cls.SATISFIED_RATE:
            return Apdex.SATISFIED
        if apdex_rate > cls.TOLERATING_RATE:
            return Apdex.TOLERATING
        return Apdex.FRUSTRATED
