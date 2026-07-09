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

from django.conf import settings

from rest_framework import serializers

from core.drf_resource.contrib.api import APIResource


class IncidentBaseResource(APIResource, metaclass=abc.ABCMeta):
    module_name = "bk_incident"

    @property
    def base_url(self):
        if settings.BK_INCIDENT_APIGW_URL:
            return settings.BK_INCIDENT_APIGW_URL
        return f"{settings.BK_COMPONENT_API_URL}/api/incident-manager/prod/"

    def convert_bk_biz_id_list_to_scope_id_list(self, params, bk_biz_id_list):
        return [params.get("scope_type", "bkcc") + "_" + str(bk_biz_id) for bk_biz_id in bk_biz_id_list]

    def convert_bk_biz_id_to_scope_value(self, params):
        """
        将 bk_biz_id 转换为 scope_value

        :param params: 请求参数字典
        :return: 转换后的参数字典
        :raises ValueError: 当既没有提供 bk_biz_id 也没有提供 scope_value 时
        """
        # 验证至少提供了一个标识参数
        if "bk_biz_id" not in params and "scope_value" not in params:
            raise ValueError("必须提供 bk_biz_id 或 scope_value 其中之一")

        # 将 bk_biz_id 转换为 scope_value
        if "bk_biz_id" in params and "scope_value" not in params:
            params["scope_value"] = str(params.pop("bk_biz_id"))
        elif "bk_biz_id" in params and "scope_value" in params:
            params.pop("bk_biz_id")

        # 如果没有指定 scope_type，默认设置为 bkcc
        # TODO 后续支持BKCI & BKSAAS
        if "scope_value" in params and "scope_type" not in params:
            params["scope_type"] = "bkcc"

        return params

    def convert_scope_id_list(self, params):
        bk_biz_id_list = params.pop("bk_biz_id_list", [])

        if bk_biz_id_list:
            params["scope_id_list"] = self.convert_bk_biz_id_list_to_scope_id_list(params, bk_biz_id_list)

        bk_biz_id_config = params.pop("bk_biz_id_config", {})

        if bk_biz_id_config:
            if bk_biz_id_config.get("scope_id_list_open", []):
                bk_biz_id_config["scope_id_list_open"] = self.convert_bk_biz_id_list_to_scope_id_list(
                    params, bk_biz_id_config.get("scope_id_list_open", [])
                )

            if bk_biz_id_config.get("scope_id_list_close", []):
                bk_biz_id_config["scope_id_list_close"] = self.convert_bk_biz_id_list_to_scope_id_list(
                    params, bk_biz_id_config.get("scope_id_list_close", [])
                )

        params["scope_id_config"] = bk_biz_id_config

        return params

    def perform_request(self, validated_request_data):
        """
        重写请求执行方法，在发送请求前转换参数
        """
        # 转换 bk_biz_id 为 scope_value
        validated_request_data = self.convert_bk_biz_id_to_scope_value(validated_request_data)
        # 转换 bk_biz_id_list 为 scope_id_list
        validated_request_data = self.convert_scope_id_list(validated_request_data)
        return super().perform_request(validated_request_data)


class GetTemplateListResource(IncidentBaseResource):
    """
    拉取业务下的执行流程列表
    """

    action = "/incident/incident_event/list_space_template/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)


class GetTemplateInfoResource(IncidentBaseResource):
    """
    拉取业务下的执行流程模版信息(参数)
    """

    action = "/incident/incident_event/fetch_space_template/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")  # bkci
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        template_id = serializers.CharField(label="模版ID", required=True)


class CreateTaskResource(IncidentBaseResource):
    """
    创建故障分析任务
    """

    action = "/incident/incident_event/create_task/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        template_id = serializers.IntegerField(label="模版ID", required=True)
        constants = serializers.JSONField(label="创建任务参数", required=False)
        name = serializers.CharField(label="任务名称", required=False)
        source = serializers.CharField(label="任务来源", required=False,default="bk_monitor_debug")


class OperateTaskResource(IncidentBaseResource):
    """
    启动故障分析任务
    """

    action = "/incident/incident_event/operate_task/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.IntegerField(label="任务ID", required=True)
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)


class GetTaskStatusResource(IncidentBaseResource):
    """
    查询故障分析任务状态
    """

    action = "/incident/incident_event/get_task_stats/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.IntegerField(label="任务ID", required=True)
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)


class GetIncidentDiagnosisResource(IncidentBaseResource):
    """
    获取故障诊断面板数据(incident_diagnosis.sub_panels)

    替代旧的 api.bkdata.get_incident_analysis_results，由 incident_manager 聚合动态编排结果后返回。
    """

    action = "/incident/incident_analysis/get_incident_diagnosis/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        incident_id = serializers.IntegerField(label="故障ID", required=True)


class GetIncidentDetailResource(IncidentBaseResource):
    """获取 incident_manager 故障详情。"""

    action = "/incident/incident/get_incident_detail/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        incident_id = serializers.IntegerField(label="故障ID", required=True)

    def perform_request(self, validated_request_data):
        return APIResource.perform_request(self, validated_request_data)


class UpdateIncidentDetailResource(IncidentBaseResource):
    """更新 incident_manager 故障详情。"""

    action = "/incident/bkmonitor_api/update_incident_detail/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        incident_id = serializers.IntegerField(label="故障ID", required=True)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        incident_name = serializers.CharField(label="故障名称", required=False)
        incident_reason = serializers.CharField(label="故障原因", required=False, allow_null=True, allow_blank=True)
        level = serializers.CharField(label="故障级别", required=False)
        status = serializers.CharField(label="故障状态", required=False)
        assignees = serializers.ListField(label="故障负责人", required=False)
        handlers = serializers.ListField(label="故障处理人", required=False)
        labels = serializers.ListField(label="故障标签", required=False)
        feedback = serializers.DictField(label="故障反馈内容", required=False)
        end_time = serializers.IntegerField(label="故障结束时间", required=False, allow_null=True)
        bkmonitor_received_time = serializers.IntegerField(label="监控接收故障事件时间", required=False)

    def perform_request(self, validated_request_data):
        return APIResource.perform_request(self, validated_request_data)


class GetIncidentSnapshotResource(IncidentBaseResource):
    """获取 incident_manager 故障快照。"""

    action = "/incident/bkmonitor_api/get_incident_snapshot/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        snapshot_id = serializers.CharField(label="快照ID", required=True)

    def perform_request(self, validated_request_data):
        return APIResource.perform_request(self, validated_request_data)


class GetConfigResource(IncidentBaseResource):
    action = "/incident/incident_config/list_configs/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        config_type = serializers.CharField(label="配置类型", default="data_source")
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        bk_biz_id_list = serializers.ListField(label="业务ID列表", required=False)


class CreateListConfigResource(IncidentBaseResource):
    action = "/incident/incident_config/create_list_config/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        config_type = serializers.CharField(label="配置类型", required=True)
        scope_type = serializers.CharField(label="空间类型", required=False, default="bkcc")
        scope_value = serializers.CharField(label="空间ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        content_list = serializers.ListField(label="配置内容", required=False)
        bk_biz_id_config = serializers.JSONField(label="scope_id配置", required=False)


class FetchGlobalVariablesResource(IncidentBaseResource):
    action = "/incident/incident_config/fetch_global_variables/"
    method = "GET"
