from enum import Enum
from typing import Any, Literal, NotRequired, TypedDict

from .client import (
    batch_get_job_instance_ip_log_client,
    create_credential_client,
    create_file_source_client,
    fast_execute_script_client,
    fast_transfer_file_client,
    get_job_instance_ip_log_client,
    get_job_instance_status_client,
)

# 跨业务JobApi调用专用业务
JOB_API_BIZ = 9991001

# step_instance 级别状态码映射
# 作业步骤状态码: 1.未执行; 2.正在执行; 3.执行成功; 4.执行失败; 5.跳过; 6.忽略错误;
# 7.等待用户; 8.手动结束; 9.状态异常; 10.步骤强制终止中; 11.步骤强制终止成功; 12.步骤强制终止失败
JOB_STEP_STATUS_MAP = {
    1: "未执行",
    2: "正在执行",
    3: "执行成功",
    4: "执行失败",
    5: "跳过",
    6: "忽略错误",
    7: "等待用户",
    8: "手动结束",
    9: "状态异常",
    10: "步骤强制终止中",
    11: "步骤强制终止成功",
    12: "步骤强制终止失败",
}

# step_instance 级别成功状态码集合
JOB_STEP_SUCCESS_STATUS = {3, 5, 6}  # 执行成功、跳过、忽略错误
# step_instance 级别失败状态码集合
JOB_STEP_FAILED_STATUS = {4, 8, 9, 11, 12}  # 执行失败、手动结束、状态异常、强制终止成功/失败
# step_instance 级别运行中状态码集合
JOB_STEP_RUNNING_STATUS = {1, 2, 7, 10}  # 未执行、正在执行、等待用户、强制终止中


class FastExecuteScriptParams(TypedDict):
    """
    快速执行脚本参数

    Attributes:
        bk_biz_id: 业务ID
        script_content: 脚本内容
        timeout: 超时时间，单位秒 (默认7200秒)
        script_language: 脚本语言：1 - shell, 2 - bat, 3 - perl, 4 - python, 5 - powershell。当使用script_content传入自定义脚本的时候，需要指定script_language
        target_server: 目标服务器信息, 例如 {"ip_list":[{"ip":"10.10.28.10","bk_cloud_id":0}]}, 具体参见作业平台文档
        account_alias: 目标账号别名, 例如 "root"、"administrator"
        task_name: 任务名称, 非必填
    """

    bk_biz_id: int
    script_content: str
    timeout: NotRequired[int]
    script_language: int
    target_server: dict[str, Any]
    account_alias: str
    task_name: NotRequired[str]


class FastExecuteJobResult(TypedDict):
    """
    快速执行job任务返回结果

    Attributes:
        job_instance_id: 作业实例ID
        job_instance_name: 作业实例名称
        step_instance_id: 步骤实例ID
    """

    job_instance_id: int
    job_instance_name: str
    step_instance_id: int


class FastTransferFileParams(TypedDict):
    """
    快速分发文件参数

    Attributes:
        bk_biz_id: 业务ID
        file_source_list: 源文件对象数组，例如 [{"file_list":["bucket名称/test.txt"],"file_type":3,"file_source_id":1}] ，具体参见作业平台文档
        file_target_path: 目标路径
        target_server: 目标服务器信息, 例如 {"ip_list":[{"ip":"10.10.28.10","bk_cloud_id":0}]}, 具体参见作业平台文档
        account_alias: 目标账号别名, 例如 "root"、"administrator"
        timeout: 超时时间，单位秒 (默认7200秒)
        transfer_mode: 传输模式。1-严谨模式，2-强制模式。默认使用强制模式
        task_name: 任务名称, 非必填
    """

    bk_biz_id: int
    file_source_list: list[dict[str, Any]]
    file_target_path: str
    target_server: dict[str, Any]
    account_alias: str
    timeout: NotRequired[int]
    transfer_mode: NotRequired[int]
    task_name: NotRequired[str]


class GetJobInstanceStatusResult(TypedDict):
    """
    获取作业实例状态返回结果

    Attributes:
        finished: 作业是否完成
        job_instance: 作业实例信息
        step_instance_list: 步骤实例列表, 详细参见作业平台文档
    """

    finished: bool
    job_instance: dict[str, Any]
    step_instance_list: list[dict[str, Any]]


class JobTargetIpInfo(TypedDict):
    """JOB 目标主机 IP 信息。"""

    ip: str
    bk_cloud_id: int


class ScriptExecutionLogResult(TypedDict):
    """
    脚本执行日志返回结果

    Attributes:
        log_type: 日志类型，1-脚本执行
        bk_host_id: 主机ID
        ip: IP地址
        bk_cloud_id: 云区域ID
        log_content: 日志内容

    Example:
        {
            "log_type": 1,
            "bk_host_id": 101,
            "ip": "10.0.0.1",
            "bk_cloud_id": 0,
            "log_content": "[2018-03-15 14:39:30][PID:56875] job_start\\n"
        }
    """

    log_type: Literal[1]
    bk_host_id: int
    ip: str
    bk_cloud_id: int
    log_content: str


class FileTransferIpInfo(TypedDict):
    """
    文件分发IP信息

    Attributes:
        bk_host_id: 主机ID
        bk_cloud_id: 云区域ID
        ip: IP地址
    """

    bk_host_id: int
    bk_cloud_id: int
    ip: str


class FileLogEntry(TypedDict):
    """
    文件分发日志条目

    Attributes:
        mode: 传输模式，0-上传，1-下载
        src_ip: 源IP信息
        src_path: 源文件路径
        dest_ip: 目标IP信息（仅mode=1时存在）
        dest_path: 目标文件路径（仅mode=1时存在）
        status: 状态码，4-成功
        log_content: 日志内容

    Example:
        下载模式 (mode=1):
        {
            "mode": 1,
            "src_ip": {"host_id": 102, "bk_cloud_id": 0, "ip": "10.0.0.2"},
            "src_path": "/data/1.log",
            "dest_ip": {"bk_host_id": 101, "bk_cloud_id": 0, "ip": "10.0.0.1"},
            "dest_path": "/tmp/1.log",
            "status": 4,
            "log_content": "[2021-06-28 11:32:16] FileName: /tmp/1.log FileSize: 9.0 Bytes..."
        }

        上传模式 (mode=0):
        {
            "mode": 0,
            "src_ip": {"bk_host_id": 102, "bk_cloud_id": 0, "ip": "10.0.0.2"},
            "src_path": "/data/1.log",
            "status": 4,
            "log_content": "[2021-06-28 11:32:16] FileName: /data/1.log FileSize: 9.0 Bytes..."
        }
    """

    mode: Literal[0, 1]
    src_ip: FileTransferIpInfo
    src_path: str
    dest_ip: NotRequired[FileTransferIpInfo]
    dest_path: NotRequired[str]
    status: int
    log_content: str


class FileTransferLogResult(TypedDict):
    """
    文件分发日志返回结果

    Attributes:
        log_type: 日志类型，2-文件分发
        bk_host_id: 主机ID
        ip: IP地址
        bk_cloud_id: 云区域ID
        file_logs: 文件分发日志列表

    Example:
        {
            "log_type": 2,
            "bk_host_id": 101,
            "ip": "10.0.0.1",
            "bk_cloud_id": 0,
            "file_logs": [
                {
                    "mode": 1,
                    "src_ip": {"host_id": 102, "bk_cloud_id": 0, "ip": "10.0.0.2"},
                    "src_path": "/data/1.log",
                    "dest_ip": {"bk_host_id": 101, "bk_cloud_id": 0, "ip": "10.0.0.1"},
                    "dest_path": "/tmp/1.log",
                    "status": 4,
                    "log_content": "..."
                }
            ]
        }
    """

    log_type: Literal[2]
    bk_host_id: int
    ip: str
    bk_cloud_id: int
    file_logs: list[FileLogEntry]


class BatchGetJobInstanceIpLogResult(TypedDict):
    """
    批量获取作业日志返回结果。

    Attributes:
        script_task_logs: 脚本执行日志列表
        file_task_logs: 文件分发日志列表
    """

    script_task_logs: NotRequired[list[ScriptExecutionLogResult]]
    file_task_logs: NotRequired[list[FileTransferLogResult]]


# Union type for get_job_instance_ip_log return value
JobInstanceIpLogResult = ScriptExecutionLogResult | FileTransferLogResult


def fast_execute_script(bk_tenant_id: str, params: FastExecuteScriptParams) -> FastExecuteJobResult:
    """
    快速执行脚本

    Args:
        bk_tenant_id: 租户ID
        params: 快速执行脚本参数

    Returns:
        快速执行job任务返回结果
    """
    result = fast_execute_script_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


def fast_transfer_file(bk_tenant_id: str, params: FastTransferFileParams) -> FastExecuteJobResult:
    """
    快速分发文件

    Args:
        bk_tenant_id: 租户ID
        params: 快速分发文件参数

    Returns:
        快速执行job任务返回结果
    """
    result = fast_transfer_file_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


def get_job_instance_status(
    bk_tenant_id: str,
    bk_biz_id: int,
    job_instance_id: int,
    return_ip_result: bool = False,
    host_id_list: list[int] | None = None,
    ip_list: list[JobTargetIpInfo] | None = None,
) -> GetJobInstanceStatusResult:
    """
    获取作业状态

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        job_instance_id: 作业实例ID
        return_ip_result: 是否返回IP维度结果
        host_id_list: 目标主机ID列表（可选）
        ip_list: 目标IP列表（可选）

    Returns:
        作业状态
    """
    params: dict[str, Any] = {
        "bk_biz_id": bk_biz_id,
        "job_instance_id": job_instance_id,
        "return_ip_result": return_ip_result,
    }
    if host_id_list:
        params["host_id_list"] = host_id_list
    if ip_list:
        params["ip_list"] = ip_list

    result = get_job_instance_status_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


def get_job_instance_ip_log(
    bk_tenant_id: str,
    bk_biz_id: int,
    job_instance_id: int,
    step_instance_id: int,
    ip: str,
    bk_cloud_id: int,
) -> JobInstanceIpLogResult:
    """
    获取作业实例某个IP的执行日志

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        job_instance_id: 作业实例ID
        step_instance_id: 步骤实例ID
        ip: 目标IP
        bk_cloud_id: 云区域ID，0表示直连区域

    Returns:
        作业实例某个IP的执行日志，根据步骤类型返回脚本执行日志或文件分发日志

    Examples:
        脚本执行步骤:
        {
            "log_type": 1,
            "bk_host_id": 101,
            "ip": "10.0.0.1",
            "bk_cloud_id": 0,
            "log_content": "[2018-03-15 14:39:30][PID:56875] job_start\\n"
        }

        文件分发步骤:
        {
            "log_type": 2,
            "bk_host_id": 101,
            "ip": "10.0.0.1",
            "bk_cloud_id": 0,
            "file_logs": [
                {
                    "mode": 1,
                    "src_ip": {"host_id": 102, "bk_cloud_id": 0, "ip": "10.0.0.2"},
                    "src_path": "/data/1.log",
                    "dest_ip": {"bk_host_id": 101, "bk_cloud_id": 0, "ip": "10.0.0.1"},
                    "dest_path": "/tmp/1.log",
                    "status": 4,
                    "log_content": "[2021-06-28 11:32:16] FileName: /tmp/1.log..."
                }
            ]
        }
    """

    result = get_job_instance_ip_log_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "bk_biz_id": bk_biz_id,
            "job_instance_id": job_instance_id,
            "ip": ip,
            "bk_cloud_id": bk_cloud_id,
            "step_instance_id": step_instance_id,
        },
    )
    return result


def batch_get_job_instance_ip_log(
    bk_tenant_id: str,
    bk_biz_id: int,
    job_instance_id: int,
    step_instance_id: int,
    host_id_list: list[int] | None = None,
    ip_list: list[JobTargetIpInfo] | None = None,
) -> BatchGetJobInstanceIpLogResult:
    """
    批量获取作业实例多个目标的执行日志。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        job_instance_id: 作业实例ID
        step_instance_id: 步骤实例ID
        host_id_list: 目标主机ID列表（可选）
        ip_list: 目标IP列表（可选）

    Returns:
        批量日志查询结果
    """
    params: dict[str, Any] = {
        "bk_biz_id": bk_biz_id,
        "job_instance_id": job_instance_id,
        "step_instance_id": step_instance_id,
    }
    if host_id_list:
        params["host_id_list"] = host_id_list
    if ip_list:
        params["ip_list"] = ip_list

    result = batch_get_job_instance_ip_log_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


class CREDENTIAL_TYPE(Enum):
    ACCESS_KEY_SECRET_KEY = "ACCESS_KEY_SECRET_KEY"
    PASSWORD = "PASSWORD"
    USERNAME_PASSWORD = "USERNAME_PASSWORD"
    SECRET_KEY = "SECRET_KEY"


def create_credential(
    bk_tenant_id: str,
    name: str,
    account: str,
    password: str,
    credential_type: CREDENTIAL_TYPE,
    description: str = "",
    bk_biz_id: int = JOB_API_BIZ,
) -> str:
    """
    创建凭据

    暂时仅支持 CREDENTIAL_TYPE.USERNAME_PASSWORD 类型的凭据

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        name: 凭据名称
        credential_type: 凭据类型，CREDENTIAL_TYPE
        description: 凭据描述
        account: 账号
        password: 密码或密钥内容

    Returns:
        凭据ID
    """

    result = create_credential_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "bk_biz_id": bk_biz_id,
            "name": name,
            "type": credential_type.value,
            "description": description,
            "credential_username": account,
            "credential_password": password,
        },
    )
    return result["id"]


class CreateFileSourceParams(TypedDict):
    bk_biz_id: int
    type: str
    credential_id: str
    code: str
    alias: str
    access_params: NotRequired[dict[str, Any]]


def create_file_source(
    bk_tenant_id: str,
    params: CreateFileSourceParams,
) -> dict[str, Any]:
    result = create_file_source_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result
