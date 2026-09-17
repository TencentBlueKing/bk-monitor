from unittest import TestCase, mock

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import OtlpKey

from apm_web.llm.adapter.fields import AGENT_CANDIDATE_Q
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

    def test_query_group_list_applies_extra_filter(self):
        query_builder = mock.Mock()
        query_builder.filter.return_value = query_builder
        query_builder.distinct.return_value = query_builder
        query_builder.values.return_value = query_builder
        query_builder.order_by.return_value = query_builder

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=[{"trace_id": "trace-1"}]) as query_list,
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field=OtlpKey.TRACE_ID,
                offset=0,
                limit=20,
                filters=[],
                extra_filter=AGENT_CANDIDATE_Q,
            )

        self.assertEqual(group_ids, ["trace-1"])
        build_queries.assert_called_once_with([], None)
        query_builder.filter.assert_called_once_with(AGENT_CANDIDATE_Q)
        query_builder.distinct.assert_called_once_with(OtlpKey.TRACE_ID)
        query_list.assert_called_once_with([query_builder], 1, 2, 0, 20)

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

    def test_query_by_group_ids_returns_empty_without_query(self):
        with mock.patch.object(self.query, "_query_list") as query_list:
            result = self.query.query_by_group_ids(group_field=OtlpKey.TRACE_ID, group_ids=[])

        self.assertEqual(result, [])
        query_list.assert_not_called()

    def test_query_by_group_ids_splits_large_id_list(self):
        group_ids = [f"trace-{index}" for index in range(self.query.GROUP_ID_BATCH_SIZE + 1)]
        builders: list[mock.Mock] = []

        def _build_queries(**kwargs):
            builder = mock.Mock()
            builder.order_by.return_value = builder

            def _filter(**filter_kwargs):
                builder.filtered_ids = filter_kwargs[f"{OtlpKey.TRACE_ID}__eq"]
                return builder

            builder.filter.side_effect = _filter
            builders.append(builder)
            return [builder]

        def _query_list(queries, start_time, end_time, offset, limit):
            return [{"trace_id": trace_id} for trace_id in queries[0].filtered_ids]

        with (
            mock.patch.object(self.query, "build_queries", side_effect=_build_queries) as build_queries,
            mock.patch.object(self.query, "_query_list", side_effect=_query_list) as query_list,
        ):
            result = self.query.query_by_group_ids(
                group_field=OtlpKey.TRACE_ID,
                group_ids=group_ids,
                start_time=1,
                end_time=2,
            )

        self.assertEqual([span["trace_id"] for span in result], group_ids)
        self.assertEqual(build_queries.call_count, 2)
        self.assertEqual(query_list.call_count, 2)
        self.assertCountEqual(
            [tuple(builder.filtered_ids) for builder in builders],
            [tuple(group_ids[: self.query.GROUP_ID_BATCH_SIZE]), tuple(group_ids[self.query.GROUP_ID_BATCH_SIZE :])],
        )
        for call in query_list.call_args_list:
            self.assertEqual(call.args[1:], (1, 2, 0, 10000))

    def test_iter_by_group_ids_yields_one_batch_per_chunk(self):
        group_ids = [f"trace-{index}" for index in range(self.query.GROUP_ID_BATCH_SIZE + 1)]

        def _build_queries(**kwargs):
            builder = mock.Mock()
            builder.order_by.return_value = builder

            def _filter(**filter_kwargs):
                builder.filtered_ids = filter_kwargs[f"{OtlpKey.TRACE_ID}__eq"]
                return builder

            builder.filter.side_effect = _filter
            return [builder]

        def _query_list(queries, start_time, end_time, offset, limit):
            return [{"trace_id": trace_id} for trace_id in queries[0].filtered_ids]

        with (
            mock.patch.object(self.query, "build_queries", side_effect=_build_queries),
            mock.patch.object(self.query, "_query_list", side_effect=_query_list),
        ):
            batches = list(
                self.query.iter_by_group_ids(
                    group_field=OtlpKey.TRACE_ID,
                    group_ids=group_ids,
                    start_time=1,
                    end_time=2,
                )
            )

        self.assertEqual(len(batches), 2)
        self.assertEqual([span["trace_id"] for span in batches[0]], group_ids[: self.query.GROUP_ID_BATCH_SIZE])
        self.assertEqual([span["trace_id"] for span in batches[1]], group_ids[self.query.GROUP_ID_BATCH_SIZE :])

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
