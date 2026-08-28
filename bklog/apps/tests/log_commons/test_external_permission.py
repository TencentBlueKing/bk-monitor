from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.constants import DEFAULT_EXTERNAL_PERMISSION_EXPIRE_DAYS
from apps.log_commons.models import ExternalPermission


class TestExternalPermissionCreate(TestCase):
    SPACE_UID = "bkcc__2"
    ACTION_ID = "log_search"

    def _get(self, user):
        return ExternalPermission.objects.get(authorized_user=user, action_id=self.ACTION_ID, space_uid=self.SPACE_UID)

    def _create(self, users, resources, expire_time=None):
        kwargs = dict(
            authorized_users=users,
            space_uid=self.SPACE_UID,
            action_id=self.ACTION_ID,
            resources=resources,
        )
        if not expire_time:
            kwargs["expire_time"] = timezone.now() + timedelta(days=30)
        else:
            kwargs["expire_time"] = expire_time
        ExternalPermission.create(**kwargs)
        return kwargs.get("expire_time")

    # ---------- 全新用户创建 ----------
    def test_new_users_created(self):
        self._create(["user_a", "user_b"], ["1001", "1002"])
        self.assertEqual(ExternalPermission.objects.filter(space_uid=self.SPACE_UID).count(), 2)
        self.assertSetEqual(set(self._get("user_a").resources), {"1001", "1002"})

    # ---------- 已有用户新增资源合并 ----------
    def test_existing_user_resources_merged(self):
        self._create(["user_a"], ["1001"])
        self._create(["user_a"], ["1001", "1002"])
        perm = self._get("user_a")
        self.assertSetEqual(set(perm.resources), {"1001", "1002"})
        self.assertEqual(ExternalPermission.objects.filter(space_uid=self.SPACE_UID).count(), 1)

    # ---------- expire_time 有新值时正常更新 ----------
    def test_different_expire_time_updated(self):
        self._create(["user_a"], ["1001"])
        new_time = timezone.now() + timedelta(days=60)
        self._create(["user_a"], ["1001"], expire_time=new_time)
        self.assertEqual(self._get("user_a").expire_time, new_time)

    def test_new_user_uses_default_expire_time_when_empty(self):
        before = timezone.now() + timedelta(days=DEFAULT_EXTERNAL_PERMISSION_EXPIRE_DAYS)
        ExternalPermission.create(
            authorized_users=["user_a"],
            space_uid=self.SPACE_UID,
            action_id=self.ACTION_ID,
            resources=["1001"],
            expire_time=None,
        )
        after = timezone.now() + timedelta(days=DEFAULT_EXTERNAL_PERMISSION_EXPIRE_DAYS)

        expire_time = self._get("user_a").expire_time
        self.assertGreaterEqual(expire_time, before)
        self.assertLessEqual(expire_time, after)


class TestClusteringConfigActionValid(TestCase):
    """PO 环境（外部版）聚类配置接口的开放范围"""

    LOG_SEARCH = ExternalPermissionActionEnum.LOG_SEARCH.value
    LOG_EXTRACT = ExternalPermissionActionEnum.LOG_EXTRACT.value

    def _is_valid(self, view_set, view_action, action_id=None):
        return ExternalPermission.is_action_valid(
            view_set=view_set, view_action=view_action, action_id=action_id or self.LOG_SEARCH
        )

    # ---------- 聚类配置读写链路对外开放 ----------
    def test_clustering_config_write_actions_allowed(self):
        # view_action 是 ViewSet 的方法名，check 对应 url_path check_regexp
        for view_action in ["get_config", "access_status", "update_access", "get_default_config", "debug", "check"]:
            with self.subTest(view_action=view_action):
                self.assertTrue(self._is_valid("ClusteringConfigViewSet", view_action))

    def test_regex_template_list_allowed(self):
        self.assertTrue(self._is_valid("RegexTemplateViewSet", "list"))

    # ---------- 接入能力不在开放范围内 ----------
    def test_create_access_not_allowed(self):
        self.assertFalse(self._is_valid("ClusteringConfigViewSet", "create_access"))

    def test_regex_template_write_actions_not_allowed(self):
        for view_action in ["create", "partial_update", "destroy"]:
            with self.subTest(view_action=view_action):
                self.assertFalse(self._is_valid("RegexTemplateViewSet", view_action))

    # ---------- 其它授权项不得越界访问聚类配置 ----------
    def test_log_extract_cannot_update_clustering_config(self):
        self.assertFalse(self._is_valid("ClusteringConfigViewSet", "update_access", action_id=self.LOG_EXTRACT))
