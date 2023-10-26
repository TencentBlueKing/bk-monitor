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

from django.test import TestCase

from core.unit import load_unit


class TestUnit(TestCase):
    def test_auto_convert(self):
        unit = load_unit("bits")
        value, suffix = unit.fn.auto_convert(10000)
        assert value == 9.765625
        assert suffix == "Kib"

        value, suffix = unit.fn.auto_convert(100000000)
        assert value == 95.367432
        assert suffix == "Mib"

    def test_convert(self):
        unit = load_unit("bits")
        value = unit.fn.convert(10000, "Ki")
        assert value == 9.765625

        value = unit.fn.convert(10000, "Ki", "aa")
        assert value == 10000

        value = unit.fn.convert(10000, "sadf")
        assert value == 10000

        value, _ = unit.fn.convert_to_max(10000, "Ki")
        assert value == 10240000

    def test_percent_convert(self):
        unit = load_unit("percent")
        value, suffix = unit.fn.auto_convert(2000)
        assert value == 2000
        assert suffix == "%"

        unit = load_unit("percentunit")
        value, suffix = unit.fn.auto_convert(2)
        assert value == 200
        assert suffix == "%"
