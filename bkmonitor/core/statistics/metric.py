# -*- coding: utf-8 -*-
import functools
import time

import dill
from prometheus_client import Gauge
from prometheus_client.exposition import generate_latest


class MetricCollector(object):
    def __init__(self):
        self.register_metrics = set()

    def register(self, metric):
        self.register_metrics.add(metric.name)


MC = MetricCollector()


class Metric(Gauge):
    def __init__(self, *args, run_every=5 * 60, **kwargs):
        super(Metric, self).__init__(*args, **kwargs)
        self.last_update_time = 0
        self.name = self._name
        self.run_every = run_every

    def labels(self, *labelvalues, **labelkwargs) -> Gauge:
        return super(Gauge, self).labels(*labelvalues, **labelkwargs)

    def set_last_update_time(self):
        self.last_update_time = int(time.time())

    def clear_data(self):
        # 清空指标
        if hasattr(self, "_lock"):
            with self._lock:
                self._metrics = {}
        self._metric_init()

    def next_execute_time(self) -> int:
        """
        计算下一次执行时间
        :return 下一次执行的时间戳(秒)
        """
        if not self.last_update_time:
            # 如果从未跑过
            return int(time.time())
        return self.last_update_time + self.run_every

    def is_time_to_execute(self, now_time=None) -> bool:
        """
        现在是否该执行了
        :param now_time: 当前时间
        :return: 是否该执行了
        """
        now_time = now_time or int(time.time())
        return self.next_execute_time() <= now_time

    def dumps(self) -> bytes:
        """
        将对象序列化，便于存储
        """
        return dill.dumps(self)

    @classmethod
    def loads(cls, data: bytes) -> "Metric":
        """
        反序列化为指标对象
        """
        return dill.loads(data)

    def export_json(self):
        """
        输出指标字典
        """
        data = []
        metrics = self.collect()
        for metric in metrics:
            for sample in metric.samples:
                data.append(sample._asdict())
        return data

    def export_text(self) -> str:
        """
        输出指标文本
        :return:
        """
        return generate_latest(self).decode("utf-8")

    def __repr__(self):
        return "<Metric: {name}{{{labelnames}}}, interval={run_every})>".format(
            name=self.name,
            labelnames=",".join(self._labelnames),
            run_every=self.run_every,
        )


def register(name="", documentation="", labelnames=(), run_every=5 * 60):
    """
    指标指标装饰器
    """

    def decorated(func):
        metric_name = name or func.__name__
        # metric_name = f"bkmonitor_{metric_name}"
        metric_documentation = documentation or func.__doc__
        metric = Metric(
            name=metric_name,
            documentation=metric_documentation.strip(),
            labelnames=labelnames,
            run_every=run_every,
        )
        MC.register(metric)

        @functools.wraps(func)
        def wrapped(_self):
            # 设置当前用户名，避免出现无权限情况
            from bkmonitor.utils.request import set_request_username

            set_request_username("admin")

            metric.clear_data()
            func(_self, metric=metric)
            metric.set_last_update_time()
            return metric

        wrapped.metric = metric

        return wrapped

    return decorated
