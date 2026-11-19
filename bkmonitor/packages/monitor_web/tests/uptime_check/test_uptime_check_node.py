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

from core.errors.uptime_check import UptimeCheckProcessError


@pytest.mark.django_db(databases="__all__")
class TestUptimeCheckNode:
    def test_query_result_no_data(self, mocker):
        from monitor_web.uptime_check.views import UptimeCheckNodeViewSet

        validated_data = {
            "bk_biz_id": 2,
            "name": "\u4e2d\u56fd\u5e7f\u4e1c\u79fb\u52a8",
            "ip": "127.0.0.1",
            "carrieroperator": "\u79fb\u52a8",
            "location": {"country": "\u4e2d\u56fd", "city": "\u5e7f\u4e1c"},
            "plat_id": 0,
            "is_common": False,
        }

        query_result_mock = mocker.patch(
            "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql", return_value=[]
        )
        with pytest.raises(UptimeCheckProcessError):
            UptimeCheckNodeViewSet._node_beat_check(
                bk_biz_id=validated_data["bk_biz_id"],
                bk_host_id=validated_data.get("bk_host_id"),
                ip=validated_data.get("ip"),
                plat_id=validated_data.get("plat_id"),
            )
            query_result_mock.assert_called_once()


def test_get_beat_version_queries_hosts_by_their_own_business(mocker):
    """公共节点的主机属于其他业务，版本查询要带上每台主机所属业务。"""
    from types import SimpleNamespace

    from monitor_web.uptime_check.views import UptimeCheckNodeViewSet

    hosts = [SimpleNamespace(bk_host_id=1, bk_biz_id=2), SimpleNamespace(bk_host_id=2, bk_biz_id=3)]
    beat_plugin_status = mocker.patch(
        "monitor_web.uptime_check.views.host_queries.beat_plugin_status",
        return_value=[
            {
                "bk_host_id": 1,
                "inner_ip": "127.0.0.1",
                "inner_ipv6": "",
                "bk_cloud_id": 0,
                "plugin_status": [{"name": "bkmonitorbeat", "version": "3.6.0"}],
            },
        ],
    )

    result = UptimeCheckNodeViewSet._get_beat_version("tenant-a", hosts)

    beat_plugin_status.assert_called_once_with(bk_biz_ids=[2, 3], bk_host_ids=[1, 2], bk_tenant_id="tenant-a")
    # 同时按 bk_host_id 和 ip|云区域 记录，兼容无 bk_host_id 的旧节点
    assert result[1] == "3.6.0"
    assert "3.6.0" in result.values()
