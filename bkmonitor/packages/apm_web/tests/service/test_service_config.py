"""APM 服务配置增量关联测试。"""

from typing import Any

import pytest

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
from monitor_web.data_explorer.event.constants import EventCategory

pytestmark = pytest.mark.django_db


BK_BIZ_ID = 2
APP_NAME = "checkout"
SERVICE_NAME = "checkout-api"
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
    serializer = ServiceConfigSerializer(data=BASE_REQUEST)

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["app_relation"] is None
    assert serializer.validated_data["cmdb_relation"] is None
    assert serializer.validated_data["log_relation_list"] == []
    assert serializer.validated_data["apdex_relation"] is None
    assert serializer.validated_data["uri_relation"] == []
    assert serializer.validated_data["event_relation"] == []


def test_incremental_serializer_rejects_mixed_event_save_modes() -> None:
    serializer = ServiceConfigSerializer(
        data={
            **BASE_REQUEST,
            "event_relation": [
                {
                    "table": EventCategory.K8S_EVENT.value,
                    "relations": [EXISTING_K8S_RELATION],
                    "options": {},
                }
            ],
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


def test_incremental_relations_create_event_records(
    application: Application,
    disable_config_delivery: None,
) -> None:
    ServiceConfigResource().request(
        {
            **BASE_REQUEST,
            "incremental_k8s_relations": [NEW_K8S_RELATION],
            "incremental_cicd_relations": [NEW_CICD_RELATION],
        }
    )

    relations = {relation.table: relation for relation in EventServiceRelation.objects.all()}
    assert relations[EventCategory.K8S_EVENT.value].relations == [NEW_K8S_RELATION]
    assert relations[EventCategory.K8S_EVENT.value].options == {}
    assert relations[EventCategory.CICD_EVENT.value].relations == [NEW_CICD_RELATION]
    assert relations[EventCategory.CICD_EVENT.value].options == {}


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
        options={"is_auto": False},
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


def test_incremental_request_rolls_back_all_relations_on_failure(
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
                "incremental_k8s_relations": [NEW_K8S_RELATION],
                "incremental_cicd_relations": [NEW_CICD_RELATION],
            }
        )

    assert not EventServiceRelation.objects.exists()


def test_missing_application_does_not_create_incremental_relation() -> None:
    with pytest.raises(Application.DoesNotExist):
        ServiceConfigResource().request(
            {
                **BASE_REQUEST,
                "incremental_k8s_relations": [NEW_K8S_RELATION],
            }
        )

    assert not EventServiceRelation.objects.exists()
