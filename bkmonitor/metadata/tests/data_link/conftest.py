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

DEFAULT_NAME = "test_demo"
DEFAULT_VM_NAME = "vm_cluster"
DEFAULT_SPACE_TYPE = "bkcc"
DEFAULT_SPACE_ID = "1"
DEFAULT_VM_CLUSTER_ID = 1011


@pytest.fixture
def create_and_delete_data_link():
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_VM_CLUSTER_ID,
        cluster_name=DEFAULT_NAME,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.com",
        port=1234,
        description="",
        is_default_cluster=False,
    )
    models.SpaceVMInfo.objects.create(
        space_type=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        vm_cluster_id=DEFAULT_VM_CLUSTER_ID,
    )
    yield
    models.SpaceVMInfo.objects.filter(
        space_type=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, vm_cluster_id=1
    ).delete()
    models.ClusterInfo.objects.filter(cluster_id=1).delete()
