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
