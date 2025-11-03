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
from django.conf import settings

from metadata import models
from metadata.resources import GetOrCreateAgentEventDataIdResource


@pytest.mark.django_db(databases="__all__")
def test_get_or_create_agent_event_data_id_resource(mocker):
    """
    测试获取或创建agent事件数据id资源
    """
    expected = {
        "kind": "DataId",
        "metadata": {
            "namespace": "bkmonitor",
            "name": "test_data_id_name",
            "labels": {"bk_biz_id": "2"},
            "annotations": {"dataId": "123456", "index0": "123456"},
        },
        "spec": {
            "description": "test_data_id_name",
            "alias": "test_data_id_name",
            "bizId": 2,
            "region": None,
            "maintainers": ["system"],
            "predefined": None,
            "eventType": "metric",
        },
        "status": {
            "phase": "Ok",
            "start_time": "2025-05-27 00:17:01.329721720 UTC",
            "update_time": "2025-05-27 00:17:02.014463881 UTC",
            "message": "",
        },
    }

    # mock两个方法
    mocker.patch("core.drf_resource.api.bkdata.apply_data_link", return_value=None)
    mocker.patch("core.drf_resource.api.bkdata.get_data_link", return_value=expected)
    settings.ENABLE_V2_VM_DATA_LINK = True

    data = GetOrCreateAgentEventDataIdResource().request(bk_biz_id=7)

    data_id_ins = models.DataIdConfig.objects.get(name="base_7_agent_event")
    assert data_id_ins.bk_biz_id == 7
    assert data == {"bk_data_id": 123456}

    data = GetOrCreateAgentEventDataIdResource().request(bk_biz_id=7)
    assert data == {"bk_data_id": 123456}
