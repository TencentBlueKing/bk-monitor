"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from metadata.task.vm import check_access_vm_task

pytestmark = pytest.mark.django_db(databases="__all__")


def test_check_access_vm_task(mocker, create_and_delete_record, table_id):
    # 移除掉已有的数据，然后进行创建
    models.AccessVMRecord.objects.filter(result_table_id=table_id).delete()
    mock_apply_datalink = mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)

    check_access_vm_task()

    assert mock_apply_datalink.call_count > 0
    assert all(call_args.kwargs == {"delay": False} for call_args in mock_apply_datalink.call_args_list)
    target_calls = [
        call_args for call_args in mock_apply_datalink.call_args_list if call_args.args[0].table_id == table_id
    ]
    assert len(target_calls) == 1
