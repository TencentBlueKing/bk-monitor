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
from django.core.management import call_command

from metadata.tests.commands.conftest import (
    DEFAULT_BIZ_ID,
    DEFAULT_DATA_ID,
    DEFAULT_NAME,
)

pytestmark = pytest.mark.django_db


def test_success(create_and_delete_record):
    out = StringIO()
    params = {"bk_biz_id": DEFAULT_BIZ_ID}
    call_command("query_table_id_and_data_id", **params, stdout=out)
    output = out.getvalue()
    output = json.loads(output)
    # 判断key存在，并且值正确
    assert len(output) == 1
    for i in output:
        assert set(i.keys()) == {"table_id", "bk_data_id"}
        assert i["table_id"] == DEFAULT_NAME
        assert i["bk_data_id"] == DEFAULT_DATA_ID

    # 查询为空
    out = StringIO()
    params = {"bk_biz_id": 2100}
    call_command("query_table_id_and_data_id", **params, stdout=out)
    output = out.getvalue()
    output = json.loads(output)
    # 判断key存在，并且值正确
    assert type(output) == list
    assert not output


def test_fail(create_and_delete_record):
    with pytest.raises(Exception):
        call_command("query_table_id_and_data_id")
