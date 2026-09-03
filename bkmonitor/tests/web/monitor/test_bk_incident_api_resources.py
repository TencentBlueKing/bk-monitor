import abc
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _Field:
    def __init__(self, *args, **kwargs):
        pass


class _Serializer:
    pass


_serializers = SimpleNamespace(
    Serializer=_Serializer,
    BooleanField=_Field,
    CharField=_Field,
    IntegerField=_Field,
    ChoiceField=_Field,
    DictField=_Field,
    ListField=_Field,
    JSONField=_Field,
)


def _load_incident_list_resource(remote_responses, authorized_biz_ids):
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_start = source.index("class IncidentListResource")
    resource_end = source.index("class ExportIncidentResource", resource_start)
    resource_source = source[resource_start:resource_end]

    class FakeGetConfigResource:
        calls = []

        def request(self, **kwargs):
            self.calls.append(kwargs)
            response = remote_responses[len(self.calls) - 1]
            if isinstance(response, Exception):
                raise response
            return response

    scope_ids = {
        -88888: "bkci_project_with_underscore",
        -99999: "bksaas_app",
        2: "bkcc_2",
        3: "bkcc_3",
        4: "bkcc_4",
    }
    monitor_ids = {
        "bkci_project_with_underscore": -88888,
        "bksaas_app": -99999,
        "bkcc_2": 2,
        "bkcc_3": 3,
        "bkcc_4": 4,
    }
    namespace = {
        "IncidentBaseResource": object,
        "IncidentSearchSerializer": _Serializer,
        "serializers": _serializers,
        "resource": SimpleNamespace(space=SimpleNamespace(get_bk_biz_ids_by_user=lambda: list(authorized_biz_ids))),
        "MONITOR_SCOPE_QUERY_SENTINELS": {-1, -2},
        "bk_biz_id_to_scope_id": lambda bk_biz_id: scope_ids[bk_biz_id],
        "scope_id_to_bk_biz_id": lambda scope_id: monitor_ids.get(scope_id, 0),
        "GetConfigResource": FakeGetConfigResource,
        "logger": SimpleNamespace(
            error=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
        ),
    }
    exec(resource_source, namespace)
    return namespace["IncidentListResource"], FakeGetConfigResource


def test_processor_incident_callbacks_use_bkmonitor_api_routes():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class GetIncidentDetailResource")
    resource_end = source.index("class UpdateIncidentDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'action = "/incident/incident/get_incident_detail/"' in resource_source
    assert 'method = "GET"' in resource_source

    resource_start = source.index("class UpdateIncidentDetailResource")
    resource_end = source.index("class GetIncidentSnapshotResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'action = "/incident/bkmonitor_api/update_incident_detail/"' in resource_source
    assert 'method = "POST"' in resource_source
    assert 'method = "PUT"' not in resource_source

    resource_start = source.index("class GetIncidentSnapshotResource")
    resource_end = source.index("class GetConfigResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'action = "/incident/bkmonitor_api/get_incident_snapshot/"' in resource_source
    assert 'method = "GET"' in resource_source


def test_incident_resources_route_remote_api_by_notice_source():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")

    resource_start = source.index("class IncidentBaseResource")
    resource_end = source.index("class IncidentListResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'BKFARA_NOTICE_SOURCE = "bkfara"' in resource_source
    assert 'get("notice_source") == cls.BKFARA_NOTICE_SOURCE' in resource_source
    assert "return api.bk_incident if cls.is_bkfara_incident(incident) else api.bkdata" in resource_source
    assert "api.bk_incident.get_incident_diagnosis" in resource_source
    assert "api.bkdata.get_incident_analysis_results" in resource_source
    assert "def normalize_incident_status" in resource_source
    assert "status.lower() in IncidentStatus.get_enum_value_list()" in resource_source
    assert "incident_value = self.normalize_incident_status(incident_value)" in resource_source
    assert "incident_info[incident_key] = incident_value" in resource_source

    resource_start = source.index("class IncidentResultsResource")
    resource_end = source.index("class IncidentDateHistogramResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "self.get_remote_analysis_results" in resource_source
    assert "api.bk_incident.get_incident_diagnosis" not in resource_source
    assert "api.bkdata.get_incident_analysis_results" not in resource_source
    assert '"extracted_info": raw_results["incident_diagnosis"].get("extracted_info", {})' in resource_source
    assert '"extracted_info": sub_panel.get("extracted_info", {})' in resource_source


def test_incident_edit_and_feedback_use_source_routed_api():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")

    resource_start = source.index("class EditIncidentResource")
    resource_end = source.index("class IncidentAlertListResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "self.get_remote_incident_api(incident)" in resource_source
    assert "incident_api.get_incident_detail" in resource_source
    assert "incident_api.update_incident_detail" in resource_source
    assert "api.bkdata.get_incident_detail" not in resource_source
    assert "api.bkdata.update_incident_detail" not in resource_source


def test_access_processor_marks_bkfara_incident_source():
    source = (PROJECT_ROOT / "alarm_backends/service/access/incident/processor.py").read_text(encoding="utf-8")

    resource_start = source.index("class AccessIncidentProcess")
    resource_end = source.index("def update_remote_incident_detail", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'BKFARA_NOTICE_SOURCE = "bkfara"' in resource_source
    assert 'sync_info.get("notice_source") == cls.BKFARA_NOTICE_SOURCE' in resource_source
    assert "def mark_incident_source" in resource_source
    assert 'incident_document.extra_info["notice_source"] = cls.BKFARA_NOTICE_SOURCE' in resource_source


def test_get_incident_diagnosis_resource_supports_optional_bk_biz_id():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class GetIncidentDiagnosisResource")
    resource_end = source.index("class UpdateIncidentDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'bk_biz_id = serializers.IntegerField(label="业务ID", required=False)' in resource_source
    assert 'incident_id = serializers.IntegerField(label="故障ID", required=True)' in resource_source


def test_panel_detail_resource_proxies_bkfara_payload_without_scope_id():
    api_source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    resource_start = api_source.index("class GetPanelDetailResource")
    resource_end = api_source.index("class GetIncidentDetailResource", resource_start)
    resource_source = api_source[resource_start:resource_end]

    assert 'action = "/incident/incident_analysis/get_panel_detail/"' in resource_source
    assert 'method = "POST"' in resource_source
    assert 'bk_biz_id = serializers.IntegerField(label="业务ID", required=False)' in resource_source
    assert 'incident_id = serializers.IntegerField(label="故障ID", required=True)' in resource_source
    assert "drawer_type = serializers.ChoiceField" in resource_source
    assert "detail_ref = serializers.DictField" in resource_source

    incident_source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_start = incident_source.index("class IncidentPanelDetailResource")
    resource_end = incident_source.index("class IncidentDateHistogramResource", resource_start)
    resource_source = incident_source[resource_start:resource_end]

    assert "return api.bk_incident.get_panel_detail(**validated_request_data)" in resource_source
    assert "scope_id" not in resource_source

    view_source = (PROJECT_ROOT / "packages/monitor_web/incident/views.py").read_text(encoding="utf-8")
    assert 'resource.incident.incident_panel_detail, endpoint="panel_detail"' in view_source


def test_panel_detail_api_converts_bk_biz_id_and_proxy_preserves_payload_and_errors():
    api_source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    base_source = api_source[
        api_source.index("class IncidentBaseResource") : api_source.index("class GetTemplateListResource")
    ]
    panel_source = api_source[
        api_source.index("class GetPanelDetailResource") : api_source.index("class GetIncidentDetailResource")
    ]

    class FakeAPIResource:
        def perform_request(self, validated_request_data):
            return validated_request_data

    namespace = {
        "abc": abc,
        "APIResource": FakeAPIResource,
        "serializers": _serializers,
        "settings": SimpleNamespace(BK_INCIDENT_APIGW_URL="", BK_COMPONENT_API_URL=""),
        "bk_biz_id_to_scope_id": lambda bk_biz_id: f"bkcc_{bk_biz_id}",
    }
    exec(base_source + panel_source, namespace)
    converted = namespace["GetPanelDetailResource"]().perform_request(
        {
            "bk_biz_id": 2,
            "incident_id": 9527,
            "drawer_type": "event",
            "detail_ref": {"panel": "events_analysis"},
        }
    )
    assert converted["scope_type"] == "bkcc"
    assert converted["scope_value"] == "2"
    assert "bk_biz_id" not in converted
    assert converted["detail_ref"] == {"panel": "events_analysis"}

    incident_source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_source = incident_source[
        incident_source.index("class IncidentPanelDetailResource") : incident_source.index(
            "class IncidentDateHistogramResource"
        )
    ]

    class FakeRemote:
        def __init__(self):
            self.params = None

        def get_panel_detail(self, **kwargs):
            self.params = kwargs
            return {"drawer_type": "event", "payload": {"list": [{"raw": True}]}}

    remote = FakeRemote()
    namespace = {
        "IncidentBaseResource": object,
        "serializers": _serializers,
        "api": SimpleNamespace(bk_incident=remote),
    }
    exec(resource_source, namespace)
    request_data = {
        "bk_biz_id": 2,
        "incident_id": 9527,
        "drawer_type": "event",
        "detail_ref": {"panel": "events_analysis"},
    }
    result = namespace["IncidentPanelDetailResource"]().perform_request(request_data)
    assert remote.params == request_data
    assert result == {"drawer_type": "event", "payload": {"list": [{"raw": True}]}}

    def raise_remote_error(**_kwargs):
        raise RuntimeError("remote failed")

    remote.get_panel_detail = raise_remote_error
    try:
        namespace["IncidentPanelDetailResource"]().perform_request(request_data)
    except RuntimeError as error:
        assert str(error) == "remote failed"
    else:
        raise AssertionError("远端异常必须由薄代理原样抛出")


def test_incident_diagnosis_preserves_interaction_metadata():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_start = source.index("class IncidentDiagnosisResource")
    resource_end = source.index("class IncidentPanelDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'content_item["interaction"] = drill_result["interaction"]' in resource_source
    assert 'display_content = raw_sub_panel.get("display")' in resource_source


def test_incident_alert_view_returns_anomaly_timestamps():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_start = source.index("class IncidentAlertViewResource")
    resource_end = source.index("class AlertIncidentDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    class FakeIncidentBaseResource:
        def get_snapshot_alerts(self, snapshot, **kwargs):
            return [
                {
                    "id": "alert-1",
                    "category": "application",
                    "dimensions": [],
                    "extra_info": {
                        "origin_alarm": {
                            "trigger": {
                                "anomaly_ids": [
                                    "hash.1763554200.strategy.item.level",
                                    "hash.1763554080.strategy.item.level",
                                ]
                            }
                        }
                    },
                }
            ]

    class FakeIncidentDocument:
        @classmethod
        def get(cls, _id):
            return SimpleNamespace(
                snapshot=SimpleNamespace(content=SimpleNamespace(to_dict=lambda: {})),
                bk_biz_id=2,
                extra_info=None,
                feedback=None,
            )

    class FakeAlertDocument:
        def __init__(self, **kwargs):
            self.event = SimpleNamespace(bk_biz_id=None)
            self.extra_info = kwargs["extra_info"]

    namespace = {
        "IncidentBaseResource": FakeIncidentBaseResource,
        "serializers": _serializers,
        "AlertSearchSerializer": object,
        "MAX_INCIDENT_ALERT_SIZE": 300,
        "IncidentDocument": FakeIncidentDocument,
        "IncidentSnapshot": lambda content: SimpleNamespace(alert_entity_mapping={}),
        "AlertDocument": FakeAlertDocument,
        "AIOPSManager": SimpleNamespace(get_graph_panel=lambda *args, **kwargs: {}),
        "resource": SimpleNamespace(
            commons=SimpleNamespace(get_label=lambda: [{"id": "application", "children": [{"id": "application"}]}])
        ),
    }
    exec(resource_source, namespace)

    result = namespace["IncidentAlertViewResource"]().perform_request({"id": 1})
    alert = result[0]["alerts"][0]

    assert alert["anomaly_timestamps"] == [1763554080, 1763554200]


def test_incident_list_fetches_enabled_spaces_with_contract_pagination_and_history_fallback():
    resource_cls, remote_cls = _load_incident_list_resource(
        remote_responses=[
            {
                "objects": [
                    {
                        "scope_id": "bkci_project_with_underscore",
                        "content": {
                            "enabled": True,
                            "scope_identity": {"space": {"id": 88888, "space_type_id": "bkci"}},
                        },
                    },
                    {"scope_id": "bkcc_2", "content": {"enabled": True}},
                    {
                        "scope_id": "unknown_scope",
                        "content": {
                            "enabled": True,
                            "scope_identity": {"space": {"id": float("nan"), "space_type_id": "bkci"}},
                        },
                    },
                    {"scope_id": "bkcc_3", "content": {"enabled": False}},
                ],
                "current_page": 1,
                "total_pages": 2,
                "has_next": True,
            },
            {
                "objects": [
                    {"scope_id": "bkcc_2", "content": {"enabled": True}},
                    {"scope_id": "bksaas_app", "content": {"enabled": True}},
                ],
                "current_page": 2,
                "has_next": False,
            },
        ],
        authorized_biz_ids=[-88888, -99999, 2, 3],
    )

    enabled_spaces = resource_cls.fetch_enabled_spaces([-1])

    assert enabled_spaces == [-88888, 2, -99999]
    assert remote_cls.calls == [
        {
            "config_type": "general_config",
            "scope_type": "bkci",
            "scope_value": "project_with_underscore",
            "scope_id_list": ["bkci_project_with_underscore", "bksaas_app", "bkcc_2", "bkcc_3"],
            "page": 1,
            "page_size": 1000,
        },
        {
            "config_type": "general_config",
            "scope_type": "bkci",
            "scope_value": "project_with_underscore",
            "scope_id_list": ["bkci_project_with_underscore", "bksaas_app", "bkcc_2", "bkcc_3"],
            "page": 2,
            "page_size": 1000,
        },
    ]


def test_incident_list_limits_enabled_space_query_to_authorized_scope():
    resource_cls, remote_cls = _load_incident_list_resource(
        remote_responses=[{"objects": [], "current_page": 1, "has_next": False}],
        authorized_biz_ids=[2, 3],
    )

    assert resource_cls.fetch_enabled_spaces([2, 4]) == []
    assert remote_cls.calls[0]["scope_id_list"] == ["bkcc_2"]


def test_incident_list_expands_monitor_sentinels_before_calling_bkfara():
    for requested_biz_ids in ([], [-1], [-2]):
        resource_cls, remote_cls = _load_incident_list_resource(
            remote_responses=[{"objects": [], "current_page": 1, "has_next": False}],
            authorized_biz_ids=[2, 3],
        )

        assert resource_cls.fetch_enabled_spaces(requested_biz_ids) == []
        assert remote_cls.calls[0]["scope_id_list"] == ["bkcc_2", "bkcc_3"]


def test_incident_list_degrades_enabled_spaces_when_list_configs_fails():
    resource_cls, _ = _load_incident_list_resource(
        remote_responses=[RuntimeError("list_configs failed")],
        authorized_biz_ids=[2],
    )

    assert resource_cls.fetch_enabled_spaces([2]) == []


def test_bk_incident_api_keeps_standard_scope_ids_when_converting_lists():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class IncidentBaseResource")
    resource_end = source.index("class GetTemplateListResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "def is_standard_scope_id" in resource_source
    assert "is_standard_scope_id(bk_biz_id)" in resource_source


def test_bk_incident_api_converts_negative_biz_ids_to_standard_scope_ids():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    resource_source = source[source.index("class IncidentBaseResource") : source.index("class GetTemplateListResource")]

    class FakeAPIResource:
        def perform_request(self, validated_request_data):
            return validated_request_data

    class FakeSpaceApi:
        calls = []

        @classmethod
        def get_space_detail(cls, bk_biz_id):
            cls.calls.append(bk_biz_id)
            return SimpleNamespace(space_type_id="bkci", space_id="bkce")

    def fake_bk_biz_id_to_scope_id(bk_biz_id):
        if isinstance(bk_biz_id, str) and bk_biz_id.startswith(("bkcc_", "bcs_", "bkci_", "bksaas_")):
            return bk_biz_id
        numeric_bk_biz_id = int(bk_biz_id)
        if numeric_bk_biz_id in {-1, -2}:
            raise ValueError("monitor query sentinel must be expanded before scope conversion")
        if numeric_bk_biz_id < 0:
            space = FakeSpaceApi.get_space_detail(numeric_bk_biz_id)
            return f"{space.space_type_id}_{space.space_id}"
        return f"bkcc_{numeric_bk_biz_id}"

    namespace = {
        "abc": abc,
        "APIResource": FakeAPIResource,
        "settings": SimpleNamespace(BK_INCIDENT_APIGW_URL="", BK_COMPONENT_API_URL=""),
        "bk_biz_id_to_scope_id": fake_bk_biz_id_to_scope_id,
    }
    exec(resource_source, namespace)
    resource = namespace["IncidentBaseResource"]()

    params = resource.perform_request(
        {
            "bk_biz_id": -88888,
            "bk_biz_id_list": [-88888],
            "bk_biz_id_config": {"scope_id_list_open": [-88888]},
        }
    )
    assert params == {
        "scope_type": "bkci",
        "scope_value": "bkce",
        "scope_id_list": ["bkci_bkce"],
        "scope_id_config": {"scope_id_list_open": ["bkci_bkce"]},
    }
    assert FakeSpaceApi.calls == [-88888]

    FakeSpaceApi.calls.clear()
    scope_ids = resource.convert_bk_biz_id_list_to_scope_id_list(
        {"scope_type": "bkcc"}, [-88888, 2, "bkci_existing", "bcs_project"]
    )
    assert scope_ids == ["bkci_bkce", "bkcc_2", "bkci_existing", "bcs_project"]
    assert FakeSpaceApi.calls == [-88888]


def test_bk_incident_api_keeps_bkcc_ids_after_converting_first_non_bkcc_space():
    """incident_list 会把 bk_biz_ids[0] 写成 scope_type，不能让后续正数业务被编成 bkci_2。"""
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    resource_source = source[source.index("class IncidentBaseResource") : source.index("class GetTemplateListResource")]

    class FakeAPIResource:
        def perform_request(self, validated_request_data):
            return validated_request_data

    namespace = {
        "abc": abc,
        "APIResource": FakeAPIResource,
        "settings": SimpleNamespace(BK_INCIDENT_APIGW_URL="", BK_COMPONENT_API_URL=""),
        "bk_biz_id_to_scope_id": lambda bk_biz_id: ("bkci_bkce" if int(bk_biz_id) < 0 else f"bkcc_{int(bk_biz_id)}"),
    }
    exec(resource_source, namespace)
    resource = namespace["IncidentBaseResource"]()
    params = resource.perform_request(
        {
            "bk_biz_id": -88888,
            "bk_biz_id_list": [-88888, 2],
        }
    )

    assert params["scope_type"] == "bkci"
    assert params["scope_value"] == "bkce"
    assert params["scope_id_list"] == ["bkci_bkce", "bkcc_2"]
    assert "scope_id_config" not in params


def test_bk_incident_api_propagates_unresolved_scope_conversion():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    resource_source = source[source.index("class IncidentBaseResource") : source.index("class GetTemplateListResource")]

    class FakeAPIResource:
        def perform_request(self, validated_request_data):
            return validated_request_data

    conversion_calls = []

    def failing_scope_converter(bk_biz_id):
        conversion_calls.append(int(bk_biz_id))
        raise ValueError(f"cannot resolve bk_biz_id: {bk_biz_id}")

    namespace = {
        "abc": abc,
        "APIResource": FakeAPIResource,
        "settings": SimpleNamespace(BK_INCIDENT_APIGW_URL="", BK_COMPONENT_API_URL=""),
        "bk_biz_id_to_scope_id": failing_scope_converter,
    }
    exec(resource_source, namespace)
    resource = namespace["IncidentBaseResource"]()

    try:
        resource.perform_request(
            {
                "bk_biz_id": -88888,
                "bk_biz_id_list": [-88888],
                "bk_biz_id_config": {"scope_id_list_open": [-88888]},
            }
        )
    except ValueError as error:
        assert str(error) == "cannot resolve bk_biz_id: -88888"
    else:
        raise AssertionError("未解析的监控空间不能降级为非标准 BKFara scope")
    assert conversion_calls == [-88888]
