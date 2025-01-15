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
from unittest import mock

import pytest

from metadata import models
from metadata.models.constants import EsSourceType
from metadata.task import clean_disable_es_storage, manage_es_storage
from metadata.task.config_refresh import manage_disable_es_storage, refresh_es_storage


@pytest.fixture
def create_or_delete_records():
    # 集群一
    models.ESStorage.objects.create(
        table_id='1001_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=1,
        need_create_index=True,
    )

    # 集群二
    models.ESStorage.objects.create(
        table_id='2001_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=2,
        need_create_index=True,
    )

    # 集群三
    models.ESStorage.objects.create(
        table_id='3001_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=3,
        need_create_index=True,
    )

    # 禁用数据一
    models.ESStorage.objects.create(
        table_id='4001_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=4,
        need_create_index=True,
    )

    # 禁用数据二
    models.ESStorage.objects.create(
        table_id='5001_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=5,
        need_create_index=True,
    )

    models.ResultTable.objects.create(
        table_id='1001_test_bklog.table',
        is_enable=True,
        is_deleted=False,
        table_name_zh="test_1001",
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
        bk_biz_id=0,
    )
    models.ResultTable.objects.create(
        table_id='2001_test_bklog.table',
        is_enable=True,
        is_deleted=False,
        table_name_zh="test_2001",
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
        bk_biz_id=0,
    )
    models.ResultTable.objects.create(
        table_id='3001_test_bklog.table',
        is_enable=True,
        is_deleted=False,
        table_name_zh="test_3001",
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
        bk_biz_id=0,
    )
    models.ResultTable.objects.create(
        table_id='4001_test_bklog.table',
        is_enable=False,
        is_deleted=False,
        table_name_zh="test_3001",
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
        bk_biz_id=0,
    )
    models.ResultTable.objects.create(
        table_id='5001_test_bklog.table',
        is_enable=False,
        is_deleted=True,
        table_name_zh="test_3001",
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
        bk_biz_id=0,
    )

    yield
    models.ESStorage.objects.all().delete()
    models.ResultTable.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_refresh_es_storage(create_or_delete_records, mocker):
    """
    测试新版ES轮转周期任务能否正常执行
    """

    # MOCK白名单
    mocker.patch("metadata.task.config_refresh.settings.ENABLE_V2_ROTATION_ES_CLUSTER_IDS", [1])

    # MOCK过程中调用的逻辑
    mocker.patch("metadata.task.config_refresh._manage_es_storage")
    mocker.patch.object(manage_es_storage, 'delay')
    mock_logger = mocker.patch("metadata.task.config_refresh.logger")

    # 执行
    refresh_es_storage()

    # 根据打印日志情况，判断是否如期工作
    log_message_found = any(
        call == mock.call("refresh_es_storage:refresh cluster_id->[%s] is enable v2 rotation,count->[%s]", 1, 1)
        for call in mock_logger.info.call_args_list
    )

    log_message_not_found_es2 = any(
        call == mock.call("refresh_es_storage:refresh cluster_id->[%s] is enable v2 rotation,count->[%s]", 2, 1)
        for call in mock_logger.info.call_args_list
    )

    log_message_not_found_es3 = any(
        call == mock.call("refresh_es_storage:refresh cluster_id->[%s] is enable v2 rotation,count->[%s]", 3, 1)
        for call in mock_logger.info.call_args_list
    )

    assert log_message_found
    assert not log_message_not_found_es2
    assert not log_message_not_found_es3


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_manage_disable_es_storage(create_or_delete_records, mocker):
    """
    测试禁用采集项索引清理能力正常调度
    """
    # MOCK过程中调用的逻辑
    # mocker.patch("metadata.task.config_refresh._clean_disable_es_storage")
    mocker.patch.object(clean_disable_es_storage, 'delay')
    mock_logger = mocker.patch("metadata.task.config_refresh.logger")

    # 执行
    manage_disable_es_storage()

    # 根据打印日志情况，判断是否如期工作
    log_message_found = any(
        call
        == mock.call("manage_disable_es_storage:clean cluster_id->[%s] es_storages count->[%s]，now try to clean", 4, 1)
        for call in mock_logger.info.call_args_list
    )

    log_message_found_es2 = any(
        call
        == mock.call("manage_disable_es_storage:clean cluster_id->[%s] es_storages count->[%s]，now try to clean", 5, 1)
        for call in mock_logger.info.call_args_list
    )

    assert log_message_found
    assert log_message_found_es2
