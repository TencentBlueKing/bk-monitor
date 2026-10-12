# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from alarm_backends.core.cache.key import ANOMALY_SIGNAL_KEY
from alarm_backends.service.trigger.handler import TriggerHandler
from core.errors.alarm_backends import LockError

pytestmark = pytest.mark.django_db


@pytest.fixture()
def run_trigger_item(mocker):
    return mocker.patch("alarm_backends.service.trigger.handler.run_trigger_item")


class TestHandler(object):
    def setup(self):
        ANOMALY_SIGNAL_KEY.client.flushall()

    def teardown(self):
        ANOMALY_SIGNAL_KEY.client.flushall()

    def test_no_data(self, run_trigger_item):
        handler = TriggerHandler()
        handler.DATA_FETCH_TIMEOUT = 0
        handler.handle()

        assert run_trigger_item.call_count == 0
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_parse_error(self, run_trigger_item):
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2.3")

        handler = TriggerHandler()
        handler.handle()

        assert run_trigger_item.call_count == 0
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_start(self, run_trigger_item):
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")

        handler = TriggerHandler()
        handler.handle()

        run_trigger_item.assert_called_once_with("1", "2", executor="trigger_worker")
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_empty_batch(self, run_trigger_item):
        run_trigger_item.return_value = 0
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")

        handler = TriggerHandler()
        handler.handle()

        run_trigger_item.assert_called_once_with("1", "2", executor="trigger_worker")
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_lock(self, run_trigger_item):
        run_trigger_item.side_effect = LockError(msg="locked")
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")
        handler = TriggerHandler()
        handler.handle()
        run_trigger_item.assert_called_once_with("1", "2", executor="trigger_worker")
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 1
