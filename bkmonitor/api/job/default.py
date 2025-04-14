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

import six
from django.conf import settings
from rest_framework import serializers

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils.request import get_request
from core.drf_resource.contrib.api import APIResource
from core.errors.alarm_backends import EmptyAssigneeError
from core.errors.iam import APIPermissionDeniedError


class IPSerializer(serializers.Serializer):
    """
    IP参数
    """

    ip = serializers.IPAddressField(required=True, label="IP地址")
    bk_cloud_id = serializers.IntegerField(required=True, label="云区域ID")


class JobBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = "%s/api/c/compapi/v2/job/" % settings.BK_COMPONENT_API_URL
    module_name = "job"

    def perform_request(self, params):
        try:
            params["_origin_user"] = get_request().user.username
        except Exception:
            pass

        assignee = params.pop("assignee", None)
        if assignee is None:
            assignee = [settings.COMMON_USERNAME]

        if not assignee:
            self.report_api_failure_metric(
                error_code=EmptyAssigneeError.code, exception_type=EmptyAssigneeError.__name__
            )
            raise EmptyAssigneeError()

        for index, username in enumerate(assignee):
            self.bk_username = username
            try:
                return super(JobBaseResource, self).perform_request(params)
            except APIPermissionDeniedError as error:
                self.report_api_failure_metric(
                    error_code=getattr(error, 'code', 0), exception_type=APIPermissionDeniedError.__name__
                )
                # 权限不足的时候，继续运行
                if index < len(assignee) - 1:
                    continue
                raise error

    def full_request_data(self, validated_request_data):
        validated_request_data = super(JobBaseResource, self).full_request_data(validated_request_data)
        # 业务id判定
        if "bk_biz_id" not in validated_request_data:
            return validated_request_data
        # 业务id关联
        bk_biz_id = int(validated_request_data["bk_biz_id"])
        validated_request_data["bk_biz_id"] = validate_bk_biz_id(bk_biz_id)
        return validated_request_data


class JobV3BaseResource(JobBaseResource):
    """
    作业平台V3
    """

    base_url = "%s/api/c/compapi/v2/jobv3/" % settings.BK_COMPONENT_API_URL
    module_name = "jobv3"


class GetJobListResource(JobBaseResource):
    """
    作业列表
    """

    action = "get_job_list"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")


class GetJobDetailResource(JobBaseResource):
    """
    作业详情
    """

    action = "get_job_detail"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        bk_job_id = serializers.IntegerField(label="作业模板ID")


class FastExecuteScriptResource(JobV3BaseResource):
    """
    快速执行脚本
    """

    action = "fast_execute_script"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_scope_type = serializers.CharField(label="资源范围类型")
        bk_scope_id = serializers.CharField(label="资源范围ID")
        script_content = serializers.CharField(label="脚本内容")
        script_param = serializers.CharField(label="脚本参数", default="", allow_blank=True)
        target_server = serializers.DictField(label="目标服务")
        script_language = serializers.IntegerField(label="脚本语言", default=1)
        account_alias = serializers.CharField(label="执行账户")


class ExecuteJobResource(JobBaseResource):
    """
    执行作业方案
    """

    action = "execute_job_plan"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_plan_id = serializers.IntegerField(label="作业执行方案")
        assignee = serializers.ListField(label="执行人", required=False, child=serializers.CharField())
        global_var_list = serializers.ListField(child=serializers.JSONField(), label="全局变量")


class GetJobPlanListResource(JobV3BaseResource):
    """
    作业列表
    """

    action = "get_job_plan_list"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")


class GetJobPlanDetailResource(JobV3BaseResource):
    """
    作业详情
    """

    action = "get_job_plan_detail"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_plan_id = serializers.IntegerField(label="作业模板ID")


class ExecuteJobPlanResource(JobV3BaseResource):
    """
    执行作业方案
    """

    action = "execute_job_plan"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_plan_id = serializers.IntegerField(label="作业执行方案")
        assignee = serializers.ListField(label="执行人", required=False, child=serializers.CharField())
        global_var_list = serializers.ListField(child=serializers.JSONField(), label="全局变量")


class GetJobInstanceStatusResource(JobV3BaseResource):
    """
    获取任务执行状态
    """

    action = "get_job_instance_status"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_instance_id = serializers.IntegerField(label="任务ID")
        return_ip_result = serializers.BooleanField(label="是否返回每个主机上的任务详情", required=False, default=False)


class GetJobInstanceLogResource(JobBaseResource):
    """
    获取IP的任务状态
    """

    action = "get_job_instance_log"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_instance_id = serializers.IntegerField(label="任务ID")


class GetJobInstanceIpLogResource(JobV3BaseResource):
    """
    获取主机的任务日志V3（Job - 3.7.x版本支持host_id）
    """

    action = "batch_get_job_instance_ip_log"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_instance_id = serializers.IntegerField(label="作业实例ID")
        step_instance_id = serializers.IntegerField(label="步骤实例ID")
        host_id_list = serializers.ListField(
            required=False, label="主机ID列表", allow_empty=True, child=serializers.IntegerField()
        )
        ip_list = IPSerializer(required=False, label="IP列表", many=True, allow_empty=True)


class PushConfigFileResource(JobBaseResource):
    """
    分发配置文件
    """

    action = "push_config_file"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class FileSerializer(serializers.Serializer):
            file_name = serializers.CharField(required=True, label="文件名称")
            content = serializers.CharField(required=True, label="文件内容")

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        ip_list = IPSerializer(required=True, many=True)
        file_list = FileSerializer(required=True, many=True)
        file_target_path = serializers.CharField(required=True, label="目标路径")
        account = serializers.CharField(default="root", label="执行账户")

    class ResponseSerializer(serializers.Serializer):
        job_instance_id = serializers.IntegerField(label="任务ID")
