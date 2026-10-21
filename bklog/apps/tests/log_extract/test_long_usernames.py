import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.log_commons.models import ExternalPermission
from apps.log_extract.models import ExtractLink, Tasks

BK_BIZ_ID = 215
USER = "admin"
BASE_URL = "/api/v1/log_extract/tasks"


class TestExternalTaskCreator(TestCase):
    def test_accepts_external_usernames_up_to_authorization_limit(self):
        creator_field = Tasks._meta.get_field("created_by")
        authorization_field = ExternalPermission._meta.get_field("authorized_user")
        for length in (33, authorization_field.max_length):
            username = "u" * (length - 4) + "@tai"
            with self.subTest(length=length):
                self.assertEqual(creator_field.clean(username, None), username)

    @override_settings(
        APP_CODE="bklog",
        IS_K8S_DEPLOY_MODE=False,
        MIDDLEWARE=("apps.tests.middlewares.OverrideMiddleware",),
    )
    @patch("apps.log_extract.handlers.tasks.user_operation_record.delay")
    @patch("apps.log_extract.handlers.tasks.TasksHandler.run_pipeline")
    @patch("apps.log_extract.handlers.tasks.ExplorerHandler.get_account", return_value="root")
    @patch("apps.log_extract.handlers.tasks.ExplorerHandler.get_strategies")
    @patch("apps.log_extract.handlers.tasks.get_request_external_username")
    def test_long_external_username_is_preserved_and_owns_its_tasks(self, external_username, get_strategies, *mocks):
        username = "u" * 29 + "@tai"
        external_username.return_value = username
        ip_list = [{"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_host_id": 101}]
        get_strategies.return_value = {"ip_list": ip_list, "allowed_dir_file_list": [], "operator": USER}
        ExtractLink.objects.create(name="test", link_type="common", operator=USER, op_bk_biz_id=BK_BIZ_ID)
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
        response = self.client.post(BASE_URL + "/", data=json.dumps(params), content_type="application/json")
        content = response.json()
        self.assertTrue(content["result"], content)
        task_id = content["data"]["task_id"]
        task = Tasks.objects.get(task_id=task_id)
        self.assertEqual(task.created_by, username)
        task.pk = None
        task.created_by = username[:32]
        task.save()

        response = self.client.get(BASE_URL + "/", {"bk_biz_id": BK_BIZ_ID, "page": 1, "pagesize": 20})
        content = response.json()
        self.assertTrue(content["result"], content)
        self.assertEqual([item["task_id"] for item in content["data"]["list"]], [task_id])
        self.assertEqual([item["created_by"] for item in content["data"]["list"]], [username])
