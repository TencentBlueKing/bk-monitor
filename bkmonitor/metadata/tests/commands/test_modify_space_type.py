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
import pytest
from django.core.management import CommandError, call_command

from metadata import models

from .conftest import DEFAULT_DATA_ID

pytestmark = pytest.mark.django_db


def test_modify_space_type(create_and_delete_record):
    # 修改成功
    expected_type = "bkci"
    params = {"data_id": [DEFAULT_DATA_ID], "space_type_id": expected_type}
    call_command("modify_data_source_space_type", **params)
    # 检查是否更新
    ds = models.DataSource.objects.get(bk_data_id=DEFAULT_DATA_ID)
    assert ds.space_type_id == expected_type

    # 异常判断
    not_found_type = "notfound"
    with pytest.raises(CommandError):
        params = {"data_id": [DEFAULT_DATA_ID], "space_type_id": not_found_type}
        call_command("modify_data_source_space_type", **params)
