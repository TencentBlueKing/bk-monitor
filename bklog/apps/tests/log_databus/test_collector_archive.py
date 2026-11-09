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

import contextlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import resolve

from apps.iam import ActionEnum
from apps.iam.handlers.drf import InstanceActionPermission
from apps.log_databus.constants import ArchiveInstanceType
from apps.log_databus.exceptions import (
    ArchiveRepositoryChangeNotAllowed,
    ArchiveRepositoryNotInCluster,
    ArchiveResultTableNotReady,
    ArchiveStorageTypeNotSupported,
    CollectorActiveException,
    CollectorConfigNotExistException,
)
from apps.log_databus.handlers import archive as archive_module
from apps.log_databus.handlers.archive import ArchiveHandler
from apps.log_databus.models import ArchiveConfig, CollectorConfig
from apps.log_databus.serializers import CollectorArchivePutSerializer
from apps.log_databus.views.collector_views import CollectorViewSet

BK_BIZ_ID = 2
REPOSITORY_NAME = "2_bklog_demo"
OTHER_REPOSITORY_NAME = "2_bklog_other"
TABLE_ID = "2_test_collector"
ARCHIVE_PATH = "/api/v1/databus/collectors/1/archive/"


class CollectorArchiveHandlerTests(TestCase):
    def setUp(self):
        self.collector = CollectorConfig.objects.create(
            bk_biz_id=BK_BIZ_ID,
            collector_config_name="test_collector",
            collector_config_name_en="test_collector",
            collector_scenario_id="row",
            category_id="os",
            table_id=TABLE_ID,
        )
        self.collector_config_id = self.collector.collector_config_id

    @contextlib.contextmanager
    def patch_metadata(self, repositories=None, cluster_id=1):
        transfer_api = mock.MagicMock()
        transfer_api.get_result_table_storage.return_value = {TABLE_ID: {"cluster_config": {"cluster_id": cluster_id}}}
        storage_handler = mock.MagicMock()
        storage_handler.return_value.repository.return_value = [
            {"repository_name": name} for name in (repositories or [REPOSITORY_NAME])
        ]
        with (
            mock.patch.object(archive_module, "TransferApi", transfer_api),
            mock.patch.object(archive_module, "StorageHandler", storage_handler),
        ):
            yield transfer_api

    def assert_no_archive(self):
        self.assertFalse(
            ArchiveConfig.objects.filter(
                instance_id=self.collector_config_id,
                instance_type=ArchiveInstanceType.COLLECTOR_CONFIG.value,
            ).exists()
        )

    def test_upsert_creates_archive_when_absent(self):
        with self.patch_metadata() as transfer_api:
            result = ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)

        self.assertEqual(result["collector_config_id"], self.collector_config_id)
        self.assertEqual(result["bk_biz_id"], BK_BIZ_ID)
        self.assertEqual(result["target_snapshot_repository_name"], REPOSITORY_NAME)
        self.assertEqual(result["snapshot_days"], 30)
        self.assertEqual(ArchiveConfig.objects.filter(instance_id=self.collector_config_id).count(), 1)
        transfer_api.create_result_table_snapshot.assert_called_once_with(
            {
                "table_id": TABLE_ID,
                "target_snapshot_repository_name": REPOSITORY_NAME,
                "snapshot_days": 30,
            }
        )

    def test_repeat_upsert_keeps_single_archive(self):
        with self.patch_metadata() as transfer_api:
            ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)
            transfer_api.reset_mock()
            result = ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)

        self.assertEqual(ArchiveConfig.objects.filter(instance_id=self.collector_config_id).count(), 1)
        transfer_api.create_result_table_snapshot.assert_not_called()
        transfer_api.modify_result_table_snapshot.assert_not_called()
        self.assertEqual(result["snapshot_days"], 30)

    def test_upsert_updates_snapshot_days(self):
        with self.patch_metadata() as transfer_api:
            ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)
            transfer_api.reset_mock()
            result = ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 60)

        transfer_api.create_result_table_snapshot.assert_not_called()
        transfer_api.modify_result_table_snapshot.assert_called_once_with({"table_id": TABLE_ID, "snapshot_days": 60})
        self.assertEqual(result["snapshot_days"], 60)

    def test_upsert_updates_snapshot_days_records_operator(self):
        with self.patch_metadata():
            ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)
            with mock.patch("apps.models.get_request_username", return_value="tester"):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 60)

        archive = ArchiveConfig.objects.get(instance_id=self.collector_config_id)
        self.assertEqual(archive.snapshot_days, 60)
        self.assertEqual(archive.updated_by, "tester")

    def test_upsert_rejects_repository_change(self):
        with self.patch_metadata(repositories=[REPOSITORY_NAME, OTHER_REPOSITORY_NAME]):
            ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)
            with self.assertRaises(ArchiveRepositoryChangeNotAllowed):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id, OTHER_REPOSITORY_NAME, 30)

        archive = ArchiveConfig.objects.get(instance_id=self.collector_config_id)
        self.assertEqual(archive.target_snapshot_repository_name, REPOSITORY_NAME)

    def test_upsert_rejects_non_es_storage(self):
        CollectorConfig.objects.filter(collector_config_id=self.collector_config_id).update(
            storage_cluster_type="doris"
        )
        with self.patch_metadata():
            with self.assertRaises(ArchiveStorageTypeNotSupported):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)

        self.assert_no_archive()

    def test_upsert_rejects_repository_not_in_cluster(self):
        with self.patch_metadata(repositories=[OTHER_REPOSITORY_NAME]):
            with self.assertRaises(ArchiveRepositoryNotInCluster):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)

        self.assert_no_archive()

    def test_upsert_rejects_collector_without_table_id(self):
        CollectorConfig.objects.filter(collector_config_id=self.collector_config_id).update(table_id=None)
        with self.patch_metadata():
            with self.assertRaises(ArchiveResultTableNotReady):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)

        self.assert_no_archive()

    def test_upsert_rejects_missing_collector(self):
        with self.patch_metadata():
            with self.assertRaises(CollectorConfigNotExistException):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id + 1000, REPOSITORY_NAME, 30)

    def test_upsert_rejects_inactive_collector(self):
        CollectorConfig.objects.filter(collector_config_id=self.collector_config_id).update(is_active=False)
        with self.patch_metadata():
            with self.assertRaises(CollectorActiveException):
                ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)

        self.assert_no_archive()

    def test_get_collector_archive_returns_none_when_absent(self):
        self.assertIsNone(ArchiveHandler.get_collector_archive(self.collector_config_id))

    def test_get_collector_archive_returns_config(self):
        ArchiveConfig.objects.create(
            instance_id=self.collector_config_id,
            instance_type=ArchiveInstanceType.COLLECTOR_CONFIG.value,
            bk_biz_id=BK_BIZ_ID,
            snapshot_days=30,
            target_snapshot_repository_name=REPOSITORY_NAME,
        )

        result = ArchiveHandler.get_collector_archive(self.collector_config_id)

        self.assertEqual(result["collector_config_id"], self.collector_config_id)
        self.assertEqual(result["target_snapshot_repository_name"], REPOSITORY_NAME)
        self.assertEqual(result["snapshot_days"], 30)

    def test_delete_collector_archive_is_idempotent(self):
        with self.patch_metadata() as transfer_api:
            self.assertIsNone(ArchiveHandler.delete_collector_archive(self.collector_config_id))

        transfer_api.delete_result_table_snapshot.assert_not_called()
        self.assert_no_archive()

    def test_delete_collector_archive_closes_archive(self):
        with self.patch_metadata() as transfer_api:
            ArchiveHandler.upsert_collector_archive(self.collector_config_id, REPOSITORY_NAME, 30)
            transfer_api.reset_mock()
            self.assertIsNone(ArchiveHandler.delete_collector_archive(self.collector_config_id))

        transfer_api.delete_result_table_snapshot.assert_called_once_with({"table_id": TABLE_ID})
        self.assert_no_archive()


class CollectorArchiveViewTests(SimpleTestCase):
    def test_archive_route_maps_to_archive_action(self):
        resolved = resolve(ARCHIVE_PATH)

        self.assertEqual(resolved.func.actions, {"get": "archive", "put": "archive", "delete": "archive"})

    @mock.patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__not_whitelisted__"},
    )
    def test_archive_requires_manage_collection(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "archive"
        view.request = SimpleNamespace(query_params={}, data={})

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])

    @mock.patch("apps.log_databus.views.collector_views.ArchiveHandler.get_collector_archive", return_value=None)
    def test_archive_get_returns_null_when_absent(self, mock_get_archive):
        view = CollectorViewSet()
        view.request = SimpleNamespace(method="GET", query_params={}, data={})

        response = view.archive(SimpleNamespace(method="GET"), collector_config_id=7)

        mock_get_archive.assert_called_once_with(7)
        self.assertIsNone(response.data)

    @mock.patch(
        "apps.log_databus.views.collector_views.ArchiveHandler.upsert_collector_archive",
        return_value={"archive_config_id": 1},
    )
    def test_archive_put_passes_validated_params(self, mock_upsert):
        view = CollectorViewSet()
        view.request = SimpleNamespace(
            method="PUT",
            query_params={},
            data={"target_snapshot_repository_name": REPOSITORY_NAME, "snapshot_days": 30},
        )

        response = view.archive(SimpleNamespace(method="PUT"), collector_config_id=7)

        mock_upsert.assert_called_once_with(
            collector_config_id=7,
            target_snapshot_repository_name=REPOSITORY_NAME,
            snapshot_days=30,
        )
        self.assertEqual(response.data, {"archive_config_id": 1})

    @mock.patch("apps.log_databus.views.collector_views.ArchiveHandler.delete_collector_archive", return_value=None)
    def test_archive_delete_closes_archive(self, mock_delete):
        view = CollectorViewSet()
        view.request = SimpleNamespace(method="DELETE", query_params={}, data={})

        response = view.archive(SimpleNamespace(method="DELETE"), collector_config_id=7)

        mock_delete.assert_called_once_with(7)
        self.assertIsNone(response.data)


class CollectorArchiveSerializerTests(SimpleTestCase):
    def test_serializer_requires_all_fields(self):
        serializer = CollectorArchivePutSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"target_snapshot_repository_name", "snapshot_days"})

    def test_serializer_rejects_negative_snapshot_days(self):
        serializer = CollectorArchivePutSerializer(
            data={"target_snapshot_repository_name": REPOSITORY_NAME, "snapshot_days": -1}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("snapshot_days", serializer.errors)
