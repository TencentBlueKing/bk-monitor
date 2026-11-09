from types import SimpleNamespace
from unittest import mock

from django.template.loader import get_template
from django.test import SimpleTestCase, override_settings

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


@override_settings(BK_INCIDENT_SAAS_HOST="https://analysis.example/o/bk_incident/")
class TestIncidentNoticeNoiseConfigUrl(SimpleTestCase):
    def test_noise_link_uses_scope_without_analysis_task(self):
        for scope_id in ("bkcc_555", "bkci_project-1", "bksaas_app-1"):
            with self.subTest(scope_id=scope_id):
                incident = SimpleNamespace(bk_biz_id=-42, extra_info={"notice_source": "bkfara", "scope_id": scope_id})
                self.assertEqual(
                    IncidentNoticeHelper._get_noise_config_url(incident),
                    f"https://analysis.example/o/bk_incident/{scope_id}/space/setting/noise",
                )

    def test_noise_link_encodes_scope_and_supports_attr_dict(self):
        incident = SimpleNamespace(
            extra_info=_AttrDictLike({"notice_source": "bkfara", "scope_id": "bkci_project/a ?#"})
        )
        self.assertEqual(
            IncidentNoticeHelper._get_noise_config_url(incident),
            "https://analysis.example/o/bk_incident/bkci_project%2Fa%20%3F%23/space/setting/noise",
        )

    def test_noise_link_is_hidden_without_bkfara_source_or_scope(self):
        for extra_info in (None, {}, {"notice_source": "bkfara"}, {"scope_id": "bkcc_555"}):
            with self.subTest(extra_info=extra_info):
                self.assertEqual(IncidentNoticeHelper._get_noise_config_url(SimpleNamespace(extra_info=extra_info)), "")

    @override_settings(BK_INCIDENT_SAAS_HOST="")
    def test_noise_link_is_hidden_without_site_url(self):
        incident = SimpleNamespace(extra_info={"notice_source": "bkfara", "scope_id": "bkcc_555"})
        self.assertEqual(IncidentNoticeHelper._get_noise_config_url(incident), "")


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
        "noise_config_url": "https://analysis.example/bkcc_555/space/setting/noise",
    }

    def test_all_incident_templates_render_all_links(self):
        for template_name in (
            "notice/incident/markdown_content.jinja",
            "notice/incident/mail_content.jinja",
            "notice/incident/sms_content.jinja",
        ):
            content = get_template(template_name).render(self.context)
            self.assertIn("故障诊断详情", content)
            self.assertIn("分析过程", content)
            self.assertIn("降噪配置", content)
            self.assertIn(self.context["noise_config_url"], content)

    def test_all_incident_templates_hide_process_link_without_url(self):
        context = {**self.context, "process_url": ""}
        for template_name in (
            "notice/incident/markdown_content.jinja",
            "notice/incident/mail_content.jinja",
            "notice/incident/sms_content.jinja",
        ):
            content = get_template(template_name).render(context)
            self.assertIn("故障诊断详情", content)
            self.assertNotIn("分析过程", content)
            self.assertIn("降噪配置", content)

    def test_all_incident_templates_hide_noise_link_for_legacy_context(self):
        for missing_value in (None, ""):
            context = {**self.context, "noise_config_url": missing_value}
            if missing_value is None:
                context.pop("noise_config_url")
            for template_name in (
                "notice/incident/markdown_content.jinja",
                "notice/incident/mail_content.jinja",
                "notice/incident/sms_content.jinja",
            ):
                with self.subTest(missing_value=missing_value, template_name=template_name):
                    content = get_template(template_name).render(context)
                    self.assertNotIn("降噪配置", content)
                    self.assertIn("分析过程", content)
