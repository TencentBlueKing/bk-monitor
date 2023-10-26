# -*- coding: utf-8 -*-

import abc
from typing import List

from core.statistics.metric import Metric


class Storage(metaclass=abc.ABCMeta):
    """
    指标存储
    """

    def get(self, metric_names: List[str]) -> List[Metric]:
        raise NotImplementedError

    def put(self, metrics: List[Metric]):
        raise NotImplementedError
