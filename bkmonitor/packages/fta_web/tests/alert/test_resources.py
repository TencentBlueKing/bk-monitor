from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from fta_web.alert import resources as alert_resources
from fta_web.alert.resources import AlertDetailResource, AlertTopNResource


class TestAlertTopNResource:
    def test_request_serializer_rejects_too_many_nested_fields(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"tags.field_{index}" for index in range(21)],
                "size": 10,
            }
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_request_serializer_allows_nested_fields_within_limit(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"tags.field_{index}" for index in range(20)],
                "size": 10,
            }
        )

        serializer.is_valid(raise_exception=True)
        assert len(serializer.validated_data["fields"]) == 20

    def test_request_serializer_rejects_prefixed_nested_fields(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"-tags.field_{index}" for index in range(21)],
                "size": 10,
            }
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TestAlertDetailResource:
    def test_perform_request_allows_empty_graph_panel(self, monkeypatch):
        alert_id = "17742505258462064"
        fake_alert = SimpleNamespace(event=SimpleNamespace(bk_biz_id=8))

        monkeypatch.setattr(alert_resources.AlertDocument, "get", lambda _alert_id: fake_alert)
        monkeypatch.setattr(alert_resources.AIOPSManager, "get_graph_panel", lambda _alert: None)
        monkeypatch.setattr(AlertDetailResource, "get_relation_info", lambda self, alert, length_limit=True: "recent")
        monkeypatch.setattr(
            alert_resources.AlertQueryHandler,
            "clean_document",
            lambda alert: {"plugin_id": "test_plugin", "dimensions": []},
        )
        monkeypatch.setattr(
            alert_resources.PluginTranslator,
            "translate",
            lambda self, plugin_ids: {"test_plugin": "Test Plugin"},
        )
        monkeypatch.setattr(
            alert_resources,
            "resource",
            SimpleNamespace(
                alert=SimpleNamespace(
                    alert_related_info=lambda ids=None, alerts=None: {alert_id: {"topo_info": "topo"}}
                )
            ),
        )

        result = AlertDetailResource().perform_request({"id": alert_id, "bk_biz_id": 8})

        assert result["graph_panel"] is None
        assert result["plugin_display_name"] == "Test Plugin"
        assert result["relation_info"] == "topo recent"
