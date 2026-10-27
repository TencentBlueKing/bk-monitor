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
from metadata.models.space.constants import SpaceTypes
from metadata.service.vm_short_link import apply_vm_short_links, update_vm_short_links

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def vm_short_link_context(mocker):
    bk_tenant_id = "system"
    bk_biz_id = 315
    vmrt = "315_demo_vmrt"
    table_id = f"{vmrt}.__default__"
    cluster_name = "vm_short_link_cluster"

    models.Space.objects.create(
        bk_tenant_id=bk_tenant_id,
        space_type_id=SpaceTypes.BKCC.value,
        space_id=str(bk_biz_id),
        space_name="vm short link biz",
    )
    models.ClusterInfo.objects.create(
        bk_tenant_id=bk_tenant_id,
        cluster_name=cluster_name,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm-short-link.example.com",
        port=80,
        description="vm short link cluster",
        is_default_cluster=False,
    )
    mocker.patch(
        "metadata.service.vm_short_link.api.bkdata.get_result_table",
        return_value={
            "bk_biz_id": bk_biz_id,
            "result_table_name": "demo vmrt",
            "storages": {"vm": {"storage_cluster": {"cluster_name": cluster_name}}},
        },
    )
    mocker.patch.object(models.TimeSeriesGroup, "get_metrics_from_redis", return_value=[])
    mocker.patch.object(models.TimeSeriesGroup, "update_metrics", return_value=False)

    yield {
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_id": bk_biz_id,
        "vmrt": vmrt,
        "table_id": table_id,
    }

    models.VMShortLinkRecord.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).delete()
    models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id=table_id).delete()
    models.TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).delete()
    models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).delete()
    models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_name=cluster_name).delete()
    models.Space.objects.filter(
        bk_tenant_id=bk_tenant_id,
        space_type_id=SpaceTypes.BKCC.value,
        space_id=str(bk_biz_id),
    ).delete()


def test_apply_vm_short_links_supports_data_labels(vm_short_link_context):
    ctx = vm_short_link_context

    result = apply_vm_short_links(
        vmrts=[ctx["vmrt"]],
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        data_labels=["short_link_label", "short.link:label"],
        refresh_router=False,
    )

    result_table = models.ResultTable.objects.get(table_id=ctx["table_id"], bk_tenant_id=ctx["bk_tenant_id"])
    short_link = models.VMShortLinkRecord.objects.get(table_id=ctx["table_id"], bk_tenant_id=ctx["bk_tenant_id"])
    assert result_table.data_label == "short_link_label,short.link:label"
    assert short_link.data_labels == ["short_link_label", "short.link:label"]
    assert result[0]["data_labels"] == ["short_link_label", "short.link:label"]
    assert result[0]["data_label"] == "short_link_label,short.link:label"


def test_update_vm_short_links_supports_data_labels(vm_short_link_context):
    ctx = vm_short_link_context
    apply_vm_short_links(
        vmrts=[ctx["vmrt"]],
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        data_labels=["short_link_label"],
        refresh_router=False,
    )

    result = update_vm_short_links(
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        vmrts=[ctx["vmrt"]],
        data_labels=["updated_short_link_label", "updated.short:label"],
        refresh_bkbase=False,
        refresh_router=False,
    )

    result_table = models.ResultTable.objects.get(table_id=ctx["table_id"], bk_tenant_id=ctx["bk_tenant_id"])
    short_link = models.VMShortLinkRecord.objects.get(table_id=ctx["table_id"], bk_tenant_id=ctx["bk_tenant_id"])
    assert result_table.data_label == "updated_short_link_label,updated.short:label"
    assert short_link.data_labels == ["updated_short_link_label", "updated.short:label"]
    assert result[0]["data_labels"] == ["updated_short_link_label", "updated.short:label"]
    assert result[0]["data_label"] == "updated_short_link_label,updated.short:label"


def test_update_vm_short_links_refreshes_old_and_new_data_labels(vm_short_link_context, mocker):
    ctx = vm_short_link_context
    apply_vm_short_links(
        vmrts=[ctx["vmrt"]],
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        data_labels=["old_label"],
        refresh_router=False,
    )
    refresh_short_link_spaces = mocker.patch("metadata.service.vm_short_link._refresh_short_link_spaces")

    update_vm_short_links(
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        vmrts=[ctx["vmrt"]],
        data_labels=["new_label"],
        refresh_bkbase=False,
        refresh_router=True,
    )

    assert set(refresh_short_link_spaces.call_args.kwargs["data_labels"]) == {"old_label", "new_label"}


def test_apply_vm_short_links_overwrite_refreshes_old_and_new_data_labels(vm_short_link_context, mocker):
    ctx = vm_short_link_context
    apply_vm_short_links(
        vmrts=[ctx["vmrt"]],
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        data_labels=["old_label"],
        refresh_router=False,
    )
    refresh_short_link_spaces = mocker.patch("metadata.service.vm_short_link._refresh_short_link_spaces")

    apply_vm_short_links(
        vmrts=[ctx["vmrt"]],
        bk_tenant_id=ctx["bk_tenant_id"],
        bk_biz_id=ctx["bk_biz_id"],
        data_labels=["new_label"],
        overwrite=True,
        refresh_router=True,
    )

    assert set(refresh_short_link_spaces.call_args.kwargs["data_labels"]) == {"old_label", "new_label"}


@pytest.mark.parametrize(
    "data_labels",
    [
        ["1bad"],
        ["Bad"],
        ["bad-label"],
        ["bad,label"],
        ["a" * 33],
        "bad_string",
    ],
)
def test_apply_vm_short_links_validates_data_labels(vm_short_link_context, data_labels):
    ctx = vm_short_link_context

    with pytest.raises(ValueError):
        apply_vm_short_links(
            vmrts=[ctx["vmrt"]],
            bk_tenant_id=ctx["bk_tenant_id"],
            bk_biz_id=ctx["bk_biz_id"],
            data_labels=data_labels,
            refresh_router=False,
        )
