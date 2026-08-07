"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

"""
TAPD5 L2 单测：TGPATaskViewSet / TGPAReportViewSet 的 get_permissions() 接线校验。

对照 tapd5.md 验收标准：
  2. 仅 VIEW_CLIENT_LOG 用户可以查看但不能创建或下载           → 各 ViewSet action 与 ActionMeta 的一一映射断言
  3. CREATE_CLIENT_LOG_TASK 与 DOWNLOAD_CLIENT_LOG 可独立授权   → TGPATaskViewSet create/download 分支
  6. 创建人和审计用户为真实 PO 外部用户                         → TestCreateAndSyncReportAuditIdentity

已知问题登记（本期不修复，仅验证现状未被破坏）：
  TGPATaskViewSet.create / get_download_url 未在 ViewSetActionEnum 注册，PO 外部用户经
  dispatch_external_proxy 代理时不可达；本文件仅测试 ViewSet 层 get_permissions() 的内部权限接线，
  不涉及外部代理层可达性（该缺口的代理层行为已在其它测试/文档中记录）。
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.drf import BusinessActionPermission
from apps.tgpa.views import TGPAReportViewSet, TGPATaskViewSet


def _make_viewset(view_cls, action_name):
    vs = view_cls(**{"format_kwarg": None})
    vs.action = action_name
    return vs


# ════════════════════════════════════════════════════════════════════
#  TGPATaskViewSet：create/download 独立 action，其余查看类切 VIEW_CLIENT_LOG
# ════════════════════════════════════════════════════════════════════


class TestTGPATaskViewSetPermissions(TestCase):
    """验收标准 2/3：查看类=VIEW_CLIENT_LOG；create=CREATE_CLIENT_LOG_TASK；download=DOWNLOAD_CLIENT_LOG，三者互相独立。"""

    def test_create_uses_create_client_log_task(self):
        vs = _make_viewset(TGPATaskViewSet, "create")
        perms = vs.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertIsInstance(perms[0], BusinessActionPermission)
        self.assertEqual(perms[0].actions, [ActionEnum.CREATE_CLIENT_LOG_TASK])

    def test_get_download_url_uses_download_client_log(self):
        vs = _make_viewset(TGPATaskViewSet, "get_download_url")
        perms = vs.get_permissions()
        self.assertEqual(perms[0].actions, [ActionEnum.DOWNLOAD_CLIENT_LOG])

    def test_download_file_uses_download_client_log(self):
        vs = _make_viewset(TGPATaskViewSet, "download_file")
        perms = vs.get_permissions()
        self.assertEqual(perms[0].actions, [ActionEnum.DOWNLOAD_CLIENT_LOG])

    def test_view_actions_use_view_client_log_not_view_business(self):
        """查看类(list/get_task_status/sync_task/get_index_set_id)不应再回退到 VIEW_BUSINESS，
        必须切换为 VIEW_CLIENT_LOG（验收 2 的核心断言：细粒度收权，不再借用粗粒度业务权限）"""
        for action_name in ("list", "get_task_status", "sync_task", "get_index_set_id", "get_username_list"):
            vs = _make_viewset(TGPATaskViewSet, action_name)
            perms = vs.get_permissions()
            self.assertEqual(len(perms), 1, action_name)
            self.assertEqual(perms[0].actions, [ActionEnum.VIEW_CLIENT_LOG], action_name)
            self.assertNotIn(ActionEnum.VIEW_BUSINESS, perms[0].actions, action_name)

    def test_create_and_download_actions_are_independent(self):
        """验收标准 3：CREATE_CLIENT_LOG_TASK 与 DOWNLOAD_CLIENT_LOG 互相独立，不因其中一个变化影响另一个"""
        create_perms = _make_viewset(TGPATaskViewSet, "create").get_permissions()
        download_perms = _make_viewset(TGPATaskViewSet, "download_file").get_permissions()
        self.assertNotEqual(create_perms[0].actions, download_perms[0].actions)
        self.assertEqual(create_perms[0].actions, [ActionEnum.CREATE_CLIENT_LOG_TASK])
        self.assertEqual(download_perms[0].actions, [ActionEnum.DOWNLOAD_CLIENT_LOG])


# ════════════════════════════════════════════════════════════════════
#  TGPAReportViewSet：全部接口(含"查看"类)切到 VIEW_CLIENT_LOG
# ════════════════════════════════════════════════════════════════════


class TestTGPAReportViewSetPermissions(TestCase):
    """验收标准 2/7：TGPAReportViewSet 不再使用 ViewBusinessPermission 兜底，统一切到 VIEW_CLIENT_LOG"""

    def test_all_actions_use_view_client_log(self):
        for action_name in ("list", "sync_report", "get_file_status", "retrieve_sync_record"):
            vs = _make_viewset(TGPAReportViewSet, action_name)
            perms = vs.get_permissions()
            self.assertEqual(len(perms), 1, action_name)
            self.assertIsInstance(perms[0], BusinessActionPermission, action_name)
            self.assertEqual(perms[0].actions, [ActionEnum.VIEW_CLIENT_LOG], action_name)


# ════════════════════════════════════════════════════════════════════
#  验收标准 6：创建人/审计用户使用真实 PO 外部用户身份
# ════════════════════════════════════════════════════════════════════


class TestCreateAndSyncReportAuditIdentity(TestCase):
    """create() 的 username 字段 / sync_report() 的 created_by 字段
    必须优先取 get_request_external_username()，仅内部用户（无 external_user）才回退到 request.user.username。
    """

    @patch("apps.tgpa.views.TGPATaskApi.create_single_user_log_task_v2")
    @patch("apps.tgpa.views.get_request_external_username")
    def test_create_uses_external_username_when_present(self, mock_get_ext, mock_create_api):
        """PO 外部用户经代理创建任务时，写入 TGPATaskApi 的 username 必须是外部用户本人，而非 authorizer"""
        mock_get_ext.return_value = "po_external_user"

        vs = TGPATaskViewSet(**{"format_kwarg": None})
        request = MagicMock()
        request.user.username = "internal_authorizer"

        with patch.object(
            vs,
            "params_valid",
            return_value={
                "bk_biz_id": 2,
                "log_path": "/data/logs",
                "task_name": "task1",
            },
        ):
            vs.create(request)

        mock_create_api.assert_called_once()
        params = mock_create_api.call_args[0][0]
        self.assertEqual(params["username"], "po_external_user",
                         "外部用户经代理创建任务时，username 必须写入 external_user 本人，不能是 authorizer")

    @patch("apps.tgpa.views.TGPATaskApi.create_single_user_log_task_v2")
    @patch("apps.tgpa.views.get_request_external_username", return_value="")
    def test_create_falls_back_to_request_user_when_internal(self, _mock_get_ext, mock_create_api):
        """内部用户直接访问（无 external_user）时，回退到 request.user.username"""
        vs = TGPATaskViewSet(**{"format_kwarg": None})
        request = MagicMock()
        request.user.username = "internal_operator"

        with patch.object(
            vs,
            "params_valid",
            return_value={
                "bk_biz_id": 2,
                "log_path": "/data/logs",
                "task_name": "task1",
            },
        ):
            vs.create(request)

        params = mock_create_api.call_args[0][0]
        self.assertEqual(params["username"], "internal_operator")

    @patch("apps.tgpa.views.fetch_and_process_tgpa_reports")
    @patch("apps.tgpa.views.FeatureToggleObject.switch", return_value=True)
    @patch("apps.tgpa.views.get_request_external_username")
    def test_sync_report_created_by_uses_external_username(self, mock_get_ext, _mock_switch, mock_task):
        """PO 外部用户经代理同步上报时，TGPAReportSyncRecord.created_by 必须是外部用户本人"""
        mock_get_ext.return_value = "po_external_user"

        vs = TGPAReportViewSet(**{"format_kwarg": None})
        request = MagicMock()
        request.user.username = "internal_authorizer"

        with patch.object(
            vs,
            "params_valid",
            return_value={"bk_biz_id": 2, "openid_list": ["openid_1"], "file_name_list": ["f1.log"]},
        ):
            response = vs.sync_report(request)

        from apps.tgpa.models import TGPAReportSyncRecord

        record = TGPAReportSyncRecord.objects.get(id=response.data["record_id"])
        self.assertEqual(record.created_by, "po_external_user",
                         "外部用户经代理同步上报时，created_by 必须写入 external_user 本人，不能是 authorizer")
