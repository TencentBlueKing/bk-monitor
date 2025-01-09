# -*- coding: utf-8 -*-
from unittest import TestCase

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.host_anomaly_detection import (
    HostAnomalyDetection,
    parse_anomaly,
)
from alarm_backends.tests.service.detect.mocked_data import mocked_item


class TestHostAnomalyDetection(TestCase):
    def test_value_0_message(self):
        datapoint_0 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 0,
                "values": {
                    "anomaly_sort": (
                        "[[\"system__net__speed_recv\", 2812154.0, 0.979932], [\"system__env__procs\", 189.0, 0.831974]"
                        ", [\"system__load__load5\", 0.62, 0.781575], [\"system__swap__pct_used\", 0.0, 0.768101]"
                        ", [\"system__cpu_detail__usage\", 55.979700797607684, 0.701839]"
                        ", [\"system__mem__psc_pct_used\", 90.33528353249342, 0.57988]"
                        ", [\"system__net__speed_sent\", 128148.5, 0.489216]"
                        ", [\"system__mem__pct_used\", 46.67824363574403, 0.399225]]"
                    ),
                    "extra_info": "{}",
                },
                "time": 1569246480,
            },
            mocked_item,
        )

        detect_engine = HostAnomalyDetection(config={})
        anomaly_result = detect_engine.detect(datapoint_0)
        assert len(anomaly_result) == 0

    def test_value_1_message(self):
        datapoint_1 = DataPoint(
            {
                "record_id": "342a08e0f85f169a7e099c18db3708ed",
                "value": 1,
                "values": {
                    "anomaly_sort": (
                        "[[\"system__net__speed_recv\", 2812154.0, 0.979932], [\"system__env__procs\", 189.0, 0.831974]"
                        ", [\"system__load__load5\", 0.62, 0.781575], [\"system__swap__pct_used\", 0.0, 0.768101]"
                        ", [\"system__cpu_detail__usage\", 55.979700797607684, 0.701839]"
                        ", [\"system__mem__psc_pct_used\", 90.33528353249342, 0.57988]"
                        ", [\"system__net__speed_sent\", 128148.5, 0.489216]"
                        ", [\"system__mem__pct_used\", 46.67824363574403, 0.399225]]"
                    ),
                    "extra_info": "{}",
                },
                "time": 1569246480,
            },
            mocked_item,
        )
        config = {
            "metrics": [
                {
                    "metric_id": "bk_monitor.system.cpu_detail.usage",
                    "name": "CPU单核使用率",
                    "unit": "percent",
                    "metric_name": "system.cpu_detail.usage",
                },
                {
                    "metric_id": "bk_monitor.system.disk.in_use",
                    "name": "磁盘空间使用率",
                    "unit": "percent",
                    "metric_name": "system.disk.in_use",
                },
                {
                    "metric_id": "bk_monitor.system.env.procs",
                    "name": "系统总进程数",
                    "unit": "short",
                    "metric_name": "system.env.procs",
                },
                {
                    "metric_id": "bk_monitor.system.io.util",
                    "name": "I/O使用率",
                    "unit": "percentunit",
                    "metric_name": "system.io.util",
                },
                {
                    "metric_id": "bk_monitor.system.load.load5",
                    "name": "5分钟平均负载",
                    "unit": "none",
                    "metric_name": "system.load.load5",
                },
                {
                    "metric_id": "bk_monitor.system.mem.pct_used",
                    "name": "应用程序内存使用占比",
                    "unit": "percent",
                    "metric_name": "system.mem.pct_used",
                },
                {
                    "metric_id": "bk_monitor.system.mem.psc_pct_used",
                    "name": "物理内存已用占比",
                    "unit": "percent",
                    "metric_name": "system.mem.psc_pct_used",
                },
            ]
        }
        detect_engine = HostAnomalyDetection(config=config)
        anomaly_result = detect_engine.detect(datapoint_1)
        anomaly_sort = parse_anomaly(datapoint_1.values["anomaly_sort"], config)
        print(anomaly_result[0].anomaly_message)
        assert len(anomaly_result) == 1
        assert anomaly_result[0].anomaly_message.startswith(f"主机智能异常检测 发现 {len(anomaly_sort)} 个指标异常")
