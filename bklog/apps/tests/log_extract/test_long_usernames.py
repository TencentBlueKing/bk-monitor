"""长外部用户名的提取任务创建和列表归属回归测试。"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.log_extract.models import ExtractLink, Tasks
from apps.tests.middlewares import OverrideMiddleware

BK_BIZ_ID = 1
BASE_URL = "/api/v1/log_extract/tasks/"


class ExternalUserMiddleware(OverrideMiddleware):
    def process_request(self, request):
        super().process_request(request)
        request.external_user = request.META.get("HTTP_X_TEST_EXTERNAL_USERNAME", "")


@override_settings(
    APP_CODE="test_app",
    IS_K8S_DEPLOY_MODE=False,
    MIDDLEWARE=("apps.tests.log_extract.test_long_usernames.ExternalUserMiddleware",),
)
class TestExternalTaskLongUsernames(TestCase):
    def setUp(self):
        request = SimpleNamespace(user=SimpleNamespace(username="admin"), external_user="", META={})
        patcher = patch("apps.utils.local._local.request", request, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("apps.log_extract.handlers.tasks.user_operation_record.delay")
    @patch("apps.log_extract.handlers.tasks.TasksHandler.run_pipeline")
    @patch("apps.log_extract.handlers.tasks.ExplorerHandler.get_account", return_value="root")
    @patch("apps.log_extract.handlers.tasks.ExplorerHandler.get_strategies")
    def test_long_external_username_is_preserved_and_owns_its_tasks(self, get_strategies, *mocks):
        ip_list = [{"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_host_id": 1}]
        get_strategies.return_value = {"ip_list": ip_list, "allowed_dir_file_list": [], "operator": "admin"}
        ExtractLink.objects.create(name="test", link_type="common", operator="admin", op_bk_biz_id=BK_BIZ_ID)
        params = {
            "bk_biz_id": BK_BIZ_ID,
            "ip_list": ip_list,
            "file_path": [],
            "filter_type": "",
            "remark": "",
            "filter_content": {},
            "preview_directory": "/data/logs/",
            "preview_ip_list": [],
            "preview_time_range": "all",
            "preview_is_search_child": False,
        }
        for length in (33, 64):
            username = "u" * length
            with self.subTest(length=length):
                headers = {"HTTP_X_TEST_EXTERNAL_USERNAME": username}
                response = self.client.post(
                    BASE_URL, data=json.dumps(params), content_type="application/json", **headers
                )
                content = response.json()
                self.assertTrue(content["result"], content)
                task_id = content["data"]["task_id"]
                task = Tasks.objects.get(task_id=task_id)
                self.assertEqual(task.created_by, username)
                self.assertEqual(task.updated_by, "admin")
                self.assertEqual(task._meta.get_field("created_by").clean(task.created_by, task), username)
                task.pk = None
                task.created_by = username[:32]
                task.save()

                response = self.client.get(BASE_URL, {"bk_biz_id": BK_BIZ_ID, "page": 1, "pagesize": 20}, **headers)
                content = response.json()
                self.assertTrue(content["result"], content)
                self.assertEqual([item["task_id"] for item in content["data"]["list"]], [task_id])
                self.assertEqual([item["created_by"] for item in content["data"]["list"]], [username])
