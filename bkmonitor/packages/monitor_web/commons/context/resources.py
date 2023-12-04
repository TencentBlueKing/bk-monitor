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
from django.middleware.csrf import get_token

from bkm_space.api import SpaceApi
from bkmonitor.models import ActionConfig
from bkmonitor.utils.request import get_request
from bkmonitor.views import serializers
from common.context_processors import get_full_context
from common.log import logger
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from fta_web.tasks import run_init_builtin_action_config
from monitor_web.strategies.built_in import run_build_in


class GetContextResource(Resource):
    """
    获取业务下的结果表列表（包含全业务）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        space_uid = serializers.CharField(required=False, default="")
        context_name = serializers.CharField(required=False)
        with_biz_id = serializers.BooleanField(required=False, default=False)

        def validate(self, attrs):
            if not attrs.get("space_uid", "") and attrs["bk_biz_id"]:
                attrs["with_biz_id"] = True
                return attrs
            if attrs.get("space_uid"):
                bk_biz_id = None
                try:
                    space = SpaceApi.get_space_detail(attrs["space_uid"])
                    bk_biz_id = space.bk_biz_id
                except BKAPIError as e:
                    logger.exception(f"获取空间信息({attrs['space_uid']})失败：{e}")
                    if settings.DEMO_BIZ_ID:
                        bk_biz_id = settings.DEMO_BIZ_ID

                if bk_biz_id:
                    attrs["bk_biz_id"] = bk_biz_id
                    attrs["with_biz_id"] = True

            return attrs

    def perform_request(self, validated_request_data):
        request = get_request()
        context_name = validated_request_data.get("context_name", None)
        # 获取csrf_token值无需获取context，提前返回
        if context_name and context_name == "csrf_token":
            return {context_name: get_token(request)}

        cc_biz_id = None
        if validated_request_data["with_biz_id"]:
            request.biz_id = cc_biz_id = validated_request_data["bk_biz_id"]

        context = get_full_context(request)

        result = {key: context[key] for key in context if key not in ["gettext", "_"]}

        result["PLATFORM"] = {key: getattr(context["PLATFORM"], key) for key in ["ce", "ee", "te"]}
        result["LANGUAGES"] = dict(result["LANGUAGES"])

        result["csrf_token"] = get_token(request)

        if context_name and context_name in result:
            return {context_name: result[context_name]}

        if validated_request_data["with_biz_id"] and settings.ENVIRONMENT != "development":
            # 创建默认内置策略
            run_build_in(int(cc_biz_id))

            # 创建k8s内置策略
            run_build_in(int(cc_biz_id), mode="k8s")
            if (
                settings.ENABLE_DEFAULT_STRATEGY
                and int(cc_biz_id) > 0
                and not ActionConfig.origin_objects.filter(bk_biz_id=cc_biz_id, is_builtin=True).exists()
            ):
                logger.warning("home run_init_builtin_action_config")
                # 如果当前页面没有出现内置套餐，则会进行快捷套餐的初始化
                try:
                    run_init_builtin_action_config.delay(cc_biz_id)
                except Exception as error:
                    # 直接忽略
                    logger.exception("run_init_builtin_action_config failed ", str(error))
            # TODO 先关闭，后面稳定了直接打开
            # if not AlertAssignGroup.origin_objects.filter(bk_biz_id=cc_biz_id, is_builtin=True).exists():
            #     # 如果当前页面没有出现内置的规则组
            #     run_init_builtin_assign_group(cc_biz_id)

        return result
