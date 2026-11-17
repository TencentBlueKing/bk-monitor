"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from pytest_mock import MockerFixture

from apm_web.models import Application


def test_get_metric_table_id_refreshes_after_data_source_sync(mocker: MockerFixture) -> None:
    get_table_id = Application.get_metric_table_id
    get_table_id.cache_clear()
    try:
        values_list = mocker.patch.object(Application.objects, "filter").return_value.values_list
        values_list.return_value = [""]

        assert get_table_id(2, "demo") == ""

        values_list.return_value = ["demo.__default__"]
        values_list.reset_mock()

        assert get_table_id(2, "demo") == "demo.__default__"
        assert get_table_id(2, "demo") == "demo.__default__"
        values_list.assert_called_once_with("metric_result_table_id", flat=True)
    finally:
        get_table_id.cache_clear()
