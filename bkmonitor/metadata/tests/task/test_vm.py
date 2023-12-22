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
from metadata.task.vm import check_access_vm_task

pytestmark = pytest.mark.django_db


def test_check_access_vm_task(mocker, create_and_delete_record, table_id):
    # 移除掉已有的数据，然后进行创建
    models.AccessVMRecord.objects.filter(result_table_id=table_id).delete()
    mocker.patch(
        "metadata.models.vm.utils.access_vm_by_kafka",
        return_value={"clean_rt_id": 1, "bk_data_id": 1, "cluster_id": ""},
    )

    check_access_vm_task()

    # 校验写入到 kafka 数据及访问 vm 的记录
    assert models.KafkaStorage.objects.filter(table_id=table_id).exists()
    assert models.AccessVMRecord.objects.filter(result_table_id=table_id).exists()
