from unittest import mock

from api.cmsi.default import SendMail


class TestSendMail:
    def test_external_exist(self):
        """一个外部用户存在"""
        validated_request_data = {
            "receiver__username": "someone@tai",
            "title": "this is title",
            "content": "this is content",
        }

        external_receiver_info = {"someone@tai": {"email": "someone00@gmail.com", "phone": ""}}
        request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": {},
        }
        with (
            mock.patch(
                "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
            ),
            mock.patch("api.cmsi.default.SendMail.send_request", mock.Mock(return_value=request_response)),
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {},
            }

    def test_external_users_partially_exist(self):
        """两个外部用户，一个存在，一个不存在"""
        validated_request_data = {
            "receiver__username": "someone@tai,someone1@tai",
            "title": "this is title",
            "content": "this is content",
        }

        external_receiver_info = {"someone@tai": {"email": "someone00@gmail.com", "phone": ""}}
        external_send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": {},  # 在调用父类的send_request中，会将self.message_detail赋值给response_data 然后返回
        }
        with (
            mock.patch(
                "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
            ),
            mock.patch(
                "api.cmsi.default.SendMail.send_request", mock.Mock(return_value=external_send_request_response)
            ),
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {"someone1@tai": "user not exists"},
            }

    def test_external_users_none_exist(self):
        """一个外部用户 不存在"""
        validated_request_data = {
            "receiver__username": "someone@tai",
            "title": "this is title",
            "content": "this is content",
        }

        external_receiver_info = {}
        with mock.patch(
            "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {"someone@tai": "user not exists"},
            }

    def test_external_users_email_none_exist(self):
        """一个外部用户邮箱不存在"""
        validated_request_data = {
            "receiver__username": "someone@tai",
            "title": "this is title",
            "content": "this is content",
        }

        external_receiver_info = {"someone@tai": {"email": "", "phone": ""}}
        with mock.patch(
            "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {"someone@tai": "user email not exists"},
            }

    # 以下为一个内部用户+一个外部用户的情况
    def test_all_exist(self):
        """内外部用户都存在"""
        validated_request_data = {
            "receiver__username": "someone@tai,someone",
            "title": "this is title",
            "content": "this is content",
        }

        internal_send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": {},
        }
        external_send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": {},
        }
        external_receiver_info = {"someone@tai": {"email": "someone00@gmail.com", "phone": ""}}
        with (
            mock.patch(
                "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
            ),
            mock.patch(
                "api.cmsi.default.SendMail.send_request",
                mock.Mock(side_effect=[internal_send_request_response, external_send_request_response]),
            ),
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {},
            }

    def test_only_external_user_none_exist(self):
        """内部用户存在，外部用户不存在"""
        validated_request_data = {
            "receiver__username": "someone@tai,someone",
            "title": "this is title",
            "content": "this is content",
        }

        internal_send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": {},
        }

        external_receiver_info = {}
        with (
            mock.patch(
                "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
            ),
            mock.patch(
                "api.cmsi.default.SendMail.send_request", mock.Mock(side_effect=[internal_send_request_response])
            ),
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": []},
                "message": "发送成功",
                "message_detail": {"someone@tai": "user not exists"},
            }

    def test_internal_user_error(self):
        """内部用户报错，外部用户存在"""
        validated_request_data = {
            "receiver__username": "someone@tai,someone",
            "title": "this is title",
            "content": "this is content",
        }

        internal_send_request_response = {
            "username_check": {"invalid": ["someone"]},
            "message": "发送失败",
            "message_detail": {},
        }
        external_send_request_response = {
            "username_check": {"invalid": []},
            "message": "发送成功",
            "message_detail": {},
        }
        external_receiver_info = {"someone@tai": {"email": "someone00@gmail.com", "phone": ""}}
        with (
            mock.patch(
                "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
            ),
            mock.patch(
                "api.cmsi.default.SendMail.send_request",
                mock.Mock(side_effect=[internal_send_request_response, external_send_request_response]),
            ),
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": ["someone"]},
                "message": "发送失败",
                "message_detail": {},
            }

    def test_all_users_none_exist(self):
        """内部用户报错，外部用户不存在"""
        validated_request_data = {
            "receiver__username": "someone@tai,someone",
            "title": "this is title",
            "content": "this is content",
        }

        internal_send_request_response = {
            "username_check": {"invalid": ["someone"]},
            "message": "发送失败",
            "message_detail": {},
        }

        external_receiver_info = {}
        with (
            mock.patch(
                "api.cmsi.default.SendMail.get_external_receiver_info", mock.Mock(return_value=external_receiver_info)
            ),
            mock.patch(
                "api.cmsi.default.SendMail.send_request", mock.Mock(side_effect=[internal_send_request_response])
            ),
        ):
            assert SendMail()(validated_request_data) == {
                "username_check": {"invalid": ["someone"]},
                "message": "发送失败",
                "message_detail": {"someone@tai": "user not exists"},
            }
