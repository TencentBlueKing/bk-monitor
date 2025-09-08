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


from django.db.models import QuerySet

from bkmonitor.models import SnapshotHostIndex
from core.drf_resource import resource
from tests.web.performance import mock_request


class TestHostIndex(object):
    def test_perform_request(self, mocker):
        host_index_one = SnapshotHostIndex(
            category="cpu",
            description="CPU总使用率",
            dimension_field="",
            id=7,
            conversion_unit="%",
            is_linux=1,
            is_aix=1,
            is_windows=1,
        )
        host_index_two = SnapshotHostIndex(
            category="net",
            description="ESTABLISHED连接数",
            dimension_field="",
            id=110,
            conversion_unit="",
            is_linux=1,
            is_aix=1,
            is_windows=1,
        )

        mocker.patch(
            "bkmonitor.models.base.SnapshotHostIndex.objects.filter", return_value=[host_index_one, host_index_two]
        )

        mocker.patch("monitor.models.GlobalConfig.objects.filter", return_value=QuerySet())

        mocker.patch("django.db.models.query.QuerySet.exists", return_value=False)

        mock_request(mocker, "admin", 2)

        get_key_alias = mocker.patch(
            "monitor_web.commons.data.resources.api.metadata.get_result_table",
            return_value={"field_list": [{"field_name": "device_type", "description": "desc"}]},
        )

        mocker.patch("django.db.models.base.Model.save")

        mocker.patch("monitor.models.GlobalConfig.objects.create")

        assert resource.performance.host_index.request() == [
            {
                "category": "CPU",
                "category_id": "cpu",
                "description": "CPU总使用率",
                "dimension_field": "",
                "dimension_field_value": "",
                "index_id": 7,
                "os": ["linux", "windows", "aix"],
                "unit_display": "%",
            },
            {
                "category": "网络",
                "category_id": "net",
                "description": "ESTABLISHED连接数",
                "dimension_field": "",
                "dimension_field_value": "",
                "index_id": 110,
                "os": ["linux", "windows", "aix"],
                "unit_display": "",
            },
        ]

        get_key_alias.assert_called_once_with(table_id="2_system_disk")
