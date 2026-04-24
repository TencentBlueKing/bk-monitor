"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

from kernel_api.rpc.functions.admin.datasource import _serialize_datasource
from kernel_api.rpc.functions.admin.result_table import _serialize_result_table_detail
from kernel_api.rpc.registry import KernelRPCRegistry


def test_admin_rpc_functions_registered_by_builtin_loader():
    func_names = {function["func_name"] for function in KernelRPCRegistry.list_functions()}

    assert {
        "admin.datasource.list",
        "admin.datasource.detail",
        "admin.result_table.list",
        "admin.result_table.detail",
        "admin.result_table.field_list",
        "admin.result_table.field_options",
    } <= func_names

    detail = KernelRPCRegistry.get_function_detail("admin.result_table.detail")
    assert detail is not None
    assert detail["params_schema"]["include"].find("fields") != -1


def test_datasource_serializer_masks_token():
    datasource = SimpleNamespace(
        bk_data_id=50010,
        bk_tenant_id="system",
        data_name="demo",
        data_description="demo datasource",
        type_label="time_series",
        source_label="bk_monitor",
        custom_label=None,
        source_system="bk_monitor",
        is_enable=True,
        is_custom_source=True,
        is_platform_data_id=False,
        space_type_id="bkcc",
        space_uid="bkcc__2",
        created_from="bkdata",
        mq_cluster_id=1,
        mq_config_id=2,
        transfer_cluster_id="default",
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
        token="secret-token",
    )

    item = _serialize_datasource(datasource)

    assert "token" not in item
    assert item["has_token"] is True


def test_result_table_detail_serializer_does_not_return_fields():
    result_table = SimpleNamespace(
        table_id="system.cpu",
        bk_tenant_id="system",
        table_name_zh="CPU",
        bk_biz_id=2,
        bk_biz_id_alias="",
        schema_type="fixed",
        default_storage="influxdb",
        label="os",
        data_label="bk_monitor",
        labels={},
        is_custom_table=False,
        is_builtin=True,
        is_enable=True,
        is_deleted=False,
        creator="admin",
        create_time=None,
        last_modify_user="admin",
        last_modify_time=None,
    )

    item = _serialize_result_table_detail(result_table)

    assert item["table_id"] == "system.cpu"
    assert "fields" not in item
