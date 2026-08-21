"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock, patch

import pytest

from bkmonitor.iam.iam_engine.core.exceptions import ProviderNotFound
from bkmonitor.iam.iam_engine.core.types import BatchAuthResult, ResourceAuthResult
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin.permission import query_user_permissions_v4, query_user_sub_resources_v4

_GET_FW = "kernel_api.rpc.functions.admin.permission._v4.get_framework"
_CATALOG_FETCH = "bkmonitor.iam.adapters.catalog.fetch_instance_info"
_CATALOG_LIST = "bkmonitor.iam.adapters.catalog.list_instances"


def _mock_fw_with_v4(v4_provider) -> MagicMock:
    from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

    mock_fw = MagicMock()
    mock_fw.schema = real_get_fw().schema
    mock_fw.get_provider.return_value = v4_provider
    return mock_fw


def _auth_items(action_id: str, resource_type: str, allowed_map: dict[str, bool]) -> BatchAuthResult:
    return BatchAuthResult(
        items=tuple(
            ResourceAuthResult(action_id=action_id, resource_type=resource_type, resource_id=rid, allowed=allowed)
            for rid, allowed in allowed_map.items()
        )
    )


# ============================================================================
# query_user_permissions_v4（总览）
# ============================================================================


class TestQueryUserPermissionsV4:
    def test_missing_username(self):
        with pytest.raises(CustomException, match="username"):
            query_user_permissions_v4({"bk_tenant_id": "system"})

    @patch(_GET_FW)
    def test_v4_provider_missing_raises(self, mock_get_fw):
        mock_fw = MagicMock()
        mock_fw.get_provider.side_effect = ProviderNotFound("provider 'v4' not found")
        mock_get_fw.return_value = mock_fw

        with pytest.raises(CustomException, match="未配置 v4 provider"):
            query_user_permissions_v4({"username": "testuser", "bk_tenant_id": "system"})

    @patch(_CATALOG_FETCH)
    @patch(_GET_FW)
    def test_overview_global_space_deferred(self, mock_get_fw, mock_fetch):
        """全局 action 走批量、space 走 get_authorized_resources、二级 deferred。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

        mock_v4 = MagicMock()
        global_ids = {a.id for a in real_get_fw().schema.all_actions() if not a.resource_type}
        mock_v4.batch_by_action.return_value = BatchAuthResult(
            items=tuple(
                ResourceAuthResult(
                    action_id=aid,
                    resource_type="",
                    resource_id="",
                    allowed=aid == "manage_global_setting",
                )
                for aid in global_ids
            )
        )
        authorized_map = {
            "view_business": [{"type": "space", "ids": ["*"]}],
            "explore_metric": [{"type": "space", "ids": ["2", "-3"]}],
        }
        mock_v4.get_authorized_resources.side_effect = lambda subject, aid: authorized_map.get(aid, [])

        def fake_fetch(rt_id, ids, requires, bk_tenant_id="system"):
            return [{"id": i, "display_name": f"业务-{i}"} for i in ids]

        mock_fetch.side_effect = fake_fetch

        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)
        result = query_user_permissions_v4({"username": "testuser", "bk_tenant_id": "system"})
        data = result["data"]
        assert data["username"] == "testuser"
        assert data["backend"] == "v4"

        actions = {a["action_id"]: a for a in data["actions"]}

        # space all（"*"）
        biz = actions["view_business"]
        assert biz["grant_type"] == "all"
        assert biz["permissions"] == [{"resource_type": "space", "resource_id": "*", "display_name": ""}]
        assert biz["sub_resources"] is None

        # space partial + 展示名批量补全
        explore = actions["explore_metric"]
        assert explore["grant_type"] == "partial"
        assert explore["permissions"] == [
            {"resource_type": "space", "resource_id": "-3", "display_name": "业务--3"},
            {"resource_type": "space", "resource_id": "2", "display_name": "业务-2"},
        ]

        # space none
        assert actions["view_plugin"]["grant_type"] == "none"
        assert actions["view_plugin"]["permissions"] == []

        # 全局 all（manage_global_setting 批量放行）
        assert actions["manage_global_setting"]["grant_type"] == "all"
        assert actions["view_self_state"]["grant_type"] == "none"

        # 二级 deferred（零平台调用）
        apm = actions["manage_apm_application"]
        assert apm["grant_type"] == "deferred"
        assert apm["permissions"] == []
        assert apm["sub_resources"] is None
        assert "query_user_sub_resources_v4" in apm["note"]

        assert data["summary"]["total_actions"] == len(data["actions"])
        assert data["summary"]["granted_actions"] == 3
        assert data["summary"]["deferred_actions"] == 6
        assert data["summary"]["error_actions"] == 0

    @patch(_GET_FW)
    def test_overview_space_query_failure(self, mock_get_fw):
        """单个 space 授权查询失败 → 该 action error + warning，不整体失败。"""
        from bkmonitor.iam.iam_engine.django.facade import get_framework as real_get_fw

        mock_v4 = MagicMock()
        global_ids = {a.id for a in real_get_fw().schema.all_actions() if not a.resource_type}
        mock_v4.batch_by_action.return_value = BatchAuthResult(
            items=tuple(
                ResourceAuthResult(action_id=aid, resource_type="", resource_id="", allowed=False) for aid in global_ids
            )
        )

        def fake_authorized(subject, aid):
            if aid == "explore_metric":
                raise RuntimeError("gateway down")
            return []

        mock_v4.get_authorized_resources.side_effect = fake_authorized

        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)
        result = query_user_permissions_v4({"username": "testuser", "bk_tenant_id": "system"})
        actions = {a["action_id"]: a for a in result["data"]["actions"]}
        assert actions["explore_metric"]["grant_type"] == "error"
        assert actions["view_business"]["grant_type"] == "none"

        failed = [w for w in result["warnings"] if w["code"] == "IAM_QUERY_FAILED"]
        assert len(failed) == 1
        assert failed[0]["details"]["action_id"] == "explore_metric"
        assert result["data"]["summary"]["error_actions"] == 1

    @patch(_GET_FW)
    def test_overview_global_batch_failure(self, mock_get_fw):
        """全局批量鉴权失败 → 全部全局 action error + warning。"""
        mock_v4 = MagicMock()
        mock_v4.batch_by_action.side_effect = RuntimeError("auth gateway down")
        mock_v4.get_authorized_resources.return_value = []

        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)
        result = query_user_permissions_v4(
            {
                "username": "testuser",
                "bk_tenant_id": "system",
                "action_ids": ["manage_global_setting", "view_self_state"],
            }
        )
        assert all(a["grant_type"] == "error" for a in result["data"]["actions"])
        failed = [w for w in result["warnings"] if w["code"] == "IAM_QUERY_FAILED"]
        assert {w["details"]["action_id"] for w in failed} == {"manage_global_setting", "view_self_state"}

    @patch(_GET_FW)
    def test_overview_action_ids_filter_and_unknown_warning(self, mock_get_fw):
        """action_ids 过滤生效；未知 ID 记 warning 忽略。"""
        mock_v4 = MagicMock()
        mock_v4.get_authorized_resources.return_value = []

        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)
        result = query_user_permissions_v4(
            {
                "username": "testuser",
                "bk_tenant_id": "system",
                "action_ids": "view_business,unknown_action",
            }
        )
        assert len(result["data"]["actions"]) == 1
        assert result["data"]["actions"][0]["action_id"] == "view_business"
        mock_v4.batch_by_action.assert_not_called()
        unknown = [w for w in result["warnings"] if w["code"] == "IAM_UNKNOWN_ACTION"]
        assert len(unknown) == 1
        assert unknown[0]["details"]["action_id"] == "unknown_action"

    @patch(_GET_FW)
    def test_overview_excludes_provider_hidden_actions(self, mock_get_fw):
        """exclude_providers=("v4",) 的过时 action（view_dashboard/manage_dashboard）不进入 v4 总览。"""
        mock_v4 = MagicMock()
        mock_v4.batch_by_action.return_value = BatchAuthResult(items=())
        mock_v4.get_authorized_resources.return_value = []

        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)
        result = query_user_permissions_v4({"username": "testuser", "bk_tenant_id": "system"})
        ids = [a["action_id"] for a in result["data"]["actions"]]
        assert "view_dashboard" not in ids
        assert "manage_dashboard" not in ids
        assert result["data"]["summary"]["total_actions"] == len(ids)
        # 缺省路径静默过滤，不产生警告
        assert not any(w["code"] == "IAM_UNSUPPORTED_ACTION" for w in result["warnings"])

    @patch(_GET_FW)
    def test_overview_explicit_hidden_action_warns(self, mock_get_fw):
        """显式请求 v4 不可见 action → warning 忽略，不进入查询。"""
        mock_v4 = MagicMock()
        mock_v4.get_authorized_resources.return_value = []

        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)
        result = query_user_permissions_v4(
            {
                "username": "testuser",
                "bk_tenant_id": "system",
                "action_ids": "view_dashboard,view_business",
            }
        )
        assert [a["action_id"] for a in result["data"]["actions"]] == ["view_business"]
        unsupported = [w for w in result["warnings"] if w["code"] == "IAM_UNSUPPORTED_ACTION"]
        assert len(unsupported) == 1
        assert unsupported[0]["details"]["action_id"] == "view_dashboard"


# ============================================================================
# query_user_sub_resources_v4（展开）
# ============================================================================


class TestQueryUserSubResourcesV4:
    def _params(self, **extra):
        params = {"username": "testuser", "bk_tenant_id": "system", "bk_biz_id": 2}
        params.update(extra)
        return params

    def test_missing_bk_biz_id(self):
        with pytest.raises(CustomException, match="bk_biz_id"):
            query_user_sub_resources_v4({"username": "testuser", "bk_tenant_id": "system"})

    def test_invalid_bk_biz_id(self):
        with pytest.raises(CustomException, match="bk_biz_id"):
            query_user_sub_resources_v4(self._params(bk_biz_id="abc"))

    @patch(_GET_FW)
    def test_v4_provider_missing_raises(self, mock_get_fw):
        mock_fw = MagicMock()
        mock_fw.get_provider.side_effect = ProviderNotFound("provider 'v4' not found")
        mock_get_fw.return_value = mock_fw

        with pytest.raises(CustomException, match="未配置 v4 provider"):
            query_user_sub_resources_v4(self._params())

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_apm_partial_and_unsupported_filtered(self, mock_get_fw, mock_list):
        """apm 展开：枚举 + 批量鉴权 → partial；非二级 action 记 warning 忽略。"""
        mock_v4 = MagicMock()
        mock_v4.batch_by_resource.return_value = _auth_items(
            "manage_apm_application", "apm_application", {"390": True, "405": False}
        )

        def fake_list(rt_id, filter_data, page, bk_tenant_id="system"):
            assert filter_data["parent"] == {"type": "space", "id": "2"}
            return {
                "count": 2,
                "results": [
                    {"id": "390", "display_name": "alias-390", "name": "app-390"},
                    {"id": "405", "display_name": "alias-405", "name": "app-405"},
                ],
            }

        mock_list.side_effect = fake_list
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        result = query_user_sub_resources_v4(self._params(action_ids=["manage_apm_application", "view_business"]))
        data = result["data"]
        assert data["bk_biz_id"] == 2
        assert len(data["actions"]) == 1

        apm = data["actions"][0]
        assert apm["grant_type"] == "partial"
        assert apm["permissions"] == []
        assert apm["sub_resources"] == [
            {
                "resource_id": "390",
                "display_name": "alias-390",
                "parent": {"type": "space", "id": "2"},
            }
        ]
        assert data["summary"] == {"total_actions": 1, "granted_actions": 1, "error_actions": 0}

        unsupported = [w for w in result["warnings"] if w["code"] == "IAM_UNSUPPORTED_ACTION"]
        assert len(unsupported) == 1
        assert unsupported[0]["details"]["action_id"] == "view_business"

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_all_and_none(self, mock_get_fw, mock_list):
        """全部候选通过 → all；无一通过 → none。"""
        mock_v4 = MagicMock()
        mock_v4.batch_by_resource.side_effect = [
            _auth_items("view_apm_application", "apm_application", {"390": True, "405": True}),
            _auth_items("manage_apm_application", "apm_application", {"390": False, "405": False}),
        ]
        mock_list.return_value = {
            "count": 2,
            "results": [
                {"id": "390", "display_name": "alias-390", "name": "app-390"},
                {"id": "405", "display_name": "alias-405", "name": "app-405"},
            ],
        }
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        result = query_user_sub_resources_v4(
            self._params(action_ids=["view_apm_application", "manage_apm_application"])
        )
        actions = {a["action_id"]: a for a in result["data"]["actions"]}
        assert actions["view_apm_application"]["grant_type"] == "all"
        assert len(actions["view_apm_application"]["sub_resources"]) == 2
        assert actions["manage_apm_application"]["grant_type"] == "none"
        assert actions["manage_apm_application"]["sub_resources"] == []

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_empty_candidates(self, mock_get_fw, mock_list):
        """空间内无该资源实例 → none + note。"""
        mock_v4 = MagicMock()
        mock_list.return_value = {"count": 0, "results": []}
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        result = query_user_sub_resources_v4(self._params(action_ids=["manage_apm_application"]))
        apm = result["data"]["actions"][0]
        assert apm["grant_type"] == "none"
        assert "无此资源类型" in apm["note"]
        mock_v4.batch_by_resource.assert_not_called()

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_enum_failure(self, mock_get_fw, mock_list):
        """枚举失败 → 该 rt 全部 action error + warning。"""
        mock_v4 = MagicMock()
        mock_list.side_effect = RuntimeError("db down")
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        result = query_user_sub_resources_v4(self._params(action_ids=["manage_apm_application"]))
        apm = result["data"]["actions"][0]
        assert apm["grant_type"] == "error"
        assert apm["note"] == "二级资源枚举失败"
        mock_v4.batch_by_resource.assert_not_called()
        failed = [w for w in result["warnings"] if w["code"] == "IAM_SUB_RESOURCE_ENUM_FAILED"]
        assert len(failed) == 1
        assert failed[0]["details"]["resource_type"] == "apm_application"

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_batch_auth_failure(self, mock_get_fw, mock_list):
        """批量鉴权失败 → 该 action error + warning。"""
        mock_v4 = MagicMock()
        mock_v4.batch_by_resource.side_effect = RuntimeError("auth gateway down")
        mock_list.return_value = {
            "count": 1,
            "results": [{"id": "390", "display_name": "alias-390", "name": "app-390"}],
        }
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        result = query_user_sub_resources_v4(self._params(action_ids=["manage_apm_application"]))
        apm = result["data"]["actions"][0]
        assert apm["grant_type"] == "error"
        failed = [w for w in result["warnings"] if w["code"] == "IAM_BATCH_AUTH_FAILED"]
        assert len(failed) == 1
        assert failed[0]["details"]["action_id"] == "manage_apm_application"

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_pagination(self, mock_get_fw, mock_list):
        """候选跨页收集：翻页直到拿满 count，再一次性批量鉴权。"""
        mock_v4 = MagicMock()
        mock_v4.batch_by_resource.return_value = BatchAuthResult(items=())

        def fake_list(rt_id, filter_data, page, bk_tenant_id="system"):
            if page.get("page") == 1:
                return {"count": 3, "results": [{"id": "390", "display_name": "a"}, {"id": "405", "display_name": "b"}]}
            return {"count": 3, "results": [{"id": "411", "display_name": "c"}]}

        mock_list.side_effect = fake_list
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        query_user_sub_resources_v4(self._params(action_ids=["manage_apm_application"]))
        request = mock_v4.batch_by_resource.call_args.args[0]
        assert [r.id for r in request.resources] == ["390", "405", "411"]
        assert request.action_id == "manage_apm_application"

    @patch(_CATALOG_LIST)
    @patch(_GET_FW)
    def test_expand_default_all_sub_actions(self, mock_get_fw, mock_list):
        """缺省 action_ids → 全部二级资源操作（共 6 个）。"""
        mock_v4 = MagicMock()
        mock_list.return_value = {"count": 0, "results": []}
        mock_get_fw.return_value = _mock_fw_with_v4(mock_v4)

        result = query_user_sub_resources_v4(self._params())
        assert len(result["data"]["actions"]) == 6
        assert all(a["grant_type"] == "none" for a in result["data"]["actions"])
        assert result["data"]["summary"]["total_actions"] == 6


# ==============================================================================
# 真实 IAM 框架集成测试 — 连接真实 V4 IAM 服务器查询用户权限
#
# 与 v3 的 TestRealFrameworkQuery 同一环境：共用同一 Django settings / 数据库
# （@pytest.mark.django_db 使用完全相同的 databases：default / monitor_api /
# bk_dataview），catalog 的 space / apm / rum / grafana 查询走同一套本地库。
# 平台连接走同一 .env 的 v4 配置（BK_IAM_V4_API_BASE_URL 等），
# 并要求 IAM_FRAMEWORK.PROVIDERS 已装配 v4 provider（未装配时运行时 skip）。
# ==============================================================================


@pytest.mark.skipif(
    not __import__("django").conf.settings.BK_IAM_V4_API_BASE_URL,
    reason="IAM v4 API 未配置（BK_IAM_V4_API_BASE_URL 为空）",
)
class TestRealFrameworkQueryV4:
    """连接真实 IAM v4 服务器，调用 v4 权限查询接口获取实际权限数据。"""

    @pytest.mark.django_db(databases=["default", "monitor_api", "bk_dataview"])
    def test_query_real_user_permissions_v4(self):
        """
        调用 query_user_permissions_v4 查询真实用户的 v4 权限总览。

        环境变量：
          IAM_V4_TEST_USER — 测试用户名（默认 "admin"）
          IAM_V4_TENANT_ID — 租户 ID（默认 "system"）

        断言：
          - 返回结构正确（username / bk_tenant_id / backend / actions / summary）
          - actions 为非空列表
          - 每个 action 含 action_id / grant_type / permissions / sub_resources 字段
          - summary 含 total_actions / granted_actions / deferred_actions / error_actions
        """
        username = __import__("os").environ.get("IAM_V4_TEST_USER", "admin")
        tenant_id = __import__("os").environ.get("IAM_V4_TENANT_ID", "system")

        from bkmonitor.iam.iam_engine.django.facade import get_framework

        if "v4" not in get_framework().providers:
            pytest.skip("框架未装配 v4 provider（IAM_FRAMEWORK.PROVIDERS 未启用 v4 块）")

        result = query_user_permissions_v4({"username": username, "bk_tenant_id": tenant_id})

        # ---- 顶层结构 ----
        assert "data" in result, f"返回缺少 data 字段: {list(result.keys())}"
        data = result["data"]

        assert data["username"] == username
        assert "bk_tenant_id" in data
        assert data["backend"] == "v4"
        assert "actions" in data
        assert "summary" in data

        actions = data["actions"]
        assert isinstance(actions, list)
        assert len(actions) > 0, f"actions 不应为空，实际 {len(actions)} 条"

        # ---- 每条 action 的结构 ----
        valid_grant_types = ("all", "partial", "none", "deferred", "error")
        for action in actions:
            assert "action_id" in action, f"action 缺少 action_id: {action}"
            assert "grant_type" in action, f"action {action['action_id']} 缺少 grant_type"
            assert "permissions" in action, f"action {action['action_id']} 缺少 permissions"
            assert "sub_resources" in action, f"action {action['action_id']} 缺少 sub_resources"
            assert action["grant_type"] in valid_grant_types, f"无效的 grant_type: {action['grant_type']}"

        # ---- summary ----
        summary = data["summary"]
        assert "total_actions" in summary
        assert "granted_actions" in summary
        assert "deferred_actions" in summary
        assert "error_actions" in summary
        assert summary["total_actions"] == len(actions)

        # ---- 将 query_user_permissions_v4 的完整返回值落盘，供人工核对数据结构 ----
        # import json

        # diag_path = _os.path.join(_os.path.dirname(__file__), "new_version_v4.json")
        # with open(diag_path, "w") as f:
        #     json.dump(result, f, ensure_ascii=False, indent=2)

    @pytest.mark.django_db(databases=["default", "monitor_api", "bk_dataview"])
    def test_query_real_user_sub_resources_v4(self):
        """
        调用 query_user_sub_resources_v4 查询真实用户在指定空间下的二级资源授权。

        环境变量：
          IAM_V4_TEST_USER     — 测试用户名（默认 "admin"）
          IAM_V4_TENANT_ID     — 租户 ID（默认 "system"）
          IAM_V4_TEST_SPACE_ID — 展开的空间 ID（默认 "2"）

        断言：
          - 返回结构正确（username / bk_tenant_id / bk_biz_id / actions / summary）
          - 每个 action 含 action_id / grant_type / sub_resources 字段
          - summary 含 total_actions / granted_actions / error_actions
        """
        username = __import__("os").environ.get("IAM_V4_TEST_USER", "admin")
        tenant_id = __import__("os").environ.get("IAM_V4_TENANT_ID", "system")
        space_id = __import__("os").environ.get("IAM_V4_TEST_SPACE_ID", "2")

        from bkmonitor.iam.iam_engine.django.facade import get_framework

        if "v4" not in get_framework().providers:
            pytest.skip("框架未装配 v4 provider（IAM_FRAMEWORK.PROVIDERS 未启用 v4 块）")

        result = query_user_sub_resources_v4({"username": username, "bk_tenant_id": tenant_id, "bk_biz_id": space_id})

        # ---- 顶层结构 ----
        assert "data" in result, f"返回缺少 data 字段: {list(result.keys())}"
        data = result["data"]

        assert data["username"] == username
        assert "bk_tenant_id" in data
        assert data["backend"] == "v4"
        assert "bk_biz_id" in data
        assert "actions" in data
        assert "summary" in data

        actions = data["actions"]
        assert isinstance(actions, list)
        assert len(actions) > 0, f"actions 不应为空，实际 {len(actions)} 条"

        # ---- 每条 action 的结构 ----
        valid_grant_types = ("all", "partial", "none", "error")
        for action in actions:
            assert "action_id" in action, f"action 缺少 action_id: {action}"
            assert "grant_type" in action, f"action {action['action_id']} 缺少 grant_type"
            assert "sub_resources" in action, f"action {action['action_id']} 缺少 sub_resources"
            assert action["grant_type"] in valid_grant_types, f"无效的 grant_type: {action['grant_type']}"
            for sub in action["sub_resources"] or []:
                assert "resource_id" in sub and "display_name" in sub and "parent" in sub, (
                    f"无效的 sub_resource 结构: {sub}"
                )

        # ---- summary ----
        summary = data["summary"]
        assert "total_actions" in summary
        assert "granted_actions" in summary
        assert "error_actions" in summary
        assert summary["total_actions"] == len(actions)

        # ---- 将 query_user_sub_resources_v4 的完整返回值落盘，供人工核对数据结构 ----
        # import json
        #
        # # diag_path = _os.path.join(_os.path.dirname(__file__), "new_version_v4_sub_resources.json")
        # with open(diag_path, "w") as f:
        #     json.dump(result, f, ensure_ascii=False, indent=2)
