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
import mock
import pytest

from alarm_backends.service.access.data import AccessDataProcess
from alarm_backends.service.access.handler import AccessBeater
from alarm_backends.tests.service.access.data.config import STRATEGY_CONFIG
from alarm_backends.tests.service.alert.manager.checker import STRATEGY

pytestmark = pytest.mark.django_db


@pytest.fixture()
def mock_get_strategy_group_detail(mocker):
    return mocker.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )


@pytest.fixture()
def mock_get_all_groups(mocker):
    return mocker.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_all_groups",
        return_value={"strategy_group_key": '{"1": [1]}'},
    )


@pytest.fixture()
def mock_get_strategy_group_keys(mocker):
    return mocker.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_keys",
        return_value=["strategy_group_key"],
    )


@pytest.fixture()
def mock_get_strategy_by_id(mocker):
    return mocker.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG
    )


@pytest.fixture()
def mock_query_instance_targets(mocker):
    return mocker.patch(
        "alarm_backends.management.commands.run_access.Command.query_instance_targets", return_value=[1]
    )


class TestAccessHandler(object):
    def test_access_data_handler(self):
        # mock config
        # mock database
        # mock redis
        # mock datasource
        data_process = AccessDataProcess(1)
        data_process.process()
        assert data_process.record_list == []

    def test_refresh_targets(self, mock_query_instance_targets):
        from alarm_backends.management.commands.run_access import Command

        service = Command()
        service.query_instance_targets = mock.MagicMock(return_value=[1])
        service.query_host_targets = mock.MagicMock(return_value=["local_node"])
        service.dispatch = mock.MagicMock(return_value=None)
        beater = AccessBeater(name="access_beater", targets=[STRATEGY["id"]], service=service)
        beater.refresh_targets()
        assert beater.targets == [1]

    def test_access_data_refresh_agg_strategy_group_interval(
        self, mock_get_strategy_group_detail, mock_get_strategy_by_id, mock_get_strategy_group_keys, mock_get_all_groups
    ):
        beater = AccessBeater(name="access_beater", targets=[STRATEGY["id"]], service=None)
        beater.max_access_data_period = 50
        beater.refresh_agg_strategy_group_interval()
        assert list(beater.entries.keys()) == [50]
        assert beater.entries[50].args == (50,)
        assert beater.interval_map[50] == {"strategy_group_key"}

    def test_access_event_handler(self):
        pass
