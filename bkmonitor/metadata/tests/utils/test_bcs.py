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
from metadata.utils.bcs import get_bcs_space_by_biz

pytestmark = pytest.mark.django_db

FAKE_PROJECT_ID = "testbcs"


@pytest.fixture
def create_or_delete_records():
    space_records = [
        models.Space(id=1, space_type_id="bkcc", space_name="bkccname", space_id="1", space_code=""),
        models.Space(id=2, space_type_id="bkci", space_name="testbkci", space_id="testbkci", space_code=""),
        models.Space(
            id=3, space_type_id="bkci", space_name="testbcs1", space_id="testbcs1", space_code=FAKE_PROJECT_ID
        ),
    ]

    models.Space.objects.bulk_create(space_records)
    yield
    models.Space.objects.all().delete()


@pytest.mark.parametrize(
    "bk_biz_ids, expected_list",
    [
        ([], []),
        (None, []),
        ([-2, -3], [{"space_type_id": "bkci", "space_id": "testbcs1", "space_code": FAKE_PROJECT_ID}]),
        ([0, 1], []),
        ([-2, 0, 1], []),
        ([-3, 0, 1], [{"space_type_id": "bkci", "space_id": "testbcs1", "space_code": FAKE_PROJECT_ID}]),
    ],
)
def test_get_project_ids(create_or_delete_records, bk_biz_ids, expected_list):
    space = get_bcs_space_by_biz(bk_biz_ids)
    assert space == expected_list
