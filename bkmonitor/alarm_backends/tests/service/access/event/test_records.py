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

import pytest

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.event.records import (
    AgentEvent,
    CorefileEvent,
    DiskFullEvent,
    DiskReadonlyEvent,
    GseProcessEventRecord,
    PingEvent,
)
from alarm_backends.service.access.event.records.custom_event import (
    GseCustomStrEventRecord,
)
from alarm_backends.tests.service.access.event.config import *  # noqa

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="function", autouse=True)
def mock_arrow(mocker):
    mocker.patch("alarm_backends.service.access.event.records.custom_event.arrow.now", return_value=now)
    mocker.patch("alarm_backends.service.access.event.records.custom_event.arrow.utcnow", return_value=utc_now)


@pytest.mark.usefixtures("mock_arrow")
class TestGseEventRecords(object):
    def test_agent(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(AGENT_LOSE_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        get_host_by_agent_id = mocker.patch.object(HostManager, "get_by_agent_id")
        get_host.return_value = HOST_OBJECT
        get_host_by_agent_id.return_value = HOST_OBJECT

        for index, data in enumerate([AGENT_LOSE_DATA, AGENT_LOSE_DATA2, AGENT_LOSE_DATA3]):
            strategy_id = 31
            strategy = Strategy(strategy_id)
            r = AgentEvent(data, {2: {31: strategy}})
            r.check()
            records = r.flat()
            assert len(records) == 1

            r = records[0]
            records = r.full()
            assert len(records) == 1

            r = records[0]
            r.clean()

            if index < 2:
                assert r.data["data"] == AGENT_LOSE_DATA_CLEAN["data"]
                assert r.data["anomaly"] == AGENT_LOSE_DATA_CLEAN["anomaly"]
            else:
                assert r.data["data"] == AGENT_LOSE_DATA_CLEAN2["data"]
                assert r.data["anomaly"] == AGENT_LOSE_DATA_CLEAN2["anomaly"]

        assert get_host_by_agent_id.call_count == 1
        assert get_host_by_agent_id.call_args[0][0] == "0100005254008ed86116666614661851"

    def test_ping(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(PING_UNREACH_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        h = HOST_OBJECT
        get_host.return_value = h

        strategy_id = 35
        strategy = Strategy(strategy_id)
        r = PingEvent(PING_UNREACH_DATA, {2: {35: strategy}})
        r.check()
        records = r.flat()
        assert len(records) == 2

        r = records[0]
        records = r.full()
        assert len(records) == 1

        r = records[0]
        r.clean()
        print(r.data)
        assert r.data["data"] == PING_UNREACH_DATA_CLEAN["data"]
        assert r.data["anomaly"] == PING_UNREACH_DATA_CLEAN["anomaly"]

    def test_disk_read_only(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(DISK_READ_ONLY_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        h = HOST_OBJECT
        get_host.return_value = h

        strategy_id = 31
        strategy = Strategy(strategy_id)
        r = DiskReadonlyEvent(DISK_READ_ONLY_DATA, {2: {31: strategy}})
        r.check()
        records = r.flat()
        assert len(records) == 1

        r = records[0]
        records = r.full()
        assert len(records) == 1

        r = records[0]
        r.clean()
        print(r.data)

        assert r.data["data"] == DISK_READ_ONLY_DATA_CLEAN["data"]
        assert r.data["anomaly"] == DISK_READ_ONLY_DATA_CLEAN["anomaly"]

    def test_disk_full(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(DISK_FULL_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        h = HOST_OBJECT
        get_host.return_value = h

        strategy_id = 31
        strategy = Strategy(strategy_id)
        r = DiskFullEvent(DISK_FULL_DATA, {2: {31: strategy}})
        r.check()
        records = r.flat()
        assert len(records) == 1

        r = records[0]
        records = r.full()
        assert len(records) == 1

        r = records[0]
        r.clean()
        print(r.data)
        assert r.data["data"] == DISK_FULL_DATA_CLEAN["data"]
        assert r.data["anomaly"] == DISK_FULL_DATA_CLEAN["anomaly"]

    def test_core_file(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(COREFILE_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        h = HOST_OBJECT
        get_host.return_value = h

        strategy_id = 31
        strategy = Strategy(strategy_id)
        r = CorefileEvent(COREFILE_DATA, {2: {31: strategy}})
        r.check()
        records = r.flat()
        assert len(records) == 1

        r = records[0]
        records = r.full()
        assert len(records) == 1

        r = records[0]
        r.clean()
        print(r.data)
        assert r.data["data"] == COREFILE_DATA_CLEAN["data"]
        assert r.data["anomaly"] == COREFILE_DATA_CLEAN["anomaly"]


@pytest.mark.usefixtures("mock_arrow")
class TestCustomEventRecords(object):
    def test_custom_str(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(CUSTOM_STR_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        h = HOST_OBJECT
        get_host.return_value = h

        strategy_id = 31
        strategy = Strategy(strategy_id)
        r = GseCustomStrEventRecord(CUSTOM_STR_DATA, {2: {31: strategy}})
        r.check()
        records = r.flat()
        assert len(records) == 1

        r = records[0]
        records = r.full()
        assert len(records) == 1

        r = records[0]
        r.clean()
        print(r.data)
        assert r.data["data"] == CUSTOM_STR_DATA_CLEAN["data"]
        assert r.data["anomaly"] == CUSTOM_STR_DATA_CLEAN["anomaly"]


@pytest.mark.usefixtures("mock_arrow")
class TestGseProcessEventRecords(object):
    def test_custom_str(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(PROCESS_EVENT_STRATEGY)
        gen_strategy_snapshot = mocker.patch.object(Strategy, "gen_strategy_snapshot")
        gen_strategy_snapshot.return_value = "123"

        get_host = mocker.patch.object(HostManager, "get")
        h = HOST_OBJECT
        get_host.return_value = h

        strategy_id = 31
        strategy = Strategy(strategy_id)
        r = GseProcessEventRecord(GSE_PROCESS_EVENT_DATA, {2: {31: strategy}})
        r.check()
        records = r.flat()
        assert len(records) == 1

        r = records[0]
        records = r.full()
        assert len(records) == 1

        r = records[0]
        r.clean()
        print(r.data)
        assert r.data["data"] == GSE_PROCESS_EVENT_DATA_CLEAN["data"]
        assert r.data["anomaly"] == GSE_PROCESS_EVENT_DATA_CLEAN["anomaly"]
