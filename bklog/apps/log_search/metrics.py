# -*- coding: utf-8 -*-
from prometheus_client import Counter, Histogram
from prometheus_client.utils import INF

from apps.utils.prometheus import register_metric

DORIS_QUERY_LATENCY = register_metric(
    Histogram,
    name="doris_query_latency",
    documentation="query latency of doris query API",
    labelnames=("index_set_id", "doris_table_id", "status", "source_app_code"),
    buckets=(0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0, 20.0, 30.0, 60.0, INF),
)


DORIS_QUERY_COUNT = register_metric(
    Counter,
    name="doris_query_count",
    documentation="query count of doris query API",
    labelnames=("index_set_id", "doris_table_id", "status", "source_app_code"),
)
