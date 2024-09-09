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

import six
from django.db import models
from django.utils.translation import ugettext as _
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource.exceptions import CustomException, record_exception
from core.drf_resource.tasks import run_perform_request
from core.drf_resource.tools import (
    format_serializer_errors,
    get_serializer_fields,
    render_schema,
)

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


__doc__ = """
Non-ORM for DRF 的架构：
serializers -> resources -> views

各模块的职责
serializers: 负责请求数据与返回数据的校验，包括简单的数据渲染
resources: 此处编写业务逻辑（工作重点）
views: 定义请求方法、使用到的Resource、是否分页、鉴权等配置（几乎没有代码量）

Resource定义：
对传入的数据进行特定处理并返回处理后的数据，这样的处理单元称为Resource
可以通过继承Resource类来实现自定义的Resource

Resource的执行流程：
1. 新建Resource实例
2. 若用户未手动设置需要用到的RequestSerializer及ResponseSerializer，
   则根据命名规则自动查找可用的serializers，并进行设置
3. 调用request方法，并传入请求参数(request_data)
4. 调用request_serializer(如果有)对request_data进行数据校验，
   返回validated_request_data
5. 用户自行实现perform_request方法，根据validated_request_data，通过用户编写的业务
   逻辑，生成返回结果response_data
6. 调用response_serializer(如果有)对response_data进行数据校验，
   返回validated_response_data
7. 将validated_response_data交给上层的views，由views进行最后的数据渲染及返回到前端

为了Resource能够正确搜索到其对应的serializers，需要遵循以下命名规则：
某Resource名称为: TestResource
其对应的request serializer应命名为: TestRequestSerializer
其对应的response serializer应命名为: TestResponseSerializer

"""


class Resource(six.with_metaclass(abc.ABCMeta, object)):
    RequestSerializer = None
    ResponseSerializer = None

    # 提供一个serializers模块，在实例化某个Resource时，在该模块内自动查找符合命名
    # 规则的serializers，并进行自动配置
    serializers_module = None

    # 数据是否为对象的列表
    many_request_data = False
    many_response_data = False

    # 支持记录请求参数(settings开启：ENABLE_RESOURCE_DATA_COLLECT后，
    # 记录所有`support_data_collect`为True的resource请求)
    support_data_collect = True

    def __init__(self, context=None):
        self.RequestSerializer, self.ResponseSerializer = self._search_serializer_class()

        self.context = context
        self._task_manager = None

    def __call__(self, *args, **kwargs):
        # thread safe
        tmp_resource = self.__class__()
        if hasattr(self, "stage"):
            tmp_resource.set_stage(self.stage)
        from core.drf_resource.models import ResourceData

        return ResourceData.objects.request(tmp_resource, args, kwargs)

    @property
    def request_serializer(self):
        """
        :rtype: serializers.Serializer
        """
        if not hasattr(self, "_request_serializer"):
            msg = "You must call `.validate_request_data()` before accessing `.request_serializer`."
            raise AssertionError(msg)
        return self._request_serializer

    @property
    def response_serializer(self):
        """
        :rtype: serializers.Serializer
        """
        if not hasattr(self, "_response_serializer"):
            msg = "You must call `.validate_response_data()` before accessing `.response_serializer`."
            raise AssertionError(msg)
        return self._response_serializer

    @classmethod
    def get_resource_name(cls):
        return f"{cls.__module__}.{cls.__qualname__}"

    @classmethod
    def _search_serializer_class(cls):
        """
        搜索该Resource对应的两个Serializer
        """

        # 若类的内部声明了RequestSerializer和ResponseSerializer，则优先使用
        request_serializer_class = cls.RequestSerializer
        response_serializer_class = cls.ResponseSerializer

        # 若类中没有声明，则对指定模块进行搜索
        resource_name = cls.get_resource_name()
        request_serializer_class_name = "%sRequestSerializer" % resource_name
        response_serializer_class_name = "%sResponseSerializer" % resource_name

        if cls.serializers_module:
            if not request_serializer_class:
                request_serializer_class = getattr(cls.serializers_module, request_serializer_class_name, None)

            if not response_serializer_class:
                response_serializer_class = getattr(cls.serializers_module, response_serializer_class_name, None)

        return request_serializer_class, response_serializer_class

    @abc.abstractmethod
    def perform_request(self, validated_request_data):
        """
        此处为Resource的业务逻辑，由子类实现
        将request_data通过一定的逻辑转化为response_data

        example:
            return validated_request_data
        """
        raise NotImplementedError

    def validate_request_data(self, request_data):
        """
        校验请求数据
        """
        self._request_serializer = None
        if not self.RequestSerializer:
            return request_data

        # model类型的数据需要特殊处理
        if isinstance(request_data, (models.Model, models.QuerySet)):
            request_serializer = self.RequestSerializer(request_data, many=self.many_request_data)
            self._request_serializer = request_serializer
            return request_serializer.data
        else:
            request_serializer = self.RequestSerializer(data=request_data, many=self.many_request_data)
            self._request_serializer = request_serializer
            is_valid_request = request_serializer.is_valid()
            if not is_valid_request:
                logger.error(
                    "Resource[{}] 请求参数格式错误：%s".format(self.get_resource_name()),
                    format_serializer_errors(request_serializer),
                )
                raise CustomException(
                    _("Resource[{}] 请求参数格式错误：{}").format(
                        self.get_resource_name(), format_serializer_errors(request_serializer)
                    )
                )
            return request_serializer.validated_data

    def validate_response_data(self, response_data):
        """
        校验返回数据
        """
        self._response_serializer = None
        if not self.ResponseSerializer:
            return response_data

        # model类型的数据需要特殊处理
        if isinstance(response_data, (models.Model, models.QuerySet)):
            response_serializer = self.ResponseSerializer(response_data, many=self.many_response_data)
            self._response_serializer = response_serializer
            return response_serializer.data
        else:
            response_serializer = self.ResponseSerializer(data=response_data, many=self.many_response_data)
            self._response_serializer = response_serializer
            is_valid_response = response_serializer.is_valid()
            if not is_valid_response:
                raise CustomException(
                    _("Resource[{}] 返回参数格式错误：{}").format(
                        self.get_resource_name(), format_serializer_errors(response_serializer)
                    )
                )
            return response_serializer.validated_data

    def request(self, request_data=None, **kwargs):
        """
        执行请求，并对请求数据和返回数据进行数据校验
        """
        with tracer.start_as_current_span(self.get_resource_name(), record_exception=False) as span:
            try:
                request_data = request_data or kwargs
                validated_request_data = self.validate_request_data(request_data)
                response_data = self.perform_request(validated_request_data)
                validated_response_data = self.validate_response_data(response_data)
                return validated_response_data
            except Exception as exc:  # pylint: disable=broad-except
                # Record the exception as an event
                record_exception(span, exc, out_limit=10)

                # Set status in case exception was raised
                span.set_status(
                    Status(
                        status_code=StatusCode.ERROR,
                        description=f"{type(exc).__name__}: {exc}",
                    )
                )
                raise

    def bulk_request(self, request_data_iterable=None, ignore_exceptions=False):
        """
        基于多线程的批量并发请求
        """
        if not isinstance(request_data_iterable, (list, tuple)):
            raise TypeError("'request_data_iterable' object is not iterable")

        pool = ThreadPool()
        futures = []
        for request_data in request_data_iterable:
            futures.append(pool.apply_async(self.request, args=(request_data,)))

        pool.close()
        pool.join()

        results = []
        exceptions = []
        for future in futures:
            try:
                results.append(future.get())
            except Exception as e:
                # 判断是否忽略错误
                if not ignore_exceptions:
                    raise e
                exceptions.append(e)
                results.append(None)

        # 如果全部报错，则必须抛出错误
        if exceptions and len(exceptions) == len(futures):
            raise exceptions[0]

        return results

    def update_state(self, state, message=None, data=None):
        """
        更新执行状态
        """
        state_message = "Async resource task running - {} [state=`{}` message=`{}` data=`{}`]".format(
            self.get_resource_name(), state, message, data
        )
        logger.info(state_message)

        if not self._task_manager:
            return

        meta = {
            "message": message,
            "data": data,
        }
        self._task_manager.update_state(state=state, meta=meta)

    def delay(self, request_data=None, **kwargs):
        """
        执行celery异步任务
        """
        request_data = request_data or kwargs
        return self.apply_async(request_data)

    def apply_async(self, request_data, **kwargs):
        """
        执行celery异步任务（高级）
        """
        async_task = run_perform_request.apply_async(args=(self, get_request_username(), request_data), **kwargs)
        return {"task_id": async_task.id}

    @classmethod
    def generate_doc(cls):
        request_serializer_class, response_serializer_class = cls._search_serializer_class()
        request_params = get_serializer_fields(request_serializer_class)
        response_params = get_serializer_fields(response_serializer_class)

        return {
            "request_params": render_schema(request_params),
            "response_params": render_schema(response_params, using_source=True),
        }

    @classmethod
    def etag(cls, request, *args, **kwargs):
        return

    @classmethod
    def last_modified(cls, request, *args, **kwargs):
        return
