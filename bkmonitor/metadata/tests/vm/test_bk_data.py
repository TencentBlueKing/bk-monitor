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

pytestmark = pytest.mark.django_db
DEFAULT_RAW_DATA_ID = 100010
DEFAULT_VM_RT_ID = "test_vm_id"
DEFAULT_CLUSTER_ID = "BCS-K8S-00000"


@pytest.fixture
def create_and_delete_record(mocker):
    mocker.patch("django.dispatch.dispatcher.Signal.send", return_value=True)
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_RAW_DATA_ID,
        cluster_name="test_vm_cluster",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.domain.mq",
        port=9090,
        username="admin",
        password="1234",
        is_default_cluster=True,
        is_ssl_verify=False,
    )
    yield
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_RAW_DATA_ID, is_default_cluster=True).delete()
