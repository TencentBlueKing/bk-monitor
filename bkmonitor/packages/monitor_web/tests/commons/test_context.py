import gzip
import json
from types import SimpleNamespace

import pytest
from django.urls import resolve
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIRequestFactory, force_authenticate

from common.context_processors import get_default_biz_id
from monitor_web.commons.biz.resources import BusinessListOptionResource, ListSpacesResource
from monitor_web.commons.context import resources, views


def test_default_biz_id_falls_back_to_smallest_space_id():
    request = SimpleNamespace(session={}, COOKIES={}, GET={}, POST={}, body=b"")
    spaces = [{"id": 30, "bk_biz_id": -30}, {"id": 1, "bk_biz_id": 2}, {"id": 5, "bk_biz_id": -5}]

    assert get_default_biz_id(request, spaces, "id") == 2


def test_enhanced_context_is_gzipped(mocker):
    mocker.patch.object(views.ContextViewSet, "renderer_classes", [JSONRenderer])
    context = {"BK_BIZ_ID": 2, "SPACE_LIST": [{"bk_biz_id": i, "space_name": f"space-{i}"} for i in range(500)]}
    mocker.patch.object(views, "get_default_biz_id", return_value=2)
    mocker.patch.object(
        views.resource.commons.enhanced_get_context,
        "request",
        return_value={"context": context, "context_type": "basic"},
    )
    request = APIRequestFactory().get(
        "/rest/v2/commons/context/enhanced/", {"context_type": "basic"}, HTTP_ACCEPT_ENCODING="gzip"
    )
    force_authenticate(request, user=mocker.MagicMock(is_authenticated=True))

    response = views.ContextViewSet.as_view({"get": "enhanced"})(request)
    response.render()

    assert response["Content-Encoding"] == "gzip"
    assert json.loads(gzip.decompress(response.content)) == context
    assert response.cookies["bk_biz_id"].value == "2"


@pytest.mark.parametrize(
    "accept_encoding,compressed",
    [
        ("gzip, deflate, br", True),
        ("br, gzip;q=0.5", True),
        (None, False),
        ("identity", False),
        ("br", False),
        ("gzip;q=0, identity", False),
    ],
)
def test_list_spaces_negotiates_compression(mocker, accept_encoding, compressed):
    spaces = [{"space_id": str(i), "space_name": f"Space {i}"} for i in range(500)]
    mocker.patch.object(ListSpacesResource, "request", return_value=spaces)

    def get_directory(encoding):
        path = "/rest/v2/commons/list_spaces/"
        request = APIRequestFactory().get(path, **({"HTTP_ACCEPT_ENCODING": encoding} if encoding else {}))
        force_authenticate(request, user=mocker.Mock(is_authenticated=True))
        response = resolve(path).func(request)
        response.render()
        return response

    identity = get_directory(None)
    response = get_directory(accept_encoding)
    assert response.status_code == identity.status_code == 200
    assert len(identity.content) > 10000
    assert "accept-encoding" in {item.strip().lower() for item in response["Vary"].split(",")}
    assert response.get("Content-Encoding") == ("gzip" if compressed else None)
    if compressed:
        assert len(response.content) < len(identity.content)
        assert gzip.decompress(response.content) == identity.content
    else:
        assert response.content == identity.content


def test_neighboring_business_options_route_keeps_its_encoding(mocker):
    mocker.patch.object(
        BusinessListOptionResource, "request", return_value=[{"id": i, "text": "option"} for i in range(500)]
    )
    path = "/rest/v2/commons/business_list_option/"
    request = APIRequestFactory().get(path, HTTP_ACCEPT_ENCODING="gzip")
    force_authenticate(request, user=mocker.Mock(is_authenticated=True))
    response = resolve(path).func(request)
    response.render()
    assert response.status_code == 200 and len(response.content) > 10000
    assert "Content-Encoding" not in response
    assert "accept-encoding" not in response.get("Vary", "").lower()


@pytest.fixture
def admission(mocker):
    request = SimpleNamespace(user=SimpleNamespace(username="tester"), session={}, COOKIES={})
    mocker.patch.object(resources, "get_request_tenant_id", return_value="tenant")
    permission = mocker.patch.object(resources, "Permission").return_value
    records = mocker.patch.object(resources.SpaceApi, "read_space_records")
    detail = mocker.patch.object(resources.SpaceApi, "get_space_detail")
    return request, permission, records, detail


@pytest.mark.parametrize("target", [17, -17])
@pytest.mark.parametrize("access", ["allowed", "denied", "not_found", "error"])
def test_explicit_target_never_scans_or_falls_back(admission, target, access):
    request, permission, records, _ = admission
    row = {"bk_biz_id": target, "space_type_id": "bkcc", "space_id": str(target)}
    records.return_value = [] if access == "not_found" else [row]
    permission.is_space_allowed.return_value = access == "allowed"
    if access == "error":
        permission.is_space_allowed.side_effect = RuntimeError("unavailable")
    result = resources.resolve_basic_space(request, "", target, 21, 22)
    assert result == (target, [row] if access == "allowed" else [], access)
    records.assert_called_once_with("tenant", [target])
    assert permission.is_space_allowed.call_count == (0 if access == "not_found" else 1)
    permission.list_authorized_space_records.assert_not_called()


@pytest.mark.parametrize(
    "status,exists,expected",
    [("normal", True, "allowed"), ("disabled", True, "not_found"), ("normal", False, "not_found")],
)
def test_non_cmdb_uid_uses_tenant_directory_when_metadata_details_are_unavailable(admission, status, exists, expected):
    request, permission, records, detail = admission
    detail.side_effect = RuntimeError("metadata details unavailable")
    row = {"bk_biz_id": -20, "space_type_id": "bkci", "space_id": "bkms-test", "status": status}
    records.return_value = [row] if exists else []
    permission.is_space_allowed.return_value = True
    assert resources.resolve_basic_space(request, "bkci__bkms-test", 18, None, None) == (
        -20 if exists else -1,
        [row] if expected == "allowed" else [],
        expected,
    )
    records.assert_called_once_with("tenant", space_uid="bkci__bkms-test")
    detail.assert_not_called()
    if expected == "allowed":
        permission.is_space_allowed.assert_called_once_with(resources.ActionEnum.VIEW_BUSINESS, row)
    else:
        permission.is_space_allowed.assert_not_called()
    permission.list_authorized_space_records.assert_not_called()


@pytest.mark.parametrize("sentinel", [-1, 0])
def test_missing_target_falls_through_preferences_to_one_grant(admission, sentinel):
    request, permission, records, _ = admission
    request.session["bk_biz_id"] = "8"
    request.COOKIES["bk_biz_id"] = "8"
    records.side_effect = [[], [], [{"bk_biz_id": 11}]]
    permission.is_space_allowed.return_value = False
    permission.list_authorized_space_records.return_value = [{"bk_biz_id": -20}]
    assert resources.resolve_basic_space(request, "", sentinel, 7, "11") == (-20, [{"bk_biz_id": -20}], "allowed")
    assert [call.args[1] for call in records.call_args_list] == [[7], [8], [11]]
    permission.list_authorized_space_records.assert_called_once_with(
        resources.ActionEnum.VIEW_BUSINESS, first_available=True
    )


def test_external_admission_does_not_call_iam(admission, mocker):
    request, _, records, _ = admission
    request.external_user = "guest"
    external = mocker.patch.object(resources.ListSpacesResource, "external_permissions")
    records.return_value = [{"bk_biz_id": 17}]
    external.return_value.filter.return_value.exists.return_value = False
    assert resources.resolve_basic_space(request, "", 17, None, None) == (17, [], "denied")
    external.assert_called_once_with("guest")
    external.return_value.filter.assert_called_once_with(bk_biz_id=17)
    resources.Permission.assert_not_called()


@pytest.mark.parametrize("flag,expected", [(None, 20), ("1", 20), ("0", "0"), ("false", "0")])
def test_view_only_supplies_cookie_as_explicit_id_to_full_context(mocker, flag, expected):
    mocker.patch.object(views, "get_default_biz_id", return_value=20)
    get_context = mocker.patch.object(
        views.resource.commons.enhanced_get_context,
        "request",
        return_value={"context": {"BK_BIZ_ID": 20}, "context_type": "basic"},
    )
    query = {"context_type": "basic"}
    if flag is not None:
        query["include_space_list"] = flag
    request = APIRequestFactory().get("/rest/v2/commons/context/enhanced/", query)
    force_authenticate(request, user=mocker.MagicMock(is_authenticated=True))
    views.ContextViewSet.as_view({"get": "enhanced"})(request)
    # QueryDict serializes dictionary values as supplied.
    assert str(get_context.call_args.args[0]["bk_biz_id"]) == str(expected)


@pytest.mark.parametrize("external", [True, False])
@pytest.mark.parametrize("access", ["allowed", "denied", "not_found", "error"])
def test_deferred_resource_returns_at_most_one_space_and_keeps_access(mocker, external, access):
    request = APIRequestFactory().get("/")
    request.user = SimpleNamespace(username="tester", is_superuser=False)
    request.LANGUAGE_CODE = "en"
    if external:
        request.external_user = "guest"
    mocker.patch.object(resources, "get_request", return_value=request)
    mocker.patch.object(resources.UserConfig.objects, "filter").return_value.first.return_value = None
    spaces = [{"bk_biz_id": 20}] if access == "allowed" else []
    mocker.patch.object(resources, "resolve_basic_space", return_value=(20, spaces, access))
    directory = mocker.patch.object(resources.resource.commons, "list_spaces")
    detail = mocker.patch.object(resources.SpaceApi, "get_space_detail")
    result = resources.EnhancedGetContextResource().request(
        {"context_type": "basic", "include_space_list": "0", "bk_biz_id": 20}
    )["context"]
    assert result["SPACE_LIST_STATE"] == "deferred"
    assert result["SPACE_ACCESS"] == access
    assert result["BK_BIZ_ID"] == 20
    assert result["SPACE_LIST"] == spaces
    directory.assert_not_called()
    detail.assert_not_called()


@pytest.mark.parametrize("fallback", [[], [{"bk_biz_id": 23}]])
def test_unavailable_preference_continues_to_confirmed_grants(admission, fallback):
    request, permission, records, _ = admission
    records.return_value = [{"bk_biz_id": 17}]
    permission.is_space_allowed.side_effect = resources.ProviderUnavailable("degraded")
    permission.list_authorized_space_records.return_value = fallback
    assert resources.resolve_basic_space(request, "", 0, 17, None) == (
        (23, fallback, "allowed") if fallback else (-1, [], "error")
    )


@pytest.mark.parametrize(
    "extra,legacy_adapter", [({}, False), ({"include_space_list": 1}, False), ({"include_space_list": 0}, True)]
)
def test_complete_basic_returns_the_legacy_directory(mocker, extra, legacy_adapter):
    if legacy_adapter:
        mocker.patch.object(resources, "SpaceApi", SimpleNamespace())
    request = APIRequestFactory().get("/")
    request.user = SimpleNamespace(username="tester", is_superuser=False)
    request.LANGUAGE_CODE = "en"
    mocker.patch.object(resources, "get_request", return_value=request)
    mocker.patch.object(resources.UserConfig.objects, "filter").return_value.first.return_value = None
    spaces = [{"bk_biz_id": i, "id": i} for i in range(2, 12)]
    directory = mocker.patch.object(resources.resource.commons, "list_spaces", return_value=spaces)
    admission = mocker.patch.object(resources, "resolve_basic_space")
    result = resources.EnhancedGetContextResource().request({"context_type": "basic", "bk_biz_id": 2, **extra})[
        "context"
    ]
    directory.assert_called_once()
    admission.assert_not_called()
    assert result["SPACE_LIST_STATE"] == "full"
    assert result["SPACE_LIST"] == spaces
