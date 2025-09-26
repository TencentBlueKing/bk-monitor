"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import time

from django.conf import settings
from django.utils.translation import ngettext as _

from bkmonitor.views import serializers
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.drf_resource.exceptions import CustomException


class IPListRequestSerializer(serializers.Serializer):
    ip = serializers.IPAddressField(required=True, label="IP地址")
    plat_id = serializers.IntegerField(required=True, label="平台ID", source="bk_cloud_id")


class IPListResponseSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(required=False, label="主机ID", allow_null=True)
    ip = serializers.CharField(required=False, label="IP", allow_null=True)
    plat_id = serializers.IntegerField(required=False, label="平台ID", allow_null=True)
    bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID", allow_null=True)


class TaskResultMixin:
    # 重试次数
    RETRY_TIMES = 600

    # 轮询间隔
    INTERVAL = 0.5

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.CharField(required=True, label="启动任务返回的id")
        step_id = serializers.CharField(required=True, label="步骤实例id")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        host_id_list = serializers.ListField(required=False, label="主机列表", allow_empty=True, default=[])
        ip_list = serializers.ListField(required=False, label="IP列表", allow_empty=True, default=[])

    class ResponseSerializer(serializers.Serializer):
        class SuccessSerializer(IPListResponseSerializer):
            log_content = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="日志信息")

        class PendingSerializer(IPListResponseSerializer):
            pass

        class FailedSerializer(IPListResponseSerializer):
            errmsg = serializers.CharField(required=True, allow_null=True, allow_blank=True, label="错误信息")
            exit_code = serializers.IntegerField(required=True, label="返回码")

        success = SuccessSerializer(required=True, many=True, label="成功IP")
        pending = PendingSerializer(required=True, many=True, label="执行中IP")
        failed = FailedSerializer(required=True, many=True, label="失败IP")


class GetInstanceLogResource(TaskResultMixin, Resource):
    """
    根据作业实例ID查询作业执行状态
    """

    class IpStatus:
        """
        IP状态对应的状态码
        """

        SUCCESS = 9
        WAITING = 5

    def fetch_job_task_result(self, data, kwargs):
        """
        统计执行结果，分为成功，等待，失败三类
        :param data: job返回的运行结果
        :param kwargs: job获取日志请求参数
        :return: 执行结果
            {
                "success": [
                    {
                        "ip": ip,
                        "plat_id": plat_id,
                        "bk_cloud_id": bk_cloud_id,
                        "bk_host_id": bk_host_id,
                        'log_content': xxx
                    }],
                "pending": [{
                        "ip": ip,
                        "plat_id": plat_id
                        "bk_cloud_id": bk_cloud_id
                        "bk_host_id": bk_host_id
                    }],
                "failed": [{
                        "ip": ip,
                        "plat_id": plat_id
                        "bk_cloud_id": bk_cloud_id
                        "bk_host_id": bk_host_id
                        "errmsg": xxx
                        "exit_code": xxx
                    }]
            }
        """

        success = []
        pending = []
        failed = []

        try:
            ip_results = data[0]["step_ip_result_list"]
        except Exception as e:
            raise CustomException(_("【模块：job】执行任务结果查询返回格式异常 %s") % str(e))

        log_results = api.job.get_job_instance_ip_log(kwargs)
        if log_results and log_results.get("script_task_logs"):
            log_content_map = {
                (log.get("host_id") or log.get("bk_host_id")): log["log_content"]
                for log in log_results["script_task_logs"]
                if log.get("host_id") or log.get("bk_host_id")
            }
        else:
            return {}

        for ip_log in ip_results:
            ip_status = ip_log["status"]
            params = {
                "bk_host_id": ip_log["bk_host_id"],
                "ip": ip_log["ip"],
                "plat_id": ip_log["bk_cloud_id"],
                "bk_cloud_id": ip_log["bk_cloud_id"],
            }
            log_content = log_content_map[ip_log["bk_host_id"]]
            if ip_status == settings.IP_STATUS_SUCCESS:
                success.append({**params, "log_content": log_content})
            elif ip_status == settings.IP_STATUS_WAITING or ip_status == settings.IP_STATUS_RUNNING:
                pending.append(params)
            else:
                exit_code = ip_log["exit_code"]
                failed.append(
                    {
                        **params,
                        "errmsg": log_content,
                        "exit_code": exit_code,
                    }
                )

        return {"success": success, "pending": pending, "failed": failed}

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        ip_list = [
            ip if isinstance(ip, dict) else {"ip": ip, "bk_cloud_id": 0} for ip in validated_request_data["ip_list"]
        ]
        kwargs = {
            "bk_biz_id": bk_biz_id,
            "job_instance_id": validated_request_data["task_id"],
            "step_instance_id": validated_request_data["step_id"],
            "host_id_list": validated_request_data["host_id_list"],
            "ip_list": ip_list,
        }
        log_result = {
            "success": [],
            "pending": [],
            "failed": [],
        }
        for i in range(self.RETRY_TIMES):
            data = api.job.get_job_instance_status({**kwargs, "return_ip_result": True})
            if data and data.get("finished", False) and data.get("step_instance_list"):
                log_result = self.fetch_job_task_result(data["step_instance_list"], kwargs)
                if log_result and not log_result["pending"]:
                    break
            time.sleep(self.INTERVAL)

        for host in log_result["pending"]:
            host.update({"errmsg": _("任务执行超时"), "exit_code": 0})

        log_result["failed"] += log_result["pending"]
        log_result["pending"] = []

        return log_result


class FastExecuteScriptResource(Resource):
    """
    快速执行脚本
    """

    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="资源范围ID")
        bk_scope_type = serializers.CharField(required=False, label="资源范围类型", default="biz")
        host_list = serializers.ListField(required=False, allow_empty=True)
        script_content = serializers.CharField(required=True, label="脚本内容")
        script_param = serializers.CharField(default="", label="脚本参数")
        account_alias = serializers.CharField(default="root", label="执行账户")
        script_type = serializers.IntegerField(default=1, label="脚本类型")

        def validate_script_content(self, script_content):
            return base64.b64encode(script_content.encode("utf-8")).decode("utf-8")

        def validate_script_param(self, script_params):
            return base64.b64encode(script_params.encode("utf-8")).decode("utf-8")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        ip_list = [host for host in validated_request_data["host_list"] if host.get("ip")]
        host_id_list = [host["bk_host_id"] for host in validated_request_data["host_list"] if host.get("bk_host_id")]
        target_server = {}
        if ip_list:
            target_server["ip_list"] = ip_list
        if host_id_list:
            target_server["host_id_list"] = host_id_list
        validated_request_data["script_language"] = validated_request_data["script_type"]
        validated_request_data["bk_scope_id"] = validated_request_data["bk_biz_id"]
        validated_request_data["target_server"] = target_server
        task_instance_data = api.job.fast_execute_script(validated_request_data)
        task_id = task_instance_data["job_instance_id"]
        step_id = task_instance_data["step_instance_id"]

        task_result = resource.commons.get_instance_log(
            task_id=task_id, step_id=step_id, bk_biz_id=bk_biz_id, **target_server
        )
        return task_result
