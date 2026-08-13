import threading
import time

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import timezone
from opentelemetry.context import attach, detach, get_value, set_value

from apps.iam.backends.v4.concurrency import map_chunks_concurrently, run_pair_concurrently
from apps.utils.local import activate_request, del_local_param, get_local_param, get_request, set_local_param
from apps.utils.thread import generate_request


class MapChunksConcurrentlyTest(SimpleTestCase):
    def test_empty_chunks(self):
        self.assertEqual(map_chunks_concurrently([], lambda chunk: chunk, max_workers=4), [])

    def test_serial_when_max_workers_one(self):
        seen = []

        def worker(chunk):
            seen.append(chunk)
            return chunk * 2

        results = map_chunks_concurrently([1, 2, 3], worker, max_workers=1)
        self.assertEqual(results, [2, 4, 6])
        self.assertEqual(seen, [1, 2, 3])

    def test_preserves_input_order_under_concurrency(self):
        results = map_chunks_concurrently(
            [1, 2, 3, 4],
            lambda chunk: chunk * 10,
            max_workers=4,
        )
        self.assertEqual(results, [10, 20, 30, 40])


class RunPairConcurrentlyTest(SimpleTestCase):
    def test_serial_when_max_workers_one(self):
        seen = []

        def left():
            seen.append("left")
            return 1

        def right():
            seen.append("right")
            return 2

        self.assertEqual(run_pair_concurrently(left, right, max_workers=1), (1, 2))
        self.assertEqual(seen, ["left", "right"])

    def test_preserves_left_right_order(self):
        self.assertEqual(run_pair_concurrently(lambda: "a", lambda: "b"), ("a", "b"))

    def test_propagates_left_exception(self):
        def left():
            raise ValueError("left failed")

        with self.assertRaises(ValueError) as ctx:
            run_pair_concurrently(left, lambda: 1)
        self.assertEqual(str(ctx.exception), "left failed")

    def test_tasks_overlap(self):
        started = threading.Event()
        release = threading.Event()

        def left():
            started.set()
            release.wait(timeout=1)
            return "left"

        def right():
            if not started.wait(timeout=1):
                return "right-missed"
            release.set()
            return "right"

        started_at = time.monotonic()
        result = run_pair_concurrently(left, right)
        elapsed = time.monotonic() - started_at
        self.assertEqual(result, ("left", "right"))
        self.assertLess(elapsed, 0.5)


class ContextPropagationTest(SimpleTestCase):
    """worker 线程必须继承调用线程的 OTel context、request 与时区，否则 V3/V4 请求的 span 挂不到请求 trace 上。"""

    def setUp(self):
        del_local_param("request")
        del_local_param("time_zone")
        self.addCleanup(del_local_param, "request")
        self.addCleanup(del_local_param, "time_zone")

    def _attach_probe(self, value):
        token = attach(set_value("probe", value))
        self.addCleanup(detach, token)

    def test_map_chunks_propagates_trace_context(self):
        self._attach_probe("on")

        results = map_chunks_concurrently([1, 2], lambda _: get_value("probe"), max_workers=2)

        self.assertEqual(results, ["on", "on"])

    def test_run_pair_propagates_trace_context(self):
        self._attach_probe("on")

        self.assertEqual(
            run_pair_concurrently(lambda: get_value("probe"), lambda: get_value("probe")),
            ("on", "on"),
        )

    def test_propagates_request_without_rewriting_request_id(self):
        request = activate_request(generate_request(), "fixed-id")

        results = map_chunks_concurrently(
            [1, 2],
            lambda _: get_request().request_id,
            max_workers=2,
        )

        self.assertEqual(results, ["fixed-id", "fixed-id"])
        self.assertEqual(request.request_id, "fixed-id")

    def test_propagates_time_zone(self):
        # 刻意选一个与 settings.TIME_ZONE 不同的时区，否则 worker 里读到的默认时区会让断言恒真
        self.assertNotEqual(settings.TIME_ZONE, "Europe/Amsterdam")
        set_local_param("time_zone", "Europe/Amsterdam")

        results = map_chunks_concurrently(
            [1, 2],
            lambda _: (get_local_param("time_zone"), timezone.get_current_timezone_name()),
            max_workers=2,
        )

        self.assertEqual(results, [("Europe/Amsterdam", "Europe/Amsterdam")] * 2)

    def test_missing_request_does_not_raise(self):
        results = map_chunks_concurrently([1, 2], lambda chunk: get_request(peaceful=True) or chunk, max_workers=2)

        self.assertEqual(results, [1, 2])
