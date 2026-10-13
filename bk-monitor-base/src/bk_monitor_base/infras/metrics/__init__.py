import time
from contextlib import contextmanager

from prometheus_client import Histogram


@contextmanager
def observe_time(histogram: Histogram, **labels: str):
    start = time.time()
    try:
        yield
    finally:
        histogram.labels(**labels).observe(time.time() - start)
