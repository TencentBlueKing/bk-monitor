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


from django.conf import settings

from bkmonitor.views import serializers
from core.drf_resource.base import Resource

# 用户白皮书在文档中心的根路径
DOCS_USER_GUIDE_ROOT = "监控平台"

DOCS_LIST = ["产品白皮书", "应用运维文档", "开发架构文档"]

DEFAULT_DOC = DOCS_LIST[0]


class GetDocLinkResource(Resource):
    """
    获取文档链接
    """

    class RequestSerializer(serializers.Serializer):
        md_path = serializers.CharField(required=True, label="文档路径(md_path)")

    def perform_request(self, validated_request_data):
        md_path = validated_request_data["md_path"].strip("/")
        if not (md_path.split("/", 1)[0] in DOCS_LIST or md_path.startswith(DOCS_USER_GUIDE_ROOT)):
            # 自动补全默认使用产品白皮书
            md_path = "/".join([DOCS_USER_GUIDE_ROOT, DEFAULT_DOC, md_path])
        doc_url = f"{settings.BK_DOCS_SITE_URL.rstrip('/')}/markdown/{md_path.lstrip('/')}"
        return doc_url
