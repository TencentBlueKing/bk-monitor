import datetime
from types import SimpleNamespace

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


def test_datasource_handler_splits_by_discoverer_and_accepts_old_arguments(mocker) -> None:
    discover = mocker.Mock(SPLIT_SECONDS=200)
    registry = mocker.patch("apm.task.tasks.DiscoverContainer.list_discovers", return_value=[discover])
    source = make_app(2, "app")
    tasks.datasource_discover_handler(source, 10, 100)
    assert discover.return_value.discover.call_args_list == [
        mocker.call(100, 300),
        mocker.call(300, 500),
        mocker.call(500, 700),
    ]
    registry.assert_called_once_with("metric")
    discover.reset_mock()
    discover.SPLIT_SECONDS = None
    tasks.datasource_discover_handler(source, 10, 100, "log")
    discover.return_value.discover.assert_called_once_with(100, 700)
    registry.assert_called_with("log")


def test_datasource_cron_dispatches_independent_module_switches(mocker) -> None:
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    mocker.patch("apm.task.tasks.timezone.now", return_value=now)
    mocker.patch("apm.task.tasks.ApmApplication.objects.filter").return_value.values.return_value = [
        {"id": 10, "bk_biz_id": 2, "app_name": "log_only", "is_enabled_log": True, "is_enabled_metric": False},
        {"id": 20, "bk_biz_id": 2, "app_name": "metric_only", "is_enabled_log": False, "is_enabled_metric": True},
        {"id": 21, "bk_biz_id": 2, "app_name": "next_minute", "is_enabled_log": True, "is_enabled_metric": True},
    ]
    sources = [make_app(2, name) for name in ("log_only", "metric_only", "next_minute", "disabled")]
    mocker.patch("apm.task.tasks.MetricDataSource.objects.filter", return_value=sources)
    mocker.patch("apm.task.tasks.LogDataSource.objects.filter", return_value=sources)
    dispatch = mocker.patch("apm.task.tasks.datasource_discover_handler.delay")
    tasks.datasource_discover_cron()
    assert dispatch.call_args_list == [
        mocker.call(sources[1], 10, int(now.timestamp()) - 600, "metric"),
        mocker.call(sources[0], 10, int(now.timestamp()) - 600, "log"),
    ]


def test_profile_cron_filters_enabled_apps_and_dispatches_async(mocker) -> None:
    applications = mocker.patch("apm.task.tasks.ApmApplication.objects.filter")
    applications.return_value.values.return_value = [
        {"bk_biz_id": 2, "app_name": "enabled"},
        {"bk_biz_id": 2, "app_name": "another"},
    ]
    mocker.patch(
        "apm.task.tasks.ProfileDataSource.objects.all",
        return_value=[make_app(2, "enabled"), make_app(2, "disabled"), make_app(2, "another")],
    )
    dispatch = mocker.patch("apm.task.tasks.profile_handler.delay")
    tasks.profile_discover_cron()
    applications.assert_called_once_with(is_enabled=True, is_enabled_profiling=True)
    assert dispatch.call_args_list == [mocker.call(2, "enabled"), mocker.call(2, "another")]


def test_profile_handler_logs_query_failure(mocker) -> None:
    mocker.patch("apm.task.tasks.ProfileDiscoverHandler").return_value.discover.side_effect = RuntimeError(
        "query failed"
    )
    log = mocker.patch("apm.task.tasks.logger.error")
    tasks.profile_handler(2, "app")
    assert "query failed" in log.call_args.args[0]
