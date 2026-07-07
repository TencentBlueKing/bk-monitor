from unittest.mock import Mock

from bkmonitor.utils.send import Sender


def test_send_wxwork_layouts_returns_error_when_webhook_url_empty(settings, monkeypatch):
    settings.WXWORK_BOT_WEBHOOK_URL = ""
    post = Mock()
    monkeypatch.setattr("bkmonitor.utils.send.requests.post", post)
    monkeypatch.setattr("bkmonitor.utils.send._", lambda message: message)

    result = Sender.send_wxwork_layouts("markdown", "[]", ["chat-id"])

    assert result["errcode"] == -1
    assert result["errmsg"] == ["未配置蓝鲸监控群机器人回调地址，请联系管理员"]
    post.assert_not_called()
