"""Tests for the Celery-based BKRepo log extraction flow."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.log_extract import constants
from apps.log_extract.models import ExtractLink, Tasks
from apps.log_extract.tasks.extract import LogExtractUtils


class TestBKRepoTransitServerAccount(TestCase):
    def setUp(self):
        self.link = ExtractLink.objects.create(
            name="bkrepo",
            link_type=constants.ExtractLinkType.BK_REPO.value,
            operator="admin",
            op_bk_biz_id=1,
        )
        self.task = Tasks.objects.create(
            bk_biz_id=1,
            ip_list=["1:127.0.0.1:100"],
            file_path=[r"c:\logs\app.log"],
            expiration_date=timezone.now(),
            link_id=self.link.link_id,
        )
        self.extract = LogExtractUtils(
            task_id=self.task.task_id,
            operator="admin",
            bk_biz_id=1,
            ip_list=[{"ip": "127.0.0.1", "bk_cloud_id": 1, "bk_host_id": 100}],
            file_path=[r"c:\logs\app.log"],
            filter_type="",
            filter_content={},
            account="system",
            os_type=constants.WINDOWS,
            username="admin",
        )
        self.extract.distribution_source_file_list = [
            {
                "account": {"alias": "system"},
                "server": {"ip_list": self.extract.ip_list},
                "file_list": [r"c:\tmp\bk_log_extract\packed.tgz"],
            }
        ]
        self.transit_server = SimpleNamespace(
            ip="127.0.0.2",
            bk_cloud_id=0,
            bk_host_id=200,
            target_dir="/data/bklog",
        )

    @patch("apps.log_extract.tasks.extract.FileServer.file_distribution")
    @patch.object(LogExtractUtils, "_get_transit_server")
    def test_distribution_separates_source_and_transit_accounts(self, get_transit_server, file_distribution):
        get_transit_server.return_value = (
            [self.transit_server],
            "/data/bk_log_extract/distribution_packing/",
            "/data/bklog/bk_log_extract/distribution/task/",
        )
        file_distribution.return_value = {"job_instance_id": 123}

        self.extract._distribution()

        self.assertEqual(file_distribution.call_args.kwargs["account"], constants.ACCOUNT["linux"])
        self.assertEqual(
            file_distribution.call_args.kwargs["file_source_list"][0]["account"]["alias"],
            "system",
        )

    @patch("apps.log_extract.tasks.extract.FileServer.execute_script")
    @patch("apps.log_extract.tasks.extract.FileServer.get_script_info")
    def test_cos_pack_runs_on_transit_server_with_linux_account(self, get_script_info, execute_script):
        self.extract.distribution_ip = [self.transit_server]
        self.extract.transit_server_file_path = ["/data/bklog/bk_log_extract/distribution/task/"]
        get_script_info.return_value = {"content": "script", "script_params": "params"}
        execute_script.return_value = {"job_instance_id": 456}

        self.extract._cos_upload()

        self.assertEqual(execute_script.call_args.kwargs["account"], constants.ACCOUNT["linux"])
        self.assertEqual(self.extract.account, "system")
