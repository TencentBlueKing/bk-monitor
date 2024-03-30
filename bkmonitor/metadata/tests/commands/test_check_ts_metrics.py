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

import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from mockredis import mock_redis_client

from metadata import models

pytestmark = pytest.mark.django_db

DEFAULT_BK_DATA_ID = 1
DEFAULT_BK_BIZ_ID = 1
DEFAULT_TABLE_ID = "test.test_1"
DEFAULT_USERNAME = "system"
DEFAULT_FIELD_NAME = "test_field1"


@pytest.fixture
def create_and_delete():
    models.TimeSeriesGroup.objects.create(
        bk_data_id=DEFAULT_BK_DATA_ID,
        bk_biz_id=DEFAULT_BK_BIZ_ID,
        table_id=DEFAULT_TABLE_ID,
        creator=DEFAULT_USERNAME,
        last_modify_user=DEFAULT_USERNAME,
        time_series_group_name="test",
    )
    models.ResultTableField.objects.create(
        table_id=DEFAULT_TABLE_ID,
        field_name=DEFAULT_FIELD_NAME,
        description="",
        is_config_by_user=True,
        creator=DEFAULT_USERNAME,
        tag=models.ResultTableField.FIELD_TAG_DIMENSION,
    )
    yield
    models.TimeSeriesGroup.objects.filter(bk_data_id=DEFAULT_BK_DATA_ID).delete()
    models.ResultTableField.objects.all().delete()


def test_failed_case():
    params = {"action": "", "data_id": DEFAULT_BK_DATA_ID}
    with pytest.raises(CommandError):
        call_command("remove_time_series_metrics", **params)

    params = {"action": "", "data_id": None}
    with pytest.raises(CommandError):
        call_command("remove_time_series_metrics", **params)


def test_query(mocker, create_and_delete):
    """测试查询"""
    # mock redis 中的数据
    mock_redis_data = [
        {
            "field_name": DEFAULT_FIELD_NAME,
            "tag_value_list": {
                "bcs_cluster_id": {"last_update_time": 1667961028, "values": []},
                "bk_biz_id": {"last_update_time": 1667961028, "values": []},
                "time": {"last_update_time": 1667961028, "values": []},
                DEFAULT_FIELD_NAME: {"last_update_time": 1667961028, "values": []},
            },
            "last_modify_time": 1667961028.0,
        },
        {
            "field_name": "test_field2",
            "tag_value_list": {
                "bcs_cluster_id": {"last_update_time": 1667961028, "values": []},
                "bk_biz_id": {"last_update_time": 1667961028, "values": []},
            },
            "last_modify_time": 1667961028.0,
        },
    ]
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis", return_value=mock_redis_data
    )
    # 获取到输出
    out = StringIO()
    params = {"action": "query", "data_id": DEFAULT_BK_DATA_ID}
    # 执行命令
    call_command("check_ts_metrics", **params, stdout=out)
    # 解析输出
    output = out.getvalue()
    output = json.loads(output)
    assert output["result_table_exist_field"]["repeated_field"] == [DEFAULT_FIELD_NAME]
    assert len(output["redis_exist_field"]["repeated_field"]) == 1


def test_remove(mocker):
    """测试移除"""
    # mock redis client
    mocker.patch("packages.utils.redis_client.RedisClient.from_envs", side_effect=mock_redis_client)
    client = mock_redis_client()
    # 写入数据
    key = f"bkmonitor:metrics_{DEFAULT_BK_DATA_ID}"
    client.zadd(key, **{DEFAULT_FIELD_NAME: 1667961028})
    params = {"action": "delete", "data_id": DEFAULT_BK_DATA_ID, "metrics": DEFAULT_FIELD_NAME}
    # 执行命令
    call_command("check_ts_metrics", **params)
    # 检测已经删除
    assert client.zcount(key, 0, 100) == 0
    assert not models.ResultTableField.objects.filter(table_id=DEFAULT_TABLE_ID, field_name=DEFAULT_FIELD_NAME).exists()
