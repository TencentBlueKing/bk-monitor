import threading
import time

from django.test import SimpleTestCase

from apps.iam.backends.v4.concurrency import map_chunks_concurrently, run_pair_concurrently


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
