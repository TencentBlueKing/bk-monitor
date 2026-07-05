import sys
from types import SimpleNamespace
from unittest.mock import Mock

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEFAULT_LOCALE="zh-hans",
        IS_WECOM_ROBOT_ENABLED=True,
        WECOM_ROBOT_ACCOUNT={},
        WECOM_LAYOUTS_BIZ_LIST=[],
        MD_SUPPORTED_NOTICE_WAYS=[],
        SMS_CONTENT_LENGTH=0,
        WXWORK_BOT_WEBHOOK_URL="",
        WXWORK_BOT_SEND_IMAGE=False,
        BK_DOMAIN="",
    )

sys.modules.setdefault("bkmonitor.models", SimpleNamespace(GlobalConfig=object))
sys.modules.setdefault(
    "bkmonitor.utils.template",
    SimpleNamespace(
        AlarmNoticeTemplate=object,
        AlarmOperateNoticeTemplate=object,
    ),
)
sys.modules.setdefault(
    "bkmonitor.utils.text",
    SimpleNamespace(
        cut_line_str_by_max_bytes=lambda value, limit, encoding=None: value,
        cut_str_by_max_bytes=lambda value, limit, encoding=None: value,
        get_content_length=lambda value, encoding=None: len(value or ""),
    ),
)
sys.modules.setdefault("common.context_processors", SimpleNamespace(Platform=SimpleNamespace(te=True)))
sys.modules.setdefault(
    "constants.action",
    SimpleNamespace(
        ActionPluginType=SimpleNamespace(NOTICE="notice"),
        NoticeType=SimpleNamespace(ALERT_NOTICE="alert_notice", ACTION_NOTICE="action_notice"),
        NoticeWay=SimpleNamespace(SMS="sms", WX_BOT="wxbot"),
    ),
)
sys.modules.setdefault("core.drf_resource", SimpleNamespace(api=SimpleNamespace()))
sys.modules.setdefault(
    "core.prometheus",
    SimpleNamespace(
        metrics=SimpleNamespace(
            ACTION_NOTICE_API_CALL_COUNT=SimpleNamespace(labels=lambda **kwargs: SimpleNamespace(inc=lambda: None)),
            StatusEnum=SimpleNamespace(FAILED="failed", SUCCESS="success"),
        )
    ),
)

from bkmonitor.utils.send import Sender


def test_send_wxwork_layouts_returns_error_when_webhook_url_empty(monkeypatch):
    settings.WXWORK_BOT_WEBHOOK_URL = ""
    post = Mock()
    monkeypatch.setattr("bkmonitor.utils.send.requests.post", post)
    monkeypatch.setattr("bkmonitor.utils.send._", lambda message: message)

    result = Sender.send_wxwork_layouts("markdown", "[]", ["chat-id"])

    assert result["errcode"] == -1
    assert result["errmsg"]
    post.assert_not_called()
