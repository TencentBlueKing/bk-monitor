import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.iam import ActionEnum, ResourceEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.log_databus.constants import ArchiveInstanceType
from apps.log_databus.models import ArchiveConfig, CollectorConfig, RestoreConfig
from apps.log_search.models import LogIndexSet


@override_settings(
    IGNORE_IAM_PERMISSION=False,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class ArchivePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.archives = []
        cls.restores = []
        for collector_id in (101, 202):
            CollectorConfig.objects.create(
                collector_config_id=collector_id,
                bk_biz_id=2,
                collector_config_name=f"collector_{collector_id}",
                collector_config_name_en=f"collector_{collector_id}",
                collector_scenario_id="row",
                category_id="os",
            )
            cls.archives.append(
                ArchiveConfig.objects.create(
                    instance_id=collector_id,
                    instance_type=ArchiveInstanceType.COLLECTOR_CONFIG.value,
                    bk_biz_id=2,
                )
            )
        LogIndexSet.objects.create(index_set_id=202, index_set_name="source", space_uid="bkcc__2", scenario_id="es")
        cls.index_archive = ArchiveConfig.objects.create(
            instance_id=202, instance_type=ArchiveInstanceType.INDEX_SET.value, bk_biz_id=2
        )
        for archive in [*cls.archives, cls.index_archive]:
            cls.restores.append(
                RestoreConfig.objects.create(
                    archive_config_id=archive.pk,
                    bk_biz_id=2,
                    start_time=timezone.now(),
                    end_time=timezone.now(),
                    expired_time=timezone.now(),
                    index_set_name="restored",
                    notice_user="[]",
                )
            )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.grant = None
        patcher = mock.patch("apps.iam.handlers.drf.Permission")
        self.permission = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.permission.is_allowed.side_effect = self.check_permission

    def check_permission(self, action, resources, raise_exception):
        self.assertTrue(raise_exception)
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        if (action.id, resource.type, resource.id) != self.grant:
            raise PermissionDeniedError(action_name=action.name, permission={"actions": []})
        return True

    def request(self, method, path, data):
        request = getattr(self.factory, method)(path, data, format="json")
        route = resolve(path)
        response = route.func(request, **route.kwargs)
        return response.data if hasattr(response, "data") else json.loads(response.content)

    def test_archive_details_use_path_permission(self):
        path = f"/api/v1/databus/archive/{self.archives[1].pk}/"
        data = {"archive_config_id": self.archives[0].pk, "snapshot_days": 30, "page": 1, "pagesize": 10}
        for method, handler_method in (("get", "retrieve"), ("put", "create_or_update"), ("delete", "delete")):
            for granted_id in (101, 202):
                with self.subTest(method=method, granted_id=granted_id):
                    self.grant = (ActionEnum.MANAGE_COLLECTION.id, ResourceEnum.COLLECTION.id, str(granted_id))
                    with mock.patch("apps.log_databus.views.archive_views.ArchiveHandler") as handler:
                        getattr(handler.return_value, handler_method).return_value = None
                        response = self.request(method, path, data)
                        if granted_id == 101:
                            self.assertFalse(response["result"])
                            self.assertEqual(response["code"], "9900403")
                            handler.assert_not_called()
                        else:
                            self.assertTrue(response["result"])
                            handler.assert_called_once_with(str(self.archives[1].pk))
                            getattr(handler.return_value, handler_method).assert_called_once()

    def test_restore_details_use_path_permission(self):
        path = f"/api/v1/databus/restore/{self.restores[1].pk}/"
        data = {"restore_config_id": self.restores[0].pk, "expired_time": "2030-01-01 00:00:00"}
        for method, handler_method in (("put", "update_restore"), ("delete", "delete_restore")):
            for granted_id in (101, 202):
                with self.subTest(method=method, granted_id=granted_id):
                    self.grant = (ActionEnum.MANAGE_COLLECTION.id, ResourceEnum.COLLECTION.id, str(granted_id))
                    with mock.patch("apps.log_databus.views.restore_views.ArchiveHandler") as handler:
                        getattr(handler, handler_method).return_value = None
                        response = self.request(method, path, data)
                        if granted_id == 101:
                            self.assertFalse(response["result"])
                            self.assertEqual(response["code"], "9900403")
                            self.assertEqual(handler.mock_calls, [])
                        else:
                            self.assertTrue(response["result"])
                            called_handler = getattr(handler, handler_method)
                            called_handler.assert_called_once()
                            self.assertEqual(called_handler.call_args.args[0], str(self.restores[1].pk))

    def test_index_set_restore_rejects_same_id_collection_permission(self):
        path = f"/api/v1/databus/restore/{self.restores[2].pk}/"
        for method, handler_method in (("put", "update_restore"), ("delete", "delete_restore")):
            for action, resource in (
                (ActionEnum.MANAGE_COLLECTION, ResourceEnum.COLLECTION),
                (ActionEnum.MANAGE_INDICES, ResourceEnum.INDICES),
            ):
                with self.subTest(method=method, action=action.id):
                    self.grant = (action.id, resource.id, "202")
                    with mock.patch("apps.log_databus.views.restore_views.ArchiveHandler") as handler:
                        getattr(handler, handler_method).return_value = None
                        response = self.request(method, path, {"expired_time": "2030-01-01 00:00:00"})
                        if resource == ResourceEnum.COLLECTION:
                            self.assertFalse(response["result"])
                            self.assertEqual(response["code"], "9900403")
                            self.assertEqual(handler.mock_calls, [])
                        else:
                            self.assertTrue(response["result"])
                            getattr(handler, handler_method).assert_called_once()
