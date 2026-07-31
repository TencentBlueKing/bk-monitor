from types import SimpleNamespace
from unittest import mock

from django.template.loader import get_template
from django.test import SimpleTestCase

from bkmonitor.aiops.incident.notice import IncidentNoticeHelper


class _AttrDictLike:
    def __init__(self, data):
        self.data = data

    def __bool__(self):
        return bool(self.data)

    def to_dict(self):
        return self.data


class TestIncidentNoticeProcessUrlTemplate(SimpleTestCase):
    def test_get_process_url_formats_bkfara_process_fields(self):
        incident = SimpleNamespace(
            incident_id=114490,
            extra_info={"notice_source": "bkfara", "scope_id": "bkcc_555", "task_id": "task 123"},
        )

        with mock.patch(
            "bkmonitor.aiops.incident.notice.settings.BK_INCIDENT_SAAS_HOST",
            "https://analysis.example/",
        ):
            url = IncidentNoticeHelper._get_process_url(incident)

        self.assertEqual(
            url,
            "https://analysis.example/bkcc_555/record/fault/114490?incident_task_id=task+123",
        )

    def test_get_process_url_returns_empty_when_bkfara_process_fields_are_missing(self):
        incident = SimpleNamespace(incident_id=114490, extra_info={"notice_source": "bkfara", "scope_id": "bkcc_555"})

        self.assertEqual(IncidentNoticeHelper._get_process_url(incident), "")

    def test_get_process_url_returns_empty_for_non_bkfara_incident(self):
        incident = SimpleNamespace(incident_id=114490, extra_info={"scope_id": "bkcc_555", "task_id": 123})

        self.assertEqual(IncidentNoticeHelper._get_process_url(incident), "")

    def test_get_process_url_supports_elasticsearch_attr_dict(self):
        incident = SimpleNamespace(
            incident_id=114490,
            extra_info=_AttrDictLike({"notice_source": "bkfara", "scope_id": "bkcc_555", "task_id": 123}),
        )

        with mock.patch(
            "bkmonitor.aiops.incident.notice.settings.BK_INCIDENT_SAAS_HOST",
            "https://analysis.example/",
        ):
            self.assertEqual(
                IncidentNoticeHelper._get_process_url(incident),
                "https://analysis.example/bkcc_555/record/fault/114490?incident_task_id=123",
            )


class TestIncidentNoticeTemplates(SimpleTestCase):
    context = {
        "title": "故障生成",
        "incident_id": 114490,
        "incident_name": "网关组件异常",
        "level": "致命",
        "incident_reason": "状态异常",
        "business_name": "[555]火影忍者手游",
        "status": "未恢复",
        "duration": "14小时",
        "number": "共1条告警",
        "assignees": "未分配",
        "notify_time": "2026-07-14 15:58:09",
        "url": "https://monitor.example/result/114490",
        "process_url": "https://analysis.example/process/114490",
    }

    def test_all_incident_templates_render_both_link_labels(self):
        for template_name in (
            "notice/incident/markdown_content.jinja",
            "notice/incident/mail_content.jinja",
            "notice/incident/sms_content.jinja",
        ):
            content = get_template(template_name).render(self.context)
            self.assertIn("查看结果", content)
            self.assertIn("分析过程", content)

    def test_all_incident_templates_hide_process_link_without_url(self):
        context = {**self.context, "process_url": ""}
        for template_name in (
            "notice/incident/markdown_content.jinja",
            "notice/incident/mail_content.jinja",
            "notice/incident/sms_content.jinja",
        ):
            content = get_template(template_name).render(context)
            self.assertIn("查看结果", content)
            self.assertNotIn("分析过程", content)
