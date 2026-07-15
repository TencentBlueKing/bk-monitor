"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from monitor_web.commons.data_access import UptimecheckDataAccessor


@pytest.mark.parametrize("protocol", ["HTTP", "TCP", "UDP", "ICMP"])
def test_uptimecheck_data_label_compatibility(mocker, protocol):
    mocker.patch("monitor_web.commons.data_access.bk_biz_id_to_bk_tenant_id", return_value="default")
    task = SimpleNamespace(bk_biz_id=2, protocol=protocol)

    accessor = UptimecheckDataAccessor(task)

    protocol = protocol.lower()
    assert accessor.data_label == f"uptimecheck_{protocol},uptimecheck.{protocol}"
