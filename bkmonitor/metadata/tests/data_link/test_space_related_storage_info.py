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
from metadata.models.vm.utils import get_vm_cluster_id_name_for_space


@pytest.fixture
def create_or_delete_records(mocker):
    models.ClusterInfo.objects.create(
        cluster_name='vm_1',
        cluster_id=111,
        domain_name='vm_1.test.com',
        is_default_cluster=True,
        port=80,
        cluster_type=models.ClusterInfo.TYPE_VM,
    )
    models.ClusterInfo.objects.create(
        cluster_name='vm_2',
        cluster_id=112,
        domain_name='vm_2.test.com',
        is_default_cluster=False,
        port=80,
        cluster_type=models.ClusterInfo.TYPE_VM,
    )
    models.SpaceRelatedStorageInfo.objects.create(
        space_type_id='bkcc', space_id='1', storage_type=models.ClusterInfo.TYPE_VM, cluster_id=112
    )
    yield
    models.ClusterInfo.objects.filter(cluster_name='vm_1').delete()
    models.ClusterInfo.objects.filter(cluster_name='vm_2').delete()
    models.SpaceRelatedStorageInfo.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_get_vm_cluster_id_name_for_space(create_or_delete_records):
    """
    测试能否正常获取到空间-VM集群关联信息
    """

    # Case1. 指定VM集群名称
    vm_data = get_vm_cluster_id_name_for_space(vm_cluster_name='vm_1')
    assert vm_data == {'cluster_id': 111, 'cluster_name': 'vm_1'}

    # Case2. 指定空间类型和空间ID,且该空间有对应的关联集群记录
    vm_data = get_vm_cluster_id_name_for_space(space_type='bkcc', space_id='1')
    assert vm_data == {'cluster_id': 112, 'cluster_name': 'vm_2'}

    # Case3. 指定空间类型和空间ID,且该空间没有对应的关联集群记录
    vm_data = get_vm_cluster_id_name_for_space(space_type='bkcc', space_id='2')
    assert vm_data == {'cluster_id': 111, 'cluster_name': 'vm_1'}
    space_vm_record = models.SpaceRelatedStorageInfo.objects.get(space_type_id='bkcc', space_id='2')
    assert space_vm_record.storage_type == models.ClusterInfo.TYPE_VM
    assert space_vm_record.cluster_id == 111

    # Case4. 未传递任何参数
    vm_data = get_vm_cluster_id_name_for_space()
    assert vm_data == {'cluster_id': 111, 'cluster_name': 'vm_1'}
