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
from django.core.management import call_command

from metadata import models

from .conftest import DEFAULT_DATA_ID

pytestmark = pytest.mark.django_db


def test_switch_transfer_for_dataid(create_and_delete_record):
    updated_transfer_cluster_id = "default1"
    call_command("switch_transfer_for_dataid", updated_transfer_cluster_id, data_id=[DEFAULT_DATA_ID])
    objs = models.DataSource.objects.get(bk_data_id=DEFAULT_DATA_ID)
    assert objs.transfer_cluster_id == updated_transfer_cluster_id
