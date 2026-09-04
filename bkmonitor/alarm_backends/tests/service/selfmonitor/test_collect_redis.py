# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.conf import settings

from alarm_backends.service.selfmonitor.collect.redis import RedisMetricCollectReport
from bkmonitor.define import global_config


class FakeRedisClient:
    """按配置项名返回 CONFIG GET 结果的 fake 客户端。

    supported 之外的配置项返回空 dict，模拟 Redis 对未知参数不报错只返回空的行为。
    """

    def __init__(self, supported: dict, raise_for: set = None):
        self.supported = supported
        self.raise_for = raise_for or set()
        self.config_get_calls: list = []

    def config_get(self, name):
        self.config_get_calls.append(name)
        if name in self.raise_for:
            raise RuntimeError(f"config get {name} failed")
        if name in self.supported:
            return {name: self.supported[name]}
        return {}


def _make_report():
    with mock.patch.object(RedisMetricCollectReport, "__init__", lambda self: None):
        report = RedisMetricCollectReport()
    report.cluster_name = "default"
    return report


def test_listpack_configs_prefer_listpack_name():
    """Redis 7+ 上直接取 listpack 配置项，不再回退 ziplist。"""
    report = _make_report()
    client = FakeRedisClient({"zset-max-listpack-entries": "128", "hash-max-listpack-entries": "128"})

    configs = report.get_listpack_entries_configs(client)

    assert configs == {"config_zset_max_listpack_entries": 128, "config_hash_max_listpack_entries": 128}
    assert "zset-max-ziplist-entries" not in client.config_get_calls


def test_listpack_configs_fallback_to_ziplist_name():
    """Redis 7 之前只有 ziplist 命名，需回退取值。"""
    report = _make_report()
    client = FakeRedisClient({"zset-max-ziplist-entries": "64", "hash-max-ziplist-entries": "512"})

    configs = report.get_listpack_entries_configs(client)

    assert configs == {"config_zset_max_listpack_entries": 64, "config_hash_max_listpack_entries": 512}


def test_listpack_configs_unavailable_returns_placeholder():
    """两种命名都取不到时返回占位值，不能让缺失伪装成真实阈值。"""
    report = _make_report()
    client = FakeRedisClient({})

    configs = report.get_listpack_entries_configs(client)

    assert configs == {
        "config_zset_max_listpack_entries": RedisMetricCollectReport.CONFIG_UNAVAILABLE,
        "config_hash_max_listpack_entries": RedisMetricCollectReport.CONFIG_UNAVAILABLE,
    }


def test_listpack_configs_exception_does_not_break_collection():
    """单个配置项取值抛异常不影响其余项，也不能中断整轮采集。"""
    report = _make_report()
    client = FakeRedisClient(
        {"hash-max-listpack-entries": "128"},
        raise_for={"zset-max-listpack-entries", "zset-max-ziplist-entries"},
    )

    configs = report.get_listpack_entries_configs(client)

    assert configs["config_zset_max_listpack_entries"] == RedisMetricCollectReport.CONFIG_UNAVAILABLE
    assert configs["config_hash_max_listpack_entries"] == 128


def test_set_instance_info_reports_maxmemory_policy():
    """redis_instance_info 需带上 maxmemory_policy，这是驱逐定性的依据。"""
    report = _make_report()
    node_info = {
        "node_type": "RedisCache",
        "mastername": "",
        "role": "master",
        "os": "Linux 5.4.0 x86_64",
        "redis_version": "7.0.5",
        "redis_build_id": "abc123",
        "maxmemory_policy": "volatile-lru",
        "run_id": "run-1",
        "tcp_port": 6379,
        "redis_mode": "standalone",
        "process_id": 1024,
        "host": "127.0.0.1",
        "port": 6379,
    }

    with mock.patch("alarm_backends.service.selfmonitor.collect.redis.metrics") as mock_metrics:
        report.set_instance_info(node_info)

    labels = mock_metrics.INSTANCE_INFO.labels.call_args.kwargs
    assert labels["maxmemory_policy"] == "volatile-lru"
    assert labels["node_type"] == "RedisCache"
    assert labels["cluster_name"] == "default"
    # 数值型标签必须是字符串，否则 prometheus_client 侧标签值不稳定
    assert labels["tcp_port"] == "6379"
    assert labels["process_id"] == "1024"
    mock_metrics.INSTANCE_INFO.labels.return_value.set.assert_called_once_with(1)


def test_set_instance_info_tolerates_missing_info_fields():
    """INFO 字段缺失时补空串，不能因个别字段缺失中断整轮采集。"""
    report = _make_report()
    node_info = {
        "node_type": "SentinelRedisCache",
        "mastername": "mymaster",
        "role": "master",
        "host": "127.0.0.1",
        "port": 26379,
    }

    with mock.patch("alarm_backends.service.selfmonitor.collect.redis.metrics") as mock_metrics:
        report.set_instance_info(node_info)

    labels = mock_metrics.INSTANCE_INFO.labels.call_args.kwargs
    assert labels["maxmemory_policy"] == ""
    assert labels["redis_version"] == ""
    assert labels["mastername"] == "mymaster"


def test_strategy_cost_snapshot_switch_is_dynamic_and_default_off():
    assert settings.ENABLE_REDIS_STRATEGY_COST_SNAPSHOT is False
    serializer = global_config.ADVANCED_OPTIONS["ENABLE_REDIS_STRATEGY_COST_SNAPSHOT"]
    assert serializer.default is False


def test_collect_runs_snapshot_once_after_all_regular_metrics(mocker, settings):
    settings.ENABLE_REDIS_STRATEGY_COST_SNAPSHOT = True
    report = _make_report()
    node = mock.Mock(id=1)
    node_info = {"node": "node-1"}
    report.successful_nodes_info = [(node, node_info)]
    report.get_redis_info = mock.Mock(return_value=[node_info, {"node": "node-2"}])
    events = []
    report.set_redis_metric_data = mock.Mock(side_effect=lambda info: events.append(("metric", info["node"])))
    collector_cls = mocker.patch("alarm_backends.service.selfmonitor.collect.redis.RedisStrategyCostSnapshotCollector")
    collector_cls.return_value.collect.side_effect = lambda nodes: events.append(("snapshot", len(nodes)))

    report.collect_redis_metric_data()

    assert events == [("metric", "node-1"), ("metric", "node-2"), ("snapshot", 1)]
    collector_cls.return_value.collect.assert_called_once_with([(node, node_info)])


def test_collect_snapshot_failure_does_not_break_regular_metrics(mocker, settings):
    settings.ENABLE_REDIS_STRATEGY_COST_SNAPSHOT = True
    report = _make_report()
    report.successful_nodes_info = []
    report.get_redis_info = mock.Mock(return_value=[{"node": "node-1"}])
    report.set_redis_metric_data = mock.Mock()
    collector_cls = mocker.patch("alarm_backends.service.selfmonitor.collect.redis.RedisStrategyCostSnapshotCollector")
    collector_cls.return_value.collect.side_effect = RuntimeError("snapshot failed")

    report.collect_redis_metric_data()

    report.set_redis_metric_data.assert_called_once_with({"node": "node-1"})


def test_collect_switch_off_does_not_create_snapshot_collector(mocker, settings):
    settings.ENABLE_REDIS_STRATEGY_COST_SNAPSHOT = False
    report = _make_report()
    report.get_redis_info = mock.Mock(return_value=[])
    collector_cls = mocker.patch("alarm_backends.service.selfmonitor.collect.redis.RedisStrategyCostSnapshotCollector")

    report.collect_redis_metric_data()

    collector_cls.assert_not_called()
