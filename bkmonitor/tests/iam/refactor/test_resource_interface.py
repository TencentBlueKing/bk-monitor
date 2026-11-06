"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.backends.config import build_provider

# ==============================================================================
# resource.py 重构对照测试
#
# 对照基线：merge-base 7b360f40 上的旧 resource.py（478 行）
# 测试目标：
#   1. ResourceEnum 成员 / .id / .name 与旧版一致（接口稳定性）
#   2. create_* 保留原生 SDK Resource，IAM 内部才转换为引擎请求
#   3. MonitorResourceResolver 补全 name / ancestor_chain，与旧版 create_instance
#      的 DB 查询语义一致（鉴权路径一致性的资源侧前提）
#   4. 元数据、资源 lookup、批量名称/父资源等旧公开接口继续可用
# 安全约束：仅内存/DB 只读查询（SpaceApi 详情、Application/Dashboard 查询），
# 不涉及任何授权写操作。
# ==============================================================================

from unittest.mock import MagicMock, patch
import pytest
from iam import Resource


from bkmonitor.iam.resource import ApmApplication, Business, GrafanaDashboard, ResourceEnum, RumApplication
from iam_engine.provider.requests import ResourceInstance


class TestResourceEnumSurface:
    """ResourceEnum 成员与旧版一致。"""

    def test_members_preserved(self):
        assert ResourceEnum.BUSINESS is Business
        assert ResourceEnum.APM_APPLICATION is ApmApplication
        assert ResourceEnum.GRAFANA_DASHBOARD is GrafanaDashboard
        assert ResourceEnum.RUM_APPLICATION is RumApplication

    def test_ids_preserved(self):
        """资源类型 ID 与旧版完全一致（space/apm_application/grafana_dashboard/rum_application）。"""
        assert Business.id == "space"
        assert ApmApplication.id == "apm_application"
        assert GrafanaDashboard.id == "grafana_dashboard"
        assert RumApplication.id == "rum_application"

    def test_names_preserved(self):
        assert str(Business.name) == "空间"
        assert str(ApmApplication.name) == "APM应用"
        assert str(GrafanaDashboard.name) == "Grafana仪表盘"
        assert str(RumApplication.name) == "RUM应用"


class TestCreateInstance:
    """create_* 保留原生 SDK Resource，内部边界转换为引擎输入。"""

    @pytest.fixture(autouse=True)
    def no_application_found(self, monkeypatch):
        from monitor_web.iam.views import ApmApplicationProvider, RumApplicationProvider
        monkeypatch.setattr(ApmApplicationProvider, "_get_app_simple_info_by_id_or_none", lambda id: None)
        monkeypatch.setattr(RumApplicationProvider, "_get_app_simple_info_by_id_or_none", lambda id: None)

    def test_create_simple_instance(self):
        r = Business.create_simple_instance("2")
        assert isinstance(r, Resource)
        assert r.type == "space"
        assert r.id == "2"

    def test_create_instance_alias(self):
        r = ApmApplication.create_instance("app-1")
        assert r.type == "apm_application"
        assert r.id == "app-1"

    def test_create_instance_by_info(self):
        r = ApmApplication.create_instance_by_info({"application_id": "app-1", "bk_biz_id": 2, "app_name": "demo"})
        assert r.type == "apm_application"
        assert r.id == "app-1"
        r2 = RumApplication.create_instance_by_info({"application_id": "rum-1", "bk_biz_id": 2, "app_name": "r"})
        assert r2.id == "rum-1"

    def test_instance_id_is_str_coerced(self):
        r = Business.create_instance(2)
        assert r.id == "2"
        assert isinstance(r.id, str)

    def test_attribute_param_preserves_v3_metadata(self):
        """显式实例属性必须保留，resolver 补全不能丢弃旧 SDK 的鉴权输入。"""
        r = ApmApplication.create_simple_instance("app-1", {"bk_biz_id": "2"})
        assert r.attribute == {"bk_biz_id": "2"}


class TestPreservedInterfaces:
    """原 V3 元数据及批量接口均保留。"""

    def test_original_module_exports_remain(self):
        import bkmonitor.iam.resource as resource_module

        for attr in (
            "get_resource_by_id",
            "_all_resources",
            "ResourceMeta",
        ):
            assert hasattr(resource_module, attr), attr

    def test_resource_classes_keep_native_metadata(self):
        assert Business.system_id == "bk_monitorv3"
        assert Business.parent_resource is None
        assert ApmApplication.parent_resource is Business
        assert callable(ApmApplication.batch_get_display_names)
        assert callable(GrafanaDashboard.batch_get_parent)
        assert ApmApplication.to_json()["related_instance_selections"] == [{"system_id": "bk_monitorv3", "id": "apm_application_list_v2"}]


class TestMonitorResourceResolver:
    """MonitorResourceResolver 补全行为与旧版 create_instance 的 DB 查询语义一致。"""

    def _resolver(self):
        from bkmonitor.iam.handlers.resolver import MonitorResourceResolver

        return MonitorResourceResolver()

    def test_resolve_unknown_type_passthrough(self):
        resolver = self._resolver()
        r = resolver.resolve(ResourceInstance(type="unknown_rt", id="x"), tenant_id="system")
        assert r.id == "x"
        assert r.name == ""
        assert r.ancestor_chain == ()

    def test_resolve_space_with_int_biz_id(self):
        resolver = self._resolver()
        space_api = MagicMock()
        space = MagicMock()
        space.space_type_id = "bkcc"
        space.space_name = "蓝鲸"
        space.bk_tenant_id = "system"
        space_api.SpaceApi.get_space_detail.return_value = space
        with patch("bkmonitor.iam.handlers.resolver.space_api", space_api):
            r = resolver.resolve(ResourceInstance(type="space", id="2"), tenant_id="system")
        assert r.type == "space"
        assert r.id == "2"
        assert r.name == "[bkcc] 蓝鲸"

    def test_resolve_space_fallback_name(self):
        resolver = self._resolver()
        space_api = MagicMock()
        space_api.SpaceApi.get_space_detail.side_effect = Exception("boom")
        with patch("bkmonitor.iam.handlers.resolver.space_api", space_api):
            r = resolver.resolve(ResourceInstance(type="space", id="999"), tenant_id="system")
        assert r.name == "999"  # 查不到时退化为实例 ID（旧版同）

    def test_resolve_apm(self):
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.handlers.resolver.MonitorResourceResolver._get_apm_app_info",
            return_value={"application_id": "app-1", "app_name": "demo", "bk_biz_id": 2},
        ):
            r = resolver.resolve(ResourceInstance(type="apm_application", id="app-1"), tenant_id="system")
        assert r.name == "demo"
        assert len(r.ancestor_chain) == 1
        assert r.ancestor_chain[0].type == "space"
        assert r.ancestor_chain[0].id == "2"

    def test_resolve_apm_missing(self):
        resolver = self._resolver()
        with patch("bkmonitor.iam.handlers.resolver.MonitorResourceResolver._get_apm_app_info", return_value=None):
            r = resolver.resolve(ResourceInstance(type="apm_application", id="app-x"), tenant_id="system")
        assert r.name == ""
        assert r.ancestor_chain == ()

    def test_resolve_grafana(self):
        """grafana 实例补全经 catalog 查询（三种 ID 格式的解析逻辑在 catalog 侧）。"""
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.handlers.resolver.catalog.fetch_instance_info",
            return_value=[{"id": "1|uid-1", "display_name": "[仪表盘] General/大盘", "_bk_iam_path_": "/space,3/"}],
        ):
            r = resolver.resolve(ResourceInstance(type="grafana_dashboard", id="1|uid-1"), tenant_id="system")
        assert r.name == "[仪表盘] General/大盘"
        assert r.ancestor_chain[0].type == "space"
        assert r.ancestor_chain[0].id == "3"

    def test_resolve_grafana_folder_format(self):
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.handlers.resolver.catalog.fetch_instance_info",
            return_value=[{"id": "folder:1|7", "display_name": "[目录] 运维大盘", "_bk_iam_path_": "/space,3/"}],
        ):
            r = resolver.resolve(ResourceInstance(type="grafana_dashboard", id="folder:1|7"), tenant_id="system")
        assert r.name == "[目录] 运维大盘"
        assert r.ancestor_chain[0].type == "space"
        assert r.ancestor_chain[0].id == "3"

    def test_resolve_grafana_missing(self):
        resolver = self._resolver()
        with patch("bkmonitor.iam.handlers.resolver.catalog.fetch_instance_info", return_value=[]):
            r = resolver.resolve(ResourceInstance(type="grafana_dashboard", id="1|uid-missing"), tenant_id="system")
        assert r.name == ""
        assert r.ancestor_chain == ()

    def test_resolve_rum(self):
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.handlers.resolver.MonitorResourceResolver._get_rum_app_info",
            return_value={"application_id": "rum-1", "app_name": "r", "bk_biz_id": 7},
        ):
            r = resolver.resolve(ResourceInstance(type="rum_application", id="rum-1"), tenant_id="system")
        assert r.name == "r"
        assert r.ancestor_chain[0].id == "7"


class TestSdkResourceParity:
    """新旧路径下，发送给 V3 平台的 SDK Resource 载荷一致（鉴权路径一致性的资源侧证明）。

    旧路径：Business.create_simple_instance(bk_biz_id) -> iam.Resource(
                system=bk_monitorv3, type=space, id=bk_biz_id, attribute={id,name,...})
    新路径：FwResource(type=space, id=bk_biz_id) -> MonitorResourceResolver 补全
                -> V3Client.make_resource(type, id, ancestors=...) -> iam.Resource
    """

    def _build_provider_with_client(self, real_schema):
        from .conftest import build_v3_options

        provider = build_provider("v3", schema=real_schema, options={**build_v3_options()})
        mock_client = MagicMock()
        provider._get_client = MagicMock(return_value=mock_client)
        provider.resolver = None
        return provider, mock_client

    def test_space_resource_payload_parity(self, real_schema):
        """space 资源：新旧路径产出相同 SDK Resource（system/type/id）。"""
        from iam import Resource as SdkResource

        # 旧路径：Business.create_simple_instance -> iam.Resource(bk_monitorv3, space, id)
        old_resource = SdkResource("bk_monitorv3", "space", "2", {"id": "2", "name": "x"})
        assert (old_resource.system, old_resource.type, old_resource.id) == ("bk_monitorv3", "space", "2")

        # 新路径：方言层用 make_resource(type, id) 构建等价 SDK Resource
        from iam_engine.core.requests import AuthRequest, ResourceInstance
        from iam_engine.provider.requests import Subject

        provider, mock_client = self._build_provider_with_client(real_schema)
        req = AuthRequest(
            subject=Subject(id="u", tenant_id="system"),
            action_id="view_business",
            resources=(ResourceInstance(type="space", id="2"),),
        )
        provider.is_allowed(req)
        # 方言层用 type/id 构造资源（system 由 client 内部固定为 bk_monitorv3）
        mock_client.make_resource.assert_called_once_with("space", "2", ancestors=(), attribute={})

    def test_apm_resource_ancestors_passed_to_sdk(self, real_schema):
        """APM 资源：resolver 补全的 ancestor_chain 经方言编码传入 SDK make_resource。"""
        from iam_engine.core.requests import AuthRequest, Subject

        provider, mock_client = self._build_provider_with_client(real_schema)

        resolved = ResourceInstance(
            type="apm_application", id="app-1", name="demo", ancestor_chain=(ResourceInstance(type="space", id="2"),)
        )
        with patch.object(provider, "_resolve", return_value=resolved):
            provider.is_allowed(
                AuthRequest(
                    subject=Subject(id="u", tenant_id="system"),
                    action_id="view_apm_application",
                    resources=(ResourceInstance(type="apm_application", id="app-1"),),
                )
            )

        # 祖先链（编码后的 DialectResource）传给 make_resource，V3Client 据此拼 _bk_iam_path_
        mock_client.make_resource.assert_called_once()
        args = mock_client.make_resource.call_args
        assert args.args[0] == "apm_application"
        assert args.args[1] == "app-1"
        ancestors = args.kwargs["ancestors"]
        assert len(ancestors) == 1
        assert ancestors[0].type == "space"
        assert ancestors[0].id == "2"


class TestProviderIsAllowedResourceHandling:
    """provider 方言层对无资源 action 的处理（与旧 Permission 行为一致）。"""

    def test_resource_free_action_drops_resource(self, real_schema):
        """旧版：action.related_resource_types 为空时 resources=[]；
        新版：方言层 _action_has_resource=False 时同样不传 SDK resources。"""
        from iam_engine.core.requests import AuthRequest, ResourceInstance
        from iam_engine.provider.requests import Subject

        from .conftest import build_v3_options

        provider = MagicMock()
        # 直接用真实 provider 验证

        provider = build_provider("v3", schema=real_schema, options={**build_v3_options()})
        mock_client = MagicMock()
        provider._get_client = MagicMock(return_value=mock_client)

        req = AuthRequest(
            subject=Subject(id="u", tenant_id="system"),
            action_id="manage_global_setting",
            resources=(ResourceInstance(type="space", id="2"),),
        )
        provider.is_allowed(req)
        # 无资源 action：不构造 SDK resource
        mock_client.make_resource.assert_not_called()
        # request 的 resources 为空列表
        call_kwargs = mock_client.make_request.call_args
        assert call_kwargs.args[2] == []
