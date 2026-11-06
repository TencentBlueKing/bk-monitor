"""分片导出的会话、边界、鉴权、持续调度、排序与租户回归。"""

import copy
import gzip
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.api.modules.unify_query import add_unify_query_header_before
from apps.iam import ActionEnum
from apps.log_search.constants import ExportJobStatus, ExportPartStatus, ExportSearchType
from apps.log_search.export import state
from apps.log_search.export.api import create_export_job
from apps.log_search.export.models import ExportPart
from apps.log_search.export.notification import send_export_notification
from apps.log_search.export.planner import build_handler, build_parts, count_rows, histogram, sample_rows
from apps.log_search.export.query import apply_time_range, snapshot_time_fields, time_order
from apps.log_search.export.scheduler import dispatch_ready_parts, finalize_export
from apps.log_search.export.worker import _execute, _write_rows
from apps.log_search.models import LogIndexSet, Scenario, Space
from apps.log_search.views.export_views import ExportJobViewSet
from apps.tests.log_search.test_export_notification import make_job
from apps.tests.log_search.test_sharded_export import FakeHandler, build_policy, create_job
from apps.utils.notify import EmailNotify


class ScrollIsolationTests(TestCase):
    def test_execution_identity_includes_job_part_delivery_and_attempt(self):
        job = create_job()
        part = SimpleNamespace(pk=1, part_no=1, start_time=0, end_time=1000)
        fences = [state.PartFence("delivery-a", 1), state.PartFence("delivery-a", 2), state.PartFence("delivery-b", 1)]
        identities = []
        with (
            patch("apps.log_search.export.worker.build_storage"),
            patch("apps.log_search.export.worker.build_handler"),
            patch("apps.log_search.export.worker._write_rows", return_value=(0, 0)) as write,
            patch("apps.log_search.export.worker._set_stage", return_value=False),
        ):
            for fence in fences:
                _execute(job, part, fence)
                identities.append(write.call_args.kwargs["session_id"])
            for change in ("part", "job"):
                if change == "part":
                    part.pk = 2
                else:
                    job = create_job()
                _execute(job, part, fences[0])
                identities.append(write.call_args.kwargs["session_id"])
        self.assertEqual(len(set(identities)), 5)

    def test_same_query_interleaves_without_resetting_or_consuming_another_cursor(self):
        cursors, sent = {}, []

        def scroll(params):
            # 按 UQ 当前的来源 Name + 查询体建立游标；首轮 clear_cache 会重置该会话。
            params = add_unify_query_header_before(copy.deepcopy(params))
            name = params["Bk-Query-Source"].split(":")[1]
            if params["clear_cache"]:
                cursors[name] = 0
            offset = cursors[name]
            cursors[name] += 1
            sent.append((name, params["clear_cache"]))
            if name == "job-a" and offset == 0:
                _write_rows(FakeHandler(), directory / "b.jsonl", session_id="job-b")
            return {"list": [offset], "done": offset == 2}

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with (
                patch("apps.api.modules.unify_query.get_request", return_value=None),
                patch("apps.api.modules.unify_query.add_esb_info_before_request", side_effect=lambda data: data),
                patch(
                    "apps.log_unifyquery.handler.base.UnifyQueryHandler.query_ts_raw_with_scroll", side_effect=scroll
                ),
            ):
                _write_rows(FakeHandler(), directory / "a.jsonl", session_id="job-a")
            for name in ("a", "b"):
                rows = [json.loads(line)["value"] for line in (directory / f"{name}.jsonl").read_text().splitlines()]
                self.assertEqual(rows, [0, 1, 2])
        self.assertEqual(sent.count(("job-a", True)), 1)
        self.assertEqual(sent.count(("job-b", True)), 1)

    @patch("apps.api.modules.unify_query.add_esb_info_before_request", side_effect=lambda data: data)
    def test_ordinary_requests_keep_the_original_source(self, _auth):
        for username, expected in (("alice", "username:alice"), ("", "backend")):
            with patch(
                "apps.api.modules.unify_query.get_request",
                return_value=SimpleNamespace(user=SimpleNamespace(username=username)),
            ):
                self.assertEqual(add_unify_query_header_before({})["Bk-Query-Source"], expected)


class TimeBoundaryTests(SimpleTestCase):
    def test_integer_units_have_no_gap_or_overlap_at_subsecond_cuts(self):
        # 15s 热点二分时会出现 937/938ms 的非规整边界。
        origin = 1784890800000
        boundaries = [origin, origin + 937, origin + 1875, origin + 2812, origin + 15000]
        for unit, factor in (("second", 0.001), ("millisecond", 1), ("microsecond", 1000), ("nanosecond", 1_000_000)):
            field = {"name": "event_time", "type": "long", "unit": unit}
            intervals = []
            for start, end in zip(boundaries, boundaries[1:]):
                params = {"query_list": [{}]}
                apply_time_range(params, [field], start, end)
                self.assertEqual((params["start_time"], params["end_time"]), (str(start), str(end)))
                conditions = params["query_list"][0]["conditions"]
                self.assertEqual([item["op"] for item in conditions["field_list"]], ["gte", "lt"])
                intervals.append(tuple(int(item["value"][0]) for item in conditions["field_list"]))
            self.assertTrue(all(left[1] == right[0] for left, right in zip(intervals, intervals[1:])), unit)
            expected_start = origin // 1000 if unit == "second" else origin * int(factor)
            self.assertEqual(intervals[0][0], expected_start)
            # 紧贴边界的前一条与边界本身，必须分别只属于一片。
            cut = intervals[0][1]
            for value in (cut - 1, cut, cut + 1):
                self.assertEqual(sum(start <= value < end for start, end in intervals), 1, (unit, value))

    def test_mixed_routes_and_or_conditions_apply_bounds_to_every_branch(self):
        original = {
            "field_list": [{"field_name": "host", "op": "eq", "value": [value]} for value in ("a", "b")],
            "condition_list": ["or"],
        }
        fields = [
            {"name": "us", "type": "long", "unit": "microsecond"},
            {"name": "date", "type": "date", "unit": "millisecond"},
            {"name": "nanos", "type": "date_nanos", "unit": "nanosecond"},
        ]
        params = {"query_list": [{"conditions": copy.deepcopy(original)} for _ in fields]}
        apply_time_range(params, fields, 1784890800937, 1784890801875)
        for index, query in enumerate(params["query_list"]):
            conditions = query["conditions"]
            self.assertEqual(conditions["condition_list"], ["and", "and", "or", "and", "and"])
            self.assertEqual([item["op"] for item in conditions["field_list"]], ["eq", "gte", "lt"] * 2)
            values = conditions["field_list"]
            self.assertEqual(values[1:3], values[4:6])
            if index == 0:
                self.assertEqual(values[2]["value"], ["1784890801875000"])
            elif index == 1:
                self.assertEqual(values[2]["value"], ["1784890801875"])
            else:
                self.assertTrue(values[2]["value"][0].endswith(".875000000Z"))
        self.assertEqual(original["condition_list"], ["or"])

    def test_statistics_and_fetch_share_the_same_exact_boundary(self):
        fields = [{"name": "time", "type": "long", "unit": "microsecond"}]
        body = {"query_list": [{"field_name": "time", "reference_name": "a"}], "order_by": ["time"]}
        job = SimpleNamespace(
            search_type=ExportSearchType.INDEX_SET, search_params={"export_time_fields": fields}, base_dict=body
        )
        with patch("apps.log_search.export.planner.UnifyQueryHandler", side_effect=[Mock(), Mock()]):
            handler = build_handler(job)
            fetch_handler = build_handler(job, 1784890800937, 1784890801875)
        handler.project_export_rows.return_value = []
        with patch("apps.log_search.export.planner.UnifyQueryApi") as api:
            api.query_ts_reference.return_value = {"series": []}
            api.query_ts_raw.return_value = {"list": []}
            count_rows(handler, 1784890800937, 1784890801875)
            histogram(handler, 1784890800937, 1784890801875, 1000)
            sample_rows(handler, 1784890800937, 1784890801875, 10)
        expected = fetch_handler.base_dict["query_list"][0]["conditions"]
        for call in api.query_ts_reference.call_args_list + api.query_ts_raw.call_args_list:
            self.assertEqual(call.args[0]["query_list"][0]["conditions"], expected)
        self.assertEqual(body["query_list"][0], {"field_name": "time", "reference_name": "a"})

    def test_snapshot_uses_real_fields_not_the_placeholder_time(self):
        handler = SimpleNamespace(index_info_list=[{"index_set_id": 1}, {"index_set_id": 2}], base_dict={})
        with patch(
            "apps.log_search.export.query.UnifyQueryHandler.init_time_field",
            side_effect=[("s", "long", "second"), ("us", "long", "microsecond")],
        ):
            fields = snapshot_time_fields(handler, ExportSearchType.INDEX_SET)
        self.assertEqual([item["unit"] for item in fields], ["second", "microsecond"])

    def test_logical_date_uses_the_physical_mapping_and_utc_nanos_literal(self):
        handler = SimpleNamespace(
            base_dict={"query_list": [{"data_source": "bklog", "table_id": "rt"}]},
            index_info_list=[{"index_set_id": 1}],
        )
        for physical in ("long", "date", "date_nanos"):
            with (
                patch(
                    "apps.log_search.export.query.UnifyQueryHandler.init_time_field",
                    return_value=("time", "date", "millisecond"),
                ),
                patch(
                    "apps.log_search.export.query.UnifyQueryApi.query_field_map",
                    return_value={"data": [{"field_name": "time", "field_type": physical}]},
                ),
            ):
                fields = snapshot_time_fields(handler, ExportSearchType.INDEX_SET)
            params = {"query_list": [{}]}
            apply_time_range(params, fields, 1784890800937, 1784890801875)
            upper = params["query_list"][0]["conditions"]["field_list"][1]["value"][0]
            self.assertEqual(upper, "2026-07-24T11:00:01.875000000Z" if physical == "date_nanos" else "1784890801875")


class FrozenTimeFieldTests(TestCase):
    def test_creation_freezes_precision_and_worker_does_not_reinterpret_it(self):
        Space.objects.create(space_uid="bkcc__2", bk_biz_id=2, space_type_id="bkcc", space_id="2", space_name="biz")
        index = LogIndexSet.objects.create(
            index_set_name="microseconds",
            space_uid="bkcc__2",
            scenario_id=Scenario.ES,
            category_id="application",
            time_field="event_time",
            time_field_type="long",
            time_field_unit="microsecond",
        )
        handler = Mock(
            base_dict={"query_list": [{"field_name": "event_time"}], "order_by": ["event_time"]},
            origin_order_by=[["event_time", "asc"]],
            is_desensitize=True,
            index_info_list=[{"index_set_id": index.pk}],
        )
        handler.pre_get_result.return_value = {"list": [{"event_time": 1784890800000000}]}
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
        ):
            job = create_export_job(
                {
                    "space_uid": "bkcc__2",
                    "index_set_id": index.pk,
                    "start_time": 1784890800000,
                    "end_time": 1784890810000,
                }
            )
        self.assertEqual(
            job.search_params["export_time_fields"], [{"name": "event_time", "type": "long", "unit": "microsecond"}]
        )
        with (
            patch("apps.log_search.export.planner.UnifyQueryHandler", return_value=Mock()),
            patch(
                "apps.log_search.export.planner.snapshot_time_fields",
                side_effect=AssertionError("must use frozen fields"),
            ),
        ):
            rebuilt = build_handler(job, 1784890800937, 1784890801875)
        self.assertEqual(
            rebuilt.base_dict["query_list"][0]["conditions"]["field_list"][1]["value"], ["1784890801875000"]
        )


class ContinuousDispatchTests(TestCase):
    @patch("apps.log_search.export.scheduler._send")
    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=8, global_parallelism=4),
    )
    def test_released_slot_is_refilled_in_single_and_multi_job_steady_state(self, _policy, _send):
        for job_count in (1, 2, 3):
            with self.subTest(job_count=job_count):
                jobs = [
                    create_job(index_set_id=index + 11, end_time=20000, status=ExportJobStatus.READY, plan_version=1)
                    for index in range(job_count)
                ]
                for job in jobs:
                    for number in range(20):
                        ExportPart.objects.create(
                            job=job,
                            part_no=number + 1,
                            plan_version=1,
                            start_time=number * 1000,
                            end_time=(number + 1) * 1000,
                        )
                self.assertEqual(len(dispatch_ready_parts()), 4)
                for _ in range(12):
                    part = ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT).order_by("pk").first()
                    part = state.claim_part(part.pk, part.task_id)
                    state.complete_part(
                        part.pk,
                        state.PartFence.of(part),
                        actual_rows=1,
                        actual_bytes=1,
                        compressed_bytes=1,
                        object_key="part",
                        checksum="checksum",
                    )
                    self.assertEqual(len(dispatch_ready_parts()), 1)
                    self.assertEqual(ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT).count(), 4)
                ExportPart.objects.all().delete()
                for job in jobs:
                    job.delete()

    @patch("apps.log_search.export.scheduler._send")
    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=8, global_parallelism=4),
    )
    def test_new_job_gets_capacity_when_a_borrowed_slot_is_released(self, _policy, _send):
        first = create_job(status=ExportJobStatus.READY, plan_version=1, end_time=10000)
        for index in range(10):
            ExportPart.objects.create(
                job=first, part_no=index + 1, plan_version=1, start_time=index * 1000, end_time=(index + 1) * 1000
            )
        dispatch_ready_parts()
        second = create_job(status=ExportJobStatus.READY, plan_version=1, index_set_id=2)
        short = ExportPart.objects.create(job=second, part_no=1, plan_version=1, start_time=0, end_time=4000)
        ExportPart.objects.filter(job=first, part_no=1).update(status=ExportPartStatus.SUCCESS)
        self.assertEqual(dispatch_ready_parts(), [short.pk])


@override_settings(IGNORE_IAM_PERMISSION=False, ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class SceneDownloadPermissionTests(TestCase):
    def test_scene_link_is_not_signed_when_business_permission_denies(self):
        Space.objects.create(
            space_uid="bkcc__21",
            bk_biz_id=21,
            space_type_id="bkcc",
            space_id="21",
            space_name="biz",
            bk_tenant_id="tenant-a",
        )
        job = make_job(
            space_uid="bkcc__21",
            bk_biz_id=21,
            created_by="another-user",
            source_app_code="bk_log",
            index_set_ids=[],
            search_type=ExportSearchType.SCENE,
            status=ExportJobStatus.SUCCESS,
            expires_at=timezone.now() + timedelta(hours=1),
            merged_object_key="full.jsonl.gz",
        )
        for artifact in ("full", "manifest", "1"):
            request = Request(
                APIRequestFactory().get("/download_link/", {"space_uid": "bkcc__21", "artifact_id": artifact})
            )
            view = ExportJobViewSet()
            view.request, view.kwargs, view.action = request, {"pk": job.pk}, "download_link"
            with (
                patch("apps.iam.handlers.drf.Permission") as permission,
                patch("apps.log_search.export.api.build_storage") as storage,
            ):
                permission.return_value.is_allowed.side_effect = PermissionDenied("denied")
                with self.assertRaises(PermissionDenied):
                    view.check_permissions(request)
                    view.download_link(request, pk=job.pk)
                storage.assert_not_called()
                call = permission.return_value.is_allowed.call_args
                self.assertEqual(call.kwargs["action"], ActionEnum.VIEW_BUSINESS)
                self.assertEqual(str(call.kwargs["resources"][0].id), "21")


class MergedOrderingTests(TestCase):
    def test_mixed_numeric_time_units_are_not_treated_as_one_sort_domain(self):
        job = create_job(
            search_params={
                "export_time_fields": [
                    {"name": "time", "type": "long", "unit": "millisecond"},
                    {"name": "time", "type": "long", "unit": "microsecond"},
                ]
            },
            base_dict={"query_list": [{"field_name": "time"}] * 2, "order_by": ["time"]},
        )
        self.assertIsNone(time_order(job))

    def test_existing_custom_sort_mult_part_job_cannot_publish_wrong_order(self):
        job = create_job(
            end_time=4000,
            status=ExportJobStatus.RUNNING,
            plan_version=1,
            base_dict={"query_list": [{"field_name": "time"}], "order_by": ["severity"]},
        )
        for index in range(2):
            ExportPart.objects.create(
                job=job,
                part_no=index + 1,
                plan_version=1,
                start_time=index * 2000,
                end_time=(index + 1) * 2000,
                status=ExportPartStatus.SUCCESS,
            )
        with patch("apps.log_search.export.scheduler.merge_export_parts") as merge:
            self.assertIsNone(finalize_export(job.pk))
        merge.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.error_code, "MERGE_FAILED")

    def test_final_file_obeys_both_time_directions(self):
        for direction in ("asc", "desc"):
            job = create_job(
                end_time=4000,
                status=ExportJobStatus.RUNNING,
                plan_version=1,
                base_dict={
                    "query_list": [{"field_name": "time"}],
                    "order_by": ["-time" if direction == "desc" else "time"],
                },
            )
            objects = {}
            for index, rows in enumerate(((1, 2), (3, 4))):
                ordered = list(reversed(rows)) if direction == "desc" else rows
                key = f"part-{index}"
                objects[key] = gzip.compress(("\n".join(map(str, ordered)) + "\n").encode())
                ExportPart.objects.create(
                    job=job,
                    part_no=index + 1,
                    plan_version=1,
                    start_time=index * 2000,
                    end_time=(index + 1) * 2000,
                    status=ExportPartStatus.SUCCESS,
                    object_key=key,
                    actual_rows=2,
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
            self.assertIsNotNone(result)
            data = gzip.decompress(objects[result.merged_object_key]).decode().splitlines()
            self.assertEqual(data, ["4", "3", "2", "1"] if direction == "desc" else ["1", "2", "3", "4"])

    def test_custom_sort_plans_one_part_and_does_not_split_it_after_timeout(self):
        job = create_job(
            base_dict={"query_list": [{"field_name": "time"}], "order_by": ["-severity", "time"]},
            policy=build_policy(part_max_attempts=1).snapshot(),
        )
        self.assertIsNone(time_order(job))
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=1_000_000),
            patch("apps.log_search.export.planner.sample_rows", return_value=[b"row"]),
            patch("apps.log_search.export.planner.histogram") as histogram_mock,
        ):
            parts, total, _ = build_parts(job, build_policy())
        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertEqual(total, 1_000_000)
        histogram_mock.assert_not_called()
        claimed = state.claim_planning(job.pk)
        state.persist_plan(job.pk, claimed.planning_attempts, parts=parts, estimated_total=total)
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "delivery")
        part = state.claim_part(part.pk, "delivery")
        state.fail_part(part.pk, state.PartFence.of(part), error_code="FETCH_TIMEOUT", retryable=True)
        self.assertEqual(ExportPart.objects.filter(job=job).count(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.FAILED)


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class NotificationTenantTests(TestCase):
    def test_background_mail_uses_the_job_space_tenant(self):
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_id="2",
            space_name="biz",
            bk_tenant_id="tenant-b",
        )
        for status in (ExportJobStatus.FAILED, ExportJobStatus.SUCCESS):
            for external in (False, True):
                job = make_job(
                    status=status,
                    search_type=ExportSearchType.SCENE,
                    bk_biz_id=2,
                    is_external=external,
                    merged_object_key="full.jsonl.gz",
                    expires_at=timezone.now() + timedelta(hours=1),
                    notification_context={"language": "zh-cn", "external_user_email": "user@example.com"},
                )
                channel = EmailNotify()
                channel.content = Mock(return_value="body")
                with (
                    patch("apps.log_search.export.notification._notify_channel", return_value=channel),
                    patch("apps.log_search.export.notification.build_storage"),
                    patch("apps.utils.notify.CmsiApi.send_mail") as mail,
                    patch("apps.utils.local.get_request", return_value=None),
                ):
                    send_export_notification(job)
                mail.assert_called_once()
                self.assertEqual(mail.call_args.kwargs["bk_tenant_id"], "tenant-b")
