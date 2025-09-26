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


from django.conf import settings
from django.utils.translation import get_language

from bkmonitor.views import serializers
from core.drf_resource.base import Resource

DOCS_LIST = ["产品白皮书", "应用运维文档", "开发架构文档"]

DEFAULT_DOC = DOCS_LIST[0]

PATH_MAPPING = {
    DEFAULT_DOC: "UserGuide",
    "应用运维文档": "Operation",
    "开发架构文档": "Architecture",
}


def make_prefix(doc_name):
    lang = "EN" if get_language() == "en" else "ZH"
    return (
        f"{settings.BK_DOCS_SITE_URL.rstrip('/')}/markdown/{lang}/"
        f"Monitor/{settings.BK_DOC_VERSION}/{PATH_MAPPING[doc_name]}/"
    )


class GetDocLinkResource(Resource):
    """
    获取文档链接
    """

    class RequestSerializer(serializers.Serializer):
        md_path = serializers.CharField(required=True, label="文档路径(md_path)")

    def perform_request(self, validated_request_data):
        md_path = validated_request_data["md_path"].strip("/")
        for doc_name in DOCS_LIST:
            if doc_name in md_path:
                break
        else:
            doc_name = DEFAULT_DOC
        prefix = make_prefix(doc_name)
        suffix = md_path.split(doc_name)[-1].lstrip("/")
        return prefix + suffix


class GetLinkMappingResource(Resource):
    """
    获取文档链接(新)
    返回数据格式:
    {
        "traceDoc": {
            "type": "splice" / "link",
            "value": "path/to/doc.md" / "{FULL_LINK}"
        }
    }
    Key 为链接名称
    Value 为链接配置
        Type: 可选值为 splice 、 link
        Value:
            Type = splice: 为文档拼接中心拼接路径
            Type = link: 为完成 http 链接
    新增链接时，需要与前端约定 Key 值。
    根据 Key 跳转链接时，前端先获取接口返回的 LinkMap 中是否有此Key，不存在的话再取前端存储的 LinkMap 进行处理。
    """

    def perform_request(self, validated_request_data):
        valid_types = ["splice", "link"]
        return {key: config for key, config in settings.DOC_LINK_MAPPING.items() if config.get("type") in valid_types}
