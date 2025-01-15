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

from metadata import models
from metadata.utils.basic import get_space_uid_and_bk_biz_id_by_bk_data_id


@pytest.fixture
def create_or_delete_records(mocker):
    models.SpaceDataSource.objects.create(space_type_id='bkci', space_id='test', bk_data_id=6001)

    models.SpaceDataSource.objects.create(space_type_id='bkcc', space_id=-100000002, bk_data_id=6002)

    models.SpaceResource.objects.create(space_type_id='bkci', space_id='test', resource_type='bkcc', resource_id=111)
    models.SpaceResource.objects.create(space_type_id='bkci', space_id='test2', resource_type='bkcc', resource_id=222)

    models.Space.objects.create(space_type_id='bkci', space_id='test2', id=100000002)


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_get_space_uid_and_bk_biz_id_by_bk_data_id(create_or_delete_records, mocker):
    """
    测试根据bk_data_id获取空间id和bk_biz_id
    """
    bk_biz_id, space_uid = get_space_uid_and_bk_biz_id_by_bk_data_id(bk_data_id=6001)
    assert space_uid == 'bkci__test'
    assert bk_biz_id == 111

    bk_biz_id, space_uid = get_space_uid_and_bk_biz_id_by_bk_data_id(bk_data_id=6002)
    assert space_uid == 'bkci__test2'
    assert bk_biz_id == 222

    bk_biz_id, space_uid = get_space_uid_and_bk_biz_id_by_bk_data_id(bk_data_id=6003)
    assert space_uid == ""
    assert bk_biz_id == 0
