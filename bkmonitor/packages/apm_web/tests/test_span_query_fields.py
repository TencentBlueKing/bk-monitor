"""APM Span 字段元数据查询测试。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from apm_web.constants import QueryMode
from apm_web.handlers.backend_data_handler import TraceBackendHandler
from apm_web.handlers.instance_handler import InstanceHandler
from apm_web.handlers.query.span import SpanQuery
from apm_web.handlers.trace_handler.view_config import TraceFieldsHandler, TraceFieldsInfoHandler
from apm_web.models import Application
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


def _make_uq_field(
    field_name: str,
    field_type: str,
    *,
    is_searchable: bool = True,
    is_agg: bool = True,
    is_list: bool = True,
    supported_operations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "field_type": field_type,
        "is_searchable": is_searchable,
        "is_agg": is_agg,
        "is_list": is_list,
        "supported_operations": supported_operations or [],
    }


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


def test_span_query_fields_by_application_uses_retention_time_range(mocker) -> None:
    app: Any = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields", autospec=True, return_value={})

    assert SpanQuery.query_fields_by_application(app) == {}

    query = query_fields.call_args.args[0]
    assert query.data_sources == [TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app")]
    query_fields.assert_called_once_with(query, 1_722_395_200, 1_723_000_000)


def test_application_retention_time_range_uses_es_retention(mocker) -> None:
    start_time = datetime(2024, 7, 31, tzinfo=UTC)
    end_time = datetime(2024, 8, 30, tzinfo=UTC)
    get_datetime_range = mocker.patch(
        "apm_web.models.application.get_datetime_range",
        return_value=(start_time, end_time),
    )
    application = Application(bk_biz_id=2, app_name="app")
    application.__dict__["es_retention"] = 30

    assert application.list_retention_time_range() == (int(start_time.timestamp()), int(end_time.timestamp()))
    get_datetime_range.assert_called_once_with(period="day", distance=30, rounding=False)


def test_trace_fields_handler_directly_maps_unify_query_metadata(mocker) -> None:
    supported_operations = [{"operator": "custom"}]
    fields_info = {
        OtlpKey.SPAN_ID: _make_uq_field(
            OtlpKey.SPAN_ID,
            "keyword",
            is_searchable=False,
            is_agg=True,
            is_list=False,
            supported_operations=supported_operations,
        )
    }
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app", username="admin")

    field_info = handler.get_fields_info(QueryMode.SPAN, [OtlpKey.SPAN_ID])[0]
    assert field_info["type"] == "keyword"
    assert field_info["is_searched"] is False
    assert field_info["is_dimensions"] is True
    assert field_info["can_displayed"] is False
    assert field_info["supported_operations"] == supported_operations


def test_trace_fields_handler_only_returns_leaf_fields(mocker) -> None:
    fields_info = {
        OtlpKey.RESOURCE: _make_uq_field(
            OtlpKey.RESOURCE,
            "object",
            is_searchable=False,
            is_agg=False,
            is_list=False,
        ),
        "events": _make_uq_field(
            "events",
            "nested",
            is_searchable=False,
            is_agg=False,
            is_list=False,
        ),
        "resource.custom_name": _make_uq_field("resource.custom_name", "keyword"),
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
    query_fields = mocker.patch.object(
        SpanQuery,
        "query_fields_by_application",
        return_value={"span_name": _make_uq_field("span_name", "keyword")},
    )

    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app", username="admin")

    assert handler.span_fields_info == {"span_name": _make_uq_field("span_name", "keyword")}
    query_fields.assert_called_once_with(app)


def test_trace_precalculated_fields_have_query_field_metadata() -> None:
    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app", username="admin")

    field_info = next(iter(handler.pre_calculate_fields_info.values()))

    assert {"field_type", "is_searchable", "is_agg", "is_list", "supported_operations"} <= field_info.keys()


def test_trace_collection_kind_keeps_keyword_query_semantics() -> None:
    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app", username="admin")
    handler.__dict__["span_fields_info"] = {
        OtlpKey.KIND: _make_uq_field(OtlpKey.KIND, "integer", supported_operations=[{"operator": "gt"}])
    }

    field_info = handler.trace_collections_fields_info["collections.kind"]

    assert field_info["field_type"] == "keyword"
    assert field_info["is_searchable"] is True
    assert field_info["is_agg"] is True
    assert field_info["is_list"] is True
    assert {operation["operator"] for operation in field_info["supported_operations"]} == {
        "equal",
        "not_equal",
        "exists",
        "not exists",
        "like",
        "not_like",
    }


def test_trace_fields_handler_returns_empty_fields_when_unify_query_returns_empty(mocker) -> None:
    app: Any = _make_application()
    mocker.patch(
        "apm_web.handlers.trace_handler.view_config.Application.objects.get",
        return_value=app,
    )
    query_fields = mocker.patch.object(SpanQuery, "query_fields_by_application", return_value={})

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app", username="admin")

    assert handler.get_fields_by_mode(QueryMode.SPAN) == []
    query_fields.assert_called_once_with(app)


def test_instance_span_fields_only_keeps_resource_leaf_fields(mocker) -> None:
    app: Any = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields_by_application")
    query_fields.return_value = {
        OtlpKey.RESOURCE: _make_uq_field(
            OtlpKey.RESOURCE,
            "object",
            is_searchable=False,
            is_agg=False,
            is_list=False,
        ),
        "resource.custom_name": _make_uq_field("resource.custom_name", "keyword"),
        InstanceHandler.BK_INSTANCE_ID_FIELD_NAME: _make_uq_field(InstanceHandler.BK_INSTANCE_ID_FIELD_NAME, "keyword"),
        "attributes.custom_name": _make_uq_field("attributes.custom_name", "keyword"),
    }

    fields = InstanceHandler.get_span_fields(app)

    assert fields == [{"id": "resource.custom_name", "name": "resource.custom_name", "alias": None}]
    query_fields.assert_called_once_with(app)


def test_trace_storage_field_info_uses_searchable_unify_query_fields(mocker) -> None:
    app: Any = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields_by_application")
    query_fields.return_value = {
        OtlpKey.RESOURCE: {"field_type": "object", "is_searchable": False},
        OtlpKey.SPAN_NAME: {"field_type": "keyword", "is_searchable": True},
        "attributes.message": {"field_type": "text", "is_searchable": True},
        "time": {"field_type": "date", "is_searchable": True},
        "attributes.status": {"field_type": "conflict", "is_searchable": True},
    }
    get_result_table = mocker.patch(
        "apm_web.handlers.backend_data_handler.api.metadata.get_result_table",
        return_value={
            "field_list": [
                {"field_name": OtlpKey.SPAN_NAME, "description": "Span 名称"},
                {"field_name": "attributes.message", "description": "消息内容"},
            ]
        },
    )

    fields = TraceBackendHandler(app).storage_field_info()

    assert fields == [
        {
            "field_name": OtlpKey.SPAN_NAME,
            "ch_field_name": "Span 名称",
            "analysis_field": False,
            "field_type": "keyword",
            "time_field": False,
        },
        {
            "field_name": "attributes.message",
            "ch_field_name": "消息内容",
            "analysis_field": True,
            "field_type": "text",
            "time_field": False,
        },
        {
            "field_name": "time",
            "ch_field_name": "",
            "analysis_field": False,
            "field_type": "date",
            "time_field": True,
        },
        {
            "field_name": "attributes.status",
            "ch_field_name": "",
            "analysis_field": False,
            "field_type": "conflict",
            "time_field": False,
        },
    ]
    query_fields.assert_called_once_with(app)
    get_result_table.assert_called_once_with({"table_id": "2_bkapm.trace_app"})


def test_trace_storage_field_info_returns_empty_without_metadata_fallback(mocker) -> None:
    app: Any = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields_by_application", return_value={})
    get_result_table = mocker.patch("apm_web.handlers.backend_data_handler.api.metadata.get_result_table")

    assert TraceBackendHandler(app).storage_field_info() == []
    query_fields.assert_called_once_with(app)
    get_result_table.assert_not_called()
