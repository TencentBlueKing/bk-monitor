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

from apm_web.constants import Apdex
from opentelemetry.trace import StatusCode


class Calculation:
    @classmethod
    def instance_cal(cls, metric_result):
        if not metric_result:
            return 0

        return sum(i["_result_"] for i in metric_result)

    @classmethod
    def range_cal(cls, metric_result):
        pass

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


class ErrorRateOriginCalculation(Calculation):
    @classmethod
    def instance_cal(cls, metric_result):
        sum_count = sum(i["_result_"] for i in metric_result)
        error_count = 0
        for ser in metric_result:
            if ser.get("status_code") == str(StatusCode.ERROR.value):
                error_count += ser["_result_"]

        return error_count, sum_count


class ApdexCalculation(Calculation):
    SATISFIED_RATE = 0.75
    TOLERATING_RATE = 0.5
    FRUSTRATING_RATE = 0.25

    @classmethod
    def instance_cal(cls, metric_result):
        return cls.common_unify_result_cal(metric_result)

    @classmethod
    def range_cal(cls, metric_result):
        datapoint_map = defaultdict(lambda: {"satisfied": 0, "tolerating": 0, "frustrated": 0, "error": 0})
        for serie in metric_result.get("series", []):
            for datapoint in serie["datapoints"]:
                datapoint_value = datapoint[0] or 0
                if serie["dimensions"].get("status_code") == str(StatusCode.ERROR.value):
                    datapoint_map[datapoint[1]]["error"] += datapoint_value

                if Apdex.DIMENSION_KEY not in serie["dimensions"]:
                    continue
                if serie["dimensions"][Apdex.DIMENSION_KEY] == Apdex.SATISFIED:
                    datapoint_map[datapoint[1]]["satisfied"] += datapoint_value
                if serie["dimensions"][Apdex.DIMENSION_KEY] == Apdex.TOLERATING:
                    datapoint_map[datapoint[1]]["tolerating"] += datapoint_value
                if serie["dimensions"][Apdex.DIMENSION_KEY] == Apdex.FRUSTRATED:
                    datapoint_map[datapoint[1]]["frustrated"] += datapoint_value
        datapoints = []
        for datapoint, value in datapoint_map.items():
            all_count = sum(value.values())
            all_count = 1 if all_count == 0 else all_count
            apdex_rate = (
                (value["satisfied"] * 1) + (value["frustrated"] * 0.5) + ((value["tolerating"] + value["error"]) * 0)
            ) / all_count

            if all_count == 0:
                apdex_rate = 1
            datapoints.append((apdex_rate, datapoint))
        return {
            "metrics": [],
            "series": [{"datapoints": datapoints, "dimensions": {}, "target": "apdex", "type": "bar", "unit": ""}],
        }

    @classmethod
    def common_unify_result_cal(cls, metric_result):
        if not metric_result:
            return None

        error_count = sum(i["_result_"] for i in metric_result if i.get("status_code") == str(StatusCode.ERROR.value))

        satisfied_count = 0
        tolerating_count = 0
        frustrated_count = 0
        for serie in metric_result:
            if Apdex.DIMENSION_KEY not in serie:
                continue
            if serie[Apdex.DIMENSION_KEY] == Apdex.SATISFIED:
                satisfied_count += serie["_result_"]
            if serie[Apdex.DIMENSION_KEY] == Apdex.TOLERATING:
                tolerating_count += serie["_result_"]
            if serie[Apdex.DIMENSION_KEY] == Apdex.FRUSTRATED:
                frustrated_count += serie["_result_"]
        return cls.calculate(satisfied_count, tolerating_count, frustrated_count, error_count)

    @classmethod
    def calculate(cls, *data):
        satisfied_count, tolerating_count, frustrated_count, error_count = data
        all_count = satisfied_count + tolerating_count + frustrated_count + error_count
        all_count = 1 if all_count == 0 else all_count

        apdex_rate = (satisfied_count * 1 + tolerating_count * 0.5 + (tolerating_count + error_count) * 0) / all_count
        if apdex_rate > cls.SATISFIED_RATE:
            return Apdex.SATISFIED
        if apdex_rate > cls.TOLERATING_RATE:
            return Apdex.TOLERATING
        return Apdex.FRUSTRATED


class AvgDurationCalculation(Calculation):
    @classmethod
    def instance_cal(cls, metric_result):
        return cls.common_unify_result_cal(metric_result)

    @classmethod
    def common_unify_result_cal(cls, metric_result):
        if not metric_result:
            return 0
        num = len(metric_result)
        total = sum(i["_result_"] for i in metric_result)

        return cls.calculate(num, total)

    @classmethod
    def calculate(cls, *data):
        """
        输入为 (num, total)
        """
        num, total = data
        return total / (1 if num == 0 else num)
