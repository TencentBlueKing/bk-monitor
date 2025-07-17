import base64

import pytest
from django.conf import settings
from django.utils.translation import gettext as _

from api.cmdb.define import Business
from bkmonitor.models import ReportContents
from bkmonitor.utils.send import Sender

pytestmark = pytest.mark.django_db

from alarm_backends.service.report.handler import ReportHandler, ReportItems
from alarm_backends.service.report.tasks import render_mails


@pytest.fixture()
def report_item():
    ReportItems.objects.all().delete()
    yield ReportItems.objects.create(
        id=3,
        mail_title="test subscribe",
        receivers=[{"id": "admin", "is_enabled": True, "type": "user"}],
        channels=[
            {"is_enabled": True, "channel_name": "email", "subscribers": [{"username": "xxxx@qq.com"}]},
            {
                "is_enabled": True,
                "channel_name": "wxbot",
                "subscribers": [{"username": "wrkSFfCgAASswixRCdUgClgmAQ6LyMnw"}],
            },
        ],
        is_link_enabled=True,
        managers=["admin"],
        frequency={"type": 4, "run_time": "14:40:38", "day_list": [1], "week_list": []},
    )


@pytest.fixture()
def report_content():
    ReportContents.objects.all().delete()
    yield [
        {
            "id": 8,
            "report_item": 3,
            "content_title": "123cesdfs",
            "content_details": "",
            "row_pictures_num": 2,
            "graphs": ["2-bLlNuRLWz-8"],
        }
    ]


@pytest.fixture()
def report_handler():
    yield ReportHandler(item_id=-1)


@pytest.fixture()
def biz_mock(mocker):
    return mocker.patch(
        "bkmonitor.iam.permission.Permission.filter_space_list_by_action", return_value=[dict(bk_biz_id=2)]
    )


@pytest.fixture()
def generate_graph_mock(mocker):
    graph_filename_maps = {"2-bLlNuRLWz-8": {"base64": base64.b64encode(b"test123"), "url": "xxx"}}
    return mocker.patch(
        "alarm_backends.service.report.handler.screenshot_by_uid_panel_id", return_value=(graph_filename_maps, "")
    )


@pytest.fixture()
def panel_titles(mocker):
    return mocker.patch(
        "alarm_backends.service.report.handler.fetch_panel_title_ids",
        return_value=[{"id": 8, "title": "test_pannel_title"}],
    )


@pytest.fixture()
def wxwork_send(mocker):
    return mocker.patch("bkmonitor.utils.send.Sender.send_wxwork_image", return_value=[{"errcode": 0}])


@pytest.fixture()
def render_mails_mock(mocker):
    return mocker.patch("alarm_backends.service.report.tasks.render_mails.apply_async", return_value="sdfdsfds")


@pytest.fixture()
def fetch_receivers_mock(mocker):
    return mocker.patch("alarm_backends.service.report.handler.ReportHandler.fetch_receivers", return_value=["admin"])


class TestSubscribeReport:
    def test_user_mail(self, report_item, report_content, report_handler, biz_mock, generate_graph_mock, panel_titles):
        render_mails(report_handler, report_item, report_content, ["admin"], True)
        assert generate_graph_mock.call_count == 1

    def test_external_mail(
        self, report_item, report_content, report_handler, biz_mock, generate_graph_mock, panel_titles
    ):
        render_mails(report_handler, report_item, report_content, ["admin"], True, channel_name="email")
        assert generate_graph_mock.call_count == 1

    def test_wxbot(
        self, report_item, report_content, report_handler, biz_mock, generate_graph_mock, panel_titles, wxwork_send
    ):
        settings.WXWORK_BOT_WEBHOOK_URL = "xxxxx"
        render_mails(report_handler, report_item, report_content, ["xxxxxxxxxxxx"], True, channel_name="wxbot")
        settings.WXWORK_BOT_WEBHOOK_URL = ""
        assert generate_graph_mock.call_count == 1
        assert wxwork_send.call_count == 1

    def test_render_external(self, report_item, report_content, generate_graph_mock, panel_titles, report_handler):
        render_args, err_msg = report_handler.render_images_to_html(
            report_item.bk_tenant_id,
            report_item.mail_title,
            report_content,
            [Business(bk_biz_id=2)],
            ["xxxx@qq.com"],
            report_item.frequency,
            True,
            is_link_enabled=False,
            channel_name=ReportItems.Channel.EMAIL,
        )

        assert render_args["is_external"]
        assert render_args["redirect_url"] == ""
        content_template_path = "report/report_full.jinja"
        sender = Sender(
            title_template_path="report/report_title.jinja",
            content_template_path=content_template_path,
            context=render_args,
        )
        assert _("请遵守公司规范，切勿泄露敏感信息，后果自负") in sender.content

        content_template_path = "report/report_content.jinja"
        sender = Sender(
            title_template_path="report/report_title.jinja",
            content_template_path=content_template_path,
            context=render_args,
        )
        assert _("请遵守公司规范，切勿泄露敏感信息，后果自负") in sender.content

    def test_render_wxbot(self, report_item, report_content, generate_graph_mock, panel_titles, report_handler):
        render_args, _ = report_handler.render_images_to_html(
            report_item.bk_tenant_id,
            report_item.mail_title,
            report_content,
            [Business(bk_biz_id=2)],
            ["sdfdsfdsfdsfdsf"],
            report_item.frequency,
            True,
            is_link_enabled=report_item.is_link_enabled,
            channel_name=ReportItems.Channel.WXBOT,
        )

        assert render_args["is_external"] is False
        assert render_args["contents"][0]["origin_graphs"][0]["title"] == "test_pannel_title"
        settings.WXWORK_BOT_WEBHOOK_URL = ""

    def test_process_and_render_mails(
        self, report_item, report_content, report_handler, render_mails_mock, fetch_receivers_mock
    ):
        contents = [ReportContents(**c) for c in report_content]
        ReportContents.objects.bulk_create(contents)
        report_handler.item_id = 3
        report_handler.process_and_render_mails()
        assert render_mails_mock.call_count == 3
