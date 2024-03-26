# -*- coding: utf-8 -*-

import abc

import six
from django.conf import settings
from rest_framework import serializers

from common.context_processors import Platform
from core.drf_resource.contrib.api import APIResource


class BkSSMBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url_prefix = f"{settings.BK_SSM_HOST}:{settings.BK_SSM_PORT}"
    base_url = f"{base_url_prefix}/api/v1/auth/"
    module_name = "bkssm"


class GetAccessToken(BkSSMBaseResource):
    """
    获取应用的api gateway access token
    {
      "code": 0,
      "data": {
        "access_token": "xxx",
        "expires_in": 43200,
        "identity": {
          "user_type": "bkuser",
          "username": "admin"
        },
        "refresh_token": "xxx"
      },
      "message": "string"
    }
    """

    action = "access-tokens"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        # 授权类型, 当前支持authorization_code登录态授权和client_credentials客户端授权两种
        # 默认是client_credentials即可
        grant_type = serializers.CharField(label="授权类型", default="client_credentials")
        # token提供方, 当grant_type=authorization_code时, 值为bk_login; 当grant_type=client_credentials时值为client
        # 默认是client即可
        id_provider = serializers.CharField(label="token提供方", default="client")
        # 用户态bk_ticket&rtx，当grant_type=authorization_code时必填
        bk_ticket = serializers.CharField(label="用户态bk_ticket", required=False)
        rtx = serializers.CharField(label="用户态rtx", required=False)

    def get_request_url(self, validated_request_data):
        if Platform.te:
            return f"{self.base_url_prefix}/auth_api/token/"
        return super(GetAccessToken, self).get_request_url(validated_request_data)

    def full_request_data(self, validated_request_data):
        validated_request_data = super(GetAccessToken, self).full_request_data(validated_request_data)
        if not Platform.te:
            return validated_request_data
        # NOTE: 去除不需要的key
        for key in ["bk_app_code", "bk_app_secret", "bk_token", "id_provider"]:
            validated_request_data.pop(key, None)
        # NOTE: 需要应用的参数为 app_code 和 app_secret
        validated_request_data.update(
            {
                "app_code": settings.APP_CODE,
                "app_secret": settings.SECRET_KEY,
                "env_name": "prod",  # 固定使用 prod
            }
        )
        return validated_request_data
