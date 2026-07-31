"""故障 TopN 聚合字段与字段白名单测试。"""

from unittest import mock

from bkmonitor.documents.incident import IncidentDocument
from fta_web.alert.handlers.base import _FIELD_MAP_CACHE
from fta_web.alert.handlers.incident import IncidentQueryHandler, IncidentQueryTransformer


class TestIncidentTopNAggField:
    def setup_method(self):
        _FIELD_MAP_CACHE.pop(IncidentQueryTransformer, None)

    def test_incident_text_fields_use_raw_for_aggregation(self):
        assert (
            IncidentQueryTransformer.transform_field_to_es_field("incident_name", for_agg=True)
            == "incident_name.raw"
        )
        assert (
            IncidentQueryTransformer.transform_field_to_es_field("incident_reason", for_agg=True)
            == "incident_reason.raw"
        )

    def test_incident_text_fields_keep_text_for_search(self):
        assert IncidentQueryTransformer.transform_field_to_es_field("incident_name") == "incident_name"
        assert IncidentQueryTransformer.transform_field_to_es_field("incident_reason") == "incident_reason"

    def test_document_mapping_has_raw_multi_fields(self):
        mapping = IncidentDocument._index.to_dict()
        properties = mapping.get("mappings", mapping).get("properties", {})

        assert properties["incident_name"]["type"] == "text"
        assert properties["incident_name"]["fields"]["raw"]["type"] == "keyword"
        assert properties["incident_name"]["fields"]["raw"]["ignore_above"] == 8191
        assert properties["incident_reason"]["type"] == "text"
        assert properties["incident_reason"]["fields"]["raw"]["type"] == "keyword"
        assert properties["incident_reason"]["fields"]["raw"]["ignore_above"] == 8191


class TestIncidentTopNFieldFilter:
    def setup_method(self):
        self.handler = IncidentQueryHandler.__new__(IncidentQueryHandler)

    def test_filter_keeps_allowed_fields_and_drops_unsupported_fields(self):
        fields = [
            "incident_name",
            "status",
            "incident_type",
            "operator",
            "duration",
            "strategy_name",
            "operate_target_string",
            "-assignees",
        ]

        assert self.handler.filter_top_n_fields(fields) == ["incident_name", "status", "-assignees"]

    def test_top_n_passes_only_filtered_fields_to_base_handler(self):
        with mock.patch.object(IncidentQueryHandler, "filter_top_n_fields", return_value=["status"]) as mock_filter:
            with mock.patch(
                "fta_web.alert.handlers.base.BaseQueryHandler.top_n",
                return_value={"doc_count": 0, "fields": []},
            ) as mock_top_n:
                result = self.handler.top_n(
                    ["incident_name", "incident_type", "strategy_name"],
                    size=10,
                    translators=None,
                )

        mock_filter.assert_called_once_with(["incident_name", "incident_type", "strategy_name"])
        mock_top_n.assert_called_once_with(["status"], 10, None)
        assert result == {"doc_count": 0, "fields": []}
