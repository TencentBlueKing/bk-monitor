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
import time
from collections import namedtuple

from mock import MagicMock

from alarm_backends.service.access.priority import PriorityChecker


class Strategy:
    def __init__(self, priority):
        self.priority = priority

    def get_interval(self):
        return 60


Item = namedtuple("Item", ["id", "strategy"])

# 使用nametuple来模拟DataRecord和EventRecord，只需要record_id和items字段
# record_id的格式为4178cbf1c02e6c90ff4dd75b5df0c091.1691654940，第一段为维度md5，第二段为时间戳
Record = namedtuple("Record", ["record_id", "items", "is_retains", "inhibitions", "md5_dimension"])

ITEMS = [
    Item(1, Strategy(1)),
    Item(2, Strategy(2)),
    Item(3, Strategy(3)),
    Item(4, Strategy(3)),
]

RECORD_LIST = [
    Record(
        "1114c2c4115aaab1adc2d54b28369455.xxxxxxxxxx",
        ITEMS,
        {1: True, 2: True, 3: True, 4: False},
        {},
        "1114c2c4115aaab1adc2d54b28369455",
    ),
    Record(
        "2d3f21b4819b98dfb4ffe0275a22a48f.xxxxxxxxxx",
        ITEMS,
        {1: True, 2: True, 3: False, 4: False},
        {},
        "2d3f21b4819b98dfb4ffe0275a22a48f",
    ),
    Record(
        "8b7130d3960a9d7cc26cfdca24e256a8.xxxxxxxxxx",
        ITEMS,
        {1: True, 2: False, 3: False, 4: True},
        {},
        "8b7130d3960a9d7cc26cfdca24e256a8",
    ),
]


def create_priority_cache():
    now_timestamp = time.time()
    return {
        "1114c2c4115aaab1adc2d54b28369455": f"1:{now_timestamp}",
        "2d3f21b4819b98dfb4ffe0275a22a48f": f"3:{now_timestamp - 100}",
        "8b7130d3960a9d7cc26cfdca24e256a8": f"3:{now_timestamp - 301}",
        "aaa": f"3:{time.time() - 601}",
        "bbb": f"3:{time.time()}",
    }


class TestPriority:
    def test_inhibited_and_sync(self):
        pc = PriorityChecker("xxx")
        pc.priority_cache = create_priority_cache()
        assert not pc.is_inhibited(RECORD_LIST[0], ITEMS[0])
        assert not pc.is_inhibited(RECORD_LIST[0], ITEMS[1])
        assert not pc.is_inhibited(RECORD_LIST[0], ITEMS[2])
        assert not pc.is_inhibited(RECORD_LIST[0], ITEMS[3])

        assert pc.is_inhibited(RECORD_LIST[1], ITEMS[0])
        assert pc.is_inhibited(RECORD_LIST[1], ITEMS[1])
        assert not pc.is_inhibited(RECORD_LIST[1], ITEMS[2])
        assert not pc.is_inhibited(RECORD_LIST[1], ITEMS[3])

        assert not pc.is_inhibited(RECORD_LIST[2], ITEMS[0])
        assert not pc.is_inhibited(RECORD_LIST[2], ITEMS[1])
        assert not pc.is_inhibited(RECORD_LIST[2], ITEMS[2])
        assert not pc.is_inhibited(RECORD_LIST[2], ITEMS[3])

        assert set(pc.need_update.keys()) == {record.record_id.split(".")[0] for record in RECORD_LIST}

        pc.client = MagicMock()
        pc.sync_priority()
        assert pc.client.expire.call_count == 1
        assert pc.client.hmset.call_count == 1
        assert len(pc.client.hmset.call_args[0][1]) == 3
        assert pc.client.hdel.call_count == 1
        assert pc.client.hdel.call_args[0][1] == "aaa"
