import base64
from typing import Any, NotRequired, TypedDict

from bk_monitor_base.config.all import get_config

from ..api_client import BkApiMode
from .client import send_mail_client

config = get_config()


class Attachment(TypedDict):
    """附件"""

    filename: str
    content: str
    type: NotRequired[str]
    disposition: NotRequired[str]
    content_id: NotRequired[str]


def send_mail(
    bk_tenant_id: str,
    title: str,
    content: str,
    is_content_base64: bool = False,
    body_format: str = "Html",
    receiver: str = "",
    receiver__username: str = "",
    sender: str = "",
    cc: str = "",
    cc__username: str = "",
    attachments: list[Attachment] | None = None,
    email_type: str = "SEND_TO_INTERNET",
) -> dict[str, Any]:
    """
    获取Es的结果表

    Args:
        bk_tenant_id: 租户ID
        title: 标题
        content: 内容
        is_content_base64: 内容是否base64编码
        body_format: 内容格式，Html或Text
        receiver: 收件人
        receiver__username: 收件人username
        sender: 发送人
        cc: 抄送人
        cc__username: 抄送人username
        attachments: 附件
        email_type: 邮件类型

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    if is_content_base64:
        content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    params: dict[str, Any] = {
        "title": title,
        "content": content,
        "is_content_base64": is_content_base64,
        "body_format": body_format,
        "receiver": receiver,
        "receiver__username": receiver__username,
        "sender": sender,
        "cc": cc,
        "cc__username": cc__username,
        "email_type": email_type,
        "attachments": attachments,
    }
    use_apigw = send_mail_client._get_api_mode() == BkApiMode.APIGW
    # 如果使用 apigw，则需要将 receiver__username, cc__username, cc, receiver 字段转换为列表
    if use_apigw:
        for field in ["receiver__username", "cc__username", "cc", "receiver"]:
            if params.get(field):
                params[field] = params[field].split(",")

    # 如果直接指定邮箱地址，则直接发送
    if receiver:
        return send_mail_client(bk_tenant_id=bk_tenant_id, params=params)

    # 区分内外部用户
    internal_users: list[str] = []
    external_users: list[str] = []
    # 兼容不同类型
    usernames: list[str] = params["receiver__username"]
    if isinstance(usernames, str):
        usernames = usernames.split(",")

    for username in usernames:
        # 通过是否以 "@tai" 结尾判断是否是内外部用户
        if username.endswith("@tai"):
            external_users.append(username)
        else:
            internal_users.append(username)

    response_data: dict[str, Any] = {
        # invalid: 通知失败的用户名列表
        "username_check": {"invalid": []},
        "message": "发送成功",
    }

    if internal_users:
        # esb 模式下，需要将 receiver__username 转换为字符串
        if not use_apigw:
            params["receiver__username"] = ",".join(internal_users)
        response_data = send_mail_client(bk_tenant_id=bk_tenant_id, params=params)

    if external_users:
        # 外部用户通知
        # todo 如果用esb，将无法发送给外部用户
        if use_apigw:
            params["receiver__username"] = external_users
            external_response_data = response_data = send_mail_client(bk_tenant_id=bk_tenant_id, params=params)
            response_data["username_check"]["invalid"] += external_response_data["username_check"]["invalid"]

    return response_data
