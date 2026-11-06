"""Monitor context binding for the same ordered IAM fan-out used by BKLog."""

from django.utils import timezone
from opentelemetry.context import attach, detach, get_current

from bkmonitor.utils.local import local
from iam_engine.concurrency import map_chunks_concurrently as _map_chunks
from iam_engine.concurrency import run_pair_concurrently as _run_pair


def bind_current_context(call):
    values = dict(local)
    trace_context = get_current()
    time_zone = timezone.get_current_timezone()

    def run():
        previous = dict(local)
        token = attach(trace_context)
        try:
            for key, value in values.items():
                setattr(local, key, value)
            with timezone.override(time_zone):
                return call()
        finally:
            local.clear()
            for key, value in previous.items():
                setattr(local, key, value)
            detach(token)

    return run


def run_pair_concurrently(left, right, *, max_workers=2):
    return _run_pair(left, right, bind=bind_current_context, max_workers=max_workers)


def map_chunks_concurrently(chunks, worker, *, max_workers):
    return _map_chunks(chunks, worker, bind=bind_current_context, max_workers=max_workers)
