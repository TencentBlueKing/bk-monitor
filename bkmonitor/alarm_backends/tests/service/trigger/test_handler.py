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


import pytest
from mock import MagicMock

from alarm_backends.core.cache.key import ANOMALY_SIGNAL_KEY, SERVICE_LOCK_TRIGGER
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.trigger.handler import TriggerHandler

pytestmark = pytest.mark.django_db


@pytest.fixture()
def processor(mocker):
    m = MagicMock()
    mocker.patch("alarm_backends.service.trigger.handler.TriggerProcessor", return_value=m)
    return m


@pytest.fixture()
def sleep(mocker):
    return mocker.patch("time.sleep", return_value=None)


class TestHandler(object):
    def setup(self):
        ANOMALY_SIGNAL_KEY.client.flushall()

    def teardown(self):
        ANOMALY_SIGNAL_KEY.client.flushall()

    def test_no_data(self, processor):
        handler = TriggerHandler()
        handler.DATA_FETCH_TIMEOUT = 0
        handler.handle()

        assert processor.process.call_count == 0
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_parse_error(self, processor):
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2.3")

        handler = TriggerHandler()
        handler.handle()

        assert processor.process.call_count == 0
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_start(self, processor):
        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")

        handler = TriggerHandler()
        handler.handle()

        assert processor.process.call_count == 1
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_exception(self, processor):
        def process(*args, **kwargs):
            raise Exception("test exc")

        processor.process.side_effect = process

        ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")

        handler = TriggerHandler()
        handler.handle()

        assert processor.process.call_count == 1
        assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 0

    def test_lock(self, processor, sleep):
        with service_lock(SERVICE_LOCK_TRIGGER, strategy_id=1, item_id=2):
            ANOMALY_SIGNAL_KEY.client.lpush(ANOMALY_SIGNAL_KEY.get_key(), "1.2")
            handler = TriggerHandler()
            handler.handle()
            assert processor.process.call_count == 0
            assert ANOMALY_SIGNAL_KEY.client.llen(ANOMALY_SIGNAL_KEY.get_key()) == 1
