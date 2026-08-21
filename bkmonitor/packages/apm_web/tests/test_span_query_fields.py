"""APM Span 字段元数据查询测试。"""

from types import SimpleNamespace
from typing import Any

from apm_web.constants import QueryMode
from apm_web.handlers.instance_handler import InstanceHandler
from apm_web.handlers.query.span import SpanQuery
from apm_web.handlers.trace_handler.view_config import TraceFieldsHandler, TraceFieldsInfoHandler
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from constants.apm import OtlpKey


def _make_application() -> SimpleNamespace:
    return SimpleNamespace(
        bk_biz_id=2,
        app_name="app",
        trace_result_table_id="2_bkapm.trace_app",
        list_retention_time_range=lambda: (1_722_395_200, 1_723_000_000),
    )


def test_span_query_fields_uses_table_and_space_uid(mocker) -> None:
    start_time = 1_722_395_200
    end_time = 1_723_000_000
    query_fields = mocker.patch.object(BaseQuery, "_query_fields", autospec=True, return_value={})
    mocker.patch(
        "apm_web.handlers.query.span.bk_biz_id_to_space_uid",
        side_effect=["bkcc__2", "bkcc__3"],
    )
    data_sources = [
        TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app"),
        TraceDatasourceTarget.build(3, "other-app", "3_bkapm.trace_other_app"),
    ]

    query = SpanQuery(data_sources)

    assert query.query_fields(start_time, end_time) == {}
    query_fields.assert_called_once_with(
        query,
        [
            ("2_bkapm.trace_app", "bkcc__2"),
            ("3_bkapm.trace_other_app", "bkcc__3"),
        ],
        start_time,
        end_time,
    )


def test_trace_fields_handler_reads_unify_query_field_type(mocker) -> None:
    fields_info = {
        OtlpKey.SPAN_NAME: {
            "field_name": OtlpKey.SPAN_NAME,
            "field_type": "keyword",
        }
    }
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app", username="admin")

    assert handler.get_fields_by_mode(QueryMode.SPAN)[0]["type"] == "keyword"


def test_trace_fields_handler_only_returns_leaf_fields(mocker) -> None:
    fields_info = {
        OtlpKey.RESOURCE: {"field_type": "object"},
        "events": {"field_type": "nested"},
        "resource.custom_name": {"field_type": "keyword"},
    }
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app", username="admin")

    assert [field["name"] for field in handler.get_fields_by_mode(QueryMode.SPAN)] == ["resource.custom_name"]


def test_trace_fields_info_handler_builds_span_query_from_local_application(mocker) -> None:
    app: Any = _make_application()
    mocker.patch(
        "apm_web.handlers.trace_handler.view_config.Application.objects.get",
        return_value=app,
    )
    span_query = mocker.patch("apm_web.handlers.trace_handler.view_config.SpanQuery")
    span_query.return_value.query_fields.return_value = {"span_name": {"field_type": "keyword"}}

    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app", username="admin")

    assert handler.span_fields_info == {"span_name": {"field_type": "keyword"}}
    span_query.assert_called_once_with([TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app")])
    span_query.return_value.query_fields.assert_called_once_with(1_722_395_200, 1_723_000_000)


def test_trace_fields_handler_returns_empty_fields_when_unify_query_returns_empty(mocker) -> None:
    app: Any = _make_application()
    mocker.patch(
        "apm_web.handlers.trace_handler.view_config.Application.objects.get",
        return_value=app,
    )
    span_query = mocker.patch("apm_web.handlers.trace_handler.view_config.SpanQuery")
    span_query.return_value.query_fields.return_value = {}

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app", username="admin")

    assert handler.get_fields_by_mode(QueryMode.SPAN) == []
    span_query.return_value.query_fields.assert_called_once_with(1_722_395_200, 1_723_000_000)


def test_instance_span_fields_only_keeps_resource_leaf_fields(mocker) -> None:
    app: Any = _make_application()
    span_query = mocker.patch("apm_web.handlers.instance_handler.SpanQuery")
    span_query.return_value.query_fields.return_value = {
        OtlpKey.RESOURCE: {"field_type": "object"},
        "resource.custom_name": {"field_type": "keyword"},
        InstanceHandler.BK_INSTANCE_ID_FIELD_NAME: {"field_type": "keyword"},
        "attributes.custom_name": {"field_type": "keyword"},
    }

    fields = InstanceHandler.get_span_fields(app)

    assert fields == [{"id": "resource.custom_name", "name": "resource.custom_name", "alias": None}]
    span_query.assert_called_once_with([TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app")])
    span_query.return_value.query_fields.assert_called_once_with(1_722_395_200, 1_723_000_000)
