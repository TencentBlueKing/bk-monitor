"""V4 输出经过 Metadata 分页、指标缓存及前端选择器查询的回归。"""

import pytest
from django.utils import timezone

from api.metadata.default import ListMonitorResultTableResource
from bkmonitor.models import MetricListCache
from kernel_api.resource import recording_rule as rule_api
from metadata import models
from metadata.resources import ListResultTableResource
from metadata.tests.record_rule.test_v4_operator import (
    TENANT_ID,
    external_api as _external_api,
    v4_base_data as _v4_base_data,
)
from metadata.tests.record_rule.test_v4_public_api import group, public_context as _public_context
from metadata.utils.data_link import get_record_rule_metrics_by_biz_id
from monitor_web.strategies.metric_list_cache import BkmonitorMetricCacheManager
from monitor_web.strategies.resources import v2 as selector

external_api = _external_api
v4_base_data = _v4_base_data
public_context = _public_context

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def metric_context(public_context, mocker):
    # 仅替换服务边界，实际执行适配器、Metadata 查询、缓存写入和选择器过滤。
    tenant = [TENANT_ID]
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", side_effect=lambda **kw: tenant[0])
    mocker.patch.object(selector, "get_request_tenant_id", side_effect=lambda: tenant[0])
    mocker.patch.object(selector, "bk_biz_id_to_bk_tenant_id", side_effect=lambda biz: tenant[0])
    mocker.patch.object(selector, "get_source_app", return_value="")
    mocker.patch.object(selector.resource.commons, "get_label", return_value=[])
    mocker.patch.object(BkmonitorMetricCacheManager, "get_label_name", side_effect=lambda label: label)
    mocker.patch("api.metadata.default.api.metadata.list_result_table", side_effect=ListResultTableResource().request)
    return tenant


def search(biz_id, query):
    return selector.GetMetricListV2Resource().request(
        bk_biz_id=biz_id,
        data_source_label=["bk_monitor"],
        data_type_label="time_series",
        conditions=[{"key": "query", "value": query}],
    )["metric_list"]


@pytest.mark.parametrize("multi_tenant", [False, True])
def test_create_refresh_search_and_soft_delete(metric_context, public_context, settings, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    config = group("selector_cpu")
    config["bkmonitor"]["data_label"] = "selector_cpu"
    created = rule_api.CreateConfigResource().request(bk_biz_id=2, config=config, apply=True)
    rule = models.RecordRuleV4.objects.get(pk=created["rule"]["id"])
    assert created["execution"]["succeeded"]
    assert not models.DataSourceResultTable.objects.filter(table_id=rule.table_id).exists()

    manager = BkmonitorMetricCacheManager(bk_tenant_id=TENANT_ID, bk_biz_id=2)
    manager._run()
    manager._run()  # 重复刷新不产生重复指标。
    [cached] = MetricListCache.objects.filter(bk_tenant_id=TENANT_ID, result_table_id=rule.table_id)
    assert cached.bk_biz_id == 2
    assert cached.metric_field == "cpu_avg"
    assert cached.related_id == "bk_pre_cal"
    assert cached.readable_name == "selector_cpu.cpu_avg"
    for query in ("cpu_avg", rule.table_id, "selector_cpu"):
        [metric] = search(2, query)
        assert metric["result_table_id"] == rule.table_id
        assert metric["data_source_label"] == "bk_monitor" and metric["data_type_label"] == "time_series"
        assert metric["promql_metric"] == "bkmonitor:selector_cpu:cpu_avg"
    assert not search(3, "cpu_avg")
    metric_context[0] = "another_tenant"
    assert not search(2, "cpu_avg")
    metric_context[0] = TENANT_ID

    # 其他租户的同名缓存不能被本租户的刷新或软删除清掉。
    cached.pk = None
    cached.bk_tenant_id = "another_tenant"
    cached.save()
    public_context.delete_data_link.side_effect = RuntimeError("Flow deletion unavailable")
    deleted = rule_api.DeleteConfigResource().request(bk_biz_id=2, id=rule.pk)
    assert not deleted["execution"]["succeeded"]
    manager._run()
    assert not search(2, "cpu_avg")
    assert MetricListCache.objects.filter(bk_tenant_id="another_tenant", result_table_id=rule.table_id).exists()
    assert models.ResultTableField.objects.filter(bk_tenant_id=TENANT_ID, table_id=rule.table_id).exists()
    assert rule.specs.exists() and rule.resolved.exists() and rule.flows.exists()


def add_output(tenant, space_type, space_id, biz_id, suffix, **rule_fields):
    table_id = f"bkm_rr_{suffix}.__default__"
    rule = models.RecordRuleV4.objects.create(
        bk_tenant_id=tenant,
        space_type=space_type,
        space_id=space_id,
        name=suffix,
        table_id=table_id,
        flow_name=suffix,
        dst_vm_table_id=f"2_{suffix}",
        **rule_fields,
    )
    models.ResultTable.objects.create(bk_tenant_id=tenant, bk_biz_id=biz_id, table_id=table_id, is_custom_table=True)
    models.ResultTableField.objects.create(
        bk_tenant_id=tenant,
        table_id=table_id,
        field_name="cpu_avg",
        field_type="float",
        tag="metric",
        is_config_by_user=True,
    )
    return rule


@pytest.mark.parametrize("multi_tenant", [False, True])
def test_non_bkcc_space_and_tenant_isolation(metric_context, settings, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    # 不同空间类型允许相同 space_id，负数 ID 必须使用实际 Space 主键定位。
    space = models.Space.objects.create(
        bk_tenant_id=TENANT_ID, space_type_id="bkci", space_id="2", space_name="ci-project"
    )
    biz_id = -space.pk
    visible = add_output(TENANT_ID, "bkci", "2", biz_id, "project")
    add_output(TENANT_ID, "bkcc", "2", 2, "business")
    add_output("another_tenant", "bkci", "2", biz_id, "other_tenant")
    add_output(TENANT_ID, "bkci", "2", biz_id, "soft_deleted", is_deleted=True)
    add_output(TENANT_ID, "bkci", "2", biz_id, "delete_pending", desired_status="deleted")
    add_output(TENANT_ID, "bkci", "2", biz_id, "deleted", deleted_at=timezone.now())
    tables = get_record_rule_metrics_by_biz_id(biz_id, TENANT_ID, with_option=False)
    assert [table["table_id"] for table in tables] == [visible.table_id]
    assert not get_record_rule_metrics_by_biz_id(biz_id, "another_tenant")
    assert not get_record_rule_metrics_by_biz_id(2, "another_tenant")
    BkmonitorMetricCacheManager(bk_tenant_id=TENANT_ID, bk_biz_id=biz_id)._run()
    [metric] = search(biz_id, "cpu_avg")
    assert metric["bk_biz_id"] == biz_id and metric["result_table_id"] == visible.table_id
    assert not search(2, "cpu_avg")


@pytest.mark.parametrize("with_option", [False, True])
def test_metadata_pagination_filters_and_legacy_coexist(metric_context, with_option):
    active = add_output(TENANT_ID, "bkcc", "2", 2, "active")
    add_output(TENANT_ID, "bkcc", "2", 2, "hidden", is_deleted=True)
    other_business = add_output(TENANT_ID, "bkcc", "3", 3, "other_business")
    add_output("another_tenant", "bkcc", "2", 2, "other_tenant")
    # 同租户普通表和旧版预计算表仍能与 V4 一起分页。
    normal_id = "normal.cpu"
    models.DataSource.objects.create(
        bk_tenant_id=TENANT_ID,
        bk_data_id=987650,
        data_name="selector_test",
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(bk_tenant_id=TENANT_ID, bk_data_id=987650, table_id=normal_id)
    models.ResultTable.objects.create(bk_tenant_id=TENANT_ID, table_id=normal_id, bk_biz_id=2, is_custom_table=False)
    legacy_id = "bkprecal_legacy.__default__"
    models.RecordRule.objects.create(
        bk_tenant_id=TENANT_ID, space_type="bkcc", space_id="2", table_id=legacy_id, record_name="legacy"
    )
    models.ResultTable.objects.create(bk_tenant_id=TENANT_ID, table_id=legacy_id, bk_biz_id=2, is_custom_table=True)
    api = ListResultTableResource()
    params = {"bk_tenant_id": TENANT_ID, "bk_biz_id": 2, "with_option": with_option}
    expected = sorted([active.table_id, normal_id, legacy_id])
    pages = [api.request(**params, page=page, page_size=1) for page in range(1, 5)]
    assert all(page["count"] == 3 for page in pages)
    assert [table["table_id"] for page in pages for table in page["info"]] == expected
    assert pages[-1]["info"] == []
    tables = api.request(**params)
    assert [table["table_id"] for table in tables] == expected
    v4_table = next(table for table in tables if table["table_id"] == active.table_id)
    assert v4_table["table_type"] == "recording_rule"
    assert v4_table["source_label"] == "bk_monitor" and v4_table["type_label"] == "time_series"
    assert ("option" in v4_table) is with_option
    assert ("option" in v4_table["field_list"][0]) is with_option
    filtered = api.request(**params, datasource_type="normal", page_size=1)
    assert filtered["count"] == 1 and filtered["info"][0]["table_id"] == normal_id
    all_tables = api.request(bk_tenant_id=TENANT_ID, with_option=with_option)
    assert {table["table_id"] for table in all_tables} == {*expected, other_business.table_id}


def test_adapter_keeps_tenant_in_paged_requests(mocker):
    batch = mocker.patch("api.metadata.default.batch_request", return_value=[])
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value=None)
    ListMonitorResultTableResource().request(bk_tenant_id="explicit_tenant", bk_biz_id=2, with_option=False)
    assert batch.call_args.args[1]["bk_tenant_id"] == "explicit_tenant"


def test_single_tenant_default_context(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = False
    mocker.patch("bkmonitor.utils.request.get_request", return_value=None)
    mocker.patch("bkmonitor.utils.tenant.get_local_tenant_id", return_value=None)
    mocker.patch.object(selector, "bk_biz_id_to_bk_tenant_id", return_value="system")
    mocker.patch.object(selector, "get_source_app", return_value="")
    mocker.patch.object(selector.resource.commons, "get_label", return_value=[])
    mocker.patch.object(BkmonitorMetricCacheManager, "get_label_name", side_effect=lambda label: label)
    mocker.patch("api.metadata.default.api.metadata.list_result_table", side_effect=ListResultTableResource().request)
    models.Space.objects.create(space_type_id="bkcc", space_id="21", space_name="single-tenant")
    rule = add_output("system", "bkcc", "21", 21, "single_tenant")
    [table] = ListMonitorResultTableResource().request(bk_biz_id=21, with_option=False)
    assert table["bk_tenant_id"] == "system"
    BkmonitorMetricCacheManager(bk_tenant_id="system", bk_biz_id=21)._run()
    [metric] = search(21, "cpu_avg")
    assert metric["result_table_id"] == rule.table_id
