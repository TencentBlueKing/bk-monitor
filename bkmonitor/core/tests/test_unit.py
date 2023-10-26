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

from core.unit import load_unit


class TestI18n(object):
    def test_unit_convert(self):
        unit = load_unit("s")
        assert unit.convert(1, target_suffix="h", current_suffix="d") == 24
        assert unit.convert(1, target_suffix="m", current_suffix="d") == 24 * 60
        assert unit.convert(1, target_suffix="s", current_suffix="d") == 24 * 60 * 60
        assert unit.convert(1, target_suffix="ms", current_suffix="d") == 24 * 60 * 60 * 1000
        assert unit.convert(24, target_suffix="d", current_suffix="h") == 1
        assert unit.convert(24 * 60, target_suffix="d", current_suffix="m") == 1
        assert unit.convert(24 * 60 * 60, target_suffix="d", current_suffix="s") == 1
        assert unit.convert(24 * 60 * 60 * 1000, target_suffix="d", current_suffix="ms") == 1
