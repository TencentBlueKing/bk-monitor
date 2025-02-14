# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import hashlib
import os

from django.conf import settings
from rest_framework import serializers

from core.drf_resource.contrib.nested_api import KernelAPIResource


class BSCPAPIGWResource(KernelAPIResource):
    TIMEOUT = 300
    base_url_statement = None
    IS_STANDARD_FORMAT = False
    base_url = (
        "%sapp" % settings.MONITOR_API_BASE_URL or "%s/api/c/compapi/v2/monitor_v3/" % settings.BK_COMPONENT_API_URL
    )

    # 模块名
    module_name = "bscp"

    @property
    def label(self):
        return self.__doc__

    def get_request_url(self, validated_request_data):
        """
        获取最终请求的url，也可以由子类进行重写
        """
        base_url = os.getenv("BKAPP_BSCP_DEV_API_URL", "")
        request_url = base_url.rstrip("/") + "/" + self.action.lstrip("/")
        return request_url.format(**validated_request_data)

    def before_request(self, kwargs):
        kwargs["headers"]["X-Bk-App-Code"] = os.getenv("BKAPP_BSCP_DEV_APP_CODE")
        kwargs["headers"]["X-Bk-App-Secret"] = os.getenv("BKAPP_BSCP_DEV_APP_SECRET")
        # print(json.dumps(kwargs, indent=2))
        return kwargs

    def request(self, request_data=None, **kwargs):
        request_data = request_data or kwargs
        # 如果参数中传递了用户信息，则记录下来，以便接口请求时使用
        if "bk_ticket" in request_data:
            setattr(self, "bk_ticket", request_data["bk_ticket"])
        data = super(BSCPAPIGWResource, self).request(request_data, **kwargs)
        return data

    def full_request_data(self, validated_request_data):
        data = super(BSCPAPIGWResource, self).full_request_data(validated_request_data)
        data["bk_app_code"] = os.getenv("BKAPP_BSCP_DEV_APP_CODE")
        data["bk_app_secret"] = os.getenv("BKAPP_BSCP_DEV_APP_SECRET")
        if hasattr(self, "bk_ticket"):
            data.update({"bk_ticket": self.bk_ticket})
        return data


class CreateAppResource(BSCPAPIGWResource):
    action = "api/v1/config/create/app/app/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        name = serializers.CharField(required=True, label="应用名称")
        config_type = serializers.CharField(required=False, label="类型", default="file")
        deploy_type = serializers.CharField(required=False, label="部署方式", default="common")


class CreateStrategySetResource(BSCPAPIGWResource):
    action = "api/v1/config/create/strategy_set/strategy_set/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        name = serializers.CharField(required=True, label="策略集名称", max_length=128)
        mode = serializers.ChoiceField(
            required=False, label="策略集类型", choices=["normal", "namespace"], default="namespace"
        )
        memo = serializers.CharField(required=False, label="备注")


class CreateConfigItemResource(BSCPAPIGWResource):
    action = "api/v1/config/create/config_item/config_item/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        name = serializers.CharField(required=True, label="配置项名称", max_length=64)
        path = serializers.CharField(required=True, label="配置项路径", max_length=255)
        file_type = serializers.ChoiceField(required=True, label="配置项类型", choices=["binary", "json", "yaml", "xml"])
        file_mode = serializers.ChoiceField(required=False, label="配置项模式", choices=["win", "unix"], default="unix")
        user = serializers.CharField(required=True, label="用户名", max_length=64)
        user_group = serializers.CharField(required=True, label="用户组", max_length=64)
        privilege = serializers.CharField(required=True, label="权限", max_length=64)
        memo = serializers.CharField(required=False, label="备注", max_length=255)


class UploadContentResource(BSCPAPIGWResource):
    action = "api/v1/api/create/content/upload/biz_id/{bk_biz_id}/app_id/{app_id}"
    method = "PUT"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        content = serializers.CharField(required=True, label="content")

    def before_request(self, kwargs):
        kwargs = super(UploadContentResource, self).before_request(kwargs)
        content: str = kwargs["json"]["content"]
        content_sh256 = hashlib.sha256(content.encode()).hexdigest()
        kwargs["headers"]["X-Bkapi-File-Content-Id"] = content_sh256
        kwargs["data"] = content.encode()
        kwargs["params"] = {
            "bk_app_code": os.getenv("BKAPP_BSCP_DEV_APP_CODE"),
            "bk_app_secret": os.getenv("BKAPP_BSCP_DEV_APP_SECRET"),
            "bk_ticket": self.bk_ticket,
        }
        kwargs.pop("json")
        return kwargs


class CreateContentResource(BSCPAPIGWResource):
    action = "api/v1/config/create/content/content/config_item_id/{config_item_id}/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        config_item_id = serializers.IntegerField(required=True, label="配置项ID")
        content = serializers.CharField(required=True, label="content")
        # signature = serializers.CharField(required=True, label="签名")
        # byte_size = serializers.IntegerField(required=True, label="文件大小 字节")

    def before_request(self, kwargs):
        kwargs = super(CreateContentResource, self).before_request(kwargs)
        content: str = kwargs["json"]["content"]
        content_sh256 = hashlib.sha256(content.encode()).hexdigest()
        kwargs["json"]["sign"] = content_sh256
        kwargs["json"]["byte_size"] = len(content.encode())
        kwargs["json"].pop("content")
        return kwargs


class CreateCommitResource(BSCPAPIGWResource):
    action = "api/v1/config/create/commit/commit/config_item_id/{config_item_id}/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        config_item_id = serializers.IntegerField(required=True, label="配置项ID")
        content_id = serializers.IntegerField(required=True, label="内容ID")
        memo = serializers.CharField(required=False, label="备注", max_length=255)


class CreateReleaseResource(BSCPAPIGWResource):
    action = "api/v1/config/create/release/release/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        name = serializers.CharField(required=True, label="发布名称", max_length=128)
        memo = serializers.CharField(required=False, label="备注", max_length=255)


class CreateStrategyResource(BSCPAPIGWResource):
    action = (
        "api/v1/config/create/strategy/strategy/strategy_set_id/{strategy_set_id}/app_id/{app_id}/biz_id/{bk_biz_id}"
    )
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        strategy_set_id = serializers.IntegerField(required=True, label="策略集ID")
        release_id = serializers.IntegerField(required=True, label="发布ID")
        as_default = serializers.BooleanField(required=False, label="是否作为兜底策略")
        name = serializers.CharField(required=True, label="策略名称", max_length=128)
        scope = serializers.DictField(required=False, label="策略范围")
        namespace = serializers.CharField(required=False, label="命名空间", allow_blank=True)
        memo = serializers.CharField(required=False, label="备注", max_length=255)


class PublishWithStrategyResource(BSCPAPIGWResource):
    action = (
        "api/v1/config/update/strategy_set/publish/publish/strategy_id/{strategy_id}/app_id/{app_id}/biz_id/{bk_biz_id}"
    )
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        strategy_id = serializers.IntegerField(required=True, label="策略ID")


class FinishPublishWithStrategyResource(BSCPAPIGWResource):
    action = "api/v1/config/update/strategy/publish/finish/strategy_id/{strategy_id}/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "PUT"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        strategy_id = serializers.IntegerField(required=True, label="策略ID")


class PublishWithInstanceResource(BSCPAPIGWResource):
    action = "api/v1/config/create/instance/publish/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        uid = serializers.CharField(required=True, label="用户ID")
        release_id = serializers.IntegerField(required=True, label="发布ID")
        memo = serializers.CharField(required=False, label="备注", max_length=255)


class DeleteStrategyResource(BSCPAPIGWResource):
    action = "api/v1/config/delete/strategy/strategy/strategy_id/{strategy_id}/app_id/{app_id}/biz_id/{bk_biz_id}"
    method = "DELETE"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        strategy_id = serializers.IntegerField(required=True, label="策略ID")


class DeletePublishWithInstanceResource(BSCPAPIGWResource):
    action = "api/v1/config/delete/instance/publish/id/{instance_id}/app_id/{app_id}/biz_id/{biz_id}"
    method = "DELETE"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_id = serializers.IntegerField(required=True, label="应用ID")
        instance_id = serializers.IntegerField(required=True, label="实例ID")
