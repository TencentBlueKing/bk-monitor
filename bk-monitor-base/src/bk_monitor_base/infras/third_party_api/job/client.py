from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class JobApiClient(BkApiClient, ABC):
    """
    作业平台 API Client
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "job"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/jobv3/"
    apigw_base_url: ClassVar[str] = "api/bk-job/prod/"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class FastExecuteScript(JobApiClient):
    """
    快速执行脚本 API Client
    """

    action: ClassVar[str] = "fast_execute_script"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "fast_execute_script/"
    apigw_path: ClassVar[str] = "api/v3/system/fast_execute_script/"


class FastTransferFile(JobApiClient):
    """
    快速分发文件 API Client
    """

    action: ClassVar[str] = "fast_transfer_file"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "fast_transfer_file/"
    apigw_path: ClassVar[str] = "api/v3/system/fast_transfer_file/"


class GetJobInstanceStatus(JobApiClient):
    """
    根据作业实例 ID 查询作业执行状态 API Client
    """

    action: ClassVar[str] = "get_job_instance_status"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "get_job_instance_status/"
    apigw_path: ClassVar[str] = "api/v3/system/get_job_instance_status/"


class GetJobInstanceIpLog(JobApiClient):
    """
    根据作业实例ID查询作业执行日志 API Client
    """

    action: ClassVar[str] = "get_job_instance_ip_log"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "get_job_instance_ip_log/"
    apigw_path: ClassVar[str] = "api/v3/system/get_job_instance_ip_log/"


class BatchGetJobInstanceIpLog(JobApiClient):
    """
    批量获取作业执行日志 API Client
    """

    action: ClassVar[str] = "batch_get_job_instance_ip_log"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "batch_get_job_instance_ip_log/"
    apigw_path: ClassVar[str] = "api/v3/system/batch_get_job_instance_ip_log/"


class CreateCredential(JobApiClient):
    """
    创建凭据 API Client
    """

    action: ClassVar[str] = "create_credential"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "create_credential/"
    apigw_path: ClassVar[str] = "api/v3/system/create_credential/"


class CreateFileSource(JobApiClient):
    """
    创建文件源 API Client
    """

    action: ClassVar[str] = "create_file_source"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "create_file_source/"
    apigw_path: ClassVar[str] = "api/v3/create_file_source/"


fast_execute_script_client: FastExecuteScript = FastExecuteScript()
fast_transfer_file_client: FastTransferFile = FastTransferFile()
get_job_instance_status_client: GetJobInstanceStatus = GetJobInstanceStatus()
get_job_instance_ip_log_client: GetJobInstanceIpLog = GetJobInstanceIpLog()
batch_get_job_instance_ip_log_client: BatchGetJobInstanceIpLog = BatchGetJobInstanceIpLog()
create_credential_client: CreateCredential = CreateCredential()
create_file_source_client: CreateFileSource = CreateFileSource()
