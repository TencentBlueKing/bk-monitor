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
from common.context_processors import get_context as _get_context
from django.middleware.csrf import get_token

from bkm_space.api import SpaceApi
from bkmonitor.utils.request import get_request
from bkmonitor.views import serializers
from core.drf_resource.base import Resource


class GetContextResource(Resource):
    """
    获取业务下的结果表列表（包含全业务）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        space_uid = serializers.CharField(required=False, default="")
        context_name = serializers.CharField(required=False)

        def validate(self, attrs):
            if not attrs.get("space_uid", ""):
                if not attrs["bk_biz_id"]:
                    raise ValueError("bk_biz_id or space_uid not found")
                return attrs
            space = SpaceApi.get_space_detail(attrs["space_uid"])
            attrs["bk_biz_id"] = space.bk_biz_id
            return attrs

    def perform_request(self, validated_request_data):
        request = get_request()
        request.biz_id = validated_request_data["bk_biz_id"]
        context_name = validated_request_data.get("context_name", None)
        # 获取csrf_token值无需获取context，提前返回
        if context_name and context_name == "csrf_token":
            return {context_name: get_token(request)}

        context = _get_context(request)

        result = {
            key.upper(): context[key]
            for key in context
            if key
            in [
                "APP_CODE",
                "SITE_URL",
                "STATIC_URL",
                "DOC_HOST",
                "BK_DOCS_SITE_URL",
                "MIGRATE_GUIDE_URL",
                "BK_JOB_URL",
                "BK_BCS_URL",
                "CSRF_COOKIE_NAME",
                "UTC_OFFSET",
                "is_superuser",
                "STATIC_VERSION",
                "AGENT_SETUP_URL",
                "RT_TABLE_PREFIX_VALUE",
                "NICK",
                "uin",
                "AVATAR",
                "APP_PATH",
                "BK_URL",
                "ENABLE_MESSAGE_QUEUE",
                "MESSAGE_QUEUE_DSN",
                "CE_URL",
                "MAX_AVAILABLE_DURATION_LIMIT",
                "BK_CC_URL",
                "BKLOGSEARCH_HOST",
                "MAIL_REPORT_BIZ",
                "BK_NODEMAN_HOST",
                "ENABLE_GRAFANA",
                "PAGE_TITLE",
                "GRAPH_WATERMARK",
                "COLLECTING_CONFIG_FILE_MAXSIZE",
                "TAM_ID",
                "BK_PAAS_HOST",
                "ENABLE_APM",
                "ENABLE_AIOPS",
                "BK_BIZ_LIST",
                "BK_BIZ_ID",
                "SPACE_INTRODUCE",
                "SPACE_LIST",
                "MONITOR_MANAGERS",
                "CLUSTER_SETUP_URL",
                "UPTIMECHECK_OUTPUT_FIELDS",
                "HOST_DATA_FIELDS",
                "SHOW_REALTIME_STRATEGY",
                "APM_EBPF_ENABLED",
            ]
        }

        # result["BK_BIZ_LIST"] = [
        #     {
        #         "id": bk_biz_id,
        #         "text": f"[{bk_biz_id}] {context['cc_biz_names'][bk_biz_id]}",
        #         "is_demo": bk_biz_id == int(settings.DEMO_BIZ_ID),
        #     }
        #     for bk_biz_id in context["cc_biz_names"]
        # ]

        result["PLATFORM"] = {key: getattr(context["PLATFORM"], key) for key in ["ce", "ee", "te"]}

        # biz_id_list = resource.cc.get_app_ids_by_user(request.user)
        # if biz_id_list:
        #
        #     bk_biz_id = request.session.get("bk_biz_id") or request.COOKIES.get("bk_biz_id")
        #     if bk_biz_id not in biz_id_list:
        #         bk_biz_id = biz_id_list[0]
        #
        #     result["BK_BIZ_ID"] = int(bk_biz_id)

        result["csrf_token"] = get_token(request)
        # 空间列表
        # result["SPACE_LIST"] = resource.commons.list_spaces()
        # result["SPACE_INTRODUCE"] = resource.commons.space_introduce(bk_biz_id=result["BK_BIZ_ID"])
        if context_name and context_name in result:
            return {context_name: result[context_name]}
        return result
