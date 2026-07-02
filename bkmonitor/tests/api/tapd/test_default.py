from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings

from api.tapd.default import GetWorkspaceInfoResource
from core.errors.api import BKAPIError


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class FakeTapdResponse:
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeTapdSession:
    def __init__(self, payload):
        self.payload = payload
        self.get_params = None

    def get(self, **kwargs):
        self.get_params = kwargs["params"]
        return FakeTapdResponse(self.payload)


def make_resource(payload):
    resource = GetWorkspaceInfoResource()
    resource.base_url = "https://api.tapd.cn"
    resource.session = FakeTapdSession(payload)
    resource.report_api_request_count_metric = mock.Mock()
    resource.report_api_failure_metric = mock.Mock()
    return resource


@pytest.fixture(autouse=True)
def disable_i18n():
    settings.USE_I18N = False


def test_tapd_request_does_not_inject_bk_username():
    resource = make_resource({"status": 1, "data": {"Workspace": {"id": "101"}}, "info": "success"})

    result = resource.request({"workspace_id": 101})

    assert result == {"Workspace": {"id": "101"}}
    assert resource.session.get_params == {"workspace_id": 101}


def test_tapd_failed_status_raises_api_error():
    resource = make_resource({"status": 0, "data": [], "info": "workspace not found"})

    with pytest.raises(BKAPIError) as error:
        resource.request({"workspace_id": 101})

    assert error.value.data == {"code": 0, "message": "workspace not found", "data": []}


def test_tapd_base_url_uses_bkapp_env_name():
    source = (PROJECT_ROOT / "config/default.py").read_text(encoding="utf-8")

    assert (
        'TAPD_API_BASE_URL = os.getenv("BKAPP_TAPD_API_BASE_URL", '
        'os.getenv("TAPD_API_BASE_URL", "http://apiv2.tapd.woa.com"))'
    ) in source
    assert 'TAPD_APP_ID = os.getenv("BKAPP_TAPD_APP_ID", os.getenv("TAPD_APP_ID", ""))' in source
    assert 'TAPD_APP_SECRET = os.getenv("BKAPP_TAPD_APP_SECRET", os.getenv("TAPD_APP_SECRET", ""))' in source
