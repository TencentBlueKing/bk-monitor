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
from unittest.mock import patch

import pytest

from metadata import models


@pytest.fixture
def create_or_update_records():
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    yield result_table
    result_table.delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_notify_bkdata_log_data_id_changed(create_or_update_records):
    """
    测试是否能够如期传递参数并通知计算平台，数据源发生改变
    """
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 使用 patch 来模拟 API 调用
    with patch('core.drf_resource.api.bkdata.notify_log_data_id_changed') as mock_notify:
        rt.notify_bkdata_log_data_id_changed(data_id=50010)

        # 验证 API 请求是否按照预期调用
        mock_notify.assert_called_once_with(data_id=50010)

        # 获取调用参数
        args, kwargs = mock_notify.call_args

        # 检查参数是否正确
        assert kwargs['data_id'] == 50010
