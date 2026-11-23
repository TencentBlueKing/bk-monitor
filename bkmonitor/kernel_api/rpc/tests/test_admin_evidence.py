from unittest.mock import Mock

import pytest
from django.db import connections, router
from django.db.utils import ConnectionHandler
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response
from rest_framework.exceptions import ValidationError

from bkmonitor.models import DutyPlan, DutyRule, UserGroup
from calendars.models import CalendarModel, CalendarItemModel
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.evidence import cmdb, rotation, incidents, rum
from metadata.models import Space
from rum.models import RumApplication, RumDataSource, RumAppConfig, MetricDataSource
from rum_web.models.application import Application, RumAppConfig as WebAppConfig

BIZ = {"bk_tenant_id": "system", "bk_biz_id": 2}


@pytest.fixture
def evidence_db(monkeypatch, django_db_blocker):
    models = [
        Space,
        CalendarModel,
        CalendarItemModel,
        DutyRule,
        DutyPlan,
        UserGroup,
        RumApplication,
        RumDataSource,
        MetricDataSource,
        RumAppConfig,
        Application,
        WebAppConfig,
    ]
    local = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})["default"]
    aliases = {"default", *(router.db_for_read(m) for m in models), *(router.db_for_write(m) for m in models)}
    for alias in aliases:
        monkeypatch.setattr(connections._connections, alias, local, raising=False)
    with django_db_blocker.unblock():
        try:
            with local.schema_editor() as editor:
                for model in models:
                    editor.create_model(model)
            Space.objects.bulk_create(
                [Space(space_type_id="bkcc", space_id="2", bk_tenant_id="system", space_name="test")]
            )
            yield
        finally:
            local.close()


def test_rotation_and_calendar_scope(evidence_db):
    for pk, tenant in [(1, "system"), (2, "other")]:
        CalendarModel.objects.bulk_create([CalendarModel(id=pk, bk_tenant_id=tenant, name="维护", classify="custom")])
        CalendarItemModel.objects.bulk_create(
            [
                CalendarItemModel(
                    id=pk,
                    bk_tenant_id=tenant,
                    name="周末",
                    calendar_id=pk,
                    start_time=1,
                    end_time=3,
                    repeat={"freq": "week"},
                )
            ]
        )
    assert rotation.calendars({"bk_tenant_id": "system"})["data"]["total"] == 1
    assert rotation.items({"bk_tenant_id": "system", "calendar_id": 2})["data"]["items"] == []
    assert rotation.items({"bk_tenant_id": "system", "calendar_id": 1})["data"]["items"][0]["repeat"] == {
        "freq": "week"
    }
    for pk, biz in [(1, 0), (2, 2), (3, 3)]:
        DutyRule.objects.bulk_create([DutyRule(id=pk, bk_biz_id=biz, name=f"rule-{pk}")])
    page = rotation.rules({**BIZ, "page": 2, "page_size": 1})["data"]
    assert page["total"] == 2 and page["items"][0]["id"] == 2
    Space.objects.bulk_create(
        [Space(id=99, space_type_id="bkci", space_id="project", bk_tenant_id="system", space_name="project")]
    )
    DutyRule.objects.bulk_create([DutyRule(id=4, bk_biz_id=-99, name="project")])
    assert {r["bk_biz_id"] for r in rotation.rules({**BIZ, "bk_biz_id": -99})["data"]["items"]} == {0, -99}
    with pytest.raises(CustomException):
        rotation.rules({**BIZ, "bk_tenant_id": "other"})
    for group, biz in [(10, 2), (11, 3)]:
        UserGroup.objects.bulk_create([UserGroup(id=group, bk_biz_id=biz, name="值班组")])
        DutyPlan.objects.bulk_create(
            [
                DutyPlan(
                    user_group_id=group,
                    order=1,
                    is_effective=1,
                    start_time="2026-11-23 00:00:00",
                    finished_time="2026-11-24 00:00:00",
                    work_times=[{"start_time": "2026-11-23 08:00", "end_time": "2026-11-23 16:00"}],
                )
            ]
        )
    assert rotation.plans({**BIZ, "user_group_id": 10, "at": "2026-11-23 09:00:00"})["data"]["items"][0]["on_duty"]
    assert not rotation.plans({**BIZ, "user_group_id": 10, "at": "2026-11-23 17:00:00"})["data"]["items"][0]["on_duty"]
    assert rotation.plans({**BIZ, "user_group_id": 11})["data"]["total"] == 0


def test_rum_data_config_and_record_scope(evidence_db, monkeypatch):
    from rum_web.handlers.level.factory import RumLevelHandlerFactory

    RumApplication.objects.bulk_create(
        [RumApplication(id=4, **BIZ, app_name="checkout", app_alias="结算", token="private")]
    )
    assert "token" not in rum.applications(BIZ)["data"]["items"][0]
    p = {**BIZ, "app_name": "checkout"}
    with pytest.raises(CustomException):
        rum.configs({**p, "bk_tenant_id": "other"})
    RumAppConfig.objects.create(bk_biz_id=2, app_name="checkout", config_type="sampler:percentage", config_value=10)
    RumDataSource.objects.create(bk_biz_id=2, app_name="checkout", result_table_id="rum", index_set_id=5)
    MetricDataSource.objects.create(bk_biz_id=2, app_name="checkout", result_table_id="metric")
    assert rum.configs(p)["data"]["items"][0]["config_value"] == 10
    assert rum.datasources({**p, "page": 2, "page_size": 1})["data"]["items"][0]["kind"] == "metric"
    Application.objects.bulk_create([Application(**BIZ, application_id=4, app_name="checkout", app_alias="结算")])
    handler = Mock()
    handler.list_records.return_value = [
        {"attributes": {"session": {"id": "one"}}, "start_time": 99, "http.headers": {"secret": "private"}}
    ]
    handler.total.return_value = {"total": 3}
    factory = Mock(return_value=handler)
    monkeypatch.setattr(RumLevelHandlerFactory, "create", factory)
    result = rum.records({**p, "session_id": "one", "start_time": 1, "end_time": 100, "page": 2, "page_size": 1})
    assert result["meta"]["safety_level"] == "inspect"
    assert result["data"]["items"] == [{"attributes.session.id": "one", "start_time": 99}]
    assert handler.list_records.call_args.kwargs["offset"] == 1
    assert handler.total.call_args.kwargs["filters"][0]["value"] == ["one"]
    target = factory.call_args.args[1][0]
    assert target.app.bk_biz_id == 2 and target.app.app_name == "checkout"


@pytest.mark.parametrize(
    ("method", "handler", "filters", "expected"),
    [
        ("search_set", cmdb.sets, {"bk_set_id": 3}, {"condition": {"bk_set_id": 3}}),
        (
            "search_module",
            cmdb.modules,
            {"bk_set_id": 3, "bk_module_id": 4},
            {"bk_set_id": 3, "condition": {"bk_module_id": 4}},
        ),
        (
            "list_biz_hosts_topo",
            cmdb.hosts,
            {"bk_module_id": 4, "ip": "127.0.0.1"},
            {
                "module_property_filter": {
                    "condition": "AND",
                    "rules": [{"field": "bk_module_id", "operator": "equal", "value": 4}],
                }
            },
        ),
        (
            "list_service_instance_detail",
            cmdb.services,
            {"service_instance_id": 12, "bk_host_id": 3},
            {"service_instance_ids": [12], "bk_host_list": [3]},
        ),
        ("search_dynamic_group", cmdb.groups, {"bk_obj_id": "set"}, {"condition": {"bk_obj_id": "set"}}),
        (
            "execute_dynamic_group",
            cmdb.members,
            {"bk_obj_id": "set", "group_id": "g-1"},
            {"id": "g-1", "fields": cmdb.SET_FIELDS},
        ),
    ],
)
def test_cmdb_forwards_one_scoped_page(monkeypatch, method, handler, filters, expected):
    upstream = Mock(return_value={"info": [], "count": 12})
    monkeypatch.setattr(cmdb.client, method, upstream)
    assert handler({**BIZ, **filters, "page": 2, "page_size": 10})["data"] == {
        "items": [],
        "total": 12,
        "page": 2,
        "page_size": 10,
    }
    kwargs = upstream.call_args.kwargs
    assert {k: kwargs[k] for k in {**BIZ, **expected}} == {**BIZ, **expected}
    assert kwargs["page"]["start"] == 10 and kwargs["page"]["limit"] == 10
    with pytest.raises(ValidationError):
        handler({**BIZ, **filters, "bk_biz_id": -2})
    upstream.assert_called_once()


def test_topology_includes_internal_and_preserves_custom_levels(monkeypatch):
    monkeypatch.setattr(
        cmdb.client,
        "search_biz_inst_topo",
        Mock(
            return_value=[
                {
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                    "bk_inst_name": "商城",
                    "child": [{"bk_obj_id": "layer", "bk_inst_id": 5, "bk_inst_name": "华南", "child": []}],
                }
            ]
        ),
    )
    monkeypatch.setattr(
        cmdb.client,
        "get_biz_internal_module",
        Mock(
            return_value={
                "bk_set_id": 12,
                "bk_set_name": "空闲池",
                "module": [{"bk_module_id": 15, "bk_module_name": "空闲机"}],
            }
        ),
    )
    assert cmdb.topology(BIZ)["data"]["total"] == 4
    assert cmdb.topology({**BIZ, "bk_inst_id": 15})["data"]["items"][0]["path"] == "商城 / 空闲池 / 空闲机"


def test_incident_and_issue_stored_evidence(evidence_db, monkeypatch):
    requests = []

    def execute(search):
        requests.append(search.to_dict())
        return Response(
            search,
            {
                "hits": {
                    "total": {"value": 7, "relation": "eq"},
                    "hits": [{"_id": "42", "_source": {"id": "42", "name": "问题", "incident_id": "22"}}],
                }
            },
        )

    monkeypatch.setattr(Search, "execute", execute)
    p = {**BIZ, "page": 2, "page_size": 2}
    result = incidents.issues({**p, "status": "ONGOING", "issue_id": "42", "start_time": 1, "end_time": 100})["data"]
    assert result["total"] == 7 and result["items"][0]["id"] == "42"
    query = requests[-1]
    assert query["from"] == 2 and query["size"] == 2
    assert {"term": {"bk_biz_id": "2"}} in query["query"]["bool"]["filter"]
    assert {"range": {"last_alert_time": {"gte": 1, "lte": 100}}} in query["query"]["bool"]["filter"]
    assert {"ids": {"values": ["42"]}} in query["query"]["bool"]["filter"]
    assert incidents.incidents({**BIZ, "incident_id": "22"})["data"]["items"][0]["incident_id"] == "22"
    assert incidents.activities({**BIZ, "issue_id": "42"})["data"]["total"] == 7
    with pytest.raises(CustomException):
        incidents.issues({**BIZ, "bk_tenant_id": "other"})
    monkeypatch.setattr(Search, "count", lambda self: 0)
    with pytest.raises(CustomException, match="Incident"):
        incidents.snapshot({**BIZ, "incident_id": "22", "snapshot_id": "12"})
    monkeypatch.setattr(Search, "count", lambda self: 1)
    assert incidents.snapshot({**BIZ, "incident_id": "22", "snapshot_id": "12"})["data"]["total"] == 7
    assert {"term": {"incident_id": "22"}} in requests[-1]["query"]["bool"]["filter"]


def test_discovery_has_specific_tenant_paging_and_no_passthrough():
    entries = [
        item
        for n, item in KernelRPCRegistry._functions.items()
        if n.startswith(("admin.cmdb.", "admin.rum.", "admin.rotation.", "admin.incident.", "admin.issue."))
        and n != "admin.issue.inspect"
    ]
    assert len(entries) == 24
    for entry in entries:
        assert entry.params_schema["additionalProperties"] is False
        assert "bk_tenant_id" in entry.params_schema["required"]
        assert entry.params_schema["properties"]["page_size"]["maximum"] == 100
        with pytest.raises(CustomException):
            entry.handler({**entry.example_params, "func_name": "other"})
        with pytest.raises(ValidationError):
            entry.handler({**entry.example_params, "bk_tenant_id": "__all__"})
