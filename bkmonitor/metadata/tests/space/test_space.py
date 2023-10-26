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

from metadata.models.space import utils
from metadata.models.space.constants import MeasurementType
from metadata.models.space.space_redis import SpaceRedis

from .conftest import DEFAULT_DATA_ID, DEFAULT_SPACE_ID, DEFAULT_SPACE_TYPE

pytestmark = pytest.mark.django_db


def test_get_platform_data_id_list(create_and_delete_record):
    """获取全空间的 data id 列表"""
    data_id_list = utils.get_platform_data_id_list()
    assert len(data_id_list) == 1
    assert DEFAULT_DATA_ID + 2 in data_id_list


def test_get_space_data_id_list(create_and_delete_record):
    """获取空间级的 data id 列表"""
    data_id_list = utils.get_space_data_id_list(DEFAULT_SPACE_TYPE)
    assert len(data_id_list) == 1
    assert DEFAULT_DATA_ID + 1 in data_id_list


def test_check_filter(create_and_delete_record):
    client = SpaceRedis()

    # bk_standard_v3_time_series
    need_add = client._is_need_add_filter(
        measurement_type=MeasurementType.BK_STANDARD_V2_TIME_SERIES.value,
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        data_id=DEFAULT_DATA_ID,
    )
    assert not need_add

    # bk_split
    need_add = client._is_need_add_filter(
        measurement_type=MeasurementType.BK_SPLIT.value,
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        data_id=DEFAULT_DATA_ID,
    )
    assert not need_add

    # bk_exporter
    need_add = client._is_need_add_filter(
        measurement_type=MeasurementType.BK_EXPORTER.value,
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        data_id=DEFAULT_DATA_ID,
    )
    assert need_add

    # platform and belong a space
    need_add = client._is_need_add_filter(
        measurement_type=MeasurementType.BK_STANDARD_V2_TIME_SERIES.value,
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        data_id=DEFAULT_DATA_ID + 1,
    )
    assert not need_add

    # platform and not belong a space
    need_add = client._is_need_add_filter(
        measurement_type=MeasurementType.BK_STANDARD_V2_TIME_SERIES.value,
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        data_id=DEFAULT_DATA_ID + 2,
    )
    assert need_add
