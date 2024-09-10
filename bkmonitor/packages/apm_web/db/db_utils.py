# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from opentelemetry.semconv.resource import ResourceAttributes

from apm_web.constants import OPERATOR_MAP
from apm_web.handlers.db_handler import DbComponentHandler
from constants.apm import OtlpKey


def get_offset(params):
    page = params.get("page", 1)
    page_size = params.get("page_size", 10)
    return (page - 1) * page_size


def build_filter_params(filters):
    res = []
    for k, v in filters.items():
        if v == "undefined":
            continue

        res.append({"key": k, "op": "=", "value": v if isinstance(v, list) else [v]})

    return res


def get_service_from_params(filters):
    """从 filters 中获取服务名称"""
    return next(
        (i["value"][0] for i in filters if i["key"] == OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)),
        None,
    )


def transform_param(params: list) -> list:
    """
    参数转化
    :param params: 参数
    :return:
    """

    return [{"operator": OPERATOR_MAP.get(item["op"]), "key": item["key"], "value": item["value"]} for item in params]


def build_db_param(validated_data):
    """
    构建查询条件
    :param validated_data:
    :return:
    """

    params = build_filter_params(validated_data["filter_params"])

    service_name = get_service_from_params(params)
    if not service_name:
        raise ValueError(f"过滤参数中没有指定服务名称(resource.service.name): {[i['key'] for i in params]}")

    DbComponentHandler.build_component_filter_params(
        validated_data["bk_biz_id"],
        validated_data["app_name"],
        service_name,
        params,
        validated_data.get("component_instance_id"),
    )
    # 去除重复的查询条件
    filter_params = transform_param(params)

    return filter_params
