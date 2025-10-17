"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import json
import logging

import requests
from blueapps.account.conf import ConfFixture
from blueapps.account.utils import load_backend
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import translation
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from requests.exceptions import HTTPError, ReadTimeout

from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.user import make_userinfo
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.contrib.cache import CacheResource
from core.errors.api import BKAPIError
from core.errors.iam import APIPermissionDeniedError
from core.prometheus import metrics

logger = logging.getLogger(__name__)

__doc__ = """
    基于蓝鲸ESB/APIGateWay封装
    http请求默认带上通用参数：bk_app_code, bk_app_secret, bk_username
"""

BK_USERNAME_FIELD = "bk_username"
APIPermissionDeniedCodeList = ["9900403", "35999999"]


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

        AuthenticationForm = load_backend(f"{ConfFixture.BACKEND_TYPE}.forms.{form_cls}")

    for form in (AuthenticationForm(c) for c in context):
        if form.is_valid():
            return form.cleaned_data

    return {}


class APIResource(CacheResource, metaclass=abc.ABCMeta):
    """
    API类型的Resource
    """

    TIMEOUT = 60
    # 是否直接使用标准格式数据，兼容BCS非标准返回的情况
    IS_STANDARD_FORMAT = True
    METRIC_REPORT_NOW = True
    # CMDB API 已在请求头的 x-bkapi-authorization 中包含了 bk_username，不需要在请求参数中重复添加
    INSERT_BK_USERNAME_TO_REQUEST_DATA = True

    ignore_error_msg_list = []

    @property
    @abc.abstractmethod
    def base_url(self):
        """
        api gateway 基本url生成规则
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def action(self):
        """
        url的后缀，通常是指定特定资源
        """
        raise NotImplementedError

    module_name: str

    method: str

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"], _(
            "method仅支持GET或POST或PUT或DELETE或PATCH"
        )
        self.method = self.method.upper()
        self.session = requests.session()
        self.bk_tenant_id: str | None = None

    def request(self, request_data=None, **kwargs):
        request_data = request_data or kwargs
        # 如果参数中传递了用户信息，则记录下来，以便接口请求时使用
        if BK_USERNAME_FIELD in request_data:
            setattr(self, "bk_username", request_data[BK_USERNAME_FIELD])

        # 如果参数中传递了租户ID，则记录下来，以便接口请求时使用
        if "bk_tenant_id" in request_data:
            self.bk_tenant_id = request_data["bk_tenant_id"]

        return super().request(request_data, **kwargs)

    def full_request_data(self, validated_request_data):
        # 如果请求参数中传递了用户信息，则直接返回
        if "bk_username" in validated_request_data or not self.INSERT_BK_USERNAME_TO_REQUEST_DATA:
            return validated_request_data

        # 组装通用参数： 1. 用户信息 2. SaaS凭证
        if hasattr(self, "bk_username"):
            validated_request_data.update({BK_USERNAME_FIELD: self.bk_username})
        else:
            user_info = make_userinfo(bk_tenant_id=self._get_tenant_id())
            self.bk_username = user_info.get("bk_username")
            validated_request_data.update(user_info)
        return validated_request_data

    def _get_tenant_id(self) -> str:
        if self.bk_tenant_id:
            return self.bk_tenant_id
        bk_tenant_id = get_request_tenant_id(peaceful=True)
        if not bk_tenant_id:
            logger.warning(
                f"get_request_tenant_id: cannot get tenant_id from request or local, {self.module_name} {self.action}"
            )
            return DEFAULT_TENANT_ID
        return bk_tenant_id

    def before_request(self, kwargs):
        return kwargs

    def get_headers(self):
        headers = {}

        # 增加语言头
        language = translation.get_language()
        if language:
            headers["blueking-language"] = language

        # 添加调用凭证
        auth_params = {"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}
        if getattr(self, "bk_username", None):
            auth_params["bk_username"] = self.bk_username
        else:
            request = get_request(peaceful=True)
            if request and not getattr(request, "external_user", None):
                auth_params.update(get_bk_login_ticket(request))
            auth_params.update(make_userinfo(bk_tenant_id=self._get_tenant_id()))
        headers["x-bkapi-authorization"] = json.dumps(auth_params)

        # 多租户模式下添加租户ID
        # 如果是web请求，通过用户名获取租户ID
        # 如果是后台请求，通过主动设置的参数或业务ID获取租户ID
        headers["X-Bk-Tenant-Id"] = self._get_tenant_id()
        return headers

    def perform_request(self, validated_request_data):
        """
        发起http请求
        """
        validated_request_data = dict(validated_request_data)

        # 获取租户ID
        if not self.bk_tenant_id:
            if "bk_tenant_id" in validated_request_data:
                # 如果传递了租户ID，则直接使用
                self.bk_tenant_id = validated_request_data["bk_tenant_id"]
            elif (
                validated_request_data.get("bk_biz_id") and isinstance(validated_request_data.get("bk_biz_id"), int)
            ) or (validated_request_data.get("space_uid") and isinstance(validated_request_data.get("space_uid"), str)):
                # 如果传递了业务ID或空间ID，则获取关联的租户ID
                space: Space | None = SpaceApi.get_space_detail(
                    bk_biz_id=validated_request_data.get("bk_biz_id", 0),
                    space_uid=validated_request_data.get("space_uid"),
                )
                if space:
                    self.bk_tenant_id = space.bk_tenant_id

        # 补充用户字段
        validated_request_data = self.full_request_data(validated_request_data)

        # 拼接最终请求的url
        request_url = self.get_request_url(validated_request_data)
        logger.debug(f"request: {request_url}")

        # 是否是流式响应
        is_stream = getattr(self, "IS_STREAM", False)

        try:
            headers = self.get_headers()
            kwargs = {
                "method": self.method,
                "url": request_url,
                "timeout": validated_request_data.get("timeout") or self.TIMEOUT,
                "headers": headers,
                "verify": False,
                "stream": is_stream,
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
                    stream=is_stream,
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
        except ReadTimeout as error:
            # 上报API调用失败统计指标
            self.report_api_failure_metric(error_code=getattr(error, "code", 0), exception_type=type(error).__name__)
            raise BKAPIError(system_name=self.module_name, url=self.action, result=_("接口返回结果超时"))

        try:
            result.raise_for_status()
        except HTTPError as err:
            logger.exception(f"【模块：{self.module_name}】请求APIGW错误：{err}，请求url: {request_url} ")
            self.report_api_failure_metric(error_code=getattr(err, "code", 0), exception_type=type(err).__name__)
            raise BKAPIError(system_name=self.module_name, url=self.action, result=str(err.response.content))

        if is_stream:
            return self.handle_stream_response(result)
        else:
            result_json = result.json()

        if not isinstance(result_json, dict):
            return result_json

        # 上报API服务观测指标
        ret_code = result_json.get("code", -1)
        self.report_api_request_count_metric(code=ret_code)

        # 权限中心无权限结构特殊处理
        if ret_code and str(ret_code) in APIPermissionDeniedCodeList:
            self.report_api_failure_metric(error_code=ret_code, exception_type=APIPermissionDeniedError.__name__)

            permission = {}
            if "permission" in result_json and isinstance(result_json["permission"], dict):
                permission = result_json["permission"]
            elif isinstance(result_json.get("data"), dict):
                permission = result_json["data"].get("permission") or {}

            raise APIPermissionDeniedError(
                context={"system_name": self.module_name, "url": self.action},
                data={"apply_url": settings.BK_IAM_SAAS_HOST},
                extra={"permission": permission},
            )

        if not result_json.get("result", True) and ret_code != 0:
            msg = result_json.get("message", "")
            errors = result_json.get("errors", "")
            if errors:
                msg = f"{msg}(detail:{errors})"

            # 忽略某些错误信息，避免过多日志
            for ignore_msg in self.ignore_error_msg_list:
                if ignore_msg in msg:
                    break
            else:
                request_id = result_json.pop("request_id", "") or result.headers.get("x-bkapi-request-id", "")
                logger.error(
                    "【Module: " + self.module_name + "】【Action: " + self.action + "】(%s) get error：%s",
                    request_id,
                    msg,
                    extra=dict(module_name=self.module_name, url=request_url),
                )
                self.report_api_failure_metric(error_code=ret_code, exception_type=BKAPIError.__name__)
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

    def report_api_failure_metric(self, error_code, exception_type):
        """
        当调用三方API异常时，上报自定义指标
        """
        try:
            metrics.API_FAILED_REQUESTS_TOTAL.labels(
                action=self.action,
                module=self.module_name,
                code=error_code,
                role=settings.ROLE,
                exception=exception_type,
                user_name=getattr(self, "bk_username", ""),
            ).inc()
            if self.METRIC_REPORT_NOW:
                metrics.report_all()
        except Exception as err:  # pylint: disable=broad-except
            logger.exception(f"APIResource: Failed to report api_failed_requests metrics,error:{err}")

    def report_api_request_count_metric(self, code):
        """
        上报API调用指标，统计返回状态码，现阶段具体实现下沉在各个API Module的render_response_data方法中
        @param code: 返回状态码
        """
        try:
            metrics.API_REQUESTS_TOTAL.labels(
                action=self.action,
                module=self.module_name,
                code=code,
                role=settings.ROLE,
            ).inc()
            if self.METRIC_REPORT_NOW:
                metrics.report_all()
        except Exception as err:  # pylint: disable=broad-except
            logger.exception(f"APIResource: Failed to report api_requests metrics,error:{err}")

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
            return f"{self.module_name}-{self.label}"
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

    def handle_stream_response(self, response):
        # 处理流式响应
        def event_stream():
            for line in response.iter_lines():
                if not line:
                    continue

                result = line.decode("utf-8") + "\n\n"
                yield result

        # 返回 StreamingHttpResponse
        sr = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        return sr
