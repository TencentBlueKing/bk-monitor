# -*- coding: utf-8 -*-
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

from opentelemetry.trace import StatusCode

from apm_web.constants import Apdex


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


class ErrorRateCalculation(Calculation):
    @classmethod
    def instance_cal(cls, metric_result):
        return cls.common_unify_result_cal(metric_result)

    @classmethod
    def common_unify_result_cal(cls, metric_result):
        sum_count = sum(i["_result_"] for i in metric_result)
        error_count = 0
        for serie in metric_result:
            if serie.get("status_code") == str(StatusCode.ERROR.value):
                error_count += serie["_result_"]

        return cls.calculate(error_count, sum_count)

    @classmethod
    def common_unify_series_cal(cls, series: []):
        sum_count = sum([serie["_result_"] for serie in series])
        error_count = 0
        for serie in series:
            if serie.get("status_code") == str(StatusCode.ERROR.value):
                error_count += serie["_result_"]
        return error_count, sum_count

    @classmethod
    def calculate(cls, *data):
        """
        输入为 (error_count, sum_count)
        """
        error_count, sum_count = data
        return error_count / (1 if sum_count == 0 else sum_count) * 100


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


class FlowMetricErrorRateCalculation(Calculation):
    """Flow 指标错误率计算"""

    def __init__(self, calculate_type):
        # choices: full / callee / caller
        self.calculate_type = calculate_type

    @classmethod
    def str_to_bool(cls, _str):
        return _str.lower() == "true"

    def range_cal(self, metric_result):
        """
        计算 Range 需要维度中包含 from_span_error / to_span_error
        此方法会忽略掉除 from_span_error / to_span_error 以外的维度
        所以如果查询中有其他维度不要使用此 Calculation
        """
        total_ts = defaultdict(int)
        error_ts = defaultdict(int)

        series = metric_result.get("series", [])
        if not series:
            return {"metrics": [], "series": []}
        all_ts = [i[-1] for i in metric_result["series"][0]["datapoints"]]

        for i, item in enumerate(metric_result.get("series", [])):
            if not item.get("datapoints"):
                continue

            dimensions = item.get("dimensions", {})
            if "from_span_error" not in dimensions or "to_span_error" not in dimensions:
                # 无效数据
                continue

            from_span_error, to_span_error = self.str_to_bool(dimensions["from_span_error"]), self.str_to_bool(
                dimensions["to_span_error"]
            )

            for value, timestamp in item["datapoints"]:
                if not value:
                    continue

                total_ts[timestamp] += value

                if (
                    (self.calculate_type == "callee" and to_span_error)
                    or (self.calculate_type == "caller" and from_span_error)
                    or (self.calculate_type == "full" and (from_span_error or to_span_error))
                ):
                    error_ts[timestamp] += value

        return {
            "metrics": [],
            "series": [
                {
                    "datapoints": [
                        (round(error_ts.get(t, 0) / total_ts.get(t), 6), t) for t in all_ts if total_ts.get(t)
                    ]
                    if total_ts
                    else [],
                    "dimensions": {},
                    "target": "flow",
                    "type": "bar",
                    "unit": "",
                }
            ],
        }

    def instance_cal(self, metric_result):

        total = sum([i.get("_result_", 0) for i in metric_result])
        if not total:
            return 0
        if self.calculate_type == "full":
            error_count = 0
            for i in metric_result:
                if "from_span_error" not in i or "to_span_error" not in i:
                    continue

                if self.str_to_bool(i["from_span_error"]) or self.str_to_bool(i["to_span_error"]):
                    error_count += i.get("_result_", 0)

        elif self.calculate_type == "caller":
            error_count = sum(
                [
                    i.get("_result_", 0)
                    for i in metric_result
                    if "from_span_error" in i and self.str_to_bool(i["from_span_error"])
                ]
            )
        elif self.calculate_type == "callee":
            error_count = sum(
                [
                    i.get("_result_", 0)
                    for i in metric_result
                    if "to_span_error" in i and self.str_to_bool(i["to_span_error"])
                ]
            )
        else:
            raise ValueError(f"Not supported calculate type: {self.calculate_type}")

        return error_count / total
