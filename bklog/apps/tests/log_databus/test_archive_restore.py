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

from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.log_databus.constants import ArchiveInstanceType
from apps.log_databus.handlers import archive as archive_module
from apps.log_databus.models import ArchiveConfig, RestoreConfig
from apps.log_databus.views.restore_views import RestoreViewSet


@override_settings(TIME_ZONE="UTC")
class ArchiveRestoreTests(TestCase):
    def test_put_updates_all_restores_in_target_index_set(self):
        archive = ArchiveConfig.objects.create(
            bk_biz_id=2, instance_id=100, instance_type=ArchiveInstanceType.INDEX_SET.value
        )
        now = timezone.now().replace(microsecond=0)
        expired_time = now + timedelta(days=1)
        new_expired_time = now + timedelta(days=2)
        restores = [
            RestoreConfig.objects.create(
                bk_biz_id=2,
                archive_config_id=archive.pk,
                meta_restore_id=meta_restore_id,
                index_set_id=index_set_id,
                index_set_name=f"restore_{index_set_id}",
                start_time=now - timedelta(days=2),
                end_time=now - timedelta(days=1),
                expired_time=expired_time,
                notice_user="tester",
            )
            for meta_restore_id, index_set_id in [(11, 200), (12, 200), (13, 201)]
        ]
        path = f"/api/v1/databus/restore/{restores[0].pk}/"
        request = APIRequestFactory().put(path, {"expired_time": new_expired_time.isoformat()}, format="json")
        resolved = resolve(path)
        with (
            mock.patch.object(RestoreViewSet, "get_permissions", return_value=[]),
            mock.patch.object(archive_module.TransferApi, "modify_restore_result_table_snapshot") as modify_restore,
        ):
            response = resolved.func(request, **resolved.kwargs)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["result"])
        self.assertEqual(response.data["data"]["errors"], [])
        self.assertEqual(
            {item["restore_config_id"] for item in response.data["data"]["restore_config_info"]},
            {restore.pk for restore in restores[:2]},
        )
        for restore in restores:
            restore.refresh_from_db()
            self.assertEqual(restore.expired_time, new_expired_time if restore.index_set_id == 200 else expired_time)
        self.assertEqual(modify_restore.call_count, 2)
        modify_restore.assert_has_calls(
            [
                mock.call(
                    {"restore_id": meta_restore_id, "expired_time": new_expired_time.strftime("%Y-%m-%d %H:%M:%S.%f")}
                )
                for meta_restore_id in (11, 12)
            ],
            any_order=True,
        )
