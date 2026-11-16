from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.iam import ActionEnum
from bkmonitor.models import ApiAuthToken, AuthType
from core.errors.share import TokenValidatedError
from fta_web.alert.views import AlertViewSet
from fta_web.alert_v2.resources import AlertDetailResource
from monitor_web.share.resources import UpdateShareTokenResource

ALERT_ID = "17000000000000001"
OTHER_ALERT_ID = "17000000000000002"
BIZ_ID = 42
TENANT_ID = "fixture-tenant"
TOKEN = "share-token"
DETAIL_URL = "/fta/alert/v2/alert/detail/"


@pytest.fixture
def detail_request(mocker):
    view = resolve(DETAIL_URL).func
    share = ApiAuthToken(
        type=AuthType.Event,
        token=TOKEN,
        bk_tenant_id=TENANT_ID,
        namespaces=[f"biz#{BIZ_ID}"],
        create_user="issuer",
        update_user="issuer",
        expire_time=datetime.now(timezone.utc) + timedelta(days=1),
        params={"data": {"name": "alarm-center-detail", "params": {"alarmId": ALERT_ID}}},
    )
    lookup = mocker.patch.object(ApiAuthToken.objects, "get", return_value=share)
    permission = mocker.patch("fta_web.alert_v2.views.Permission")
    permission.return_value.is_allowed_by_biz.return_value = True
    mocker.patch("fta_web.alert_v2.views.get_request_tenant_id", return_value=None)
    tenant_lookup = mocker.patch("fta_web.alert_v2.views.bk_biz_id_to_bk_tenant_id", return_value=TENANT_ID)
    detail = mocker.patch.object(AlertDetailResource, "perform_request", return_value={"id": ALERT_ID})

    def request(*, alert_id=ALERT_ID, biz_id=BIZ_ID, user=None):
        http_request = APIRequestFactory().get(DETAIL_URL, {"id": alert_id, "bk_biz_id": biz_id})
        http_request.user = AnonymousUser()
        http_request.biz_id = BIZ_ID
        http_request.token = TOKEN
        if user is not None:
            force_authenticate(http_request, user=user)
        return view(http_request)

    return request, share, lookup, permission, tenant_lookup, detail


@pytest.mark.parametrize(
    "share_data",
    [
        {"name": "alarm-center-detail", "params": {"alarmId": ALERT_ID}},
        {"name": "event-center", "eventId": int(ALERT_ID)},
    ],
)
def test_anonymous_event_share_reads_bound_alert(detail_request, share_data):
    request, share, lookup, permission, tenant_lookup, detail = detail_request
    share.params["data"] = share_data

    response = request()

    assert response.status_code == 200
    assert response.data == {"id": ALERT_ID}
    tenant_lookup.assert_called_once_with(BIZ_ID)
    assert response.renderer_context["request"].user.tenant_id == TENANT_ID
    lookup.assert_called_once_with(token=TOKEN, type=AuthType.Event, bk_tenant_id=TENANT_ID, is_enabled=True)
    permission.assert_called_once_with(username="issuer", bk_tenant_id=TENANT_ID)
    permission.return_value.is_allowed_by_biz.assert_called_once_with(bk_biz_id=BIZ_ID, action=ActionEnum.VIEW_EVENT)
    detail.assert_called_once_with({"id": ALERT_ID, "bk_biz_id": BIZ_ID})


@pytest.mark.parametrize(
    "scenario",
    [
        "another-alert",
        "another-business",
        "different-tenant",
        "wrong-namespace",
        "missing",
        "expired",
        "rewritten",
        "issuer-denied",
    ],
)
def test_anonymous_event_share_denies_out_of_scope_detail(mocker, detail_request, scenario):
    request, share, lookup, permission, _, detail = detail_request
    params = {}
    if scenario == "another-alert":
        params["alert_id"] = OTHER_ALERT_ID
    elif scenario == "another-business":
        params["biz_id"] = BIZ_ID + 1
    elif scenario == "different-tenant":
        mocker.patch("fta_web.alert_v2.views.get_request_tenant_id", return_value="other-tenant")
    elif scenario == "wrong-namespace":
        share.namespaces = [f"biz#{BIZ_ID + 1}"]
    elif scenario == "missing":
        lookup.side_effect = ApiAuthToken.DoesNotExist
    elif scenario == "expired":
        share.expire_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif scenario == "rewritten":
        share.update_user = "another-user"
    elif scenario == "issuer-denied":
        permission.return_value.is_allowed_by_biz.return_value = False

    response = request(**params)

    assert response.status_code == 400
    assert response.data["code"] == TokenValidatedError.code
    detail.assert_not_called()


def test_authenticated_detail_uses_existing_permissions(mocker, detail_request):
    request, _, lookup, _, _, detail = detail_request
    existing_permissions = mocker.patch.object(AlertViewSet, "check_permissions")

    response = request(user=mocker.Mock(is_authenticated=True))

    assert response.status_code == 200
    existing_permissions.assert_called_once()
    lookup.assert_not_called()
    detail.assert_called_once()


@pytest.mark.parametrize(
    ("owner", "last_writer", "target", "allowed"),
    [
        ("issuer", "issuer", ALERT_ID, True),
        ("issuer", "issuer", OTHER_ALERT_ID, False),
        ("other-user", "issuer", ALERT_ID, False),
        ("issuer", "other-user", ALERT_ID, False),
    ],
)
def test_updating_alert_share_cannot_change_who_or_what_was_authorized(
    mocker, detail_request, owner, last_writer, target, allowed
):
    _, share, _, _, _, _ = detail_request
    share.update_user = last_writer
    saved = mocker.patch.object(share, "save")
    mocker.patch.object(ApiAuthToken.origin_objects, "get", return_value=share)
    mocker.patch("monitor_web.share.resources.get_request_tenant_id", return_value=TENANT_ID)
    mocker.patch(
        "monitor_web.share.resources.get_request",
        return_value=mocker.Mock(user=mocker.Mock(username=owner, is_authenticated=True)),
    )
    params = {"token": TOKEN, "data": {"name": "alarm-center-detail", "params": {"alarmId": target}}}

    if allowed:
        assert UpdateShareTokenResource().perform_request(params)["token"] == TOKEN
        saved.assert_called_once()
    else:
        with pytest.raises(TokenValidatedError):
            UpdateShareTokenResource().perform_request(params)
        saved.assert_not_called()
