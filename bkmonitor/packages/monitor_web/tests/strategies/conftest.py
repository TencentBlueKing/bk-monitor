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

from bkmonitor.models import StrategyLabel, StrategyModel, DefaultStrategyBizAccessModel
from bkmonitor.models.metric_list_cache import MetricListCache


@pytest.fixture
def add_strategy_label():
    StrategyLabel.objects.all().delete()

    StrategyLabel.objects.create(
        **{
            "label_name": "/k8s_系统内置/",
            "bk_biz_id": 2,
            "strategy_id": 1,
        }
    )
    StrategyLabel.objects.create(
        **{
            "label_name": "/kube-pod/",
            "bk_biz_id": 3,
            "strategy_id": 2,
        }
    )


@pytest.fixture
def add_default_strategy_biz_access():
    DefaultStrategyBizAccessModel.objects.all().delete()

    DefaultStrategyBizAccessModel.objects.create(
        **{
            "create_user": "admin",
            "bk_biz_id": 2,
            "version": "v2",
            "access_type": "os",
        }
    )
    DefaultStrategyBizAccessModel.objects.create(
        **{
            "create_user": "admin",
            "bk_biz_id": 2,
            "version": "v2",
            "access_type": "gse",
        }
    )
    DefaultStrategyBizAccessModel.objects.create(
        **{
            "create_user": "admin",
            "bk_biz_id": 2,
            "version": "v2",
            "access_type": "k8s",
        }
    )


@pytest.fixture
def add_strategy_model():
    StrategyModel.objects.all().delete()

    StrategyModel.objects.create(
        **{
            "name": "CPU总使用率",
            "bk_biz_id": 2,
            "source": "bk_monitorv3",
            "scenario": "os",
            "type": "monitor",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "create_user": "admin",
            "update_user": "admin",
            "app": "",
            "path": "",
            "hash": "",
            "snippet": "",
        }
    )
    StrategyModel.objects.create(
        **{
            "name": "进程端口",
            "bk_biz_id": 2,
            "source": "bk_monitorv3",
            "scenario": "host_process",
            "type": "monitor",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "create_user": "admin",
            "update_user": "admin",
            "app": "",
            "path": "",
            "hash": "",
            "snippet": "",
        }
    )


@pytest.fixture
def add_metric_list_cache():
    MetricListCache.objects.all().delete()

    MetricListCache.objects.create(
        **{
            "bk_biz_id": 0,
            "category_display": "物理机",
            "collect_config": "",
            "collect_config_ids": "",
            "collect_interval": 1,
            "data_source_label": "bk_monitor",
            "data_target": "host_target",
            "data_type_label": "time_series",
            "default_condition": [],
            "default_dimensions": ["bk_target_ip", "bk_target_cloud_id"],
            "description": "CPU使用率",
            "dimensions": [
                {"id": "ip", "is_dimension": True, "name": "采集器IP", "type": "string"},
                {"id": "hostname", "is_dimension": True, "name": "主机名", "type": "string"},
                {"id": "device_name", "is_dimension": True, "name": "设备名", "type": "string"},
                {"id": "bk_biz_id", "is_dimension": True, "name": "业务ID", "type": "string"},
                {"id": "bk_cloud_id", "is_dimension": True, "name": "采集器云区域ID", "type": "string"},
                {"id": "bk_target_ip", "is_dimension": True, "name": "目标IP", "type": "string"},
                {"id": "bk_target_cloud_id", "is_dimension": True, "name": "云区域ID", "type": "string"},
            ],
            "extend_fields": {},
            "metric_field": "usage",
            "metric_field_name": "CPU使用率",
            "plugin_type": "",
            "related_id": "system",
            "related_name": "system",
            "result_table_id": "system.cpu_summary",
            "result_table_label": "os",
            "result_table_label_name": "操作系统",
            "result_table_name": "CPU",
            "unit": "percent",
            "unit_conversion": 1.0,
            "use_frequency": 6,
        }
    )
