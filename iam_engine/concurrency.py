"""Ordered IAM fan-out; products inject their request/tenant/trace context binder."""

from concurrent.futures import ThreadPoolExecutor
from functools import partial


def run_pair_concurrently(left, right, *, bind, max_workers=2):
    if max_workers <= 1:
        return left(), right()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(bind(call)) for call in (left, right)]
        return tuple(future.result() for future in futures)


def map_chunks_concurrently(chunks, worker, *, bind, max_workers):
    if not chunks:
        return []
    if max_workers <= 1 or len(chunks) == 1:
        return [worker(chunk) for chunk in chunks]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(chunks))) as executor:
        futures = [executor.submit(bind(partial(worker, chunk))) for chunk in chunks]
        return [future.result() for future in futures]
