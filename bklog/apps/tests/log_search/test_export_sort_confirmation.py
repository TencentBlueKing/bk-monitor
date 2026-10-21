"""非时间主排序导出的确认、冻结、分片与整包顺序回归。"""

import copy
import gzip
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from apps.log_search.constants import ExportJobStatus, ExportPartStatus, ExportSearchType
from apps.log_search.export import state
from apps.log_search.export.api import ExportSortConfirmation, create_export_job
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.planner import PartSpec, build_handler, build_parts
from apps.log_search.export.query import normalize_export_sort, time_order
from apps.log_search.export.scheduler import finalize_export
from apps.log_search.export.worker import _write_rows
from apps.log_search.models import LogIndexSet, Scenario, Space
from apps.log_search.serializers import SearchExportSerializer, UnionSearchExportSerializer
from apps.log_search.views.scene_search_views import SceneExportSerializer, SceneSearchViewSet
from apps.log_search.views.search_views import SearchViewSet
from apps.tests.log_search.test_sharded_export import build_policy, create_job


FIELDS = [{"name": "event_time", "type": "long", "unit": "millisecond"}]


class ExportSortTests(SimpleTestCase):
    def test_all_entry_serializers_keep_the_client_confirmation_capability(self):
        for cls in (SearchExportSerializer, UnionSearchExportSerializer, SceneExportSerializer):
            with self.subTest(serializer=cls.__name__):
                serializer = cls(partial=True)
                self.assertEqual(
                    serializer.to_internal_value({"supports_sort_confirmation": True}),
                    {"supports_sort_confirmation": True},
                )
                self.assertFalse(serializer.fields["supports_sort_confirmation"].default)

    def test_only_non_time_primary_sort_is_changed(self):
        cases = [
            ([], [["event_time", "desc"]]),
            (
                [["duration", "desc"], ["level", "asc"]],
                [["event_time", "desc"], ["duration", "desc"], ["level", "asc"]],
            ),
            (
                [["duration", "asc"], ["event_time", "asc"], ["level", "desc"]],
                [["event_time", "desc"], ["duration", "asc"], ["level", "desc"]],
            ),
            (
                [["event_time", "asc"], ["duration", "desc"], ["level", "asc"]],
                [["event_time", "asc"], ["duration", "desc"], ["level", "asc"]],
            ),
            ([["event_time", "desc"], ["duration", "asc"]], [["event_time", "desc"], ["duration", "asc"]]),
            ([["another_date", "asc"]], [["event_time", "desc"], ["another_date", "asc"]]),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                before = copy.deepcopy(original)
                self.assertEqual(normalize_export_sort(original, FIELDS), expected)
                self.assertEqual(original, before)

    def test_incompatible_routes_keep_the_existing_policy(self):
        original = [["duration", "desc"]]
        for fields in ([], FIELDS + [{**FIELDS[0], "name": "other_time"}], FIELDS + [{**FIELDS[0], "unit": "second"}]):
            with self.subTest(fields=fields):
                self.assertEqual(normalize_export_sort(original, fields), original)


class ExportSortCreationTests(TestCase):
    def setUp(self):
        Space.objects.create(space_uid="bkcc__2", bk_biz_id=2, space_type_id="bkcc", space_id="2", space_name="biz")
        self.index = LogIndexSet.objects.create(
            index_set_name="logs", space_uid="bkcc__2", scenario_id=Scenario.ES, category_id="application"
        )
        self.params = {
            "space_uid": "bkcc__2",
            "index_set_id": self.index.pk,
            "start_time": 0,
            "end_time": 1_200_000,
            "supports_sort_confirmation": True,
        }
        self.saved_sort = [["duration", "desc"], ["event_time", "asc"], ["level", "asc"]]
        self.handlers = []

        def handler_factory(params):
            sort = copy.deepcopy(params.get("sort_list") or self.saved_sort)
            handler = Mock(
                origin_order_by=sort,
                base_dict={
                    "query_list": [{"field_name": "event_time"}],
                    "order_by": [f"-{field}" if direction == "desc" else field for field, direction in sort],
                },
                is_desensitize=True,
            )
            handler.pre_get_result.return_value = {"list": [{"event_time": 1}]}
            self.handlers.append(handler)
            return handler

        for target, kwargs in (
            ("is_sharded_export_enabled", {"return_value": True}),
            ("UnifyQueryHandler", {"side_effect": handler_factory}),
            ("SceneUnifyQueryHandler", {"side_effect": handler_factory}),
            ("snapshot_time_fields", {"return_value": FIELDS}),
            ("get_request_username", {"return_value": "tester"}),
            ("get_request_external_username", {"return_value": ""}),
        ):
            patcher = patch(f"apps.log_search.export.api.{target}", **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_saved_default_sort_requires_confirmation_without_creating_a_job(self):
        original = copy.deepcopy(self.params)
        result = create_export_job(self.params)
        self.assertIsInstance(result, ExportSortConfirmation)
        self.assertEqual(result.sort_list, [["event_time", "desc"], ["duration", "desc"], ["level", "asc"]])
        self.assertFalse(ExportJob.objects.exists())
        self.assertFalse(ExportPart.objects.exists())
        self.handlers[-1].pre_get_result.assert_not_called()
        self.assertEqual(self.params, original)

    def test_old_client_keeps_the_original_response_and_sort(self):
        params = {key: value for key, value in self.params.items() if key != "supports_sort_confirmation"}
        job = create_export_job(params)
        self.assertIsInstance(job, ExportJob)
        self.assertEqual(job.search_params["sort_list"], self.saved_sort)
        self.assertIsNone(time_order(job))

    def test_confirmed_sort_is_frozen_and_large_job_gets_multiple_parts(self):
        proposal = create_export_job(self.params)
        confirmed = {**self.params, "sort_list": proposal.sort_list, "export_fields": ["message"]}
        job = create_export_job(confirmed)
        self.assertEqual(ExportJob.objects.count(), 1)
        self.assertEqual(job.search_params["sort_list"], proposal.sort_list)
        self.assertEqual(job.raw_params["sort_list"], proposal.sort_list)
        self.assertEqual(job.search_params["export_fields"], ["message"])
        self.assertEqual(job.base_dict["order_by"], ["-event_time", "-duration", "level"])
        self.assertEqual(time_order(job), "desc")
        with patch("apps.log_search.export.planner.UnifyQueryHandler", return_value=Mock()):
            rebuilt = build_handler(job, 0, 30000)
        self.assertEqual(rebuilt.base_dict["order_by"], job.base_dict["order_by"])
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=1_000_000),
            patch("apps.log_search.export.planner.sample_rows", return_value=[b"row"]),
            patch("apps.log_search.export.planner.histogram", return_value={i * 60000: 50000 for i in range(20)}),
        ):
            parts, total, _ = build_parts(job, build_policy())
        self.assertEqual(total, 1_000_000)
        self.assertEqual(len(parts), 20)
        self.assertEqual(sum(part.estimated_rows for part in parts), total)

    def test_time_primary_keeps_all_secondary_fields_and_directions(self):
        for direction in ("asc", "desc"):
            sort = [["event_time", direction], ["duration", "desc"], ["level", "asc"]]
            job = create_export_job({**self.params, "sort_list": sort})
            self.assertIsInstance(job, ExportJob)
            self.assertEqual(job.search_params["sort_list"], sort)
            self.assertEqual(job.raw_params["sort_list"], sort)

    def test_confirmed_job_can_split_after_fetch_timeout(self):
        proposal = create_export_job(self.params)
        job = create_export_job({**self.params, "sort_list": proposal.sort_list})
        job.policy = build_policy(part_max_attempts=1).snapshot()
        job.save(update_fields=["policy"])
        claimed = state.claim_planning(job.pk)
        state.persist_plan(
            job.pk,
            claimed.planning_attempts,
            parts=[PartSpec(0, job.end_time, 1000000, 1000000)],
            estimated_total=1000000,
        )
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "delivery")
        part = state.claim_part(part.pk, "delivery")
        state.fail_part(part.pk, state.PartFence.of(part), error_code="FETCH_TIMEOUT", retryable=True)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SPLIT)
        self.assertEqual(ExportPart.objects.filter(parent_part=part).count(), 2)
        job.refresh_from_db()
        self.assertNotEqual(job.status, ExportJobStatus.FAILED)

    def test_worker_sends_the_complete_frozen_sort_to_every_scroll_batch(self):
        proposal = create_export_job(self.params)
        job = create_export_job({**self.params, "sort_list": proposal.sort_list})
        handler = Mock(base_dict=copy.deepcopy(job.base_dict), export_result_window=1)
        handler.export_scroll_batch.side_effect = [([{"message": "one"}], False), ([{"message": "two"}], True)]
        with tempfile.TemporaryDirectory() as directory:
            result = _write_rows(handler, Path(directory) / "logs.jsonl", session_id="sort-regression")
        self.assertEqual(result[0], 2)
        self.assertEqual(handler.export_scroll_batch.call_count, 2)
        for call in handler.export_scroll_batch.call_args_list:
            self.assertEqual(call.args[0]["order_by"], ["-event_time", "-duration", "level"])

    def test_all_three_web_entries_return_a_proposal_then_create_after_confirmation(self):
        for entry in ("single", "union", "scene"):
            with self.subTest(entry=entry):
                data = {
                    "bk_biz_id": 2,
                    "space_uid": "bkcc__2",
                    "start_time": 0,
                    "end_time": 1200000,
                    "table_id_conditions": [],
                    "supports_sort_confirmation": True,
                }

                def submit(data):
                    if entry == "scene":
                        return SceneSearchViewSet()._sharded_scene_export(data)
                    kwargs = {"index_set_ids": [self.index.pk]} if entry == "union" else {"index_set_id": self.index.pk}
                    return SearchViewSet()._sharded_export_from_data(data, **kwargs)

                count = ExportJob.objects.count()
                response = submit(data)
                self.assertTrue(response.data["requires_sort_confirmation"])
                self.assertNotIn("task_id", response.data)
                self.assertEqual(ExportJob.objects.count(), count)
                response = submit({**data, "sort_list": response.data["sort_list"]})
                job = ExportJob.objects.get(pk=response.data["task_id"])
                self.assertEqual(ExportJob.objects.count(), count + 1)
                self.assertEqual(
                    job.search_type, ExportSearchType.SCENE if entry == "scene" else ExportSearchType.INDEX_SET
                )


class MultiFieldMergeTests(TestCase):
    def test_time_then_secondary_fields_remain_globally_ordered_after_gzip_merge(self):
        for direction in ("asc", "desc"):
            with self.subTest(direction=direction):
                job = create_job(
                    end_time=4000,
                    status=ExportJobStatus.RUNNING,
                    plan_version=1,
                    base_dict={
                        "query_list": [{"field_name": "event_time"}],
                        "order_by": ["event_time" if direction == "asc" else "-event_time", "duration", "-level"],
                    },
                )
                objects = {}
                all_rows = []
                for index in range(2):
                    rows = [
                        {"event_time": index * 2000 + 1000, "duration": duration, "level": level}
                        for duration, level in ((1, 3), (1, 2), (2, 4))
                    ]
                    all_rows.extend(rows)
                    key = f"part-{index}"
                    objects[key] = gzip.compress(("\n".join(json.dumps(row) for row in rows) + "\n").encode())
                    ExportPart.objects.create(
                        job=job,
                        part_no=index + 1,
                        plan_version=1,
                        start_time=index * 2000,
                        end_time=(index + 1) * 2000,
                        status=ExportPartStatus.SUCCESS,
                        object_key=key,
                        actual_rows=len(rows),
                    )
                storage = Mock()
                state.sync_actual_total(job)
                storage.download_fileobj.side_effect = lambda key, writer: writer.write(objects[key])
                storage.export_upload.side_effect = lambda *, file_path, file_name: objects.update(
                    {file_name: Path(file_path).read_bytes()}
                )
                with (
                    patch("apps.log_search.export.merger.build_storage", return_value=storage),
                    patch("apps.log_search.export.scheduler.build_storage"),
                ):
                    result = finalize_export(job.pk)
                rows = [json.loads(line) for line in gzip.decompress(objects[result.merged_object_key]).splitlines()]
                expected = sorted(
                    all_rows,
                    key=lambda row: (
                        row["event_time"] * (-1 if direction == "desc" else 1),
                        row["duration"],
                        -row["level"],
                    ),
                )
                self.assertEqual(rows, expected)
