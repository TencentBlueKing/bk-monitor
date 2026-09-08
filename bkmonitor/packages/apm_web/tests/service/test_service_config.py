"""APM 服务配置测试。"""

from typing import Any

import pytest
from rest_framework.exceptions import ValidationError

from apm_web.constants import ServiceRelationLogTypeChoices
from apm_web.models import (
    ApdexServiceRelation,
    ApmMetaConfig,
    Application,
    AppServiceRelation,
    CMDBServiceRelation,
    EventServiceRelation,
    LogServiceRelation,
    UriServiceRelation,
)
from apm_web.service.resources import ServiceConfigResource
from apm_web.service.serializers import ServiceConfigSerializer
from apm_web.service.views import ServiceViewSet
from bkmonitor.iam import ActionEnum
from bkmonitor.models import DutyArrange, UserGroup
from monitor_web.data_explorer.event.constants import EventCategory

pytestmark = pytest.mark.django_db(databases=["default", "monitor_api"])


BK_BIZ_ID = 2
APP_NAME = "checkout"
SERVICE_NAME = "checkout-api"
SERVICE_NOTICE_GROUP_NAME = "【APM】 checkout/checkout-api 服务告警组"
BASE_REQUEST = {
    "bk_biz_id": BK_BIZ_ID,
    "app_name": APP_NAME,
    "service_name": SERVICE_NAME,
}
EXISTING_K8S_RELATION = {
    "bcs_cluster_id": "BCS-K8S-00000",
    "namespace": "prod",
    "kind": "Deployment",
    "name": "checkout-api",
}
NEW_K8S_RELATION = {
    "bcs_cluster_id": "BCS-K8S-00000",
    "namespace": "prod",
    "kind": "StatefulSet",
    "name": "checkout-worker",
}
EXISTING_CICD_RELATION = {
    "project_id": "demo-project",
    "pipeline_id": "p-checkout-api",
    "pipeline_name": "checkout-api 发布流水线",
}
NEW_CICD_RELATION = {
    "project_id": "demo-project",
    "pipeline_id": "p-checkout-worker",
    "pipeline_name": "checkout-worker 发布流水线",
}


@pytest.fixture
def application() -> Application:
    return Application.objects.create(
        application_id=1,
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        app_alias=APP_NAME,
        description="test application",
    )


@pytest.fixture
def disable_config_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apm_web.tasks.update_application_config.delay", lambda *_args, **_kwargs: None)


def test_incremental_serializer_only_keeps_explicit_config_fields() -> None:
    serializer = ServiceConfigSerializer(
        data={
            **BASE_REQUEST,
            "incremental_k8s_relations": [NEW_K8S_RELATION],
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert set(serializer.validated_data) == {
        "bk_biz_id",
        "app_name",
        "service_name",
        "incremental_k8s_relations",
    }


def test_full_save_serializer_keeps_existing_default_semantics() -> None:
    serializer = ServiceConfigSerializer(data={**BASE_REQUEST, "uri_relation": []})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["app_relation"] is None
    assert serializer.validated_data["cmdb_relation"] is None
    assert serializer.validated_data["log_relation_list"] == []
    assert serializer.validated_data["apdex_relation"] is None
    assert serializer.validated_data["uri_relation"] == []
    assert serializer.validated_data["event_relation"] == []


def test_base_only_serializer_does_not_apply_full_save_defaults() -> None:
    serializer = ServiceConfigSerializer(data=BASE_REQUEST)

    assert serializer.is_valid(), serializer.errors
    assert set(serializer.validated_data) == set(BASE_REQUEST)


def test_labels_only_serializer_does_not_apply_relation_defaults() -> None:
    serializer = ServiceConfigSerializer(data={**BASE_REQUEST, "labels": ["critical"]})

    assert serializer.is_valid(), serializer.errors
    assert set(serializer.validated_data) == {*BASE_REQUEST, "labels"}


def test_owners_only_serializer_does_not_apply_relation_defaults() -> None:
    serializer = ServiceConfigSerializer(data={**BASE_REQUEST, "owners": ["alice", "bob"]})

    assert serializer.is_valid(), serializer.errors
    assert set(serializer.validated_data) == {*BASE_REQUEST, "owners"}


@pytest.mark.parametrize(("service_name_length", "is_valid"), [(65, True), (66, False)])
def test_owners_serializer_validates_notice_group_name_length_boundary(
    service_name_length: int,
    is_valid: bool,
) -> None:
    serializer = ServiceConfigSerializer(
        data={
            **BASE_REQUEST,
            "app_name": "a" * 50,
            "service_name": "s" * service_name_length,
            "owners": [],
        }
    )

    assert serializer.is_valid() is is_valid
    if not is_valid:
        assert "owners" in serializer.errors


@pytest.mark.parametrize(
    "full_config",
    [
        {"app_relation": None},
        {"cmdb_relation": None},
        {"log_relation_list": []},
        {"apdex_relation": None},
        {"uri_relation": []},
        {"event_relation": []},
        {"labels": []},
    ],
)
def test_incremental_serializer_rejects_mixed_save_modes(full_config: dict[str, Any]) -> None:
    serializer = ServiceConfigSerializer(
        data={
            **BASE_REQUEST,
            **full_config,
            "incremental_k8s_relations": [NEW_K8S_RELATION],
        }
    )

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


@pytest.mark.parametrize(
    ("field", "relation"),
    [
        ("incremental_k8s_relations", {"bcs_cluster_id": "BCS-K8S-00000"}),
        ("incremental_cicd_relations", {"project_id": "demo-project", "pipeline_id": "pipeline-id"}),
    ],
)
def test_incremental_serializer_rejects_incomplete_relations(field: str, relation: dict[str, str]) -> None:
    serializer = ServiceConfigSerializer(data={**BASE_REQUEST, field: [relation]})

    assert not serializer.is_valid()
    assert field in serializer.errors


def test_service_config_uses_view_permission() -> None:
    view = ServiceViewSet()
    view.action = "service_config"

    permissions = view.get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.VIEW_APM_APPLICATION]


@pytest.mark.parametrize(
    ("request_data", "error_field"),
    [
        ({**BASE_REQUEST, "app_name": "a" * 51}, "app_name"),
        ({**BASE_REQUEST, "service_name": "s" * 513}, "service_name"),
        (
            {
                **BASE_REQUEST,
                "incremental_k8s_relations": [{**NEW_K8S_RELATION, "bcs_cluster_id": "c" * 65}],
            },
            "incremental_k8s_relations",
        ),
        (
            {**BASE_REQUEST, "incremental_k8s_relations": [{**NEW_K8S_RELATION, "namespace": "n" * 64}]},
            "incremental_k8s_relations",
        ),
        (
            {**BASE_REQUEST, "incremental_k8s_relations": [{**NEW_K8S_RELATION, "kind": "k" * 65}]},
            "incremental_k8s_relations",
        ),
        (
            {**BASE_REQUEST, "incremental_k8s_relations": [{**NEW_K8S_RELATION, "name": "n" * 254}]},
            "incremental_k8s_relations",
        ),
        (
            {**BASE_REQUEST, "incremental_cicd_relations": [{**NEW_CICD_RELATION, "project_id": "p" * 129}]},
            "incremental_cicd_relations",
        ),
        (
            {**BASE_REQUEST, "incremental_cicd_relations": [{**NEW_CICD_RELATION, "pipeline_id": "p" * 129}]},
            "incremental_cicd_relations",
        ),
        (
            {**BASE_REQUEST, "incremental_cicd_relations": [{**NEW_CICD_RELATION, "pipeline_name": "p" * 256}]},
            "incremental_cicd_relations",
        ),
    ],
)
def test_service_config_serializer_rejects_overlong_fields(request_data: dict[str, Any], error_field: str) -> None:
    serializer = ServiceConfigSerializer(data=request_data)

    assert not serializer.is_valid()
    assert error_field in serializer.errors


def test_incremental_relations_create_event_records(
    application: Application,
    disable_config_delivery: None,
) -> None:
    ServiceConfigResource().request(
        {
            **BASE_REQUEST,
            "owners": ["alice"],
            "incremental_k8s_relations": [NEW_K8S_RELATION],
            "incremental_cicd_relations": [NEW_CICD_RELATION],
        }
    )

    relations = {relation.table: relation for relation in EventServiceRelation.objects.all()}
    assert relations[EventCategory.K8S_EVENT.value].relations == [NEW_K8S_RELATION]
    assert relations[EventCategory.K8S_EVENT.value].options == {"is_auto": False}
    assert relations[EventCategory.CICD_EVENT.value].relations == [NEW_CICD_RELATION]
    assert relations[EventCategory.CICD_EVENT.value].options == {}
    group = UserGroup.objects.get(bk_biz_id=BK_BIZ_ID, name=SERVICE_NOTICE_GROUP_NAME)
    assert DutyArrange.objects.get(user_group_id=group.id).users == [{"id": "alice", "type": "user"}]


def test_owners_create_and_replace_service_notice_group(
    application: Application,
    disable_config_delivery: None,
) -> None:
    resource = ServiceConfigResource()
    resource.request({**BASE_REQUEST, "owners": ["alice", "bob", "alice"]})

    group = UserGroup.objects.get(bk_biz_id=BK_BIZ_ID, name=SERVICE_NOTICE_GROUP_NAME)
    for notice_config in group.alert_notice + group.action_notice:
        assert notice_config["time_range"] == "00:00:00--23:59:59"
        assert all(notify_config["type"] == ["rtx"] for notify_config in notice_config["notify_config"])

    assert DutyArrange.objects.get(user_group_id=group.id).users == [
        {"id": "alice", "type": "user"},
        {"id": "bob", "type": "user"},
    ]
    original_group_config: dict[str, Any] = {
        "alert_notice": group.alert_notice,
        "action_notice": group.action_notice,
        "desc": group.desc,
        "channels": group.channels,
    }

    resource.request({**BASE_REQUEST, "owners": ["carol"]})

    group.refresh_from_db()
    assert UserGroup.objects.filter(bk_biz_id=BK_BIZ_ID, name=group.name).count() == 1
    assert DutyArrange.objects.get(user_group_id=group.id).users == [{"id": "carol", "type": "user"}]
    assert {
        "alert_notice": group.alert_notice,
        "action_notice": group.action_notice,
        "desc": group.desc,
        "channels": group.channels,
    } == original_group_config

    resource.request({**BASE_REQUEST, "owners": []})

    assert DutyArrange.objects.get(user_group_id=group.id).users == []


def test_owners_reject_existing_notice_group_with_duty(
    application: Application,
    disable_config_delivery: None,
) -> None:
    group = UserGroup.objects.create(
        bk_biz_id=BK_BIZ_ID,
        name=SERVICE_NOTICE_GROUP_NAME,
        desc="",
        alert_notice=[],
        action_notice=[],
        need_duty=True,
        duty_rules=[1],
    )

    with pytest.raises(ValidationError) as exc_info:
        ServiceConfigResource().request(
            {
                **BASE_REQUEST,
                "owners": ["alice"],
                "incremental_k8s_relations": [NEW_K8S_RELATION],
            }
        )

    assert "owners" in exc_info.value.detail
    assert not EventServiceRelation.objects.exists()
    group.refresh_from_db()
    assert group.need_duty is True
    assert group.duty_rules == [1]
    assert not DutyArrange.objects.filter(user_group_id=group.id).exists()


def test_notice_group_write_rolls_back_on_duty_arrange_failure(
    application: Application,
    disable_config_delivery: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_bulk_create(
        _model_cls: type[DutyArrange],
        _duty_arranges: list[dict[str, Any]],
        _instance: UserGroup,
    ) -> None:
        raise RuntimeError("duty arrange failed")

    monkeypatch.setattr(DutyArrange, "bulk_create", classmethod(fail_bulk_create))

    with pytest.raises(RuntimeError, match="duty arrange failed"):
        ServiceConfigResource().request({**BASE_REQUEST, "owners": ["alice"]})

    assert not UserGroup.objects.filter(bk_biz_id=BK_BIZ_ID, name=SERVICE_NOTICE_GROUP_NAME).exists()


def test_request_without_owners_does_not_create_service_notice_group(
    application: Application,
    disable_config_delivery: None,
) -> None:
    ServiceConfigResource().request(BASE_REQUEST)

    assert not UserGroup.objects.filter(bk_biz_id=BK_BIZ_ID, name=SERVICE_NOTICE_GROUP_NAME).exists()


def test_incremental_relations_append_deduplicate_and_preserve_existing_configs(
    application: Application,
    disable_config_delivery: None,
) -> None:
    AppServiceRelation.objects.create(
        **BASE_REQUEST,
        relate_bk_biz_id=3,
        relate_app_name="payment",
    )
    CMDBServiceRelation.objects.create(**BASE_REQUEST, template_id=100)
    LogServiceRelation.objects.create(
        **BASE_REQUEST,
        log_type=ServiceRelationLogTypeChoices.BK_LOG,
        related_bk_biz_id=BK_BIZ_ID,
        value="",
        value_list=[1001],
    )
    ApdexServiceRelation.objects.create(
        **BASE_REQUEST,
        apdex_key=Application.ApdexConfig.APDEX_DEFAULT,
        apdex_value=500,
    )
    UriServiceRelation.objects.create(**BASE_REQUEST, uri="/checkout", rank=0)
    ApmMetaConfig.service_config_setup(BK_BIZ_ID, APP_NAME, SERVICE_NAME, "labels", '["critical"]')

    k8s_relation = EventServiceRelation.objects.create(
        **BASE_REQUEST,
        table=EventCategory.K8S_EVENT.value,
        relations=[EXISTING_K8S_RELATION],
        options={"is_auto": True},
    )
    cicd_relation = EventServiceRelation.objects.create(
        **BASE_REQUEST,
        table=EventCategory.CICD_EVENT.value,
        relations=[EXISTING_CICD_RELATION],
        options={"source": "bkci"},
    )
    system_relation = EventServiceRelation.objects.create(
        **BASE_REQUEST,
        table=EventCategory.SYSTEM_EVENT.value,
        relations=[{"bk_biz_id": BK_BIZ_ID}],
        options={"level": ["warning"]},
    )
    other_service_relation = EventServiceRelation.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        service_name="payment-api",
        table=EventCategory.K8S_EVENT.value,
        relations=[{**EXISTING_K8S_RELATION, "name": "payment-api"}],
        options={"owner": "payment"},
    )
    global_relation = EventServiceRelation.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        service_name="",
        is_global=True,
        table=EventCategory.K8S_EVENT.value,
        relations=[{"bcs_cluster_id": "BCS-K8S-GLOBAL"}],
        options={"scope": "application"},
    )
    request_data: dict[str, Any] = {
        **BASE_REQUEST,
        "incremental_k8s_relations": [EXISTING_K8S_RELATION, NEW_K8S_RELATION, NEW_K8S_RELATION],
        "incremental_cicd_relations": [
            {**EXISTING_CICD_RELATION, "pipeline_name": "不应覆盖已有名称"},
            NEW_CICD_RELATION,
            NEW_CICD_RELATION,
        ],
    }

    resource = ServiceConfigResource()
    resource.request(request_data)
    resource.request(request_data)

    k8s_relation.refresh_from_db()
    cicd_relation.refresh_from_db()
    system_relation.refresh_from_db()
    other_service_relation.refresh_from_db()
    global_relation.refresh_from_db()
    assert k8s_relation.relations == [EXISTING_K8S_RELATION, NEW_K8S_RELATION]
    assert k8s_relation.options == {"is_auto": False}
    assert cicd_relation.relations == [EXISTING_CICD_RELATION, NEW_CICD_RELATION]
    assert cicd_relation.options == {"source": "bkci"}
    assert system_relation.relations == [{"bk_biz_id": BK_BIZ_ID}]
    assert system_relation.options == {"level": ["warning"]}
    assert other_service_relation.relations == [{**EXISTING_K8S_RELATION, "name": "payment-api"}]
    assert other_service_relation.options == {"owner": "payment"}
    assert global_relation.relations == [{"bcs_cluster_id": "BCS-K8S-GLOBAL"}]
    assert global_relation.options == {"scope": "application"}
    assert EventServiceRelation.objects.count() == 5

    assert AppServiceRelation.objects.filter(**BASE_REQUEST).count() == 1
    assert CMDBServiceRelation.objects.filter(**BASE_REQUEST).count() == 1
    assert LogServiceRelation.objects.filter(**BASE_REQUEST).count() == 1
    assert ApdexServiceRelation.objects.filter(**BASE_REQUEST).count() == 1
    assert UriServiceRelation.objects.filter(**BASE_REQUEST).count() == 1
    assert (
        ApmMetaConfig.get_service_config_value(BK_BIZ_ID, APP_NAME, SERVICE_NAME, "labels").config_value
        == '["critical"]'
    )


def test_incremental_k8s_relation_survives_follow_up_full_save(
    application: Application,
    disable_config_delivery: None,
) -> None:
    resource = ServiceConfigResource()
    resource.request({**BASE_REQUEST, "incremental_k8s_relations": [NEW_K8S_RELATION]})
    k8s_relation = EventServiceRelation.objects.get(table=EventCategory.K8S_EVENT.value)

    resource.request(
        {
            **BASE_REQUEST,
            "event_relation": [
                {
                    "table": EventCategory.K8S_EVENT.value,
                    "relations": [],
                    "options": {"is_auto": True},
                }
            ],
        }
    )

    k8s_relation.refresh_from_db()
    assert k8s_relation.relations == [NEW_K8S_RELATION]
    assert k8s_relation.options == {"is_auto": False}


def test_empty_incremental_relations_do_not_change_existing_record(
    application: Application,
    disable_config_delivery: None,
) -> None:
    relation = EventServiceRelation.objects.create(
        **BASE_REQUEST,
        table=EventCategory.K8S_EVENT.value,
        relations=[EXISTING_K8S_RELATION],
        options={"is_auto": False},
    )
    updated_at = relation.updated_at

    ServiceConfigResource().request({**BASE_REQUEST, "incremental_k8s_relations": []})

    relation.refresh_from_db()
    assert relation.relations == [EXISTING_K8S_RELATION]
    assert relation.options == {"is_auto": False}
    assert relation.updated_at == updated_at


def test_base_only_request_does_not_delete_existing_relations(
    application: Application,
    disable_config_delivery: None,
) -> None:
    app_relation = AppServiceRelation.objects.create(
        **BASE_REQUEST,
        relate_bk_biz_id=3,
        relate_app_name="payment",
    )
    uri_relation = UriServiceRelation.objects.create(**BASE_REQUEST, uri="/checkout", rank=0)

    ServiceConfigResource().request(BASE_REQUEST)

    app_relation.refresh_from_db()
    uri_relation.refresh_from_db()
    assert app_relation.relate_app_name == "payment"
    assert uri_relation.uri == "/checkout"


def test_relation_failure_rolls_back_relations_and_skips_notice_group(
    application: Application,
    disable_config_delivery: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_sync_relations = EventServiceRelation.sync_relations
    sync_count = 0

    def fail_second_sync(
        _model_cls: type[EventServiceRelation],
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal sync_count
        sync_count += 1
        if sync_count == 2:
            raise RuntimeError("second relation failed")
        return original_sync_relations(*args, **kwargs)

    monkeypatch.setattr(EventServiceRelation, "sync_relations", classmethod(fail_second_sync))

    with pytest.raises(RuntimeError, match="second relation failed"):
        ServiceConfigResource().request(
            {
                **BASE_REQUEST,
                "owners": ["alice"],
                "incremental_k8s_relations": [NEW_K8S_RELATION],
                "incremental_cicd_relations": [NEW_CICD_RELATION],
            }
        )

    assert not EventServiceRelation.objects.exists()
    assert not UserGroup.objects.filter(bk_biz_id=BK_BIZ_ID, name=SERVICE_NOTICE_GROUP_NAME).exists()


def test_missing_application_does_not_create_incremental_relation() -> None:
    with pytest.raises(Application.DoesNotExist):
        ServiceConfigResource().request(
            {
                **BASE_REQUEST,
                "incremental_k8s_relations": [NEW_K8S_RELATION],
            }
        )

    assert not EventServiceRelation.objects.exists()
