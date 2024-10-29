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
import time

import pytest

from metadata import models
from metadata.models.constants import EsSourceType
from metadata.task.config_refresh import refresh_es_storage_v2


@pytest.fixture
def create_or_delete_records():
    # 集群一
    models.ESStorage.objects.create(
        table_id='1001_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=1,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='1002_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=1,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='1003_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=1,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='1004_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=1,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='1005_test_bklog.table',
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
    models.ESStorage.objects.create(
        table_id='2002_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=2,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='2003_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=2,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='2004_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=2,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='2005_test_bklog.table',
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
    models.ESStorage.objects.create(
        table_id='3002_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=3,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='3003_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=3,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='3004_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=3,
        need_create_index=True,
    )
    models.ESStorage.objects.create(
        table_id='3005_test_bklog.table',
        source_type=EsSourceType.LOG.value,
        storage_cluster_id=3,
        need_create_index=True,
    )

    yield
    models.ESStorage.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_refresh_es_storage_v2(create_or_delete_records, mocker):
    """
    测试新版ES轮转周期任务能否正常执行
    1. 测试线程池是否正常并发工作，预期应该存在3个线程分别处理3个集群的采集项
    """

    start_time = time.time()
    refresh_es_storage_v2()
    end_time = time.time()

    execution_time = end_time - start_time
    assert 10 < execution_time < 22
