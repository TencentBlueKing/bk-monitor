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


import abc
import logging

import requests
import six
from blueapps.account.conf import ConfFixture
from blueapps.account.utils import load_backend
from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import ugettext as _
from requests.exceptions import HTTPError, ReadTimeout

from bkmonitor.utils.request import get_common_headers, get_request
from bkmonitor.utils.user import make_userinfo
from core.drf_resource.contrib.cache import CacheResource
from core.errors.api import BKAPIError
from core.errors.iam import APIPermissionDeniedError

logger = logging.getLogger(__name__)


__doc__ = """
    基于蓝鲸ESB/APIGateWay封装
    http请求默认带上通用参数：bk_app_code, bk_app_secret, bk_username
"""


# 接口调用的公共参数
INTERFACE_COMMON_PARAMS = {
    "bk_app_code": settings.APP_CODE,
    "bk_app_secret": settings.SECRET_KEY,
}


BK_USERNAME_FIELD = "bk_username"
APIPermissionDeniedCodeList = ["9900403", 9900403]


def get_bk_login_ticket(request):
    """
    从 request 中获取用户登录凭据
    """
    form_cls = "AuthenticationForm"
    context = [request.COOKIES, request.GET]

    if request.is_rio():
        # 为了保证能够使用RIO,需要调整import路径
        context.insert(0, request.META)
        AuthenticationForm = import_string("blueapps.account.components.rio.forms.RioAuthenticationForm")
    else:
        if request.is_wechat():
            form_cls = "WeixinAuthenticationForm"

        AuthenticationForm = load_backend("{}.forms.{}".format(ConfFixture.BACKEND_TYPE, form_cls))

    for form in (AuthenticationForm(c) for c in context):
        if form.is_valid():
            return form.cleaned_data

    return {}


class APIResource(six.with_metaclass(abc.ABCMeta, CacheResource)):
    """
    API类型的Resource
    """

    TIMEOUT = 60
    # 是否直接使用标准格式数据，兼容BCS非标准返回的情况
    IS_STANDARD_FORMAT = True

    @abc.abstractproperty
    def base_url(self):
        """
        api gateway 基本url生成规则
        """
        raise NotImplementedError

    @abc.abstractproperty
    def module_name(self):
        """
        在apigw中的模块名
        """
        raise NotImplementedError

    @abc.abstractproperty
    def action(self):
        """
        url的后缀，通常是指定特定资源
        """
        raise NotImplementedError

    @abc.abstractproperty
    def method(self):
        """
        请求方法，仅支持GET或POST
        """
        raise NotImplementedError

    @staticmethod
    def split_request_data(data):
        """
        切分请求参数为文件/非文件类型，便于requests参数组装
        """
        file_data = {}
        non_file_data = {}
        for request_param, param_value in list(data.items()):
            if hasattr(param_value, "read"):
                # 一般认为含有read属性的为文件类型
                file_data[request_param] = param_value
            else:
                non_file_data[request_param] = param_value
        return non_file_data, file_data

    def __init__(self, **kwargs):
        super(APIResource, self).__init__(**kwargs)
        assert self.method.upper() in ["GET", "POST", "PUT", "DELETE"], _("method仅支持GET或POST或PUT或DELETE")
        self.method = self.method.upper()
        self.session = requests.session()

    def request(self, request_data=None, **kwargs):
        request_data = request_data or kwargs
        # 如果参数中传递了用户信息，则记录下来，以便接口请求时使用
        if BK_USERNAME_FIELD in request_data:
            setattr(self, "bk_username", request_data[BK_USERNAME_FIELD])
        return super(APIResource, self).request(request_data, **kwargs)

    def full_request_data(self, validated_request_data):
        # 组装通用参数： 1. 用户信息 2. SaaS凭证
        if hasattr(self, "bk_username"):
            validated_request_data.update({BK_USERNAME_FIELD: self.bk_username})
        else:
            request = get_request(peaceful=True)
            user_info = make_userinfo()
            if request and not getattr(request, "external_user", None):
                user_info.update(get_bk_login_ticket(request))
            validated_request_data.update(user_info)

        # 2. SaaS凭证
        validated_request_data.update(INTERFACE_COMMON_PARAMS)
        return validated_request_data

    def before_request(self, kwargs):
        return kwargs

    def get_headers(self):
        return get_common_headers()

    def perform_request(self, validated_request_data):
        """
        发起http请求
        """
        validated_request_data = dict(validated_request_data)
        validated_request_data = self.full_request_data(validated_request_data)

        # 拼接最终请求的url
        request_url = self.get_request_url(validated_request_data)
        logger.debug("request: {}".format(request_url))

        try:
            headers = self.get_headers()
            kwargs = {
                "method": self.method,
                "url": request_url,
                "timeout": validated_request_data.get("timeout") or self.TIMEOUT,
                "headers": headers,
                "verify": False,
            }
            if self.method == "GET":
                kwargs = self.before_request(kwargs)
                request_url = kwargs.pop("url")
                if "method" in kwargs:
                    del kwargs["method"]

                result = self.session.get(
                    url=request_url,
                    params=validated_request_data,
                    headers=headers,
                    verify=False,
                    timeout=validated_request_data.get("timeout") or self.TIMEOUT,
                )
            else:
                non_file_data, file_data = self.split_request_data(validated_request_data)

                if not file_data:
                    # 不存在文件数据，则按照json方式去请求
                    kwargs["json"] = non_file_data
                else:
                    # 若存在文件数据，则将非文件数据和文件数据分开传参
                    kwargs["files"] = file_data
                    kwargs["data"] = non_file_data

                kwargs = self.before_request(kwargs)
                result = self.session.request(**kwargs)
        except ReadTimeout:
            raise BKAPIError(system_name=self.module_name, url=self.action, result=_("接口返回结果超时"))

        try:
            result.raise_for_status()
        except HTTPError as err:
            logger.exception("【模块：{}】请求APIGW错误：{}，请求url: {} ".format(self.module_name, err, request_url))
            raise BKAPIError(system_name=self.module_name, url=self.action, result=str(err.response.content))

        result_json = result.json()

        # 权限中心无权限结构特殊处理
        if result_json.get("code") in APIPermissionDeniedCodeList:
            raise APIPermissionDeniedError(
                context={"system_name": self.module_name, "url": self.action},
                data={"apply_url": settings.BK_IAM_SAAS_HOST},
                extra={"permission": result_json.get("permission")},
            )

        if not result_json.get("result", True) and result_json.get("code") != 0:
            msg = result_json.get("message", "")
            errors = result_json.get("errors", "")
            if errors:
                msg = f"{msg}(detail:{errors})"
            request_id = result_json.pop("request_id", "") or result.headers.get("x-bkapi-request-id", "")
            logger.error(
                "【Module: " + self.module_name + "】【Action: " + self.action + "】(%s) get error：%s",
                request_id,
                msg,
                extra=dict(module_name=self.module_name, url=request_url),
            )
            # 调试使用
            # msg = u"【模块：%s】接口【%s】返回结果错误：%s###%s" % (
            #     self.module_name, request_url, validated_request_data, result_json)
            raise BKAPIError(system_name=self.module_name, url=self.action, result=result_json)

        # 渲染数据
        if self.IS_STANDARD_FORMAT:
            response_data = self.render_response_data(validated_request_data, result_json.get("data"))
        else:
            response_data = self.render_response_data(validated_request_data, result_json)

        return response_data

    @property
    def label(self):
        return ""

    @property
    def action_display(self):
        """
        api描述
        eg: data(基础事件下发)
        """
        if self.label:
            return "{}-{}".format(self.module_name, self.label)
        return self.module_name

    def get_request_url(self, validated_request_data):
        """
        获取最终请求的url，也可以由子类进行重写
        """
        return self.base_url.rstrip("/") + "/" + self.action.lstrip("/")

    def render_response_data(self, validated_request_data, response_data):
        """
        在提供数据给response_serializer之前，对数据作最后的处理，子类可进行重写
        """
        return response_data
