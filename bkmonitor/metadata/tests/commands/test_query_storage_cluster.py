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

from metadata.tests.commands.conftest import DEFAULT_NAME

pytestmark = pytest.mark.django_db


def test_query_storage(create_and_delete_record):
    out = StringIO()
    # 查询为空
    params = {"domains": ""}
    call_command("query_storage_cluster", **params, stdout=out)
    output = out.getvalue()
    assert output == "please input domains\n"

    # 查询为空
    out = StringIO()
    params = {"domains": DEFAULT_NAME}
    call_command("query_storage_cluster", **params, stdout=out)
    output = out.getvalue()
    output = json.loads(output)
    # 判断key存在，并且值正确
    assert isinstance(output, list)
    assert output[0]["domain_name"] == DEFAULT_NAME
