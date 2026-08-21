"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock

from bkmonitor.iam.iam_engine.core.types import Subject
from bkmonitor.iam.iam_engine.provider.dialect_types import (
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
    DialectResource,
)
from bkmonitor.iam.iam_v4.provider import V4PermissionProvider, _build_iam_path


def _subject() -> Subject:
    return Subject(id="user1", tenant_id="system")


def _space_ancestor() -> DialectResource:
    return DialectResource(type="space", id="space|2")


def _build_provider() -> tuple[V4PermissionProvider, MagicMock]:
    """构造真实 v4 provider（mock client），codec 用真实 MonitorV4Codec。"""
    from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

    provider = V4PermissionProvider(
        real_get_fw().schema,
        base_url="http://iam.example.com",
        bk_tenant_id="system",
        credentials={"app_code": "test_app", "app_secret": "test_secret"},
        system={"id": "bk_monitor_v4", "name": "监控平台V4"},
        codec_class="bkmonitor.iam.adapters.v4.codec.MonitorV4Codec",
    )
    mock_client = MagicMock()
    provider._get_client = MagicMock(return_value=mock_client)
    return provider, mock_client


class TestBuildIamPath:
    def test_with_ancestors(self):
        r = DialectResource(type="grafana_dashboard", id="folder:3|182", ancestors=(_space_ancestor(),))
        assert _build_iam_path(r) == "/space,space|2/"

    def test_multi_ancestors(self):
        apm = DialectResource(type="apm_application", id="390", ancestors=(_space_ancestor(),))
        assert _build_iam_path(apm) == "/space,space|2/"

    def test_no_ancestors(self):
        r = DialectResource(type="space", id="space|2")
        assert _build_iam_path(r) is None


class TestToV4Resource:
    def test_payload_with_ancestors(self):
        req = DialectAuthRequest(
            subject=_subject(),
            action_id="view_single_dashboard",
            resource=DialectResource(type="grafana_dashboard", id="folder:3|182", ancestors=(_space_ancestor(),)),
        )
        payload = V4PermissionProvider._to_v4_resource(req)
        assert payload == {
            "id": "folder:3|182",
            "type": "grafana_dashboard",
            "attributes": {"_bk_iam_path_": "/space,space|2/"},
        }

    def test_payload_without_ancestors(self):
        req = DialectAuthRequest(
            subject=_subject(), action_id="view_business", resource=DialectResource(type="space", id="space|2")
        )
        payload = V4PermissionProvider._to_v4_resource(req)
        assert payload == {"id": "space|2", "type": "space"}

    def test_none_resource(self):
        req = DialectAuthRequest(subject=_subject(), action_id="x", resource=None)
        assert V4PermissionProvider._to_v4_resource(req) == {}


class TestBatchByResourceDialectPage:
    def test_payload_contains_iam_path(self):
        provider, mock_client = _build_provider()
        mock_client.direct_auth_by_resources.return_value = {"folder:3|182": True}
        req = DialectBatchByResourceRequest(
            subject=_subject(),
            action_id="view_single_dashboard",
            resource_type="grafana_dashboard",
            resource_ids=("folder:3|182",),
            resources=(DialectResource(type="grafana_dashboard", id="folder:3|182", ancestors=(_space_ancestor(),)),),
        )
        provider._batch_by_resource_dialect_page(req)
        sent = mock_client.direct_auth_by_resources.call_args.kwargs["resources"]
        assert sent == [
            {
                "id": "folder:3|182",
                "type": "grafana_dashboard",
                "attributes": {"_bk_iam_path_": "/space,space|2/"},
            }
        ]

    def test_fallback_to_bare_ids(self):
        """旧构造（仅 resource_ids、无祖先链）→ payload 带 type、不带 attributes。"""
        provider, mock_client = _build_provider()
        mock_client.direct_auth_by_resources.return_value = {"3": True}
        req = DialectBatchByResourceRequest(
            subject=_subject(), action_id="x", resource_type="space", resource_ids=("3",)
        )
        provider._batch_by_resource_dialect_page(req)
        sent = mock_client.direct_auth_by_resources.call_args.kwargs["resources"]
        assert sent == [{"id": "3", "type": "space"}]


class TestBatchByActionDialectPage:
    def test_payload_contains_iam_path(self):
        provider, mock_client = _build_provider()
        mock_client.direct_auth_by_actions.return_value = {"view_single_dashboard": True}
        req = DialectBatchByActionRequest(
            subject=_subject(),
            action_ids=("view_single_dashboard",),
            resource=DialectResource(type="grafana_dashboard", id="3|_zCiy5INk", ancestors=(_space_ancestor(),)),
        )
        provider._batch_by_action_dialect_page(req)
        sent = mock_client.direct_auth_by_actions.call_args.kwargs["resource"]
        assert sent == {
            "id": "3|_zCiy5INk",
            "type": "grafana_dashboard",
            "attributes": {"_bk_iam_path_": "/space,space|2/"},
        }


class TestBatchByResourceBasePlumbing:
    def test_ancestors_reach_dialect_layer(self):
        """基类 batch_by_resource：业务 ancestor_chain 经 codec 编码到达方言层。"""
        from bkmonitor.iam.iam_engine.core.types import BatchByResourceRequest, ResourceInstance

        provider, _ = _build_provider()
        captured: dict = {}

        def fake_dialect(request):
            captured["req"] = request
            return [("folder:3|182", True)]

        provider._batch_by_resource_dialect_page = fake_dialect

        result = provider.batch_by_resource(
            BatchByResourceRequest(
                subject=_subject(),
                action_id="view_single_dashboard",
                resources=(
                    ResourceInstance(
                        type="grafana_dashboard",
                        id="folder:3|182",
                        ancestor_chain=(ResourceInstance(type="space", id="2"),),
                    ),
                ),
            )
        )
        req = captured["req"]
        assert req.resource_ids == ("folder:3|182",)
        assert len(req.resources) == 1
        assert req.resources[0].id == "folder:3|182"
        assert req.resources[0].type == "grafana_dashboard"
        assert req.resources[0].ancestors == (_space_ancestor(),)
        assert result.items[0].allowed is True
