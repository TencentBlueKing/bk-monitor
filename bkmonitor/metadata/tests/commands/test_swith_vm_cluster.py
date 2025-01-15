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

from .conftest import DEFAULT_NAME, DEFAULT_VM_CLUSTER_ID, DEFAULT_VM_CLUSTER_ID_ONE


def test_switch_vm_cluster_error():
    # 无参数
    with pytest.raises(CommandError):
        call_command("switch_vm_cluster")

    # 无目的vm集群参数
    with pytest.raises(CommandError):
        call_command("switch_vm_cluster", {"src_vm_ids": "1"})

    # 无源vm集群参数
    with pytest.raises(CommandError):
        call_command("switch_vm_cluster", {"dst_vm_id": "1"})


def test_switch_vm_cluster_success(create_and_delete_record):
    params = {"src_vm_ids": DEFAULT_VM_CLUSTER_ID, "dst_vm_id": DEFAULT_VM_CLUSTER_ID_ONE}
    call_command("switch_vm_cluster", **params)
    # 校验vm记录中使用的集群ID，已经切换为DEFAULT_VM_CLUSTER_ID_ONE
    obj = models.AccessVMRecord.objects.filter(result_table_id=DEFAULT_NAME)
    assert obj.exists()
    assert obj.first().vm_cluster_id == DEFAULT_VM_CLUSTER_ID_ONE
