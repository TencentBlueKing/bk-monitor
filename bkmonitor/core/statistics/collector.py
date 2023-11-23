# -*- coding: utf-8 -*-
from typing import Dict, List

from core.statistics.metric import MC, Metric
from core.statistics.storage import Storage


class Collector:
    """
    指标采集器
    """

    STORAGE_BACKEND = Storage

    def __init__(self):
        self.storage = self.STORAGE_BACKEND()

    @property
    def registry(self):
        functions = {}
        for var_name in dir(self):
            if var_name == "registry":
                continue
            if var_name in MC.register_metrics:
                metric_func = getattr(self, var_name)
                functions[metric_func.metric.name] = metric_func
        return functions

    def collect(self, refresh=False):
        """
        采集指标
        :param refresh: 是否强制刷新
        """
        metric_functions = self.registry
        if not metric_functions:
            return

        metrics = self.storage.get(metric_names=list(metric_functions.keys()))
        metrics_mapping = {m.name: m for m in metrics}

        metrics_to_update = []
        err = None

        for metric_name, collect_func in metric_functions.items():
            cached_metric: Metric = metrics_mapping.get(metric_name, collect_func.metric)
            if refresh or cached_metric.is_time_to_execute():
                try:
                    metric = collect_func()
                    metrics_to_update.append(metric)
                except Exception as e:
                    err = e
                    continue

        if metrics_to_update:
            self.storage.put(metrics_to_update)

        # 指标数据应写尽写
        if err:
            raise err

    def export(self):
        """
        输出原始指标对象
        """
        metric_functions = self.registry
        metrics = self.storage.get(metric_names=list(metric_functions.keys()))
        return metrics

    def export_json(self) -> List[Dict]:
        """
        输出指标字典
        """
        data = []
        metrics = self.export()
        for metric in metrics:
            data.extend(metric.export_json())
        return data

    def export_text(self) -> str:
        """
        输出指标文本
        :return:
        """
        metrics = self.export()
        return "\n".join([metric.export_text() for metric in metrics])
