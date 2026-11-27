"""Run independently: this suite isolates gateway/IAM clients without loading Monitor settings."""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.conf import settings

ROOT = Path(__file__).resolve().parents[2] / "bkmonitor"
if not settings.configured:
    settings.configure(
        SECRET_KEY="denoise-tests",
        USE_I18N=False,
        USE_TZ=True,
        ENABLE_MULTI_TENANT_MODE=True,
        BKFARA_APIGW_BASE_URL="https://bkfara.example.test",
        BK_INCIDENT_APIGW_URL="",
        APP_CODE="monitor-tests",
        SECRET_TEST_PLACEHOLDER="test",
        REST_FRAMEWORK={},
    )


def module(name, **attrs):
    result = types.ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load(name, path, dependencies):
    with patch.dict(sys.modules, dependencies):
        spec = importlib.util.spec_from_file_location(name, path)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result


@pytest.fixture
def boundary():
    user = SimpleNamespace(is_authenticated=True, username="alice", tenant_id="tenant-a")
    request = SimpleNamespace(user=user, biz_id=2, method="POST")
    iam = Mock()
    iam.is_allowed.return_value = True
    spaces = Mock()
    spaces.get_space_detail.return_value = SimpleNamespace(
        bk_biz_id=2, bk_tenant_id="tenant-a", space_type_id="bkcc", space_id="2"
    )
    api = SimpleNamespace(bk_incident=Mock())
    dependencies = {
        "bkm_space.api": module("bkm_space.api", SpaceApi=spaces),
        "bkmonitor.iam": module("bkmonitor.iam", Permission=lambda: iam),
        "bkmonitor.iam.action": module(
            "bkmonitor.iam.action", ActionEnum=SimpleNamespace(VIEW_BUSINESS="view_business")
        ),
        "bkmonitor.iam.resource": module(
            "bkmonitor.iam.resource",
            ResourceEnum=SimpleNamespace(BUSINESS=SimpleNamespace(create_instance=lambda biz: ("business", biz))),
        ),
        "bkmonitor.utils.request": module("bkmonitor.utils.request", get_request=lambda **kwargs: request),
        "core.drf_resource": module("core.drf_resource", api=api),
        "core.drf_resource.base": module("core.drf_resource.base", Resource=object),
    }
    web = load("denoise_web_test", ROOT / "packages/monitor_web/incident/denoise.py", dependencies)
    return SimpleNamespace(web=web, request=request, iam=iam, spaces=spaces, api=api, dependencies=dependencies)


@pytest.fixture
def transport(boundary):
    client = Mock()
    client.denoise.get_alert_decisions.return_value = {"result": True, "data": {"results": []}}
    client.denoise.list_decisions.return_value = {"result": True, "data": {"items": []}}
    client.denoise.get_policy.return_value = {"result": True, "data": {"default_denoise_enabled": True}}
    client_factory = Mock(return_value=client)
    oauth = Mock()
    oauth.get_access_token.return_value = SimpleNamespace(access_token="synthetic-user-token")

    class ResponseError(Exception):
        response_status_code = 403

    class BKAPIError(Exception):
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    dependencies = {
        **boundary.dependencies,
        "bkapi_client_core.exceptions": module("bkapi_client_core.exceptions", ResponseError=ResponseError),
        "bkoauth.client": module("bkoauth.client", oauth_client=oauth),
        "api.bk_incident.client": module("api.bk_incident.client", BKFaraClient=client_factory),
        "core.drf_resource.contrib.api": module(
            "core.drf_resource.contrib.api", APIResource=type("APIResource", (), {"TIMEOUT": 60})
        ),
        "core.errors.api": module("core.errors.api", BKAPIError=BKAPIError),
    }
    loaded = load("denoise_transport_test", ROOT / "api/bk_incident/denoise.py", dependencies)
    resource = loaded.DenoiseReadBaseResource()
    resource.client_operation, resource.action, resource.method = (
        "get_alert_decisions",
        "/core/v1/incident_denoise/get_alert_decisions/",
        "POST",
    )
    return SimpleNamespace(
        module=loaded,
        resource=resource,
        client=client,
        client_factory=client_factory,
        oauth=oauth,
        ResponseError=ResponseError,
        BKAPIError=BKAPIError,
    )
