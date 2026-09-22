import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fakeredis
import pytest
from celery.exceptions import SoftTimeLimitExceeded

from apm.core.discover.metric.service import ServiceDiscover as MetricServiceDiscover

from apm.core.discover.exceptions import IncompleteDiscoveryError

from apm.task import tasks


class FixedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, 0, 0, tzinfo=tz)


class FakeApplicationQuerySet(list):
    def values_list(self, *fields):
        return [(application.bk_biz_id, application.app_name) for application in self]


def make_app(bk_biz_id: int, app_name: str):
    return SimpleNamespace(bk_biz_id=bk_biz_id, app_name=app_name)


def test_refresh_apm_config_keeps_all_apps_for_delivery_layer(settings, mocker):
    settings.NEW_ENV_START_BIZ_ID = "10"
    settings.NEW_ENV_BIZ_BLACK_LIST = [12, 0]
    settings.NEW_ENV_BIZ_WHITE_LIST = [5]

    mocker.patch("apm.task.tasks.datetime.datetime", FixedDatetime)
    mocker.patch(
        "apm.task.tasks.ApmApplication.objects.filter",
        return_value=FakeApplicationQuerySet(
            [
                make_app(12, "black"),
                make_app(10, "threshold"),
                make_app(5, "white"),
                make_app(11, "new"),
            ]
        ),
    )
    refresh_apm_application_config = mocker.patch("apm.task.tasks.refresh_apm_application_config.delay")

    tasks.refresh_apm_config()

    refresh_apm_application_config.assert_called_once_with(12, "black", skip_k8s=True)


def test_refresh_apm_config_to_k8s_keeps_all_apps_for_delivery_layer(settings, mocker):
    settings.NEW_ENV_START_BIZ_ID = "10"
    settings.NEW_ENV_BIZ_BLACK_LIST = [12, 0]
    settings.NEW_ENV_BIZ_WHITE_LIST = [5]

    applications = [
        make_app(12, "black"),
        make_app(10, "threshold"),
        make_app(5, "white"),
        make_app(11, "new"),
    ]
    mocker.patch("apm.task.tasks.ApmApplication.objects.filter", return_value=FakeApplicationQuerySet(applications))
    refresh_k8s = mocker.patch("apm.task.tasks.ApplicationConfig.refresh_k8s")

    tasks.refresh_apm_config_to_k8s()

    refresh_k8s.assert_called_once_with(applications, need_config_cache=True)


def test_datasource_handler_checks_past_window_and_preserves_old_task_arguments(settings, mocker) -> None:
    settings.ENABLE_MULTI_TENANT_MODE = False
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    mocker.patch("apm.task.tasks.timezone.now", return_value=now)
    mocker.patch("apm.task.tasks.ApmCacheHandler")
    discover = mocker.Mock()
    registry = mocker.patch("apm.task.tasks.DiscoverContainer.list_discovers", return_value=[discover])
    datasource = make_app(2, "app")
    # 旧任务起点为派发时的当前时间，兼容后仍只检查过去十分钟。
    tasks.datasource_discover_handler(datasource, 10, int(now.timestamp()))
    discover.return_value.discover.assert_called_once_with(int(now.timestamp()) - 600, int(now.timestamp()))
    registry.assert_called_once_with("metric")
    discover.reset_mock()
    tasks.datasource_discover_handler(datasource, 10, int(now.timestamp()) - 900, "log")
    discover.return_value.discover.assert_called_once_with(int(now.timestamp()) - 900, int(now.timestamp()) - 300)
    registry.assert_called_with("log")


def test_datasource_cron_dispatches_independent_module_switches(mocker) -> None:
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    mocker.patch("apm.task.tasks.timezone.now", return_value=now)
    mocker.patch("apm.task.tasks.ApmApplication.objects.filter").return_value.values.return_value = [
        {"id": 15, "bk_biz_id": 2, "app_name": "log_only", "is_enabled_log": True, "is_enabled_metric": False},
        {"id": 20, "bk_biz_id": 2, "app_name": "metric_only", "is_enabled_log": False, "is_enabled_metric": True},
        {"id": 21, "bk_biz_id": 2, "app_name": "next_minute", "is_enabled_log": True, "is_enabled_metric": True},
    ]
    datasources = [make_app(2, name) for name in ("log_only", "metric_only", "next_minute", "disabled")]
    mocker.patch("apm.task.tasks.MetricDataSource.objects.filter", return_value=datasources)
    mocker.patch("apm.task.tasks.LogDataSource.objects.filter", return_value=datasources)
    mocker.patch("apm.task.tasks.ApmCacheHandler")
    dispatch = mocker.patch("apm.task.tasks.datasource_discover_handler.delay")
    tasks.datasource_discover_cron()
    assert dispatch.call_args_list == [
        mocker.call(datasources[1], 10, int(now.timestamp()) - 600, "metric"),
        mocker.call(datasources[0], 10, int(now.timestamp()) - 600, "log"),
    ]


def test_profile_cron_filters_enabled_apps_and_dispatches_async(mocker) -> None:
    applications = mocker.patch("apm.task.tasks.ApmApplication.objects.filter")
    applications.return_value.values_list.return_value = [(10, 2, "enabled"), (11, 2, "next_minute")]
    mocker.patch("apm.task.tasks.timezone.now", return_value=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    mocker.patch(
        "apm.task.tasks.ProfileDataSource.objects.all",
        return_value=[make_app(2, "enabled"), make_app(2, "disabled"), make_app(2, "next_minute")],
    )
    dispatch = mocker.patch("apm.task.tasks.profile_handler.delay")
    tasks.profile_discover_cron()
    applications.assert_called_once_with(is_enabled=True, is_enabled_profiling=True)
    dispatch.assert_called_once_with(2, "enabled")


def test_profile_worker_lock_prevents_reentry_and_releases_after_failure(settings, mocker) -> None:
    settings.ENABLE_MULTI_TENANT_MODE = False
    redis = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch("apm.task.tasks.ApmCacheHandler.get_redis_client", return_value=redis)
    handler = mocker.patch("apm.task.tasks.ProfileDiscoverHandler")

    def reenter() -> None:
        tasks.profile_handler(2, "app")

    handler.return_value.discover.side_effect = reenter
    tasks.profile_handler(2, "app")
    assert handler.return_value.discover.call_count == 1
    assert redis.keys() == []
    handler.return_value.discover.side_effect = RuntimeError("discovery failed")
    with pytest.raises(RuntimeError):
        tasks.profile_handler(2, "app")
    assert redis.keys() == []
    handler.return_value.discover.side_effect = None
    tasks.profile_handler(2, "app")
    assert handler.return_value.discover.call_count == 3


def test_datasource_worker_does_not_release_another_owners_lock(settings, mocker) -> None:
    settings.ENABLE_MULTI_TENANT_MODE = False
    redis = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch("apm.task.tasks.ApmCacheHandler.get_redis_client", return_value=redis)
    key = tasks.ApmCacheHandler().get_lock_key("service_discovery", bk_biz_id=2, app_name="app", data_type="log")
    redis.set(key, "other-worker", ex=660)
    registry = mocker.patch("apm.task.tasks.DiscoverContainer.list_discovers")
    tasks.datasource_discover_handler(make_app(2, "app"), 10, 100, "log")
    registry.assert_not_called()
    assert redis.get(key) == "other-worker"


def test_datasource_worker_lock_lifetime_covers_execution_and_timeout(settings, mocker) -> None:
    settings.ENABLE_MULTI_TENANT_MODE = False
    redis = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch("apm.task.tasks.ApmCacheHandler.get_redis_client", return_value=redis)
    key = tasks.ApmCacheHandler().get_lock_key("service_discovery", bk_biz_id=2, app_name="app", data_type="metric")
    discover = mocker.Mock()

    def execute(*args: Any) -> None:
        assert redis.exists(key)
        assert redis.ttl(key) > tasks.datasource_discover_handler.time_limit
        raise IncompleteDiscoveryError("partial result")

    discover.return_value.discover.side_effect = execute
    mocker.patch("apm.task.tasks.DiscoverContainer.list_discovers", return_value=[discover])
    tasks.datasource_discover_handler(make_app(2, "app"), 10, 100)
    assert redis.keys() == []


def test_profile_sharding_covers_every_application_once_per_cycle(settings, mocker) -> None:
    applications = mocker.patch("apm.task.tasks.ApmApplication.objects.filter")
    applications.return_value.values_list.return_value = [(app_id, 2, f"app-{app_id}") for app_id in range(10)]
    mocker.patch(
        "apm.task.tasks.ProfileDataSource.objects.all",
        return_value=[make_app(2, f"app-{app_id}") for app_id in range(10)],
    )
    clock = mocker.patch("apm.task.tasks.timezone.now")
    dispatch = mocker.patch("apm.task.tasks.profile_handler.delay")
    for minute in range(10):
        clock.return_value = datetime.datetime(2026, 1, 1, 0, minute, tzinfo=datetime.UTC)
        tasks.profile_discover_cron()
    assert dispatch.call_args_list == [mocker.call(2, f"app-{app_id}") for app_id in range(10)]
    # 测试环境会覆盖 DEFAULT_CRONTAB，这里核对生产配置，避免只改分片而漏改 beat。
    config = ast.parse((Path(__file__).resolve().parents[2] / "config/role/worker.py").read_text())
    cron_node = next(
        node
        for node in config.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DEFAULT_CRONTAB" for target in node.targets)
    )
    cron_tasks = ast.literal_eval(cron_node.value)
    assert next(cron for name, cron, _ in cron_tasks if name == "apm.task.tasks.profile_discover_cron") == "* * * * *"


def test_metric_worker_soft_timeout_releases_execution_lock(settings, mocker) -> None:
    settings.ENABLE_MULTI_TENANT_MODE = False
    redis = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch("apm.task.tasks.ApmCacheHandler.get_redis_client", return_value=redis)
    mocker.patch("apm.task.tasks.DiscoverContainer.list_discovers", return_value=[MetricServiceDiscover])
    query = mocker.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql", side_effect=SoftTimeLimitExceeded
    )
    datasource = SimpleNamespace(bk_biz_id=2, app_name="app", result_table_id="2_apm.app")
    with pytest.raises(SoftTimeLimitExceeded):
        tasks.datasource_discover_handler(datasource, 10, 100)
    assert query.call_count == 1
    assert redis.keys() == []
