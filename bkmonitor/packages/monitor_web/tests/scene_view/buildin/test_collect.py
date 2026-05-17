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

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from monitor_web.scene_view.builtin.collect import _get_result_table_id


@pytest.mark.parametrize(
    ("plugin_type", "expected_group_name"),
    [
        ("Log", "Log_demo_plugin"),
        ("SNMP_Trap", "SNMP_Trap_demo_plugin"),
        ("SNMP_TRAP", "SNMP_Trap_demo_plugin"),
        (PluginType.LOG, "Log_demo_plugin"),
        (PluginType.SNMP_TRAP, "SNMP_Trap_demo_plugin"),
    ],
)
def test_get_result_table_id_uses_compatible_event_group_name_prefix(
    mocker, plugin_type: str, expected_group_name: str
) -> None:
    """日志类插件查询事件分组时应使用兼容的新旧统一前缀。"""

    mock_refresh = mocker.patch(
        "monitor_web.scene_view.builtin.collect.api.metadata.query_event_group.request.refresh",
        return_value=[{"table_id": "2_bkmonitor_time_series_123"}],
    )

    result = _get_result_table_id(plugin_type, "demo_plugin", "__default__", bk_biz_id=2)

    assert result == "2_bkmonitor_time_series_123"
    mock_refresh.assert_called_once_with(bk_biz_id=2, event_group_name=expected_group_name)
