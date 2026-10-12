from types import SimpleNamespace

from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from common.middlewares import TimeZoneMiddleware


@override_settings(TIME_ZONE="Asia/Shanghai", TIMEZONE_SESSION_KEY="time_zone")
def test_timezone_middleware_falls_back_to_default_for_unknown_timezone(mocker):
    mocker.patch("common.middlewares.fetch_biz_id_from_request", return_value=1)
    get_space_detail = mocker.patch(
        "common.middlewares.SpaceApi.get_space_detail",
        return_value=SimpleNamespace(time_zone="Asia/Beijing"),
    )
    request = SimpleNamespace(session={})

    try:
        TimeZoneMiddleware(lambda _request: None).process_view(request, lambda: None, (), {})

        assert timezone.get_current_timezone_name() == settings.TIME_ZONE
        assert request.session[settings.TIMEZONE_SESSION_KEY] == settings.TIME_ZONE
        get_space_detail.assert_called_once_with(bk_biz_id=1)
    finally:
        timezone.deactivate()
