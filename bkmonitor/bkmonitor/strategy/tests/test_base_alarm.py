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

from bkmonitor.models import QueryConfigModel
from bkmonitor.strategy.new_strategy import Strategy

pytestmark = pytest.mark.django_db


class TestCustomEvent:
    Config = {
        "bk_biz_id": 3,
        "name": "日志时序告警",
        "source": "bk_monitor",
        "scenario": "os",
        "type": "monitor",
        "is_enabled": True,
        "items": [
            {
                "name": "name",
                "expression": "a + b",
                "origin_sql": "test",
                "no_data_config": {},
                "target": [[]],
                "algorithms": [
                    {"type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}
                ],
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "event",
                        "alias": "a",
                        "result_table_id": "xxxx",
                        "metric_field": "aaa",
                        "agg_condition": [],
                    }
                ],
            }
        ],
        "actions": [
            {
                "type": "operate",
                "config": {
                    "alarm_end_time": "23:59:59",
                    "send_recovery_alarm": False,
                    "alarm_start_time": "00:00:00",
                    "alarm_interval": 1440,
                },
                "notice_group_ids": [1],
            }
        ],
        "detects": [
            {
                "level": 1,
                "expression": "",
                "trigger_config": {"count": 1, "check_window": 2},
                "recovery_config": {"check_window": 2},
                "connector": "and",
            }
        ],
    }

    def test_save(self, clean_model):
        strategy = Strategy(**self.Config)
        strategy.save()

        query_config: QueryConfigModel = QueryConfigModel.objects.first()
        assert query_config is not None
        for field, value in self.Config["items"][0]["query_configs"][0].items():
            assert getattr(query_config, field, None) == value or query_config.config.get(field) == value
