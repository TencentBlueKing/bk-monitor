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


import datetime

import mock  # noqa
import pytz
from mock import MagicMock, call, patch  # noqa


class MockAnomalyRecord(object):
    def __init__(self, **kwargs):
        self.anomaly_id = kwargs.get("anomaly_id", 1)
        self.source_time = kwargs.get("source_time", datetime.datetime.now(pytz.utc))
        self.create_time = kwargs.get("create_time", datetime.datetime.now(pytz.utc))
        self.strategy_id = kwargs.get("strategy_id", 1)
        self.origin_alarm = kwargs.get("origin_alarm", {})


class MockEventModel(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.create_time = kwargs.get("create_time", datetime.datetime.now(pytz.utc))
        self.begin_time = kwargs.get("begin_time", datetime.datetime.now(pytz.utc))
        self.end_time = kwargs.get("end_time", datetime.datetime.now(pytz.utc))
        self.bk_biz_id = kwargs.get("bk_biz_id", 0)
        self.event_id = kwargs.get("event_id", 1)
        self.strategy_id = kwargs.get("strategy_id", 1)
        self.origin_alarm = kwargs.get("origin_alarm", {})
        self.origin_config = kwargs.get("origin_config", {})
        self.level = kwargs.get("level", 1)
        self.status = kwargs.get("status", "ABNORMAL")
        self.is_ack = kwargs.get("is_ack", False)
        self.p_event_id = kwargs.get("p_event_id", "")
        self.is_shielded = kwargs.get("is_shielded", 1)
        self.target_key = kwargs.get("target_key", "target_key")
        self.latest_anomaly_record = MockAnomalyRecord(**(kwargs.get("latest_anomaly_record", {})))
        self.duration = datetime.timedelta(seconds=60)
        self.anomaly_message = "anomaly_message1"


class MockEventAction(object):
    def __init__(self, **kwargs):
        self.status = kwargs.get("status", "SUCCESS")
        self.extend_info = kwargs.get("extend_info", {})


class MockQuerySet(object):
    def __init__(self, get_result=None, get_raise=None, filter_result=None, aggregate_result=None, exist_return=True):
        self.get = MagicMock(return_value=get_result) if get_result else MagicMock(side_effect=get_raise)
        self.filter = MagicMock(return_value=filter_result)
        self.exist = MagicMock(return_value=exist_return)
        self.aggregate = MagicMock(return_value=aggregate_result)
