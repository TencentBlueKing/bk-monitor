"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import os
from bkstorages.backends.bkrepo import BKGenericRepoClient
from core.drf_resource import Resource
from rest_framework import serializers
from django.conf import settings

logger = logging.getLogger(__name__)

# 是否启用制品库能力
if os.getenv("USE_BKREPO", os.getenv("BKAPP_USE_BKREPO", "")).lower() == "true":
    client = BKGenericRepoClient(
        bucket=settings.AI_BKREPO_BUCKET,
        project=settings.AI_BKREPO_PROJECT,
        username=settings.BKREPO_USERNAME,
        password=settings.BKREPO_PASSWORD,
        endpoint_url=settings.BKREPO_ENDPOINT_URL,
    )


class ListRepoDirResource(Resource):
    """
    拉取制品库下的目录和文件列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        key_prefix = serializers.CharField(required=False, label="路径", default="/")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info(
            "ListRepoDirResource: try to list repo dir, bk_biz_id->[%s], key_prefix->[%s]",
            bk_biz_id,
            validated_request_data["key_prefix"],
        )
        return client.list_dir(validated_request_data["key_prefix"])


class DownloadRepoFileResource(Resource):
    """
    下载制品库下的文件 -- 当前仅支持URL模式
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        key = serializers.CharField(required=True, label="文件路径")
        expires = serializers.IntegerField(required=False, label="过期时间(秒)", default=60)

    def perform_request(self, validated_request_data):
        key = validated_request_data["key"]
        expires = validated_request_data["expires"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info("DownloadRepoFileResource: try to download repo file, bk_biz_id->[%s], key->[%s]", bk_biz_id, key)
        download_url = client.generate_presigned_url(key=key, expires_in=expires)

        return download_url
