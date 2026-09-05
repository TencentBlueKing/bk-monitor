"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import warnings

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import resolve
from rest_framework import RemovedInDRF317Warning
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from bkmonitor.iam.adapters.v4.callback import auth as callback_auth
from bkmonitor.iam.adapters.v4.callback.auth import IamCallbackAuthentication, V4SystemTokenProvider
from bkmonitor.iam.adapters.v4.callback.config import V4CallbackConfig, get_v4_callback_config
from bkmonitor.iam.adapters.v4.callback.registry import V4CallbackRegistry
from bkmonitor.iam.adapters.v4.callback.service import V4CallbackService
from bkmonitor.iam.adapters.v4.callback.views import MonitorV4ResourceCallbackView, V4ResourceCallbackView
from bkmonitor.iam.adapters.v4.codec import MonitorV4Codec
from bkmonitor.iam.iam_engine.provider.codec import IdentityCodec


class PrefixTypeCodec(IdentityCodec):
    """为回调回归测试提供资源类型和实例 ID 都非恒等的 codec。"""

    def encode_resource_type(self, resource_type: str) -> str:
        return f"v4_{resource_type}"

    def decode_resource_type(self, resource_type: str) -> str:
        return resource_type.removeprefix("v4_")

    def encode_resource_id(self, resource_type: str, resource_id: str) -> str:
        return f"{resource_type}:{resource_id}"

    def decode_resource_id(self, resource_type: str, resource_id: str) -> str:
        return resource_id.removeprefix(f"{resource_type}:")


def _service(codec=None) -> V4CallbackService:
    return V4CallbackService(codec=codec, registry=V4CallbackRegistry())


class TestV4CallbackService:
    def test_register_and_dispatch_identity_codec(self):
        service = _service(IdentityCodec())

        @service.registry.register_list_instance("test_type")
        def list_instances(filter_data, page):
            return {"count": 1, "results": [{"id": "1", "display_name": "one"}]}

        @service.registry.register_fetch_instance_info("test_type")
        def fetch_instances(ids, requires):
            return [{"id": resource_id, "display_name": f"name-{resource_id}"} for resource_id in ids]

        assert service.dispatch_list_instance("test_type", {}, {"page": 1}) == {
            "count": 1,
            "results": [{"id": "1", "display_name": "one"}],
        }
        assert service.dispatch_fetch_instance_info("test_type", ["1"], ["display_name"]) == [
            {"id": "1", "display_name": "name-1"}
        ]

    def test_registry_is_project_scoped_and_rejects_implicit_overwrite(self):
        first = _service()
        second = _service()

        @first.registry.register_list_instance("space")
        def list_spaces(filter_data, page):
            return {"count": 1, "results": [{"id": "3"}]}

        assert second.dispatch_list_instance("space", {}, {}) == {"count": 0, "results": []}
        with pytest.raises(ValueError, match="already registered"):

            @first.registry.register_list_instance("space")
            def replacement(filter_data, page):
                return {"count": 0, "results": []}

    def test_monitor_codec_decodes_parent_and_encodes_iam_path(self):
        service = _service(MonitorV4Codec())
        received_filter = {}

        @service.registry.register_fetch_instance_info("apm_application")
        def fetch_applications(ids, requires):
            assert ids == ["42"]
            return [{"id": "42", "_bk_iam_path_": "/space,3/apm_application,42/"}]

        @service.registry.register_list_instance("apm_application")
        def list_applications(filter_data, page):
            received_filter.update(filter_data)
            return {"count": 0, "results": []}

        service.dispatch_list_instance(
            "apm_application",
            {"parent": {"type": "space", "id": "space|3"}},
            {},
        )
        result = service.dispatch_fetch_instance_info("apm_application", ["42"], ["_bk_iam_path_"])

        assert received_filter["parent"] == {"type": "space", "id": "3"}
        assert result == [{"id": "42", "_bk_iam_path_": "/space,space|3/apm_application,42/"}]

    def test_monitor_codec_encodes_space_results_and_accepts_legacy_ids(self):
        """保留迁移前的 space ID 编解码与无前缀兼容行为。"""
        service = _service(MonitorV4Codec())
        received_ids = []

        @service.registry.register_list_instance("space")
        def list_spaces(filter_data, page):
            return {"count": 2, "results": [{"id": "3"}, {"id": "-42"}]}

        @service.registry.register_fetch_instance_info("space")
        def fetch_spaces(ids, requires):
            received_ids.extend(ids)
            return [{"id": resource_id} for resource_id in ids]

        assert service.dispatch_list_instance("space", {}, {})["results"] == [
            {"id": "space|3"},
            {"id": "space|-42"},
        ]
        assert service.dispatch_fetch_instance_info("space", ["space|3", "-42"], []) == [
            {"id": "space|3"},
            {"id": "space|-42"},
        ]
        assert received_ids == ["3", "-42"]

    def test_monitor_codec_keeps_non_space_ids_and_path_segments_unchanged(self):
        service = _service(MonitorV4Codec())

        @service.registry.register_fetch_instance_info("grafana_dashboard")
        def fetch_dashboards(ids, requires):
            assert ids == ["1|dashboard-uid"]
            return [
                {
                    "id": "1|dashboard-uid",
                    "_bk_iam_path_": "/space,3/grafana_dashboard,1|dashboard-uid/",
                }
            ]

        assert service.dispatch_fetch_instance_info("grafana_dashboard", ["1|dashboard-uid"], []) == [
            {
                "id": "1|dashboard-uid",
                "_bk_iam_path_": "/space,space|3/grafana_dashboard,1|dashboard-uid/",
            }
        ]

    def test_callback_path_edge_cases_keep_protocol_compatibility(self):
        """覆盖无尾斜杠、畸形段、非字符串路径和未返回路径的旧行为。"""
        service = _service(MonitorV4Codec())

        @service.registry.register_fetch_instance_info("space")
        def fetch_spaces(ids, requires):
            return [
                {"id": "3", "_bk_iam_path_": "/space,3"},
                {"id": "4", "_bk_iam_path_": "/top/"},
                {"id": "5", "_bk_iam_path_": None},
                {"id": "6"},
            ]

        assert service.dispatch_fetch_instance_info("space", ["space|3", "space|4", "space|5", "space|6"], []) == [
            {"id": "space|3", "_bk_iam_path_": "/space,space|3"},
            {"id": "space|4", "_bk_iam_path_": "/top/"},
            {"id": "space|5", "_bk_iam_path_": None},
            {"id": "space|6"},
        ]

    def test_identity_codec_keeps_callback_path_unchanged(self):
        service = _service(IdentityCodec())

        @service.registry.register_fetch_instance_info("space")
        def fetch_spaces(ids, requires):
            return [{"id": "3", "_bk_iam_path_": "/space,3/apm_application,42/"}]

        assert service.dispatch_fetch_instance_info("space", ["3"], []) == [
            {"id": "3", "_bk_iam_path_": "/space,3/apm_application,42/"}
        ]

    def test_monitor_handlers_are_registered_on_the_project_service(self, monkeypatch):
        """确保移动后的 handlers 仍由项目侧 service 持有并委托 catalog。"""
        from bkmonitor.iam.adapters.v4.callback import handlers

        calls = []

        def list_instances(resource_type, filter_data, page):
            calls.append(("list", resource_type, filter_data, page))
            return {"count": 1, "results": [{"id": "3"}]}

        def fetch_instance_info(resource_type, ids, requires):
            calls.append(("fetch", resource_type, ids, requires))
            return [{"id": resource_id} for resource_id in ids]

        monkeypatch.setattr(handlers.catalog, "list_instances", list_instances)
        monkeypatch.setattr(handlers.catalog, "fetch_instance_info", fetch_instance_info)

        service = handlers.get_callback_service()
        assert service.dispatch_list_instance("space", {"keyword": "demo"}, {"page": 1})["results"] == [
            {"id": "space|3"}
        ]
        assert service.dispatch_fetch_instance_info("space", ["space|3"], ["display_name"]) == [{"id": "space|3"}]
        assert calls == [
            ("list", "space", {"keyword": "demo"}, {"page": 1}),
            ("fetch", "space", ["3"], ["display_name"]),
        ]

    def test_unregistered_resource_type_returns_empty_result(self):
        service = _service()
        assert service.dispatch_list_instance("unknown", {}, {}) == {"count": 0, "results": []}
        assert service.dispatch_fetch_instance_info("unknown", ["1"], []) == []


class TestV4CallbackView:
    def test_monitor_project_view_owns_its_service(self):
        service = MonitorV4ResourceCallbackView().get_callback_service()

        assert isinstance(service, V4CallbackService)

    def test_project_injected_service_handles_type_codec_without_provider(self):
        service = _service(PrefixTypeCodec())
        received_filter = {}

        @service.registry.register_list_instance("document")
        def list_documents(filter_data, page):
            received_filter.update(filter_data)
            return {
                "count": 1,
                "results": [{"id": "42", "_bk_iam_path_": "/space,3/document,42/"}],
            }

        class ProjectCallbackView(V4ResourceCallbackView):
            callback_service = service

        factory = APIRequestFactory()
        view = ProjectCallbackView()
        request = view.initialize_request(
            factory.post(
                "/",
                {
                    "method": "list_instance",
                    "type": "v4_document",
                    "filter": {"parent": {"type": "v4_space", "id": "space:3"}},
                    "page": {"page": 1, "page_size": 20},
                },
                format="json",
            )
        )

        response = view.post(request)

        assert response.status_code == 200
        assert received_filter["parent"] == {"type": "space", "id": "3"}
        assert response.data["data"] == {
            "count": 1,
            "results": [
                {
                    "id": "document:42",
                    "_bk_iam_path_": "/v4_space,space:3/v4_document,document:42/",
                }
            ],
        }

    def test_base_view_requires_project_service(self):
        with pytest.raises(ImproperlyConfigured, match="project-provided callback_service"):
            V4ResourceCallbackView().get_callback_service()

    def test_monitor_view_uses_project_token_provider(self, monkeypatch):
        class StaticTokenProvider:
            def get_system_token(self) -> str:
                return "callback-token"

        monkeypatch.setattr(callback_auth, "get_callback_token_provider", lambda: StaticTokenProvider())
        factory = APIRequestFactory()
        credential = base64.b64encode(b"bk_iam:callback-token").decode()

        response = MonitorV4ResourceCallbackView.as_view()(
            factory.post(
                "/",
                {"method": "list_instance", "type": "unknown", "filter": {}, "page": {}},
                format="json",
                HTTP_AUTHORIZATION=f"Basic {credential}",
            )
        )

        assert response.status_code == 200
        assert response.data == {"code": 0, "data": {"count": 0, "results": []}}
        response.render()
        rendered = json.loads(response.content)
        assert rendered == {"code": 0, "data": {"count": 0, "results": []}}
        assert "result" not in rendered

    def test_monitor_view_renders_health_response_without_monitor_envelope(self, monkeypatch):
        class StaticTokenProvider:
            def get_system_token(self) -> str:
                return "callback-token"

        monkeypatch.setattr(callback_auth, "get_callback_token_provider", lambda: StaticTokenProvider())
        credential = base64.b64encode(b"bk_iam:callback-token").decode()
        request = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Basic {credential}")

        response = MonitorV4ResourceCallbackView.as_view()(request)

        assert response.status_code == 200
        response.render()
        rendered = json.loads(response.content)
        assert rendered == {"code": 0, "data": {"status": "ok"}}
        assert "result" not in rendered


class TestV4CallbackRouting:
    def test_both_project_urls_mount_monitor_callback_view(self):
        # kernel_api URLConf 仍会触发 DRF CoreAPI 的弃用告警；该告警与
        # callback 路由无关，测试只验证实际挂载的 View。
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RemovedInDRF317Warning)
            from kernel_api import urls as kernel_urls

        from monitor_web.iam import urls as monitor_iam_urls

        kernel_match = resolve("/rest/v2/iam/v4/callback/", urlconf=kernel_urls)
        monitor_match = resolve("/iam/v4/callback/", urlconf=monitor_iam_urls)

        assert kernel_match.func.view_class is MonitorV4ResourceCallbackView
        assert monitor_match.func.view_class is MonitorV4ResourceCallbackView


class TestCallbackAuth:
    """验证 callback 使用独立 token provider，不读取 Provider 配置。"""

    @staticmethod
    def _config() -> V4CallbackConfig:
        return V4CallbackConfig.from_dict(
            {
                "base_url": "https://callback-iam.example.com",
                "system_id": "callback-system",
                "credentials": {"app_code": "callback-app", "app_secret": "callback-secret"},
                "bk_tenant_id": "callback-tenant",
            }
        )

    def test_token_cache_hit(self):
        call_count = 0

        class FakeClient:
            def get_auth_token(self):
                nonlocal call_count
                call_count += 1
                return "test-token-123"

        token_provider = V4SystemTokenProvider(self._config(), client_factory=lambda config: FakeClient())

        assert token_provider.get_system_token() == "test-token-123"
        assert token_provider.get_system_token() == "test-token-123"
        assert call_count == 1

    def test_basic_auth_uses_injected_token_provider(self):
        class StaticTokenProvider:
            def get_system_token(self) -> str:
                return "callback-token"

        factory = APIRequestFactory()
        credential = base64.b64encode(b"bk_iam:callback-token").decode()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Basic {credential}")

        assert IamCallbackAuthentication(StaticTokenProvider()).authenticate(request) == (None, None)

    def test_basic_auth_rejects_invalid_callback_credentials(self):
        class StaticTokenProvider:
            def get_system_token(self) -> str:
                return "callback-token"

        factory = APIRequestFactory()
        wrong_user = base64.b64encode(b"not_iam:callback-token").decode()
        wrong_token = base64.b64encode(b"bk_iam:wrong-token").decode()

        with pytest.raises(AuthenticationFailed, match="Missing or invalid"):
            IamCallbackAuthentication(StaticTokenProvider()).authenticate(factory.get("/"))
        with pytest.raises(AuthenticationFailed, match="Invalid callback username"):
            IamCallbackAuthentication(StaticTokenProvider()).authenticate(
                factory.get("/", HTTP_AUTHORIZATION=f"Basic {wrong_user}")
            )
        with pytest.raises(AuthenticationFailed, match="Invalid callback token"):
            IamCallbackAuthentication(StaticTokenProvider()).authenticate(
                factory.get("/", HTTP_AUTHORIZATION=f"Basic {wrong_token}")
            )

    @override_settings(
        IAM_V4_CALLBACK={
            "base_url": "https://callback-iam.example.com",
            "system_id": "callback-system",
            "credentials": {"app_code": "callback-app", "app_secret": "callback-secret"},
            "bk_tenant_id": "callback-tenant",
        }
    )
    def test_callback_config_is_independent_from_provider_options(self):
        config = get_v4_callback_config()

        assert config.base_url == "https://callback-iam.example.com"
        assert config.system_id == "callback-system"
        assert config.credentials.app_code == "callback-app"
        assert config.credentials.app_secret == "callback-secret"

    @override_settings(
        IAM_V4_CALLBACK={},
        IAM_FRAMEWORK={
            "PROVIDERS": [
                {
                    "class": "bkmonitor.iam.iam_v4.provider.V4PermissionProvider",
                    "options": {
                        "base_url": "https://provider-iam.example.com",
                        "system": {"id": "provider-system", "name": "Provider"},
                        "credentials": {"app_code": "provider-app", "app_secret": "provider-secret"},
                    },
                }
            ]
        },
    )
    def test_callback_config_never_falls_back_to_provider_options(self):
        with pytest.raises(ImproperlyConfigured, match="Invalid IAM_V4_CALLBACK configuration"):
            get_v4_callback_config()
