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

import six
from django.conf import settings
from rest_framework import serializers

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.user import get_admin_username
from core.drf_resource.contrib.api import APIResource
from core.errors.alarm_backends import EmptyAssigneeError
from core.errors.iam import APIPermissionDeniedError


class JobBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    def use_apigw(self):
        """
        是否使用apigw
        """
        return settings.ENABLE_MULTI_TENANT_MODE or settings.JOB_USE_APIGW

    @property
    def base_url(self):
        if self.use_apigw():
            base_url = settings.JOB_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-job/prod/"
            return f"{base_url}api/v3/system/"
        return f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/jobv3/"

    module_name = "bk-job"

    def perform_request(self, params):
        try:
            params["_origin_user"] = get_request().user.username
        except Exception:
            pass

        assignee = params.pop("assignee", None)
        if assignee is None:
            assignee = [get_admin_username(get_request_tenant_id())]

        if not assignee:
            self.report_api_failure_metric(
                error_code=EmptyAssigneeError.code, exception_type=EmptyAssigneeError.__name__
            )
            raise EmptyAssigneeError()

        for index, username in enumerate(assignee):
            self.bk_username = username
            try:
                return super().perform_request(params)
            except APIPermissionDeniedError as error:
                self.report_api_failure_metric(
                    error_code=getattr(error, "code", 0), exception_type=APIPermissionDeniedError.__name__
                )
                # 权限不足的时候，继续运行
                if index < len(assignee) - 1:
                    continue
                raise error

    def full_request_data(self, validated_request_data):
        validated_request_data = super().full_request_data(validated_request_data)
        # 业务id判定
        if "bk_biz_id" not in validated_request_data:
            return validated_request_data
        # 业务id关联
        bk_biz_id = int(validated_request_data["bk_biz_id"])
        validated_request_data["bk_biz_id"] = validate_bk_biz_id(bk_biz_id)
        return validated_request_data


class GetJobPlanListResource(JobBaseResource):
    """
    作业方案列表
    """

    action = "get_job_plan_list"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params):
        job_plans = batch_request(
            super().perform_request,
            params,
            limit=1000,
            get_count=lambda result: result.get("total"),
            get_data=lambda result: result.get("data", []),
            thread_num=5,
            app="job",
        )
        return job_plans


class GetJobListResource(GetJobPlanListResource):
    """
    作业方案列表（适配旧的调用）
    """

    def perform_request(self, params):
        result = super().perform_request(params)
        for plan in result:
            plan["bk_job_id"] = plan["id"]
        return result


class GetJobPlanDetailResource(JobBaseResource):
    """
    作业方案详情
    """

    action = "get_job_plan_detail"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_plan_id = serializers.IntegerField(label="作业模板ID")


class ExecuteJobPlanResource(JobBaseResource):
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


class GetJobInstanceStatusResource(JobBaseResource):
    """
    获取任务执行状态
    """

    action = "get_job_instance_status"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        job_instance_id = serializers.IntegerField(label="任务ID")
        return_ip_result = serializers.BooleanField(label="是否返回每个主机上的任务详情", required=False, default=False)


class FastExecuteScriptResource(JobBaseResource):
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


class GetJobInstanceIpLogResource(JobBaseResource):
    """
    获取主机的任务日志V3
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

        class IPSerializer(serializers.Serializer):
            """
            IP参数
            """

            ip = serializers.IPAddressField(required=True, label="IP地址")
            bk_cloud_id = serializers.IntegerField(required=True, label="云区域ID")

        ip_list = IPSerializer(required=False, label="IP列表", many=True, allow_empty=True)
