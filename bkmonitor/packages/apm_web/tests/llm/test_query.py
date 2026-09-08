from unittest import TestCase, mock

from django.db.models import Q

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

    def test_keyword_logic_filter(self):
        value = ["search-text"]

        result = self.query._build_filters([{"key": "keyword", "operator": "logic", "value": value}])

        expected = (
            Q(**{f"{OtlpKey.TRACE_ID}__eq": value})
            | Q(**{f"{OtlpKey.SPAN_ID}__eq": value})
            | Q(**{f"{OtlpKey.get_attributes_key('user.id')}__include": value})
            | Q(**{f"{OtlpKey.get_attributes_key('gen_ai.conversation.id')}__include": value})
        )
        self.assertEqual(result, expected)
