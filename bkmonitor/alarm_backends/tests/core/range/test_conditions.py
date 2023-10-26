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


from bkmonitor.utils.range.conditions import (
    AndCondition,
    EqualCondition,
    ExcludeCondition,
    GreaterCondition,
    GreaterOrEqualCondition,
    IncludeCondition,
    LesserCondition,
    LesserOrEqualCondition,
    NotEqualCondition,
    NotRegularCondition,
    OrCondition,
    RegularCondition,
)
from bkmonitor.utils.range.fields import DimensionField


class TestCondition(object):
    def test_equal(self):
        field = DimensionField("key", "value")
        condition = EqualCondition(field)
        assert condition.is_match({"key": "value"})
        assert not condition.is_match({"key": "value1"})

    def test_not_equal(self):
        field = DimensionField("key", "value")
        condition = NotEqualCondition(field)
        assert not condition.is_match({"key": "value"})
        assert condition.is_match({"key": "value1"})

    def test_include(self):
        field = DimensionField("key", "value")
        condition = IncludeCondition(field)
        assert condition.is_match({"key": ["value", "v"]})
        assert not condition.is_match({"key": ["v", "value"]})
        assert condition.is_match({"key": "value"})
        assert condition.is_match({"key": "asdfvalueasdf"})
        assert not condition.is_match({"key": "asdfalueasdf"})
        assert not condition.is_match({"key": ["asdfalueasdf"]})

    def test_exclude(self):
        field = DimensionField("key", "value")
        condition = ExcludeCondition(field)
        assert not condition.is_match({"key": ["value", "v"]})
        assert condition.is_match({"key": ["v", "value"]})
        assert not condition.is_match({"key": "value"})
        assert not condition.is_match({"key": "asdfvalueasdf"})
        assert condition.is_match({"key": "asdfalueasdf"})
        assert condition.is_match({"key": ["asdfalueasdf"]})

    def test_gt(self):
        field = DimensionField("key", 101)
        condition = GreaterCondition(field)
        assert condition.is_match({"key": 102})
        assert not condition.is_match({"key": 101})
        assert not condition.is_match({"key": 99})
        assert not condition.is_match({"key": [99, 12]})
        assert not condition.is_match({"key": [99, 102]})
        assert condition.is_match({"key": [102, 103]})

        field = DimensionField("key", [101, 102])
        condition = GreaterCondition(field)
        assert not condition.is_match({"key": 102})
        assert condition.is_match({"key": 103})
        assert not condition.is_match({"key": 101})
        assert not condition.is_match({"key": [99, 12]})
        assert not condition.is_match({"key": [102, 103]})
        assert condition.is_match({"key": [103, 103.1]})

    def test_gte(self):
        """gte 实际上是not lt"""
        field = DimensionField("key", 101)
        condition = GreaterOrEqualCondition(field)
        assert condition.is_match({"key": 102})
        assert condition.is_match({"key": 101})
        assert not condition.is_match({"key": 99})
        assert not condition.is_match({"key": [99, 12]})
        assert condition.is_match({"key": [99, 102]})
        assert condition.is_match({"key": [102, 103]})

        field = DimensionField("key", [101, 102])
        condition = GreaterOrEqualCondition(field)
        assert condition.is_match({"key": 102})
        assert not condition.is_match({"key": 100})
        assert condition.is_match({"key": 101})
        assert not condition.is_match({"key": [99, 12]})
        assert condition.is_match({"key": [102, 101]})
        assert not condition.is_match({"key": [100, 100.9]})

    def test_lt(self):
        field = DimensionField("key", 101)
        condition = LesserCondition(field)
        assert not condition.is_match({"key": 102})
        assert not condition.is_match({"key": 101})
        assert condition.is_match({"key": 99})
        assert condition.is_match({"key": [99, 12]})
        assert not condition.is_match({"key": [99, 102]})
        assert not condition.is_match({"key": [102, 103]})

        field = DimensionField("key", [101, 102])
        condition = LesserCondition(field)
        assert not condition.is_match({"key": 102})
        assert condition.is_match({"key": 100})
        assert not condition.is_match({"key": 101})
        assert condition.is_match({"key": [99, 12]})
        assert not condition.is_match({"key": [102, 101]})
        assert condition.is_match({"key": [100, 100.9]})

    def test_lte(self):
        """lte 实际上是 not gt"""
        field = DimensionField("key", 101)
        condition = LesserOrEqualCondition(field)
        assert not condition.is_match({"key": 102})
        assert condition.is_match({"key": 101})
        assert condition.is_match({"key": 99})
        assert condition.is_match({"key": [99, 12]})
        assert condition.is_match({"key": [99, 102]})
        assert not condition.is_match({"key": [102, 103]})

        field = DimensionField("key", [101, 102])
        condition = LesserOrEqualCondition(field)
        assert condition.is_match({"key": 102})
        assert not condition.is_match({"key": 103})
        assert condition.is_match({"key": 101})
        assert condition.is_match({"key": [99, 12]})
        assert condition.is_match({"key": [102, 103]})
        assert not condition.is_match({"key": [103, 103.1]})

    def test_regular(self):
        field = DimensionField("key", r"1234\d+5678")
        condition = RegularCondition(field)
        assert condition.is_match({"key": "1234235678"})
        assert condition.is_match({"key": ["1234235678"]})
        assert not condition.is_match({"key": "12345678"})
        assert not condition.is_match({"key": ["12345678"]})
        assert condition.is_match({"key": ["1234235678", "234"]})

        field = DimensionField("key", [r"1234\d+5678", r"123\d+5678"])
        condition = RegularCondition(field)
        assert condition.is_match({"key": "1234235678"})
        assert condition.is_match({"key": "12345678"})
        assert not condition.is_match({"key": "128"})
        assert condition.is_match({"key": ["12345678"]})
        assert condition.is_match({"key": ["1234235678", "234"]})
        assert not condition.is_match({"key": ["234", "1234235678"]})

    def test_not_regular(self):
        field = DimensionField("key", r"1234\d+5678")
        condition = NotRegularCondition(field)
        assert not condition.is_match({"key": "1234235678"})
        assert not condition.is_match({"key": ["1234235678"]})
        assert condition.is_match({"key": "12345678"})
        assert condition.is_match({"key": ["12345678"]})
        assert not condition.is_match({"key": ["1234235678", "234"]})

        field = DimensionField("key", [r"1234\d+5678", r"123\d+5678"])
        condition = NotRegularCondition(field)
        assert not condition.is_match({"key": "1234235678"})
        assert not condition.is_match({"key": "12345678"})
        assert condition.is_match({"key": "128"})
        assert not condition.is_match({"key": ["12345678"]})
        assert not condition.is_match({"key": ["1234235678", "234"]})
        assert condition.is_match({"key": ["234", "1234235678"]})

    def test_or(self):
        field = DimensionField("key", r"1234\d+5678")
        condition1 = RegularCondition(field)
        condition2 = NotRegularCondition(field)

        or_condition = OrCondition()
        or_condition.add(condition1)
        or_condition.add(condition2)

        assert or_condition.is_match({"key": "1234235678"})
        assert or_condition.is_match({"key": "12345678"})

        or_condition.remove(condition2)
        field2 = DimensionField("key", r"123\d+5678")
        condition3 = RegularCondition(field2)
        or_condition.add(condition3)
        assert not or_condition.is_match({"key": "123"})
        assert or_condition.is_match({"key": "1234235678"})

    def test_and(self):
        field = DimensionField("key", r"1234\d+5678")
        condition1 = RegularCondition(field)
        condition2 = NotRegularCondition(field)

        and_condition = AndCondition()
        and_condition.add(condition1)
        and_condition.add(condition2)

        assert not and_condition.is_match({"key": "1234235678"})
        assert not and_condition.is_match({"key": "12345678"})

        and_condition.remove(condition2)
        field2 = DimensionField("key", r"123\d+5678")
        condition3 = RegularCondition(field2)
        and_condition.add(condition3)
        assert not and_condition.is_match({"key": "123"})
        assert and_condition.is_match({"key": "1234235678"})
