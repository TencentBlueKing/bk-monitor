"""业务访问（空间访问）授权：两代协议入口不同，这里守住各自的请求契约与失败上报。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.iam.backends.v3.writer import V3AuthorizationWriter
from apps.iam.backends.v4.writer import SPACE_ACCESS_ROLE_ID, V4AuthorizationWriter
from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.log_search.models import Space, SpaceType


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search", BK_IAM_V4_GRANT_EXPIRE_DAYS=365)
class SpaceAccessWriterTest(SimpleTestCase):
    @patch("apps.iam.backends.v4.writer.timezone.now")
    def test_v4_grants_minimal_space_access_role(self, now):
        now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        client = Mock()
        writer = V4AuthorizationWriter(client, operator="operator")

        writer.grant_space_access(space_id="2", subject_id="owner1", space_name="[业务] 蓝鲸")

        expected_expired_at = int((now.return_value + timedelta(days=365)).timestamp())
        client.add_authorization.assert_called_once_with(
            items=[
                {
                    "subject": {"type": "user", "id": "owner1"},
                    "role_id": SPACE_ACCESS_ROLE_ID,
                    "related_resource_type_id": "space",
                    "resources": [{"type": "space", "id": "2"}],
                    "expired_at": expected_expired_at,
                }
            ],
            operator="operator",
        )

    def test_v4_keeps_negative_space_id_for_client_codec(self):
        """负数空间 ID 的 neg_ 编码由 client 的 codec 负责，writer 不得提前编码成两套口径。"""
        client = Mock()
        writer = V4AuthorizationWriter(client, operator="operator")

        writer.grant_space_access(space_id="-3", subject_id="owner1")

        items = client.add_authorization.call_args.kwargs["items"]
        self.assertEqual(items[0]["resources"], [{"type": "space", "id": "-3"}])

    def test_v3_grants_view_business_through_instance_authorization_api(self):
        grant_instance_api = Mock()
        writer = V3AuthorizationWriter(Mock(), bk_tenant_id="tenant-1", grant_instance_api=grant_instance_api)

        writer.grant_space_access(space_id="2", subject_id="owner1", space_name="[业务] 蓝鲸")

        grant_instance_api.assert_called_once_with(
            {
                "asynchronous": False,
                "operate": "grant",
                "system": "bk_log_search",
                "actions": [{"id": "view_business_v2"}],
                "subject": {"type": "user", "id": "owner1"},
                # 空间资源归属监控平台，不是日志平台自己的资源类型
                "resources": [
                    {
                        "system": "bk_monitorv3",
                        "type": "space",
                        "instances": [{"id": "2", "name": "[业务] 蓝鲸"}],
                    }
                ],
            },
            # 授权 API 不像 SDK client 自带租户，后台任务里漏传会授到请求上下文的租户
            bk_tenant_id="tenant-1",
        )

    def test_v3_falls_back_to_space_id_when_name_is_unknown(self):
        grant_instance_api = Mock()
        writer = V3AuthorizationWriter(Mock(), grant_instance_api=grant_instance_api)

        writer.grant_space_access(space_id="2", subject_id="owner1")

        instances = grant_instance_api.call_args[0][0]["resources"][0]["instances"]
        self.assertEqual(instances, [{"id": "2", "name": "2"}])

    def test_v3_default_api_is_the_batch_instance_endpoint(self):
        """默认实现必须落在权限中心实例授权接口上，否则线上是空转。"""
        writer = V3AuthorizationWriter(Mock())

        with patch("apps.api.IAMApi.batch_instance") as batch_instance:
            writer.grant_space_access(space_id="2", subject_id="owner1")

        batch_instance.assert_called_once()


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search", BK_APP_TENANT_ID="default")
class SpaceAccessBatchGrantTest(TestCase):
    def setUp(self):
        self.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
        patchers = [
            patch.object(Permission, "get_iam_client", return_value=Mock()),
            patch("apps.iam.handlers.permission.get_mode_provider", return_value=self.mode_provider),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.v3_writer = Mock()
        self.v4_writer = Mock()

    def _make_permission(self, *, with_v4: bool = True) -> Permission:
        permission = Permission(username="admin", bk_tenant_id="tenant-1")
        bundles = {AuthMode.V3: ProviderBundle(writer=self.v3_writer)}
        if with_v4:
            bundles[AuthMode.V4] = ProviderBundle(writer=self.v4_writer)
        permission._provider_bundles = bundles
        return permission

    def test_legacy_writer_carries_the_resolved_tenant(self):
        """门面解析出的租户必须落到 V3 Writer 上，后台调用没有请求上下文可回落。"""
        permission = Permission(username="admin", bk_tenant_id="tenant-1")

        self.assertEqual(permission.provider_bundles[AuthMode.V3].writer.bk_tenant_id, "tenant-1")

    def test_grants_on_both_stacks_and_dedupes_subjects(self):
        permission = self._make_permission()

        failed = permission.grant_space_access_batch(2, ["owner1", "owner1", "owner2", "", None])

        self.assertEqual(failed, [])
        self.assertEqual(
            [call.kwargs["subject_id"] for call in self.v3_writer.grant_space_access.call_args_list],
            ["owner1", "owner2"],
        )
        self.assertEqual(
            [call.kwargs["subject_id"] for call in self.v4_writer.grant_space_access.call_args_list],
            ["owner1", "owner2"],
        )

    def test_resolves_space_display_name_from_local_space(self):
        SpaceType.objects.create(type_id="bkcc", type_name="业务")
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="2",
            space_name="蓝鲸",
        )
        permission = self._make_permission(with_v4=False)

        permission.grant_space_access_batch("bkcc__2", ["owner1"])

        self.v3_writer.grant_space_access.assert_called_once_with(
            space_id="2", subject_id="owner1", space_name="[业务] 蓝鲸"
        )

    def test_reports_subject_when_any_stack_fails(self):
        self.v4_writer.grant_space_access.side_effect = [RuntimeError("iam v4 timeout"), None]
        permission = self._make_permission()

        failed = permission.grant_space_access_batch(2, ["owner1", "owner2"])

        # 一侧失败只影响该主体的上报，不阻断其它主体，也不影响 legacy 侧已完成的授权
        self.assertEqual(failed, ["owner1"])
        self.assertEqual(self.v3_writer.grant_space_access.call_count, 2)

    def test_empty_subjects_short_circuit_without_touching_iam(self):
        permission = self._make_permission()

        self.assertEqual(permission.grant_space_access_batch(2, []), [])
        self.assertEqual(permission.grant_space_access_batch(2, None), [])
        self.v3_writer.grant_space_access.assert_not_called()
        self.v4_writer.grant_space_access.assert_not_called()

    def test_missing_current_writer_still_grants_on_legacy(self):
        permission = self._make_permission(with_v4=False)

        self.assertEqual(permission.grant_space_access_batch(2, ["owner1"]), [])
        self.v3_writer.grant_space_access.assert_called_once()
        self.v4_writer.grant_space_access.assert_not_called()
