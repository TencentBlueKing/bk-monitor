from typing import List

import mock

from api.cmsi.default import SendMail


class TestSendMail:
    """需要验证目的"""

    def test_all_exist(self):
        """
        全部都存在的情况

        receiver__username = "jiananzhang_bkci@tai"
        ```python
        # 获取外部用户信息mock数据
        {
            "data": [
                {
                    "username": "jiananzhang_bkci@tai",
                    "phone": "",
                    "phone_country_code": "",
                    "email": "jiananzhang00@gmail.com"
                }
            ]
        }
        ```
        """
        validated_request_data = {
            "receiver__username": "jiananzhang_bkci@tai",
            "title": "this is title",
            "content": "this is content",
        }

        send_mail = SendMail()
        send_mail.message_detail = {}

        internal_users: List[str] = []
        external_users: List[str] = []
        for username in validated_request_data["receiver__username"].split(","):
            if SendMail.is_external_user(username):
                external_users.append(username)
            else:
                internal_users.append(username)
        assert external_users == ["jiananzhang_bkci@tai"]
        assert internal_users == []

        # 构造获取外部用户信息
        external_receiver_info = {"jiananzhang_bkci@tai": {"email": "jiananzhang00@gmail.com", "phone": ""}}

        # 验证 get_receivers_with_external_users
        with mock.patch(
            "api.cmsi.default.SendMail.get_external_receiver_info",
            mock.Mock(return_value=external_receiver_info),
        ):
            receivers = ["jiananzhang00@gmail.com"]
            assert send_mail.get_receivers_with_external_users(external_users) == receivers
            assert send_mail.message_detail == {}

        # 由于没法在开发环境调用发送邮件接口所以改用 mock 的形式处理
        send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": send_mail.message_detail,
        }
        with mock.patch(
            "api.cmsi.default.SendMail.send_request",
            mock.Mock(return_value=send_request_response),
        ):
            response = {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {},
            }
            assert send_request_response == response

    def test_partially_exist(self):
        """
        部分存在
        receiver__username = "jiananzhang_1bkci@tai,jiananzhang_bkci@tai"
        ```python
        # 获取外部用户信息mock数据
        {
            "data": [
                {
                    "username": "jiananzhang_bkci@tai",
                    "phone": "",
                    "phone_country_code": "",
                    "email": "jiananzhang00@gmail.com"
                }
            ]
        }
        ```
        """
        validated_request_data = {
            "receiver__username": "jiananzhang_1bkci@tai,jiananzhang_bkci@tai",
            "title": "this is title",
            "content": "this is content",
        }

        send_mail = SendMail()
        send_mail.message_detail = {}

        internal_users: List[str] = []
        external_users: List[str] = []
        for username in validated_request_data["receiver__username"].split(","):
            if SendMail.is_external_user(username):
                external_users.append(username)
            else:
                internal_users.append(username)
        assert external_users == ["jiananzhang_1bkci@tai", "jiananzhang_bkci@tai"]
        assert internal_users == []

        # 验证 get_receivers_with_external_users
        external_receiver_info = {"jiananzhang_bkci@tai": {"email": "jiananzhang00@gmail.com", "phone": ""}}
        with mock.patch(
            "api.cmsi.default.SendMail.get_external_receiver_info",
            mock.Mock(return_value=external_receiver_info),
        ):
            receivers = ["jiananzhang00@gmail.com"]
            assert send_mail.get_receivers_with_external_users(external_users) == receivers
            # 另外一个不存在的用户会被记录到这里
            assert send_mail.message_detail == {"jiananzhang_1bkci@tai": "user not exists"}

        # 由于没法在开发环境调用发送邮件接口所以改用 mock 的形式处理
        # 在 CheckCMSIResource.send_request 中
        # 会将子类的message_detail 传递给 response_data["message_detail"]
        send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": send_mail.message_detail,
        }
        with mock.patch(
            "api.cmsi.default.SendMail.send_request",
            mock.Mock(return_value=send_request_response),
        ):
            response = {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {"jiananzhang_1bkci@tai": "user not exists"},
            }
            assert send_request_response == response

    def test_none_exist(self):
        """
        都不存在

        receiver__username = "jiananzhang_bkci@tai"
        ```python
        # 获取外部用户信息mock数据
        {
            "data": []
        }
        ```
        """
        validated_request_data = {
            "receiver__username": "jiananzhang_bkci@tai",
            "title": "this is title",
            "content": "this is content",
        }

        send_mail = SendMail()
        send_mail.message_detail = {}

        internal_users: List[str] = []
        external_users: List[str] = []
        for username in validated_request_data["receiver__username"].split(","):
            if SendMail.is_external_user(username):
                external_users.append(username)
            else:
                internal_users.append(username)
        assert external_users == ["jiananzhang_bkci@tai"]
        assert internal_users == []

        # 验证 get_receivers_with_external_users
        external_receiver_info = {}
        with mock.patch(
            "api.cmsi.default.SendMail.get_external_receiver_info",
            mock.Mock(return_value=external_receiver_info),
        ):
            receivers = []
            assert send_mail.get_receivers_with_external_users(external_users) == receivers
            # 另外一个不存在的用户会被记录到这里
            assert send_mail.message_detail == {"jiananzhang_bkci@tai": "user not exists"}

        # 由于没法在开发环境调用发送邮件接口所以改用 mock 的形式处理
        # 在 CheckCMSIResource.send_request 中
        # 会将子类的message_detail 传递给 response_data["message_detail"]
        send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": send_mail.message_detail,
        }
        with mock.patch(
            "api.cmsi.default.SendMail.send_request",
            mock.Mock(return_value=send_request_response),
        ):
            response = {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {"jiananzhang_bkci@tai": "user not exists"},
            }
            assert send_request_response == response
