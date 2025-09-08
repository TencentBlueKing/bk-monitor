# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
import os
from typing import Any, Dict

import yaml
from django import urls
from django.conf import settings
from rest_framework.test import APIRequestFactory
from yaml.parser import ParserError

from bkmonitor.utils.request import get_request
from core.drf_resource import APIResource
from core.errors.api import BKAPIError
from core.errors.common import HTTP404Error

logger = logging.getLogger(__name__)


__doc__ = """
    在监控后台API服务中，除了提供底层api服务外，还暴露了SaaS的部分业务逻辑接口。这些逻辑接口完全复用自SaaS。
    由于部分SaaS逻辑中，有针对监控后台的API调用，因此在后台API模式下，会出现循环调用的问题。
    Client -> ESB -> kernel_api ->do something(call api.metadata or api.monitor) -> ESB -> kernel_api
    当kernel api基于gunicorn的sync模式下，会概率造成worker的堵塞
    因此，封装虚拟api的resource，上层使用依然基于api调用，但实际执行的时候，判断调用角色是否是后台api，如果是api则不经过ESB，
    如果不是则正常走ESB调用
    注意： 不支持，monitor_v3.yaml 中dest_path 使用变量。
"""

IS_API_MODE = settings.ROLE == "api"
API_DEFINE: Dict[str, Dict[str, str]] = {}
GET_DATA_RESOURCES = {}

if settings.ROLE != "web":
    # client.get_ts_data -> esb -> query_api.GetTSDataResource
    # client.get_es_data -> esb -> kernel_api.GetEsDataViewSet.QueryEsResource -> query_api.GetEsDataResource
    from kernel_api.resource.query import QueryEsResource
    from query_api.resources import GetTSDataResource

    GET_DATA_RESOURCES = {
        "get_ts_data": GetTSDataResource,
        "get_es_data": QueryEsResource,
    }


class KernelAPIResource(APIResource):
    """
    自动选择api调用方式的API类型的Resource
    """

    def get_api_from_url(self, api_url):
        api_name = api_url.replace(self.base_url, "").strip("/")
        api_item = API_DEFINE.get(api_name, None)
        return api_name, api_item

    def perform_request(self, validated_request_data):
        if IS_API_MODE:
            return self.direct_request(validated_request_data)

        api_name, api_item = self.get_api_from_url(self.get_request_url(validated_request_data))
        if api_item and api_item.get("dest_path"):
            action = api_item["dest_path"].strip("/").rsplit("/", 1)[-1]
            # 后台时序数据拉取直联influxdb-proxy获取数据，避免经过esb序列化
            if action in GET_DATA_RESOURCES:
                return GET_DATA_RESOURCES[action]()(validated_request_data)
        return super(KernelAPIResource, self).perform_request(validated_request_data)

    def direct_request(self, validated_request_data):
        # 重要： 当前不支持action带模板变量的方式（当前kernel_api未使用）
        api_url = self.get_request_url(validated_request_data)
        api_name, api_item = self.get_api_from_url(api_url)
        if api_item is None:
            raise HTTP404Error(message="api [{}] not define in monitor_v3.yaml".format(api_name))

        dest_path = api_item["dest_path"]
        http_method = api_item["dest_http_method"]
        match_obj = urls.resolve(dest_path)
        factory = APIRequestFactory()

        if http_method.lower() == "get":
            request = factory.get(dest_path, data=validated_request_data)
        else:
            request = getattr(factory, http_method.lower())(
                dest_path,
                data=json.dumps(validated_request_data),
                content_type="application/json",
            )
        # 请求身份透传
        source_request = get_request(peaceful=True)
        if source_request:
            request.META["HTTP_BK_APP_CODE"] = source_request.META.get("HTTP_BK_APP_CODE")
            request.META["HTTP_BK_USERNAME"] = source_request.META.get("HTTP_BK_USERNAME")

        response = match_obj.func(request, **match_obj.kwargs)
        result_json = json.loads(response.rendered_content)

        if not result_json["result"]:
            msg = result_json.get("message", "")
            logger.error(
                "【Module: " + self.module_name + "】【Action: " + self.action + "】get error：%s",
                msg,
                extra=dict(module_name=self.module_name, url=api_url),
            )
            raise BKAPIError(system_name=self.module_name, url=self.action, result=result_json)

        # 渲染数据
        response_data = self.render_response_data(validated_request_data, result_json.get("data"))

        return response_data


def load_api_yaml():
    global API_DEFINE

    # 读取esb的api定义
    yaml_file_path = os.path.join(settings.BASE_DIR, "docs", "api", "monitor_v3.yaml")
    if not os.path.exists(yaml_file_path):
        logger.error("api configfile not found. [{}]".format(yaml_file_path))
        return
    with open(yaml_file_path, encoding="utf8") as yaml_fd:
        try:
            for api_item in yaml.load(yaml_fd, Loader=yaml.FullLoader):
                name = api_item["name"]
                API_DEFINE[name] = {
                    "dest_path": api_item["dest_path"],
                    "dest_http_method": api_item["dest_http_method"],
                }
        except ParserError:
            logger.error("api configfile is invalid. [{}]".format(yaml_file_path))

    # 读取apigw的api定义
    yaml_file_path = os.path.join(settings.BASE_DIR, "support-files", "apigw", "resources")
    sub_dir_paths = ["external/app", "internal/app", "external/user", "internal/user"]
    for sub_dir_path in sub_dir_paths:
        path = os.path.join(yaml_file_path, sub_dir_path)
        if not os.path.exists(path):
            continue

        # 遍历文件夹下的yaml文件
        for file_name in os.listdir(path):
            if not file_name.endswith(".yaml"):
                continue
            file_path = os.path.join(path, file_name)
            with open(file_path, encoding="utf8") as yaml_fd:
                api_config: Dict[str, Any] = yaml.load(yaml_fd, Loader=yaml.FullLoader)
                for api_path, api_item in api_config["paths"].items():
                    if "post" in api_item:
                        dest_http_method = "POST"
                    elif "get" in api_item:
                        dest_http_method = "GET"
                    else:
                        continue
                    API_DEFINE[api_path.strip("/")] = {
                        "dest_path": api_item[dest_http_method.lower()]["x-bk-apigateway-resource"]["backend"]["path"],
                        "dest_http_method": dest_http_method,
                    }


load_api_yaml()
