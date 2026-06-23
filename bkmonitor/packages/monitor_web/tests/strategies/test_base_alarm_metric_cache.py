"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import pytest
from django.test import override_settings

from monitor_web.strategies.metric_list_cache import BaseAlarmMetricCacheManager

pytestmark = pytest.mark.django_db


class TestBaseAlarmMetricCacheManagerMultiTenant:
    """系统事件指标缓存的多租户内置行为。

    本次修复点：解开 BaseAlarmMetricCacheManager 在多租户下「暂不内置系统事件」的总闸，
    但保持选择性——多租户仅内置 proc_port/os_restart 两个 bk_monitor 源伪事件
    （底层 system.proc_port/system.env 时序在多租户同样产出），gse 系统事件与 gse 进程
    托管事件继续走 V4 custom 链路（CustomEventCacheManager + os/v2）。否则 os/v1 的 gse
    事件（bk_monitor 源）会与 os/v2 的 custom 版重复创建、产生双告警。
    """

    def _fields_in_mode(self, multi_tenant: bool) -> set:
        mgr = BaseAlarmMetricCacheManager(bk_tenant_id="tenant", bk_biz_id=0)
        with override_settings(ENABLE_MULTI_TENANT_MODE=multi_tenant):
            # get_label_name 会调 api.metadata，测试中直接打桩为标签原值
            with mock.patch.object(BaseAlarmMetricCacheManager, "get_label_name", side_effect=lambda label: label):
                return {metric["metric_field"] for metric in mgr.get_metrics_by_table({})}

    def test_get_available_biz_ids_includes_zero_in_both_modes(self):
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            assert BaseAlarmMetricCacheManager.get_available_biz_ids("tenant") == [0]
        with override_settings(ENABLE_MULTI_TENANT_MODE=False):
            assert BaseAlarmMetricCacheManager.get_available_biz_ids("tenant") == [0]

    def test_get_tables_yields_in_multi_tenant(self):
        mgr = BaseAlarmMetricCacheManager(bk_tenant_id="tenant", bk_biz_id=0)
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            assert list(mgr.get_tables()) == [{}]

    def test_multi_tenant_yields_only_proc_port_and_os_restart(self):
        # 多租户：catalog 只产出 proc_port/os_restart（gse 系统事件 + gse 进程托管事件均不在此）
        assert self._fields_in_mode(multi_tenant=True) == {"proc_port", "os_restart"}

    def test_single_tenant_still_includes_gse_process_event(self):
        # 单租户：proc_port/os_restart 之外，仍内置 gse 进程托管事件（多租户不含，构成差异守护）
        fields = self._fields_in_mode(multi_tenant=False)
        assert {"proc_port", "os_restart", "gse_process_event"} <= fields
        # 多租户相对单租户的差异：恰好少了 gse 进程托管事件
        assert "gse_process_event" not in self._fields_in_mode(multi_tenant=True)
