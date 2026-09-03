"""APM Span 字段元数据查询测试。"""

from typing import Any, cast

import pytest
from django.db.models import Q

from apm_web.constants import QueryMode
from apm_web.handlers.backend_data_handler import TraceBackendHandler
from apm_web.handlers.instance_handler import InstanceHandler
from apm_web.handlers.query import get_query
from apm_web.handlers.query.base import BaseQuery as APMBaseQuery
from apm_web.handlers.query.span import SpanQuery
from apm_web.handlers.trace_handler.view_config import TraceFieldsHandler, TraceFieldsInfoHandler
from apm_web.models import Application
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery as DataSourceBaseQuery
from constants.apm import OtlpKey, PreCalculateSpecificField


def _make_application() -> Application:
    application = Application(bk_biz_id=2, app_name="app", trace_result_table_id="2_bkapm.trace_app")
    cast(dict[str, Any], application.__dict__)["es_retention"] = 30
    return application


def _make_uq_field(
    field_name: str,
    field_type: str,
    *,
    is_searchable: bool = True,
    is_agg: bool = True,
    is_list: bool = True,
    field_alias: str | None = None,
    origin_field: str | None = None,
    supported_operations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "field_alias": field_name if field_alias is None else field_alias,
        "field_type": field_type,
        "origin_field": field_name.split(".", 1)[0] if origin_field is None else origin_field,
        "is_searchable": is_searchable,
        "is_agg": is_agg,
        "is_list": is_list,
        "supported_operations": supported_operations or [],
    }


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [
        (1_722_395_200, 1_723_000_000),
        (None, None),
    ],
)
def test_span_query_fields_uses_table_and_space_uid(mocker, start_time: int | None, end_time: int | None) -> None:
    query_fields = mocker.patch.object(APMBaseQuery, "_query_fields", autospec=True, return_value={})
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


def test_span_query_build_queries(mocker) -> None:
    data_source = TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app")
    query_builder = mocker.Mock()
    query_builder.time_field.return_value = query_builder
    query_builder.filter.return_value = query_builder
    query_builder.query_string.return_value = query_builder
    get_q = mocker.patch("apm_web.handlers.query.span.TraceQueryGuard.get_q", return_value=query_builder)

    query = SpanQuery([data_source])

    assert query.build_queries(query_string="span_name:chat", time_field=OtlpKey.START_TIME) == [query_builder]
    get_q.assert_called_once_with([data_source])
    query_builder.time_field.assert_called_once_with(OtlpKey.START_TIME)
    query_builder.filter.assert_called_once_with(Q())
    query_builder.query_string.assert_called_once_with("span_name:chat")


def test_span_query_get_qs_uses_business_scope(mocker) -> None:
    data_source = TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app")
    queryset = mocker.Mock()
    scoped_queryset = mocker.Mock()
    queryset.scope.return_value = scoped_queryset
    get_qs = mocker.patch.object(DataSourceBaseQuery, "get_qs", autospec=True, return_value=queryset)

    query = SpanQuery([data_source])

    assert query.get_qs(1_722_395_200, 1_723_000_000) is scoped_queryset
    get_qs.assert_called_once_with(query, 1_722_395_200, 1_723_000_000)
    queryset.scope.assert_called_once_with(2)


def test_application_build_data_sources_uses_trace_retention() -> None:
    app = _make_application()

    assert app.build_data_sources() == [
        TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app", retention=30),
    ]


def test_get_query_initializes_span_query() -> None:
    data_sources = [TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app", retention=30)]

    query = get_query(data_sources)

    assert isinstance(query, SpanQuery)
    assert query.data_sources == data_sources
    assert query.retention == 30


def test_apm_base_query_logs_data_sources_when_fields_are_empty(mocker) -> None:
    data_sources = [TraceDatasourceTarget.build(2, "app", "2_bkapm.trace_app", retention=30)]
    query = APMBaseQuery(data_sources)
    query_fields = mocker.patch.object(DataSourceBaseQuery, "_query_fields", autospec=True, return_value={})
    logger = mocker.patch("apm_web.handlers.query.base.logger")

    assert query._query_fields([("2_bkapm.trace_app", "bkcc__2")], None, None) == {}

    query_fields.assert_called_once_with(query, [("2_bkapm.trace_app", "bkcc__2")], None, None)
    logger.warning.assert_called_once_with(
        "[BaseQuery] query fields returned empty: data_sources=%s",
        data_sources,
    )


def test_trace_fields_handler_maps_query_metadata_but_calculates_dimensions(mocker) -> None:
    supported_operations = [{"operator": "custom"}]
    fields_info = {
        "attributes.custom_name": _make_uq_field(
            "attributes.custom_name",
            "keyword",
            is_agg=False,
            supported_operations=supported_operations,
        )
    }
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    field_info = handler.get_fields_info(QueryMode.SPAN, ["attributes.custom_name"])[0]
    assert field_info["type"] == "keyword"
    assert field_info["is_searched"] is True
    assert field_info["is_dimensions"] is True
    assert field_info["can_displayed"] is True
    assert field_info["supported_operations"] == supported_operations


@pytest.mark.parametrize(
    ("field_name", "field_type"),
    [
        (PreCalculateSpecificField.TIME.value, "date"),
        (OtlpKey.START_TIME, "long"),
        (OtlpKey.END_TIME, "long"),
        (OtlpKey.SPAN_ID, "keyword"),
        (OtlpKey.TRACE_ID, "keyword"),
    ],
)
def test_span_special_fields_do_not_support_dimensions(mocker, field_name: str, field_type: str) -> None:
    fields_info = {field_name: _make_uq_field(field_name, field_type, is_agg=True)}
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    field_info = handler.get_fields_info(QueryMode.SPAN, [field_name])[0]
    assert field_info["is_dimensions"] is False


def test_span_parent_span_id_still_supports_dimensions(mocker) -> None:
    fields_info = {
        OtlpKey.PARENT_SPAN_ID: _make_uq_field(OtlpKey.PARENT_SPAN_ID, "keyword", is_agg=False),
    }
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    field_info = handler.get_fields_info(QueryMode.SPAN, [OtlpKey.PARENT_SPAN_ID])[0]
    assert field_info["is_dimensions"] is True


@pytest.mark.parametrize("field_type", ["keyword", "integer", "long", "double"])
def test_supported_field_types_support_dimensions_independent_of_is_agg(mocker, field_type: str) -> None:
    field_name = "attributes.custom_name"
    fields_info = {field_name: _make_uq_field(field_name, field_type, is_agg=False)}
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    field_info = handler.get_fields_info(QueryMode.SPAN, [field_name])[0]
    assert field_info["is_dimensions"] is True


@pytest.mark.parametrize("field_type", ["text", "date", "boolean", "conflict"])
def test_unsupported_field_types_do_not_support_dimensions(mocker, field_type: str) -> None:
    field_name = "attributes.custom_name"
    fields_info = {field_name: _make_uq_field(field_name, field_type, is_agg=True)}
    mocker.patch.object(TraceFieldsInfoHandler, "get_fields_info_by_mode", return_value=fields_info)

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    field_info = handler.get_fields_info(QueryMode.SPAN, [field_name])[0]
    assert field_info["is_dimensions"] is False


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

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    assert [field["name"] for field in handler.get_fields_by_mode(QueryMode.SPAN)] == ["resource.custom_name"]


def test_trace_fields_info_handler_builds_span_query_from_local_application(mocker) -> None:
    app = _make_application()
    mocker.patch(
        "apm_web.handlers.trace_handler.view_config.Application.objects.get",
        return_value=app,
    )
    query_fields = mocker.patch.object(
        SpanQuery, "query_fields", autospec=True, return_value={"span_name": _make_uq_field("span_name", "keyword")}
    )

    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app")

    assert handler.span_fields_info == {"span_name": _make_uq_field("span_name", "keyword")}
    query = query_fields.call_args.args[0]
    assert query.data_sources == app.build_data_sources()
    query_fields.assert_called_once_with(query, None, None)


def test_trace_precalculated_fields_have_view_field_metadata() -> None:
    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app")

    field_info = next(iter(handler.pre_calculate_fields_info.values()))

    assert set(field_info) == {"field_type", "is_searchable", "is_list", "supported_operations"}


def test_trace_precalculated_non_dimension_fields_keep_original_semantics() -> None:
    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")
    handler.fields_info_handler.__dict__["span_fields_info"] = {}

    non_dimension_fields = {
        PreCalculateSpecificField.MIN_START_TIME.value,
        PreCalculateSpecificField.MAX_END_TIME.value,
        PreCalculateSpecificField.ROOT_SPAN_ID.value,
        PreCalculateSpecificField.TRACE_ID.value,
    }

    fields_info = handler.get_fields_info(QueryMode.TRACE, list(non_dimension_fields))
    assert all(field_info["is_dimensions"] is False for field_info in fields_info)


def test_trace_collection_kind_keeps_keyword_query_semantics() -> None:
    handler = TraceFieldsInfoHandler(bk_biz_id=2, app_name="app")
    handler.__dict__["span_fields_info"] = {
        OtlpKey.KIND: _make_uq_field(OtlpKey.KIND, "integer", supported_operations=[{"operator": "gt"}])
    }

    field_info = handler.trace_collections_fields_info["collections.kind"]

    assert field_info["field_type"] == "keyword"
    assert field_info["is_searchable"] is True
    assert "is_agg" not in field_info
    assert field_info["is_list"] is True
    assert {operation["operator"] for operation in field_info["supported_operations"]} == {
        "equal",
        "not_equal",
        "exists",
        "not exists",
        "like",
        "not_like",
    }


def test_trace_collection_dimensions_do_not_depend_on_unify_query_is_agg() -> None:
    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")
    handler.fields_info_handler.__dict__["span_fields_info"] = {
        OtlpKey.SPAN_NAME: _make_uq_field(OtlpKey.SPAN_NAME, "keyword", is_agg=False),
    }

    field_info = handler.get_fields_info(QueryMode.TRACE, ["collections.span_name"])[0]

    assert field_info["is_dimensions"] is True


def test_trace_fields_handler_returns_empty_fields_when_unify_query_returns_empty(mocker) -> None:
    app = _make_application()
    mocker.patch(
        "apm_web.handlers.trace_handler.view_config.Application.objects.get",
        return_value=app,
    )
    query_fields = mocker.patch.object(SpanQuery, "query_fields", autospec=True, return_value={})

    handler = TraceFieldsHandler(bk_biz_id=2, app_name="app")

    assert handler.get_fields_by_mode(QueryMode.SPAN) == []
    query = query_fields.call_args.args[0]
    assert query.data_sources == app.build_data_sources()
    query_fields.assert_called_once_with(query, None, None)


def test_instance_span_fields_only_keeps_resource_leaf_fields(mocker) -> None:
    app = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields", autospec=True)
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
    query = query_fields.call_args.args[0]
    assert query.data_sources == app.build_data_sources()
    query_fields.assert_called_once_with(query, None, None)


def test_instance_span_fields_preserve_unify_query_order(mocker) -> None:
    app = _make_application()
    field_names = ["resource.z_field", "resource.a_field", "resource.m_field", "resource.b_field"]
    mocker.patch.object(
        SpanQuery,
        "query_fields",
        autospec=True,
        return_value={field_name: _make_uq_field(field_name, "keyword") for field_name in field_names},
    )

    fields = InstanceHandler.get_span_fields(app)

    assert [field["id"] for field in fields] == field_names


def test_trace_storage_field_info_uses_searchable_unify_query_fields(mocker) -> None:
    app = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields", autospec=True)
    query_fields.return_value = {
        OtlpKey.RESOURCE: _make_uq_field(OtlpKey.RESOURCE, "object", is_searchable=False),
        OtlpKey.SPAN_NAME: _make_uq_field(OtlpKey.SPAN_NAME, "keyword", field_alias="接口名称"),
        "attributes.message": _make_uq_field("attributes.message", "text"),
        "time": _make_uq_field("time", "date", field_alias="时间"),
        "attributes.status": _make_uq_field("attributes.status", "conflict"),
    }
    get_result_table = mocker.patch("apm_web.handlers.backend_data_handler.api.metadata.get_result_table")

    fields = TraceBackendHandler(app).storage_field_info()

    assert fields == [
        {
            "field_name": OtlpKey.SPAN_NAME,
            "ch_field_name": "接口名称",
            "analysis_field": False,
            "field_type": "keyword",
            "time_field": False,
        },
        {
            "field_name": "attributes.message",
            "ch_field_name": "attributes.message",
            "analysis_field": True,
            "field_type": "text",
            "time_field": False,
        },
        {
            "field_name": "time",
            "ch_field_name": "时间",
            "analysis_field": False,
            "field_type": "date",
            "time_field": True,
        },
        {
            "field_name": "attributes.status",
            "ch_field_name": "attributes.status",
            "analysis_field": False,
            "field_type": "conflict",
            "time_field": False,
        },
    ]
    query = query_fields.call_args.args[0]
    assert query.data_sources == app.build_data_sources()
    query_fields.assert_called_once_with(query, None, None)
    get_result_table.assert_not_called()


def test_trace_storage_field_info_returns_empty_when_unify_query_returns_empty(mocker) -> None:
    app = _make_application()
    query_fields = mocker.patch.object(SpanQuery, "query_fields", autospec=True, return_value={})
    get_result_table = mocker.patch("apm_web.handlers.backend_data_handler.api.metadata.get_result_table")

    assert TraceBackendHandler(app).storage_field_info() == []
    query = query_fields.call_args.args[0]
    assert query.data_sources == app.build_data_sources()
    query_fields.assert_called_once_with(query, None, None)
    get_result_table.assert_not_called()
