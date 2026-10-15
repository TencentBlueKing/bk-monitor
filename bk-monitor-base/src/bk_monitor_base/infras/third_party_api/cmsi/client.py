from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class CMSIClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "cmsi"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/cmsi/"
    apigw_base_url: ClassVar[str] = "api/bk-cmsi/prod/"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class SendMail(CMSIClient):
    """发送邮件消息"""

    action: ClassVar[str] = "send_mail"
    method: ClassVar[str] = "POST"

    esb_path: ClassVar[str] = "send_mail"
    apigw_path: ClassVar[str] = "v1/send_mail/"


send_mail_client = SendMail()
