# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import importlib
import logging
import time

from django.core.cache import cache

from bk_monitor.utils.metric import REGISTERED_METRICS, build_metric_id

logger = logging.getLogger("bk_monitor")


class MetricCollector(object):
    """
    实际采集
    """

    def __init__(self, collector_import_paths=None):
        if collector_import_paths and not REGISTERED_METRICS:
            for key in collector_import_paths:
                importlib.reload(importlib.import_module(key))

    def collect(self, namespaces=None, data_names=None, sub_types=None):
        """
        采集入口
        """
        metric_methods = self.metric_filter(namespaces=namespaces, data_names=data_names, sub_types=sub_types)
        metric_groups = []
        for metric_method in metric_methods:
            metric_id = build_metric_id(
                metric_method["data_name"],
                metric_method["namespace"],
                metric_method["prefix"],
                metric_method["sub_type"],
            )
            try:
                begin_time = time.time()
                metric_groups.append(
                    {
                        "prefix": metric_method["prefix"],
                        "sub_type": metric_method["sub_type"],
                        "namespace": metric_method["namespace"],
                        "description": metric_method["description"],
                        "metrics": metric_method["method"](),
                        "data_name": metric_method["data_name"],
                    }
                )
                logger.info(
                    "[statistics_data] collect metric->[{}] took {}s".format(metric_id, int(time.time() - begin_time)),
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.exception("[statistics_data] collect metric->[{}] failed: {}".format(metric_id, e))
            finally:
                # 释放metric_id对应执行锁
                cache.delete(metric_id)

        return metric_groups

    @classmethod
    def metric_filter(cls, namespaces=None, data_names=None, sub_types=None):
        metric_methods = []
        for metric_id, metric in REGISTERED_METRICS.items():
            if data_names and metric["data_name"] not in data_names:
                continue

            if namespaces and metric["namespace"] not in namespaces:
                continue

            if sub_types and metric["sub_type"] not in sub_types:
                continue

            # 根据执行锁是否过期判定是否采集，避免队列堆积时同时执行子任务
            if not cls.is_allow_execute(metric):
                continue
            metric_methods.append(metric)
        return metric_methods

    @classmethod
    def is_allow_execute(cls, metric):
        metric_id = build_metric_id(**metric)
        key = cache.get(metric_id)
        # 执行锁未被占用则允许执行
        if key is None:
            logger.info("[statistics_data] collect metric->[{}] start.".format(metric_id))
            cache.set(
                metric_id,
                True,
                timeout=metric["time_filter"] * 60,
            )
            return True
        # 否则跳过当前轮次
        logger.info("[statistics_data] collect metric->[{}] is not allowed.".format(metric_id))
        return False
