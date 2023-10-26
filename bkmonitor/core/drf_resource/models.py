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


import json
import logging
import random

import arrow
import six
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

ResourceNameCache = set()
ResourceNameCount = {}


class ResourceDataManager(models.Manager):
    @staticmethod
    def get_data_string(data):
        """
        数据转换为字符串，同时避免QuerySet查询
        """
        if isinstance(data, (dict, list, six.string_types, int)) or data is None:
            try:
                data_string = json.dumps(data)
            except Exception as e:
                data_string = str(e)
        else:
            data_string = str(type(data))
        return data_string

    def request(self, resource, args, kwargs):
        """
        请求并记录数据
        :type resource: Resource
        :type args: list
        :type kwargs: dict
        :return: Resource response
        """
        # 如果没有配置则退出
        if not (getattr(settings, "ENABLE_RESOURCE_DATA_COLLECT", False) and resource.support_data_collect):
            return resource.request(*args, **kwargs)

        resource_name = "{}.{}".format(resource.__class__.__module__, resource.__class__.__name__)
        # Resource首次访问必收集，否则采样
        if resource_name in ResourceNameCache:
            ratio = getattr(settings, "RESOURCE_DATA_COLLECT_RATIO", 0)
            if random.random() > ratio:
                return resource.request(*args, **kwargs)

        ResourceNameCache.add(resource_name)

        start_time = arrow.now().datetime
        request_str = self.get_data_string({"args": args, "kwargs": kwargs})
        response_str = ""
        try:
            response = resource.request(*args, **kwargs)
            # 请求/响应数据转换为字符串
            response_str = self.get_data_string(response)
            return response
        except Exception as err:
            logger.exception(err)
            response_str = str(err)
            raise err
        finally:
            end_time = arrow.now().datetime
            self.create(
                name=resource_name,
                start_time=start_time,
                end_time=end_time,
                response_data=response_str,
                request_data=request_str,
            )


class ResourceData(models.Model):
    """
    Resource请求数据
    """

    name = models.CharField("名称", max_length=128, db_index=True)
    start_time = models.DateTimeField("开始时间")
    end_time = models.DateTimeField("结束事件")
    request_data = models.TextField("请求参数")
    response_data = models.TextField("响应参数")

    objects = ResourceDataManager()

    class Meta:
        db_table = "resource_data"
