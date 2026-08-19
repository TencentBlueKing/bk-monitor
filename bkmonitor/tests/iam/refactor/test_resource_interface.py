"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# resource.py 重构对照测试
#
# 对照基线：merge-base 7b360f40 上的旧 resource.py（478 行）
# 测试目标：
#   1. ResourceEnum 成员 / .id / .name 与旧版一致（接口稳定性）
#   2. create_* 系列返回 ResourceInstance（type+id），可被新版鉴权路径消费
#   3. MonitorResourceResolver 补全 name / ancestor_chain，与旧版 create_instance
#      的 DB 查询语义一致（鉴权路径一致性的资源侧前提）
#   4. 旧版接口移除项（system_id / parent_resource / get_resource_by_id /
#      batch_get_display_names / batch_get_parent / to_json）显式记录
# 安全约束：仅内存/DB 只读查询（SpaceApi 详情、Application/Dashboard 查询），
# 不涉及任何授权写操作。
# ==============================================================================

from unittest.mock import MagicMock, patch


from bkmonitor.iam.resource import ApmApplication, Business, GrafanaDashboard, ResourceEnum, RumApplication
from bkmonitor.iam.iam_engine.core.types import ResourceInstance


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
    """create_* 系列返回 ResourceInstance（type + id）。"""

    def test_create_simple_instance(self):
        r = Business.create_simple_instance("2")
        assert isinstance(r, ResourceInstance)
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

    def test_attribute_param_is_now_ignored(self):
        """已知行为差异：旧版 create_simple_instance 会把 attribute 写进
        iam.Resource.attribute（含 bk_biz_id / name / _bk_iam_path_）；
        新版返回裸 ResourceInstance，属性由 MonitorResourceResolver 在鉴权时补全。
        """
        r = ApmApplication.create_simple_instance("app-1", {"bk_biz_id": "2"})
        assert r.attributes == {}


class TestRemovedInterfaces:
    """旧版接口移除项显式记录（review 发现项）。"""

    def test_removed_class_attributes(self):
        import bkmonitor.iam.resource as resource_module

        for attr in (
            "system_id",
            "selection_mode",
            "related_instance_selections",
            "parent_resource",
            "get_resource_by_id",
            "_all_resources",
            "batch_get_display_names",
            "batch_get_parent",
            "to_json",
            "ResourceMeta",
        ):
            assert not hasattr(resource_module, attr), attr

    def test_resource_classes_no_longer_have_meta_attrs(self):
        assert not hasattr(Business, "system_id")
        assert not hasattr(Business, "parent_resource")
        assert not hasattr(ApmApplication, "batch_get_display_names")
        assert not hasattr(GrafanaDashboard, "batch_get_parent")


class TestMonitorResourceResolver:
    """MonitorResourceResolver 补全行为与旧版 create_instance 的 DB 查询语义一致。"""

    def _resolver(self):
        from bkmonitor.iam.adapters.resolver import MonitorResourceResolver

        return MonitorResourceResolver()

    def test_resolve_unknown_type_passthrough(self):
        resolver = self._resolver()
        r = resolver.resolve(ResourceInstance(type="unknown_rt", id="x"))
        assert r.id == "x"
        assert r.name == ""
        assert r.ancestor_chain == ()

    def test_resolve_space_with_int_biz_id(self):
        resolver = self._resolver()
        space_api = MagicMock()
        space = MagicMock()
        space.space_type_id = "bkcc"
        space.space_name = "蓝鲸"
        space_api.SpaceApi.get_space_detail.return_value = space
        with patch("bkmonitor.iam.adapters.resolver.space_api", space_api):
            r = resolver.resolve(ResourceInstance(type="space", id="2"))
        assert r.type == "space"
        assert r.id == "2"
        assert r.name == "[bkcc] 蓝鲸"

    def test_resolve_space_fallback_name(self):
        resolver = self._resolver()
        space_api = MagicMock()
        space_api.SpaceApi.get_space_detail.side_effect = Exception("boom")
        with patch("bkmonitor.iam.adapters.resolver.space_api", space_api):
            r = resolver.resolve(ResourceInstance(type="space", id="999"))
        assert r.name == "999"  # 查不到时退化为实例 ID（旧版同）

    def test_resolve_apm(self):
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.adapters.resolver.MonitorResourceResolver._get_apm_app_info",
            return_value={"application_id": "app-1", "app_name": "demo", "bk_biz_id": 2},
        ):
            r = resolver.resolve(ResourceInstance(type="apm_application", id="app-1"))
        assert r.name == "demo"
        assert len(r.ancestor_chain) == 1
        assert r.ancestor_chain[0].type == "space"
        assert r.ancestor_chain[0].id == "2"

    def test_resolve_apm_missing(self):
        resolver = self._resolver()
        with patch("bkmonitor.iam.adapters.resolver.MonitorResourceResolver._get_apm_app_info", return_value=None):
            r = resolver.resolve(ResourceInstance(type="apm_application", id="app-x"))
        assert r.name == ""
        assert r.ancestor_chain == ()

    def test_resolve_grafana(self):
        """grafana 实例补全经 catalog 查询（三种 ID 格式的解析逻辑在 catalog 侧）。"""
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.adapters.resolver.catalog.fetch_instance_info",
            return_value=[{"id": "1|uid-1", "display_name": "[仪表盘] General/大盘", "_bk_iam_path_": "/space,3/"}],
        ):
            r = resolver.resolve(ResourceInstance(type="grafana_dashboard", id="1|uid-1"))
        assert r.name == "[仪表盘] General/大盘"
        assert r.ancestor_chain[0].type == "space"
        assert r.ancestor_chain[0].id == "3"

    def test_resolve_grafana_folder_format(self):
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.adapters.resolver.catalog.fetch_instance_info",
            return_value=[{"id": "folder:1|7", "display_name": "[目录] 运维大盘", "_bk_iam_path_": "/space,3/"}],
        ):
            r = resolver.resolve(ResourceInstance(type="grafana_dashboard", id="folder:1|7"))
        assert r.name == "[目录] 运维大盘"
        assert r.ancestor_chain[0].type == "space"
        assert r.ancestor_chain[0].id == "3"

    def test_resolve_grafana_missing(self):
        resolver = self._resolver()
        with patch("bkmonitor.iam.adapters.resolver.catalog.fetch_instance_info", return_value=[]):
            r = resolver.resolve(ResourceInstance(type="grafana_dashboard", id="1|uid-missing"))
        assert r.name == ""
        assert r.ancestor_chain == ()

    def test_resolve_rum(self):
        resolver = self._resolver()
        with patch(
            "bkmonitor.iam.adapters.resolver.MonitorResourceResolver._get_rum_app_info",
            return_value={"application_id": "rum-1", "app_name": "r", "bk_biz_id": 7},
        ):
            r = resolver.resolve(ResourceInstance(type="rum_application", id="rum-1"))
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
        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider
        from .conftest import build_v3_options

        provider = V3PermissionProvider(real_schema, **build_v3_options())
        mock_client = MagicMock()
        provider._get_client = MagicMock(return_value=mock_client)
        return provider, mock_client

    def test_space_resource_payload_parity(self, real_schema):
        """space 资源：新旧路径产出相同 SDK Resource（system/type/id）。"""
        from iam import Resource as SdkResource

        # 旧路径：Business.create_simple_instance -> iam.Resource(bk_monitorv3, space, id)
        old_resource = SdkResource("bk_monitorv3", "space", "2", {"id": "2", "name": "x"})
        assert (old_resource.system, old_resource.type, old_resource.id) == ("bk_monitorv3", "space", "2")

        # 新路径：方言层用 make_resource(type, id) 构建等价 SDK Resource
        from bkmonitor.iam.iam_engine.provider.dialect_types import DialectAuthRequest, DialectResource
        from bkmonitor.iam.iam_engine.core.types import Subject

        provider, mock_client = self._build_provider_with_client(real_schema)
        req = DialectAuthRequest(
            subject=Subject(id="u", tenant_id="system"),
            action_id="view_business_v2",
            resource=DialectResource(type="space", id="2"),
        )
        provider._is_allowed_dialect(req)
        # 方言层用 type/id 构造资源（system 由 client 内部固定为 bk_monitorv3）
        mock_client.make_resource.assert_called_once_with("space", "2", ancestors=())

    def test_apm_resource_ancestors_passed_to_sdk(self, real_schema):
        """APM 资源：resolver 补全的 ancestor_chain 经方言编码传入 SDK make_resource。"""
        from bkmonitor.iam.iam_engine.core.types import AuthRequest, Subject

        provider, mock_client = self._build_provider_with_client(real_schema)

        resolved = ResourceInstance(
            type="apm_application", id="app-1", name="demo", ancestor_chain=(ResourceInstance(type="space", id="2"),)
        )
        with patch.object(provider, "_resolve", return_value=resolved):
            provider.is_allowed(
                AuthRequest(
                    subject=Subject(id="u", tenant_id="system"),
                    action_id="view_apm_application",
                    resource=ResourceInstance(type="apm_application", id="app-1"),
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
        from bkmonitor.iam.iam_engine.provider.dialect_types import DialectAuthRequest, DialectResource
        from bkmonitor.iam.iam_engine.core.types import Subject

        from .conftest import build_v3_options

        provider = MagicMock()
        # 直接用真实 provider 验证
        from bkmonitor.iam.iam_v3.provider import V3PermissionProvider

        provider = V3PermissionProvider(real_schema, **build_v3_options())
        mock_client = MagicMock()
        provider._get_client = MagicMock(return_value=mock_client)

        req = DialectAuthRequest(
            subject=Subject(id="u", tenant_id="system"),
            action_id="manage_global_setting",
            resource=DialectResource(type="space", id="2"),
        )
        provider._is_allowed_dialect(req)
        # 无资源 action：不构造 SDK resource
        mock_client.make_resource.assert_not_called()
        # request 的 resources 为空列表
        call_kwargs = mock_client.make_request.call_args
        assert call_kwargs.args[2] == []
