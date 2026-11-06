import json
from types import SimpleNamespace
from unittest.mock import Mock

from bkmonitor.utils.send import ChannelBkchatSender, Sender
from bkmonitor.utils.template import AlarmNoticeTemplate
from constants.action import NoticeChannel, NoticeWay
from core.errors.api import BKAPIError

LAYOUTS_TEMPLATE = "notice/abnormal/action/markdown_content.jinja"


def mock_wxwork_post(monkeypatch):
    response = Mock()
    response.json.return_value = {"errcode": 0, "errmsg": "ok"}
    post = Mock(return_value=response)
    monkeypatch.setattr("bkmonitor.utils.send.requests.post", post)
    return post


def test_send_wxwork_layouts_returns_error_when_webhook_url_empty(settings, monkeypatch):
    settings.WXWORK_BOT_WEBHOOK_URL = ""
    post = Mock()
    monkeypatch.setattr("bkmonitor.utils.send.requests.post", post)
    monkeypatch.setattr("bkmonitor.utils.send._", lambda message: message)

    result = Sender.send_wxwork_layouts("markdown", "[]", ["chat-id"])

    assert result["errcode"] == -1
    assert result["errmsg"] == ["未配置蓝鲸监控群机器人回调地址，请联系管理员"]
    post.assert_not_called()


def test_is_wxwork_layouts_enabled_skips_bkchat_channel(settings, monkeypatch):
    settings.WECOM_LAYOUTS_BIZ_LIST = [100380]
    monkeypatch.setattr("bkmonitor.utils.send.get_template", lambda path: object())

    assert (
        Sender.is_wxwork_layouts_enabled(
            100380,
            NoticeWay.WX_BOT,
            {"notice_channel": NoticeChannel.BK_CHAT},
            LAYOUTS_TEMPLATE,
        )
        is False
    )
    assert (
        Sender.is_wxwork_layouts_enabled(
            100380,
            NoticeWay.WX_BOT,
            SimpleNamespace(notice_channel=NoticeChannel.BK_CHAT),
            LAYOUTS_TEMPLATE,
        )
        is False
    )


def test_is_wxwork_layouts_enabled_keeps_native_wxwork_bot(settings, monkeypatch):
    settings.WECOM_LAYOUTS_BIZ_LIST = [100380]
    monkeypatch.setattr("bkmonitor.utils.send.get_template", lambda path: object())

    assert (
        Sender.is_wxwork_layouts_enabled(
            100380,
            NoticeWay.WX_BOT,
            {"notice_channel": NoticeChannel.WX_BOT},
            LAYOUTS_TEMPLATE,
        )
        is True
    )


def test_channel_bkchat_sender_never_enables_layouts(settings, monkeypatch):
    settings.WECOM_LAYOUTS_BIZ_LIST = [100380]
    monkeypatch.setattr("bkmonitor.utils.send.get_template", lambda path: object())

    assert (
        ChannelBkchatSender.is_wxwork_layouts_enabled(
            100380,
            NoticeWay.WX_BOT,
            {"notice_channel": NoticeChannel.WX_BOT},
            LAYOUTS_TEMPLATE,
        )
        is False
    )


def test_send_wxwork_markdown_uses_login_name_in_multi_tenant_mode(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
    query_display_info = Mock(
        return_value=[
            {"bk_username": "xxx_id_1", "display_name": "xxx_login_1(xxx_name)"},
            {"bk_username": "xxx_id_2", "display_name": "xxx_login_2(xxx_name)"},
        ]
    )
    monkeypatch.setattr(
        "core.drf_resource.api.bk_login.batch_query_user_display_info",
        query_display_info,
    )
    post = mock_wxwork_post(monkeypatch)

    result = Sender.send_wxwork_content(
        "markdown",
        "告警内容\n--mention-users--\n",
        ["xxx_chat_id_1", "xxx_chat_id_2"],
        {
            "xxx_chat_id_1": ["xxx_id_1", "xxx_id_2"],
            "xxx_chat_id_2": ["xxx_id_1"],
        },
    )

    assert result["errcode"] == 0
    query_display_info.assert_called_once_with(bk_usernames=["xxx_id_1", "xxx_id_2"])
    assert "<@xxx_login_1><@xxx_login_2>" in post.call_args_list[0].kwargs["json"]["markdown"]["content"]
    assert "<@xxx_login_1>" in post.call_args_list[1].kwargs["json"]["markdown"]["content"]
    assert "<@xxx_login_2>" not in post.call_args_list[1].kwargs["json"]["markdown"]["content"]


def test_send_wxwork_text_uses_login_name_in_multi_tenant_mode(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
    monkeypatch.setattr(
        "core.drf_resource.api.bk_login.batch_query_user_display_info",
        Mock(return_value=[{"bk_username": "xxx_id_2", "display_name": "xxx_login_2(xxx_name)"}]),
    )
    post = mock_wxwork_post(monkeypatch)

    Sender.send_wxwork_content("text", "告警内容", ["xxx_chat_id"], {"xxx_chat_id": ["xxx_id_2"]})

    assert post.call_args.kwargs["json"]["text"]["mentioned_list"] == ["xxx_login_2"]


def test_send_wxwork_layouts_uses_login_name_in_multi_tenant_mode(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
    query_display_info = Mock(
        return_value=[
            {"bk_username": "xxx_id_1", "display_name": "xxx_login_1(xxx_name)"},
            {"bk_username": "xxx_id_2", "display_name": "xxx_login_2(xxx_name)"},
        ]
    )
    monkeypatch.setattr(
        "core.drf_resource.api.bk_login.batch_query_user_display_info",
        query_display_info,
    )
    post = mock_wxwork_post(monkeypatch)

    Sender.send_wxwork_layouts(
        "markdown",
        json.dumps([{"type": "markdown", "text": "--mention-users--"}]),
        ["xxx_chat_id_1", "xxx_chat_id_2"],
        {
            "xxx_chat_id_1": ["xxx_id_1", "xxx_id_2"],
            "xxx_chat_id_2": ["xxx_id_1"],
        },
    )

    query_display_info.assert_called_once_with(bk_usernames=["xxx_id_1", "xxx_id_2"])
    assert "<@xxx_login_1><@xxx_login_2>" in post.call_args_list[0].kwargs["json"]["layouts"][0]["text"]
    assert "<@xxx_login_1>" in post.call_args_list[1].kwargs["json"]["layouts"][0]["text"]
    assert "<@xxx_login_2>" not in post.call_args_list[1].kwargs["json"]["layouts"][0]["text"]


def test_send_wxwork_keeps_username_in_single_tenant_mode(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
    query_display_info = Mock()
    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", query_display_info)
    post = mock_wxwork_post(monkeypatch)

    Sender.send_wxwork_content("markdown", "告警内容", ["xxx_chat_id"], {"xxx_chat_id": ["xxx_login"]})

    assert "<@xxx_login>" in post.call_args.kwargs["json"]["markdown"]["content"]
    query_display_info.assert_not_called()


def test_send_wxwork_falls_back_to_user_id_when_display_info_fails(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
    monkeypatch.setattr(
        "core.drf_resource.api.bk_login.batch_query_user_display_info",
        Mock(side_effect=BKAPIError(system_name="bk-user", url="display_info", result="failed")),
    )
    post = mock_wxwork_post(monkeypatch)

    result = Sender.send_wxwork_content("markdown", "告警内容", ["xxx_chat_id"], {"xxx_chat_id": ["xxx_id_1"]})

    assert result["errcode"] == 0
    assert "<@xxx_id_1>" in post.call_args.kwargs["json"]["markdown"]["content"]


def test_recovered_markdown_templates_use_green_status():
    context = {
        "action": None,
        "notice_way": NoticeWay.WX_BOT,
        "content_template": "**内容: **测试",
        "default_content_template": "",
        "title_template": "",
        "default_title_template": "",
        "alarm": SimpleNamespace(collect_count=2, detail_url="https://example.com", strategy_url=""),
        "alert": SimpleNamespace(alert_name="测试告警"),
        "level_name": "致命",
    }

    action_content = AlarmNoticeTemplate("notice/recovered/action/markdown_content.jinja").render(context)
    converge_content = AlarmNoticeTemplate("notice/recovered/converge/markdown_content.jinja").render(context)

    assert '<font color="info">[已恢复]</font>' in action_content
    assert "</font> [致命] 测试告警" in action_content
    assert '<font color="info">已恢复</font>2条致命告警' in converge_content
    assert "详情：[汇总详情](https://example.com)" in converge_content
    assert "**内容: **测试" in action_content
    assert "**内容: **测试" in converge_content


def test_recovered_markdown_template_has_english_variant():
    template_path = Sender.get_language_template_path("notice/recovered/action/markdown_content.jinja", "en")

    assert template_path == "notice/recovered/action/markdown_content_en.jinja"
