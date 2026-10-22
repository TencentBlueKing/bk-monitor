from threading import Barrier, get_ident

import pytest

from iam_engine.concurrency import map_chunks_concurrently, run_pair_concurrently


def test_pair_runs_both_branches_and_preserves_order():
    barrier = Barrier(2, timeout=3)
    caller = get_ident()
    bound = []

    def bind(call):
        bound.append(call)
        return call

    def worker(value):
        assert get_ident() != caller
        barrier.wait()
        return value

    assert run_pair_concurrently(lambda: worker("v3"), lambda: worker("v4"), bind=bind) == ("v3", "v4")
    assert len(bound) == 2


def test_chunks_use_configured_workers_and_preserve_order():
    barrier = Barrier(3, timeout=3)

    def worker(value):
        barrier.wait()
        return value * 2

    assert map_chunks_concurrently([3, 1, 2], worker, bind=lambda call: call, max_workers=3) == [6, 2, 4]


def test_serial_and_empty_paths_do_not_bind_context():
    def forbidden(call):
        raise AssertionError("serial calls already have request context")

    assert run_pair_concurrently(lambda: 1, lambda: 2, bind=forbidden, max_workers=1) == (1, 2)
    assert map_chunks_concurrently([], lambda value: value, bind=forbidden, max_workers=4) == []
    assert map_chunks_concurrently([1], lambda value: value, bind=forbidden, max_workers=4) == [1]
    assert map_chunks_concurrently([1, 2], lambda value: value, bind=forbidden, max_workers=1) == [1, 2]


def test_worker_errors_are_not_converted_to_successful_empty_results():
    def fail(*args):
        raise TimeoutError("offline timeout")

    with pytest.raises(TimeoutError, match="offline timeout"):
        run_pair_concurrently(fail, lambda: True, bind=lambda call: call)
    with pytest.raises(TimeoutError, match="offline timeout"):
        map_chunks_concurrently([1, 2], fail, bind=lambda call: call, max_workers=2)
