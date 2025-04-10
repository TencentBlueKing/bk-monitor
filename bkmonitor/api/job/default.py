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
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.request import get_request
from core.drf_resource.contrib.api import APIResource
from core.errors.alarm_backends import EmptyAssigneeError
from core.errors.iam import APIPermissionDeniedError


class JobBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = "%s/api/c/compapi/v2/jobv3/" % settings.BK_COMPONENT_API_URL
    module_name = "bk-job"

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
