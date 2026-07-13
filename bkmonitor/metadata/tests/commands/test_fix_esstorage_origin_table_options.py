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
from metadata.management.commands.fix_esstorage_origin_table_options import Command

pytestmark = pytest.mark.django_db(databases="__all__")


def test_fill_esstorage_index_set_filters_by_tenant_and_biz():
    target = models.ESStorage.objects.create(
        bk_tenant_id="system",
        table_id="100147_bklog.target",
        storage_cluster_id=1,
        index_set="",
    )
    other_biz = models.ESStorage.objects.create(
        bk_tenant_id="system",
        table_id="100148_bklog.other_biz",
        storage_cluster_id=1,
        index_set="",
    )
    other_tenant = models.ESStorage.objects.create(
        bk_tenant_id="other",
        table_id="100147_bklog.other_tenant",
        storage_cluster_id=1,
        index_set="",
    )

    table_ids = Command().fill_esstorage_index_set("system", 100147, dry_run=False)

    target.refresh_from_db()
    other_biz.refresh_from_db()
    other_tenant.refresh_from_db()
    assert table_ids == [target.table_id]
    assert target.index_set == "100147_bklog_target"
    assert other_biz.index_set == ""
    assert other_tenant.index_set == ""


def test_fill_rt_options_creates_one_time_field_for_multiple_virtual_tables():
    default_origin_table_id = "100147_bklog.default_origin"
    inherited_origin_table_id = "100147_bklog.inherited_origin"
    es_storages = [
        models.ESStorage(
            bk_tenant_id="system",
            table_id=default_origin_table_id,
            storage_cluster_id=1,
        ),
        models.ESStorage(
            bk_tenant_id="system",
            table_id=f"{default_origin_table_id}.__virtual_1__",
            origin_table_id=default_origin_table_id,
            storage_cluster_id=1,
        ),
        models.ESStorage(
            bk_tenant_id="system",
            table_id=f"{default_origin_table_id}.__virtual_2__",
            origin_table_id=default_origin_table_id,
            storage_cluster_id=1,
        ),
        models.ESStorage(
            bk_tenant_id="system",
            table_id=inherited_origin_table_id,
            storage_cluster_id=1,
        ),
        models.ESStorage(
            bk_tenant_id="system",
            table_id=f"{inherited_origin_table_id}.__virtual_1__",
            origin_table_id=inherited_origin_table_id,
            storage_cluster_id=1,
        ),
        models.ESStorage(
            bk_tenant_id="system",
            table_id=f"{inherited_origin_table_id}.__virtual_2__",
            origin_table_id=inherited_origin_table_id,
            storage_cluster_id=1,
        ),
    ]
    models.ESStorage.objects.bulk_create(es_storages)
    inherited_time_field = '{"name":"timestamp","type":"date","unit":"millisecond"}'
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=f"{inherited_origin_table_id}.__virtual_2__",
        name="time_field",
        value=inherited_time_field,
        value_type="dict",
        creator="system",
    )

    Command().fill_rt_options("system", 100147, dry_run=False)

    default_options = models.ResultTableOption.objects.filter(
        bk_tenant_id="system", table_id=default_origin_table_id, name="time_field"
    )
    inherited_options = models.ResultTableOption.objects.filter(
        bk_tenant_id="system", table_id=inherited_origin_table_id, name="time_field"
    )
    assert default_options.count() == 1
    assert default_options.get().value == '{"name":"dtEventTimeStamp","type":"date","unit":"millisecond"}'
    assert inherited_options.count() == 1
    assert inherited_options.get().value == inherited_time_field


def test_handle_refreshes_changed_tables_for_specified_biz(mocker):
    command = Command()
    mocker.patch.object(command, "fill_esstorage_index_set", return_value=["100147_bklog.index"])
    mocker.patch.object(command, "fill_rt_options", return_value=["100147_bklog.option", "100147_bklog.index"])
    refresh_routes = mocker.patch.object(command, "refresh_routes")

    command.handle(bk_tenant_id="system", bk_biz_id=100147, dry_run=False)

    refresh_routes.assert_called_once_with("system", ["100147_bklog.index", "100147_bklog.option"])


@pytest.mark.parametrize(
    ("bk_biz_id", "dry_run"),
    [
        (0, False),
        (100147, True),
    ],
)
def test_handle_skips_refresh_without_biz_or_in_dry_run(mocker, bk_biz_id, dry_run):
    command = Command()
    mocker.patch.object(command, "fill_esstorage_index_set", return_value=["100147_bklog.index"])
    mocker.patch.object(command, "fill_rt_options", return_value=["100147_bklog.option"])
    refresh_routes = mocker.patch.object(command, "refresh_routes")

    command.handle(bk_tenant_id="system", bk_biz_id=bk_biz_id, dry_run=dry_run)

    refresh_routes.assert_not_called()
