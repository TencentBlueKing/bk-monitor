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


import math

from bkmonitor.utils.range.fields import DimensionField, IpDimensionField


class TestDimensionField(object):
    def test_get_value_from_data(self):
        dimension_field = DimensionField("key", "value")

        data = {"key": "value", "key2": "value1"}
        assert dimension_field.get_value_from_data(data) == (True, "value")

        data = {"key2": "value1"}
        assert dimension_field.get_value_from_data(data)[0] is False

    def test_to_str_list(self):
        dimension_field = DimensionField("key", " value  ")
        result = dimension_field.to_str_list()

        assert isinstance(result, list)
        print("----------" + result[0] + "----------")
        assert result[0] == "value"

        dimension_field = DimensionField("key", [" value"])
        result = dimension_field.to_str_list()

        assert isinstance(result, list)
        assert result[0] == "value"

        dimension_field = DimensionField("key", ("value ",))
        result = dimension_field.to_str_list()

        assert isinstance(result, list)
        assert result[0] == "value"

    def test_to_float_list(self):
        dimension_field = DimensionField("key", "100")
        result = dimension_field.to_float_list()

        assert isinstance(result, list)
        assert result[0] == 100

        dimension_field = DimensionField("key", "value")
        result = dimension_field.to_float_list()

        assert isinstance(result, list)
        assert math.isnan(result[0])

        dimension_field = DimensionField("key", ["100", "121"])
        result = dimension_field.to_float_list()

        assert isinstance(result, list)
        assert result[0] == 100
        assert result[1] == 121

        dimension_field = DimensionField("key", ("100 ",))
        result = dimension_field.to_float_list()

        assert isinstance(result, list)
        assert result[0] == 100


class TestIpDimensionField(object):
    def test_get_value_from_data(self):
        data = {
            "key": "1.1.1.1",
        }

        dimension_field = IpDimensionField("key", "1.1.1.2")
        assert dimension_field.get_value_from_data(data)[1] == "1.1.1.1"

        dimension_field = IpDimensionField("key", ["1.1.1.2"])
        assert dimension_field.get_value_from_data(data)[1] == "1.1.1.1"

        data = {"key": "1.1.1.1", "bk_cloud_id": "1"}

        dimension_field = IpDimensionField("key", {"bk_cloud_id": "2"})
        value = dimension_field.get_value_from_data(data)[1]
        assert isinstance(value, list)
        assert value[0]["ip"] == "1.1.1.1"
        assert value[0]["bk_cloud_id"] == "1"

        dimension_field = IpDimensionField("key", [{"bk_cloud_id": "2"}])
        value = dimension_field.get_value_from_data(data)[1]
        assert isinstance(value, list)
        assert value[0]["ip"] == "1.1.1.1"
        assert value[0]["bk_cloud_id"] == "1"

        data = {"key": "1.1.1.1", "plat_id": "1"}

        dimension_field = IpDimensionField("key", [{}])
        value = dimension_field.get_value_from_data(data)[1]
        assert value == "1.1.1.1"

        data = {
            "key": "1.1.1.1",
        }

        dimension_field = IpDimensionField("key", {"bk_cloud_id": "2"})
        value = dimension_field.get_value_from_data(data)[1]
        assert isinstance(value, list)
        assert value[0]["ip"] == "1.1.1.1"
        assert value[0]["bk_cloud_id"] == "0"

    def test_to_str_list(self):
        dimension_field = IpDimensionField("key", "1.1.1.1")
        result = dimension_field.to_str_list()
        assert isinstance(result, list)
        assert result[0] == "1.1.1.1"
