"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest
from rest_framework import serializers

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.user import get_admin_username
from core.drf_resource.contrib.api import APIResource
from core.errors.alarm_backends import EmptyAssigneeError
from core.errors.api import BKAPIError


class SopsBaseResource(APIResource, metaclass=abc.ABCMeta):
    module_name = "sops"

    @property
    def base_url(self):
        if settings.BKSOPS_API_BASE_URL:
            return settings.BKSOPS_API_BASE_URL

        if self.use_apigw:
            return f"{settings.BK_COMPONENT_API_URL}/api/bk-sops/prod/"
        else:
            return f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/sops/"

    @property
    def use_apigw(self):
        return settings.BKSOPS_API_BASE_URL or settings.ENABLE_MULTI_TENANT_MODE

    def get_request_url(self, validated_request_data: dict[str, Any]) -> str:
        request_url: str = super().get_request_url(validated_request_data)

        # apigw模式下，需要渲染url参数
        if self.use_apigw:
            request_url = request_url.format(**validated_request_data)

        return request_url

    def perform_request(self, validated_request_data: dict[str, Any]):
        try:
            request = cast(HttpRequest, get_request())
            validated_request_data["_origin_user"] = request.user.username
        except Exception:
            pass
        assignee = validated_request_data.pop("assignee", None)
        if assignee is None:
            bk_tenant_id = get_request_tenant_id(peaceful=True) or bk_biz_id_to_bk_tenant_id(
                validated_request_data["bk_biz_id"]
            )
            assignee = [get_admin_username(bk_tenant_id)]
        if not assignee:
            self.report_api_failure_metric(
                error_code=EmptyAssigneeError.code, exception_type=EmptyAssigneeError.__name__
            )
            raise EmptyAssigneeError()
        for index, username in enumerate(assignee):
            self.bk_username = username
            try:
                return super().perform_request(validated_request_data)
            except BKAPIError as error:
                code = error.data.get("code")
                if code == 3599999:
                    # 标准运维权限不足的时候，继续运行
                    if index < len(assignee) - 1:
                        continue
                raise error

    def full_request_data(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        validated_request_data = super().full_request_data(validated_request_data)
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

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/get_user_project_detail/{bk_biz_id}/"
        return "get_user_project_detail"

    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")


class GetTemplateListResource(SopsBaseResource):
    """
    业务模板列表
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/get_template_list/{bk_biz_id}/"
        return "get_template_list"

    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        template_source = serializers.CharField(label="模板类型", required=False)


class GetTemplateInfoResource(SopsBaseResource):
    """
    流程详情
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/get_template_info/{template_id}/{bk_biz_id}/"
        return "get_template_info"

    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        template_id = serializers.IntegerField(label="模板模板ID")
        template_source = serializers.CharField(label="模板类型", required=False)


class PreviewTaskTreeIResource(SopsBaseResource):
    """
    流程详情
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/preview_task_tree/{bk_biz_id}/{template_id}/"
        return "preview_task_tree"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        template_id = serializers.IntegerField(label="模板模板ID")


class CreateTaskResource(SopsBaseResource):
    """
    作业列表
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/create_task/{template_id}/{bk_biz_id}/"
        return "create_task"

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

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/start_task/{task_id}/{bk_biz_id}/"
        return "start_task"

    method = "post"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        task_id = serializers.IntegerField(label="任务ID", required=True)
        assignee = serializers.ListField(label="执行人", required=False, child=serializers.CharField())


class GetTaskStatusResource(SopsBaseResource):
    """
    获取任务状态
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/get_task_status/{task_id}/{bk_biz_id}/"
        return "get_task_status"

    method = "get"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        task_id = serializers.IntegerField(label="任务ID", required=True)


class ImportProjectTemplate(SopsBaseResource):
    """
    导入流程
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/import_project_template/{bk_biz_id}/"
        return "import_project_template"

    method = "post"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        project_id = serializers.IntegerField(label="项目ID", required=True)
        template_data = serializers.CharField(label="模版的编码", required=True)


class GetCommonTemplateListResource(SopsBaseResource):
    """
    获取公共流程列表
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/get_common_template_list/"
        return "get_common_template_list"

    method = "GET"


class GetCommonTemplateInfoResource(SopsBaseResource):
    """
    获取公共流程详情
    """

    @property
    def action(self) -> str:
        if self.use_apigw:
            return "/system/get_common_template_info/{template_id}/"
        return "get_common_template_info"

    method = "GET"

    class RequestSerializer(serializers.Serializer):
        template_id = serializers.IntegerField(label="模板ID", required=True)
