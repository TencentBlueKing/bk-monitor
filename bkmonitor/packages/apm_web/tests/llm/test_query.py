from unittest import TestCase, mock

from django.db.models import Q

from bkmonitor.data_source.data_source import q_to_dict
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import OtlpKey

from apm_web.llm.query import LLMQuery


class LLMQueryTestCase(TestCase):
    def setUp(self):
        self.query = LLMQuery(
            [
                TraceDatasourceTarget.build(
                    bk_biz_id=11,
                    app_name="demo",
                    table_id="11_bkapm.trace_demo",
                    retention=7,
                )
            ]
        )

    def test_query_group_list(self):
        with mock.patch.object(
            self.query,
            "_query_list",
            return_value=[{"attributes.session.id": "session-2"}, {"attributes.session.id": "session-1"}],
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field="attributes.session.id",
                offset=0,
                limit=20,
                filters=[],
            )

        self.assertEqual(group_ids, ["session-2", "session-1"])

    def test_query_group_list_with_nested_field(self):
        with mock.patch.object(
            self.query,
            "_query_list",
            return_value=[
                {
                    "attributes": {
                        "gen_ai": {
                            "conversation": {"id": "conversation-1"},
                        },
                    }
                }
            ],
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field="attributes.gen_ai.conversation.id",
                offset=0,
                limit=20,
                filters=[],
            )

        self.assertEqual(group_ids, ["conversation-1"])

    def test_query_by_group_ids(self):
        query_builder = mock.Mock()
        query_builder.order_by.return_value = query_builder
        query_builder.filter.return_value = query_builder
        spans = [{"trace_id": "trace-1", "span_id": "span-1"}]

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=spans) as query_list,
        ):
            result = self.query.query_by_group_ids(
                group_field="attributes.session.id",
                group_ids=["session-1", "session-2"],
                start_time=1,
                end_time=2,
            )

        self.assertEqual(result, spans)
        build_queries.assert_called_once_with(time_field="start_time")
        query_builder.order_by.assert_called_once_with("start_time")
        query_builder.filter.assert_called_once_with(**{"attributes.session.id__eq": ["session-1", "session-2"]})
        query_list.assert_called_once_with([query_builder], 1, 2, 0, 10000)

    def test_query_group_trace_list(self):
        query_builder = mock.Mock()
        query_builder.filter.return_value = query_builder
        query_builder.distinct.return_value = query_builder
        query_builder.values.return_value = query_builder
        records = [
            {"attributes.session.id": "session-1", "trace_id": "trace-1"},
            {"attributes.session.id": "session-1", "trace_id": "trace-2"},
        ]

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=records) as query_list,
        ):
            result = self.query.query_group_trace_list(
                group_field="attributes.session.id",
                group_ids=["session-1"],
            )

        self.assertEqual(result, records)
        build_queries.assert_called_once_with()
        query_builder.filter.assert_called_once_with(**{"attributes.session.id__eq": ["session-1"]})
        query_builder.distinct.assert_called_once_with(OtlpKey.TRACE_ID)
        query_builder.values.assert_called_once_with("attributes.session.id", OtlpKey.TRACE_ID)
        query_list.assert_called_once_with([query_builder], None, None, 0, 10000)

    def test_keyword_filters_before_group_pagination(self):
        value = ["search-text"]
        keyword_fields = [
            "trace_id",
            "attributes.user.id",
            "attributes.gen_ai.user.id",
            "attributes.gen_ai.conversation.id",
            "attributes.gen_ai.session.id",
        ]
        with mock.patch.object(self.query, "_query_list", return_value=[{"trace_id": "trace-1"}]) as query_list:
            result = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field="trace_id",
                offset=20,
                limit=10,
                filters=[{"key": "resource.service.name", "operator": "equal", "value": ["agent-service"]}],
                query_string="_exists_:attributes.gen_ai.span.kind",
                keyword=value[0],
                keyword_fields=keyword_fields,
            )

        expected = Q(**{"resource.service.name__eq": ["agent-service"]}) & (
            Q(trace_id__eq=value)
            | Q(**{"attributes.user.id__include": value})
            | Q(**{"attributes.gen_ai.user.id__include": value})
            | Q(**{"attributes.gen_ai.conversation.id__include": value})
            | Q(**{"attributes.gen_ai.session.id__include": value})
        )
        query_list.assert_called_once()
        queries, *pagination = query_list.call_args.args
        self.assertEqual(pagination, [1, 2, 20, 10])
        self.assertEqual(len(queries), 1)
        query = queries[0].query
        self.assertEqual(q_to_dict(query.where), q_to_dict(expected))
        self.assertEqual(query.distinct, "trace_id")
        self.assertEqual(query.select, ["trace_id"])
        self.assertEqual(query.order_by, ["end_time desc"])
        self.assertEqual(query.raw_query_string, "_exists_:attributes.gen_ai.span.kind")
        self.assertEqual(result, ["trace-1"])

    def test_empty_keyword_keeps_only_service_filter(self):
        with mock.patch.object(self.query, "_query_list", return_value=[]) as query_list:
            result = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field="attributes.gen_ai.conversation.id",
                offset=0,
                limit=20,
                filters=[{"key": "resource.service.name", "operator": "equal", "value": ["agent-service"]}],
                keyword="",
                keyword_fields=["attributes.user.id", "attributes.gen_ai.conversation.id"],
            )

        query = query_list.call_args.args[0][0].query
        self.assertEqual(q_to_dict(query.where), {"resource.service.name__eq": ["agent-service"]})
        self.assertEqual(result, [])
