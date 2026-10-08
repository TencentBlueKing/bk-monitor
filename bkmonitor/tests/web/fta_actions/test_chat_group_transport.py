# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.urls import include, path

from api.monitor.default import CreateChatGroupActionBackendResource
from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request
from core.drf_resource.contrib import api as api_client
from core.drf_resource.contrib import nested_api
from core.drf_resource.routers import ResourceRouter
from fta_web.action.resources import backend_resources


@pytest.fixture
def chat_request(monkeypatch):
    request = SimpleNamespace(
        user=SimpleNamespace(username="operator"),
        META={"HTTP_BK_USERNAME": "operator", "HTTP_BK_APP_CODE": "monitor-web"},
        COOKIES={},
    )
    monkeypatch.setattr(local, "current_request", request, raising=False)
    return request, {"alert_ids": ["alert-a", "alert-b"], "chat_members": ["member"], "content_type": ["detail_url"]}


def test_chat_client_preserves_login_credentials(chat_request, settings, mocker):
    request, data = chat_request
    settings.APP_CODE = "monitor-web"
    settings.SECRET_KEY = "test-only-secret"
    ticket = mocker.patch.object(api_client, "get_bk_login_ticket", return_value={"bk_token": "test-only-ticket"})
    client = CreateChatGroupActionBackendResource()
    assert client.full_request_data(dict(data)) == data
    assert json.loads(client.get_headers()["x-bkapi-authorization"]) == {
        "bk_app_code": "monitor-web",
        "bk_app_secret": "test-only-secret",
        "bk_username": "operator",
        "bk_token": "test-only-ticket",
    }
    ticket.assert_called_once_with(request)


def test_generated_gateway_requires_verified_user(tmp_path):
    root = Path(__file__).resolve().parents[3]
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/convert_yaml.py"),
            "-s",
            str(root / "docs/api/monitor_v3.yaml"),
            "-t",
            str(tmp_path),
            "-f",
            "swagger",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    paths = yaml.safe_load((tmp_path / "apigw_default.swagger").read_text())["paths"]
    route = paths[CreateChatGroupActionBackendResource.action]["post"]
    assert route["operationId"] == "create_chat_group_action"
    assert route["x-bk-apigateway-resource"]["authConfig"] == {
        "userVerifiedRequired": True,
        "appVerifiedRequired": True,
        "resourcePermissionRequired": True,
    }
    assert route["x-bk-apigateway-resource"]["backend"]["path"] == "/api/v4/action_instance/create_chat_group_action/"
    # Existing interfaces retain their authentication configuration.
    for name, methods in paths.items():
        if name != CreateChatGroupActionBackendResource.action:
            for operation in methods.values():
                assert operation["x-bk-apigateway-resource"]["authConfig"] == {"userVerifiedRequired": False}


def test_packaged_mapping_and_direct_route_keep_original_request(chat_request, settings, monkeypatch, mocker, tmp_path):
    request, data = chat_request
    root = Path(__file__).resolve().parents[3]
    # The Dockerfile and binary package copy this source into kernel_api at build time.
    (tmp_path / "kernel_api").mkdir()
    shutil.copyfile(root / "docs/api/monitor_v3.yaml", tmp_path / "kernel_api/monitor_v3.yaml")
    settings.BASE_DIR = str(tmp_path)
    monkeypatch.setattr(nested_api, "API_DEFINE", {})
    nested_api.load_api_yaml()
    spec = importlib.util.spec_from_file_location("chat_action_routes", root / "kernel_api/views/v4/action.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Match config/role/api.py instead of the web test environment's default business permission.
    monkeypatch.setattr(module.ActionInstanceViewSet, "permission_classes", ())
    router = ResourceRouter()
    router.register("action_instance", module.ActionInstanceViewSet)
    settings.ROOT_URLCONF = (path("api/v4/", include(router.urls)),)

    def perform(validated):
        assert validated == data
        assert get_request() is request
        return {"actions": [1], "alert_ids": data["alert_ids"]}

    backend = mocker.patch.object(
        backend_resources.CreateChatGroupActionResource, "perform_request", side_effect=perform
    )
    result = CreateChatGroupActionBackendResource().direct_request(data)
    assert result == {"actions": [1], "alert_ids": data["alert_ids"]}
    backend.assert_called_once()
