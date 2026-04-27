from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

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
