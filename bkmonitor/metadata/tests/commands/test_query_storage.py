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

from metadata.tests.commands.conftest import (
    DEFAULT_DATA_ID,
    DEFAULT_DATA_ID_ONE,
    DEFAULT_NAME,
)

pytestmark = pytest.mark.django_db


def test_query_storage(create_and_delete_record):
    out = StringIO()
    params = {"bk_data_id": DEFAULT_DATA_ID}
    call_command("query_storage", **params, stdout=out)
    output = out.getvalue()
    output = json.loads(output)

    assert isinstance(output, list)
    # 确认字段包含输出内容
    keys = [
        'bk_biz_info',
        'transfer_cluster',
        'kafka_config',
        'elasticsearch',
        'influxdb',
        'redis',
        'kafka',
        'bkdata',
        'argus',
        'influxdb_instance_cluster',
        'data_source',
        'victoria_metrics',
        'result_table',
    ]
    assert not (set(keys) - set(output[0].keys()))
    assert output[0]["kafka_config"]["topic"] == DEFAULT_NAME
    assert "vm_cluster_domain" in output[0]["victoria_metrics"]


def test_only_datasource_query_storage(create_and_delete_record):
    """测试仅包含数据源的场景"""
    out = StringIO()
    params = {"bk_data_id": DEFAULT_DATA_ID_ONE}
    call_command("query_storage", **params, stdout=out)
    output = out.getvalue()
    output = json.loads(output)

    assert isinstance(output, list)
    # 返回字段匹配
    assert {"data_source", "transfer_cluster", "kafka_config"} == set(output[0].keys())
    assert output[0]["data_source"]["bk_data_id"] == DEFAULT_DATA_ID_ONE


def test_query_storage_not_exist(create_and_delete_table_storage, create_and_delete_record):
    """测试仅有部分链路的场景"""
    params = {"table_id": f"{DEFAULT_NAME}1"}
    call_command("query_storage", **params)


def test_query_storage_params_error():
    """测试错误的场景"""
    params = {"data_id": "123"}
    with pytest.raises(Exception):
        call_command("query_storage", **params)

    params = {"metric_name": "container_spec_memory_limit_bytes"}
    with pytest.raises(CommandError):
        call_command("query_storage", **params)
