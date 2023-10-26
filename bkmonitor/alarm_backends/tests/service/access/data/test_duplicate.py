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


import copy

import fakeredis
import pytest

from alarm_backends.service.access.data.duplicate import Duplicate

from .config import STANDARD_DATA


pytestmark = pytest.mark.django_db


class MockRecord(object):
    def __init__(self, attrs):
        self.__dict__.update(attrs)


class TestDuplicate(object):
    def setup_method(self, method):
        redis = fakeredis.FakeRedis(decode_responses=True)
        redis.flushall()

    def test_duplicate(self):
        strategy_group_key = "123456789"
        dup = Duplicate(strategy_group_key)

        raw_data_1 = copy.deepcopy(STANDARD_DATA)
        record_1 = MockRecord(raw_data_1)
        assert dup.is_duplicate(record_1) is False

        dup.add_record(record_1)
        assert dup.is_duplicate(record_1) is True

    def test_refresh_cache(self):
        strategy_group_key = "123456789"
        dup = Duplicate(strategy_group_key)
        record = MockRecord(STANDARD_DATA)

        raw_data_1 = copy.deepcopy(STANDARD_DATA)
        record_1 = MockRecord(raw_data_1)
        record_1.time += 60
        dup.add_record(record_1)

        raw_data_2 = copy.deepcopy(STANDARD_DATA)
        record_2 = MockRecord(raw_data_2)
        record_2.time += 120
        dup.add_record(record_2)

        dup.refresh_cache()

        dup = Duplicate(strategy_group_key)
        assert dup.is_duplicate(record_1) is True
        assert dup.is_duplicate(record_2) is True
        assert dup.is_duplicate(record) is False
