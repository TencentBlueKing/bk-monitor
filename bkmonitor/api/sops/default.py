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
import os

import six
from django.conf import settings
from rest_framework import serializers

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils.request import get_request
from core.drf_resource.contrib.api import APIResource
from core.errors.alarm_backends import EmptyAssigneeError
from core.errors.api import BKAPIError


class SopsBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = os.path.join(settings.BK_COMPONENT_API_URL, "api/c/compapi/v2/sops/")
    module_name = "sops"

    def perform_request(self, params):
        try:
            params["_origin_user"] = get_request().user.username
        except Exception:
            pass
        assignee = params.pop("assignee", None)
        if assignee is None:
            assignee = [settings.COMMON_USERNAME]
        if not assignee:
            raise EmptyAssigneeError()
        for index, username in enumerate(assignee):
            self.bk_username = username
            try:
                return super(SopsBaseResource, self).perform_request(params)
            except BKAPIError as error:
                code = error.data.get("code")
                if code == 3599999:
                    # 标准运维权限不足的时候，继续运行
                    if index < len(assignee) - 1:
                        continue
                raise error

    def full_request_data(self, validated_request_data):
        validated_request_data = super(SopsBaseResource, self).full_request_data(validated_request_data)
        # 业务id判定
        if "bk_biz_id" not in validated_request_data:
            return validated_request_data
        # 业务id关联
        bk_biz_id = int(validated_request_data["bk_biz_id"])
        validated_request_data["bk_biz_id"] = validate_bk_biz_id(bk_biz_id)
        return validated_request_data


class GetUserProjectDetailResource(SopsBaseResource):
    """
    获取用户的项目详情
    """

    action = "get_user_project_detail"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")


class GetTemplateListResource(SopsBaseResource):
    """
    业务模板列表
    """

    action = "get_template_list"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        template_source = serializers.CharField(label="模板类型", required=False)


class GetTemplateInfoResource(SopsBaseResource):
    """
    流程详情
    """

    action = "get_template_info"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        template_id = serializers.IntegerField(label="模板模板ID")
        template_source = serializers.CharField(label="模板类型", required=False)


class PreviewTaskTreeIResource(SopsBaseResource):
    """
    流程详情
    """

    action = "preview_task_tree"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        template_id = serializers.IntegerField(label="模板模板ID")


class CreateTaskResource(SopsBaseResource):
    """
    作业列表
    """

    action = "create_task"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        template_id = serializers.IntegerField(label="模板ID", required=True)
        name = serializers.CharField(label="任务名称", required=True)
        template_source = serializers.CharField(label="模板类型", required=False)
        constants = serializers.JSONField(label="创建任务参数", required=False)
        assignee = serializers.ListField(label="执行人", required=False, child=serializers.CharField())


class StartTaskResource(SopsBaseResource):
    """
    启动任务
    """

    action = "start_task"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        task_id = serializers.IntegerField(label="任务ID", required=True)
        assignee = serializers.ListField(label="执行人", required=False, child=serializers.CharField())


class GetTaskStatusResource(SopsBaseResource):
    """
    获取任务状态
    """

    action = "get_task_status"
    method = "get"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        task_id = serializers.IntegerField(label="任务ID", required=True)


class ImportProjectTemplate(SopsBaseResource):
    """
    导入流程
    """

    action = "import_project_template"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        project_id = serializers.IntegerField(label="业务ID", required=True)
        template_data = serializers.CharField(label="模版的编码", required=True)
