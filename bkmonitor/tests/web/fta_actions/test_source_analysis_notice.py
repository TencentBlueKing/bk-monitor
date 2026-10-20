"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bkoauth.exceptions import TokenNotExist
from django.conf import settings
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone, translation

from bkmonitor.models import IssueSourceAnalysisExecution
from bkmonitor.utils.user import set_local_username
from constants.action import NoticeWay
from constants.issue import (
    SourceAnalysisFailureMessage,
    SourceAnalysisFailureStage,
    SourceAnalysisResultType,
    SourceAnalysisStatus,
)
from fta_web.issue.resources import SourceAnalysisExecutionBaseResource
from fta_web.issue.source_analysis_notice import send_source_analysis_notice
from fta_web.tasks import run_source_analysis_execution


@override_settings(
    BK_MONITOR_HOST="https://monitor.example.com/monitor/",
    TIME_ZONE="Asia/Shanghai",
    LANGUAGE_CODE="zh-hans",
    MD_SUPPORTED_NOTICE_WAYS=["wxwork-bot"],
    NOTICE_MESSAGE_MAX_LENGTH={},
)
class TestSourceAnalysisNotice(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        set_local_username("clicker")
        self.addCleanup(set_local_username, None)
        self.enterContext(translation.override("zh-hans"))
        self.issue_lookup = self.enterContext(
            patch("fta_web.issue.source_analysis_notice.IssueDocument.get_issue_or_raise")
        )
        self.issue_lookup.return_value = SimpleNamespace(name="异常登录日志告警")
        self.tenant = self.enterContext(
            patch("fta_web.issue.source_analysis_notice.bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
        )
        self.send = self.enterContext(patch("fta_web.issue.source_analysis_notice.api.cmsi.send_msg"))
        self.send.return_value = {"username_check": {"invalid": []}, "message": "OK"}

    @staticmethod
    def build_result(result_type=SourceAnalysisResultType.HIGH_CONFIDENCE):
        return {
            "schema_version": "1.0.0",
            "result_type": result_type,
            "result_card": {
                "description": "validateToken 缺少空值校验。",
                "responsibility": (
                    {
                        "commit_id": "a3fa531",
                        "commit_message": "restore guard",
                        "author_name": "Edwin Wu",
                        "bk_username": "edwinwu",
                    }
                    if result_type == SourceAnalysisResultType.HIGH_CONFIDENCE
                    else None
                ),
            },
            "content_type": "text/markdown",
            "content": "# 完整报告不应出现在通知中",
        }

    def create_execution(self, **overrides):
        fields = {
            "bk_biz_id": 2,
            "issue_id": "issue-1",
            "alert_id": "alert-1",
            "bkci_project_id": "project-a",
            "repository_alias": "repo-a",
            "agent_id": "agent-a",
            "run_as_user": "configurator",
        }
        fields.update(overrides)
        return IssueSourceAnalysisExecution.objects.create(**fields)

    def successful_execution(self, result_type=SourceAnalysisResultType.HIGH_CONFIDENCE):
        execution = self.create_execution(
            status=SourceAnalysisStatus.SUCCESS,
            result_type=result_type,
            result_payload=self.build_result(result_type),
        )
        execution.create_time = datetime(2026, 10, 20, 7, 40, tzinfo=dt_timezone.utc)
        return execution

    def fail(self, execution):
        SourceAnalysisExecutionBaseResource._mark_failed(
            execution,
            failure_stage=SourceAnalysisFailureStage.TASK_EXECUTE,
            failure_code="DEVOPS_BUILD_FAILED",
            failure_message="流水线执行失败",
            failure_retryable=False,
        )

    def test_success_notice_matches_copy_and_notifies_clicker_in_correct_tenant(self):
        execution = self.successful_execution()
        send_source_analysis_notice(execution)

        params = self.send.call_args.kwargs
        self.assertEqual(params["title"], "✅【蓝鲸监控】源码分析完成｜异常登录日志告警")
        self.assertEqual(params["msg_type"], NoticeWay.QY_WEIXIN)
        self.assertEqual(params["receiver__username"], "clicker")
        self.assertEqual(params["bk_tenant_id"], "tenant-a")
        self.assertIn("你于 15:40 发起的源码关联分析已完成", params["content"])
        self.assertIn("分析结论：validateToken 缺少空值校验。", params["content"])
        self.assertIn("置信度：高", params["content"])
        self.assertIn("责任提交：a3fa531 · edwinwu", params["content"])
        self.assertNotIn("完整报告不应出现在通知中", params["content"])
        self.assertNotIn("%", params["content"].split("查看完整报告：")[0])
        self.issue_lookup.assert_called_once_with("issue-1", bk_biz_id=2)
        self.tenant.assert_called_once_with(2)
        url = params["content"].split("查看完整报告：", 1)[1].strip()
        parsed = urlsplit(url)
        self.assertEqual(parsed.path, "/monitor/")
        self.assertEqual(parse_qs(parsed.query), {"bizId": ["2"]})
        route, query = parsed.fragment.split("?", 1)
        self.assertEqual(route, "/trace/alarm-center")
        self.assertEqual(
            parse_qs(query),
            {"alarmType": ["issues"], "showDetail": ["true"], "detailId": ["issue-1"], "detailBizId": ["2"]},
        )

    def test_insufficient_evidence_is_success_without_responsibility(self):
        send_source_analysis_notice(self.successful_execution(SourceAnalysisResultType.INSUFFICIENT_EVIDENCE))
        params = self.send.call_args.kwargs
        self.assertTrue(params["title"].startswith("✅"))
        self.assertIn("置信度：证据不足", params["content"])
        self.assertNotIn("责任提交", params["content"])

    def test_failed_notice_contains_reason_and_not_success_fields(self):
        execution = self.create_execution(
            status=SourceAnalysisStatus.FAILED,
            failure_message=SourceAnalysisFailureMessage.RULE_AGENT_MISSING,
        )
        send_source_analysis_notice(execution)
        params = self.send.call_args.kwargs
        self.assertEqual(params["title"], "❌【蓝鲸监控】源码分析失败｜异常登录日志告警")
        self.assertIn("发起的源码关联分析失败", params["content"])
        self.assertIn(SourceAnalysisFailureMessage.RULE_AGENT_MISSING, params["content"])
        self.assertIn("查看详情并重新分析：https://monitor.example.com/monitor/", params["content"])
        self.assertNotIn("置信度", params["content"])

    @override_settings(LANGUAGE_CODE="en")
    def test_application_default_language_uses_english_templates(self):
        send_source_analysis_notice(self.successful_execution())
        params = self.send.call_args.kwargs
        self.assertIn("✅【BlueKing Monitor】Source analysis completed", params["title"])
        self.assertIn("The source analysis you started at 15:40 has completed.", params["content"])
        self.assertIn("View full report:", params["content"])
        self.assertNotIn("你于", params["content"])

    def test_web_role_sends_success_and_failure_without_mocking_i18n(self):
        self.assertEqual(settings.ROLE, "web")
        self.assertFalse(hasattr(settings, "REDIS_CELERY_CONF"))
        # 真实模板、翻译和 CMSI 调用链；仅隔离 Issue 查询、租户解析及消息外部调用。
        send_source_analysis_notice(self.successful_execution())
        failed = self.create_execution(status=SourceAnalysisStatus.FAILED, failure_message="pipeline failed")
        send_source_analysis_notice(failed)
        self.assertEqual(self.send.call_count, 2)
        self.assertTrue(self.send.call_args_list[0].kwargs["title"].startswith("✅"))
        self.assertTrue(self.send.call_args_list[1].kwargs["title"].startswith("❌"))

    @override_settings(LANGUAGE_CODE="en")
    def test_rendering_restores_callers_language_and_timezone(self):
        with translation.override("zh-hans"), timezone.override("Europe/Paris"):
            original_language = translation.get_language()
            original_timezone = timezone.get_current_timezone_name()
            send_source_analysis_notice(self.successful_execution())
            self.assertEqual(translation.get_language(), original_language)
            self.assertEqual(timezone.get_current_timezone_name(), original_timezone)
        self.assertIn("Source analysis completed", self.send.call_args.kwargs["title"])

    @override_settings(LANGUAGE_CODE="en")
    def test_rendering_failure_restores_language_and_does_not_send(self):
        with (
            translation.override("zh-hans"),
            patch(
                "fta_web.issue.source_analysis_notice.AlarmNoticeTemplate.render", side_effect=RuntimeError("failed")
            ),
            self.assertLogs("fta_web.issue.source_analysis_notice", level="WARNING"),
        ):
            send_source_analysis_notice(self.successful_execution())
            self.assertEqual(translation.get_language(), "zh-hans")
        self.send.assert_not_called()

    def test_missing_receiver_and_active_state_do_not_send(self):
        execution = self.successful_execution()
        execution.create_user = ""
        send_source_analysis_notice(execution)
        execution.create_user = "clicker"
        execution.status = SourceAnalysisStatus.RUNNING
        send_source_analysis_notice(execution)
        self.send.assert_not_called()
        self.issue_lookup.assert_not_called()

    def test_issue_lookup_failure_falls_back_to_issue_id(self):
        self.issue_lookup.side_effect = RuntimeError("ES unavailable")
        send_source_analysis_notice(self.successful_execution())
        self.assertTrue(self.send.call_args.kwargs["title"].endswith("｜issue-1"))

    def test_long_multiline_summary_is_bounded_and_keeps_report_link(self):
        execution = self.successful_execution()
        execution.result_payload["result_card"]["description"] = "摘要\n" * 4000
        send_source_analysis_notice(execution)
        content = self.send.call_args.kwargs["content"]
        self.assertLess(len(content.encode("utf-8")), 1800)
        self.assertIn("查看完整报告：https://monitor.example.com/monitor/", content)
        self.assertNotIn("摘要\n摘要", content)

    def test_dynamic_text_is_not_evaluated_as_template_and_control_characters_are_removed(self):
        execution = self.successful_execution()
        self.issue_lookup.return_value.name = "告警\r\n额外标题\t{{ 7 * 7 }}"
        execution.result_payload["result_card"]["description"] = "原文 {{ 7 * 7 }}\r\n第二行\t末尾"
        send_source_analysis_notice(execution)
        params = self.send.call_args.kwargs
        self.assertEqual(params["title"], "✅【蓝鲸监控】源码分析完成｜告警 额外标题 {{ 7 * 7 }}")
        self.assertIn("分析结论：原文 {{ 7 * 7 }} 第二行 末尾", params["content"])

    def test_issue_id_is_encoded_as_a_single_query_parameter(self):
        execution = self.successful_execution()
        execution.issue_id = "issue&showDetail=false#other"
        send_source_analysis_notice(execution)
        url = self.send.call_args.kwargs["content"].split("查看完整报告：", 1)[1].strip()
        query = parse_qs(urlsplit(url).fragment.split("?", 1)[1])
        self.assertEqual(query["detailId"], [execution.issue_id])
        self.assertEqual(query["showDetail"], ["true"])

    def test_sender_exception_does_not_escape_or_change_terminal_state(self):
        execution = self.successful_execution()
        self.send.side_effect = RuntimeError("sensitive response")
        with self.assertLogs("fta_web.issue.source_analysis_notice", level="WARNING") as logs:
            send_source_analysis_notice(execution)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)
        self.assertNotIn("sensitive response", " ".join(logs.output))
        self.send.assert_called_once()

    def test_sender_failure_response_is_logged(self):
        self.send.return_value = {"username_check": {"invalid": ["clicker"]}, "message": "failed"}
        with self.assertLogs("fta_web.issue.source_analysis_notice", level="WARNING") as logs:
            send_source_analysis_notice(self.successful_execution())
        self.assertIn("notification was not sent", " ".join(logs.output))

    def test_cmsi_message_detail_failure_is_not_treated_as_success(self):
        self.send.return_value = {"username_check": {"invalid": []}, "message_detail": {"clicker": "failed"}}
        with self.assertLogs("fta_web.issue.source_analysis_notice", level="WARNING") as logs:
            send_source_analysis_notice(self.successful_execution())
        self.assertIn("notification was not sent", " ".join(logs.output))

    def test_missing_cmsi_delivery_status_is_not_treated_as_success(self):
        self.send.return_value = {}
        with self.assertLogs("fta_web.issue.source_analysis_notice", level="WARNING") as logs:
            send_source_analysis_notice(self.successful_execution())
        self.assertIn("notification was not sent", " ".join(logs.output))

    def test_success_transition_schedules_exactly_one_notification_after_commit(self):
        execution = self.create_execution(status=SourceAnalysisStatus.RUNNING)
        stale = IssueSourceAnalysisExecution.objects.get(pk=execution.pk)
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with self.captureOnCommitCallbacks(using=alias, execute=True) as callbacks:
            SourceAnalysisExecutionBaseResource._validate_and_persist_result(execution, self.build_result())
            SourceAnalysisExecutionBaseResource._validate_and_persist_result(stale, self.build_result())
            self.send.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.send.assert_called_once()
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.SUCCESS)

    def test_failed_transition_schedules_exactly_one_notification_for_stale_workers(self):
        execution = self.create_execution()
        stale = IssueSourceAnalysisExecution.objects.get(pk=execution.pk)
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with self.captureOnCommitCallbacks(using=alias, execute=True) as callbacks:
            self.fail(execution)
            self.fail(stale)
            self.send.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.send.assert_called_once()

    def test_transaction_rollback_does_not_notify(self):
        execution = self.create_execution()
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with self.captureOnCommitCallbacks(using=alias, execute=True) as callbacks:
            with self.assertRaisesMessage(RuntimeError, "rollback"), transaction.atomic(using=alias):
                self.fail(execution)
                raise RuntimeError("rollback")
        self.assertEqual(callbacks, [])
        self.send.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.PENDING)

    def test_credential_failure_during_web_dispatch_also_notifies_clicker(self):
        execution = self.create_execution()
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with (
            patch("fta_web.issue.resources.oauth_client.get_access_token_by_user", side_effect=TokenNotExist()),
            patch("fta_web.issue.resources.run_source_analysis_execution.apply_async") as dispatch,
            self.captureOnCommitCallbacks(using=alias, execute=True),
        ):
            SourceAnalysisExecutionBaseResource.dispatch_execution(execution)
        self.send.assert_called_once()
        dispatch.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.failure_code, "USER_ACCESS_TOKEN_UNAVAILABLE")

    def test_missing_agent_during_inline_trigger_also_notifies(self):
        execution = self.create_execution(agent_id="")
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with self.captureOnCommitCallbacks(using=alias, execute=True):
            SourceAnalysisExecutionBaseResource._trigger_bkfara_task(execution)
        self.send.assert_called_once()
        execution.refresh_from_db()
        self.assertEqual(execution.failure_code, "SOURCE_ANALYSIS_AGENT_MISSING")

    def test_celery_sender_exception_does_not_reschedule_analysis(self):
        execution = self.create_execution(bkfara_task_id="task-1", status=SourceAnalysisStatus.RUNNING)
        self.send.side_effect = RuntimeError("CMSI unavailable")
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with (
            patch("fta_web.issue.resources.api.bk_incident.get_source_analysis_task") as get_task,
            patch("fta_web.tasks.run_source_analysis_execution.apply_async") as dispatch,
            self.captureOnCommitCallbacks(using=alias, execute=True),
        ):
            get_task.return_value = {
                "status": "failed",
                "terminal": True,
                "error": {"code": "DEVOPS_BUILD_FAILED", "message": "pipeline failed", "retryable": False},
            }
            run_source_analysis_execution(execution.analysis_id)
        execution.refresh_from_db()
        self.assertEqual(execution.status, SourceAnalysisStatus.FAILED)
        dispatch.assert_not_called()
        self.send.assert_called_once()

    def test_persistence_failure_does_not_schedule_notification(self):
        execution = self.create_execution()
        alias = SourceAnalysisExecutionBaseResource.db_alias()
        with self.captureOnCommitCallbacks(using=alias, execute=True) as callbacks:
            with (
                patch.object(execution, "mark_success", side_effect=DatabaseError("unavailable")),
                self.assertRaises(DatabaseError),
            ):
                SourceAnalysisExecutionBaseResource._validate_and_persist_result(execution, self.build_result())
        self.assertEqual(callbacks, [])
        self.send.assert_not_called()
