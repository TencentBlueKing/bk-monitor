from types import SimpleNamespace
from unittest.mock import Mock

from bkmonitor.utils.send import ChannelBkchatSender, Sender
from constants.action import NoticeChannel, NoticeWay

LAYOUTS_TEMPLATE = "notice/abnormal/action/markdown_content.jinja"


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
