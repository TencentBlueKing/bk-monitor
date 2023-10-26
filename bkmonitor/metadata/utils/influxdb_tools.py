# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from string import Template

from influxdb import InfluxDBClient

# import influxdb
"""
提取influxdb中指定database.measurement的metric信息
输出格式:
    [{
        "metric_name": "xxx",
        "metric_display_name": "xxx",
        "unit": "",
        "type": "float",
        "dimensions": [{
            "dimension_name": "",
            "dimension_display_name": ""
        }]
    }]
"""


def parse_serie(serie):
    items = serie.split(",")
    items = items[1:]
    data = dict()
    for item in items:
        key, value = item.split("=", 1)
        data[key] = value
    return data


class InfluxDBSchemaProxy(object):
    def __init__(self, host, port, database, measurement):
        self.client = InfluxDBClient(host=host, port=port, database=database)
        self.database = database
        self.measurement = measurement

    def get_measurements(self):
        result = self.client.get_list_measurements()
        return [item["name"] for item in result]

    def get_filed_types(self):
        query = Template("SHOW FIELD KEYS FROM $measurement").substitute({"measurement": self.measurement})
        resultSet = self.client.query(query)
        return {item["fieldKey"]: item["fieldType"] for item in resultSet.get_points()}

    def get_metric_names(self):
        query = Template("SHOW TAG VALUES FROM $measurement WITH key=metric_name").substitute(
            {"measurement": self.measurement}
        )
        resultSet = self.client.query(query)
        keys = [item["value"] for item in resultSet.get_points()]
        return keys

    def get_series_by_metric(self, metric):
        query = Template("SHOW SERIES FROM $measurement WHERE metric_name='$metric'").substitute(
            {"measurement": self.measurement, "metric": metric}
        )
        resultSet = self.client.query(query)
        keys = [item["key"] for item in resultSet.get_points()]
        return keys

    def get_tag_values_by_metric(self, metric):
        series = self.get_series_by_metric(metric)
        result = dict()
        for serie in series:
            data = parse_serie(serie)
            for key, value in data.items():
                if key not in result:
                    result[key] = list()
                result[key].append(value)
        for key in result:
            result[key] = list(set(result[key]))

        return result

    def get_metric_tag_values(self):
        """
        [{
            "metric_name": "foo",
            "metric_display_name": "fooName",
            "unit": "",
            "type": "int",
            "dimensions": [{
                "dimension_name": "",
                "dimension_display_name": ""
            }]
        }]
        """
        if self.measurement not in self.get_measurements():
            return list()

        field_types = self.get_filed_types()

        metric_list = list()
        metrics = self.get_metric_names()
        for metric in metrics:
            tag_values = self.get_tag_values_by_metric(metric)
            metric_detail = {
                "metric_name": metric,
                "metric_display_name": metric,
                "unit": "",
                "type": field_types.get("metric_value", ""),
                "dimensions": [{"dimension_name": tag, "dimension_display_name": tag} for tag in tag_values.keys()],
            }
            metric_list.append(metric_detail)

        return metric_list

    def get_tag_values(self, tag_name):
        query = Template("SHOW TAG VALUES FROM $measurement WITH key=$tag_name").substitute(
            {"measurement": self.measurement, "tag_name": tag_name}
        )
        resultSet = self.client.query(query)
        values = [item["value"] for item in resultSet.get_points()]
        return values
