from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field

from .client import (
    create_export_plugin_task_client,
    create_plugin_config_template_client,
    create_register_plugin_task_client,
    create_subscription_client,
    get_plugin_info_client,
    get_proxies_by_biz_client,
    get_proxies_client,
    get_subscription_info_client,
    get_subscription_task_result_client,
    get_subscription_task_result_detail_client,
    ipchooser_host_details_client,
    plugin_operate_client,
    plugin_search_client,
    query_export_plugin_task_client,
    query_plugin_debug_client,
    query_register_plugin_task_client,
    release_plugin_client,
    release_plugin_config_template_client,
    render_plugin_config_template_client,
    retry_subscription_client,
    revoke_subscription_client,
    run_subscription_client,
    start_plugin_debug_client,
    stop_plugin_debug_client,
    subscription_check_task_ready_client,
    switch_subscription_client,
    update_subscription_client,
    upload_plugin_client,
)


class UploadPluginResult(TypedDict):
    """
    上传插件 返回值
    """

    name: str


def upload_plugin(
    bk_tenant_id: str,
    file_name: str,
    download_url: str,
    md5: str,
) -> UploadPluginResult:
    """
    上传插件

    Args:
        bk_tenant_id: 租户ID
        file_name: 文件名
        download_url: 下载链接
        md5: 文件MD5

    Returns:
        UploadPluginResult: 上传插件结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = upload_plugin_client(
        bk_tenant_id=bk_tenant_id,
        params={"file_name": file_name, "download_url": download_url, "md5": md5},
    )
    return result


def create_register_plugin_task(bk_tenant_id: str, file_name: str, is_release: bool) -> int:
    """
    创建注册插件任务

    Args:
        bk_tenant_id: 租户ID
        file_name: 文件名
        is_release: 是否发布

    Returns:
        任务ID

    Raises:
        BkApiError: 接口调用失败
    """
    result = create_register_plugin_task_client(
        bk_tenant_id=bk_tenant_id,
        params={"file_name": file_name, "is_release": is_release},
    )
    return result["job_id"]


class QueryRegisterPluginTaskResult(TypedDict):
    """
    查询注册插件任务 返回值

    Attributes:
        status: 任务状态
        is_finish: 任务是否完成
        message: 任务信息
    """

    status: Literal["FAILED", "SUCCESS", "RUNNING"]
    is_finish: str
    message: str


def query_register_plugin_task(bk_tenant_id: str, job_id: int) -> QueryRegisterPluginTaskResult:
    """
    查询注册插件任务

    Args:
        bk_tenant_id: 租户ID
        job_id: 任务ID

    Returns:
        is_finish: 任务是否完成
        message: 任务信息

    Raises:
        BkApiError: 接口调用失败
    """
    result = query_register_plugin_task_client(
        bk_tenant_id=bk_tenant_id,
        params={"job_id": job_id},
    )
    return result


class PluginInfo(BaseModel):
    """
    插件信息
    """

    id: int = Field(description="插件信息记录ID")
    name: str = Field(description="插件名")
    version: str = Field(description="插件版本", examples=["1.1"])
    os: str = Field(description="操作系统", examples=["linux", "windows"])
    cpu_arch: str = Field(description="CPU架构", examples=["x86_64"])
    pkg_name: str = Field(description="包名", examples=["test_script-1.1.tgz"])
    pkg_size: int = Field(description="包大小")
    pkg_mtime: str = Field(description="包修改时间", examples=["2025-08-20 07:14:13.560398+00:00"])
    md5: str = Field(description="MD5")
    creator: str = Field(description="创建者")
    is_ready: bool = Field(description="是否就绪")
    is_release_version: bool = Field(description="是否是发布版本")
    source_app_code: str = Field(description="来源应用")


def get_plugin_info(bk_tenant_id: str, name: str, version: str | None = None) -> list[PluginInfo]:
    """获取插件信息

    Args:
        bk_tenant_id: 租户ID
        name: 插件名
        version: 插件版本

    Returns:
        插件信息列表

    Raises:
        pydantic.ValidationError: 返回值校验失败
    """
    params = {"name": name}
    if version is not None:
        params["version"] = version

    result: list[dict[str, Any]] = get_plugin_info_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return [PluginInfo(**item) for item in result]


def release_plugin(bk_tenant_id: str, name: str, version: str, md5_list: list[str]) -> None:
    """发布插件

    Args:
        bk_tenant_id: 租户ID
        name: 插件名
        version: 插件版本
        md5_list: MD5列表

    Raises:
        BkApiError: 接口调用失败
    """
    release_plugin_client(bk_tenant_id=bk_tenant_id, params={"name": name, "version": version, "md5_list": md5_list})


class PluginConfigTemplateParams(TypedDict):
    """创建插件配置模板 参数"""

    plugin_name: str
    plugin_version: str
    name: str
    file_path: str
    format: str
    content: str
    md5: str
    version: str
    is_release_version: bool


def create_plugin_config_template(bk_tenant_id: str, params: PluginConfigTemplateParams) -> PluginConfigTemplateParams:
    """创建插件配置模板

    Args:
        bk_tenant_id: 租户ID
        params: 插件配置模板参数

    Returns:
        插件配置模板参数

    Raises:
        BkApiError: 接口调用失败
    """

    result = create_plugin_config_template_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


def release_plugin_config_template(
    bk_tenant_id: str, plugin_name: str, plugin_version: str, name: str, version: int
) -> None:
    """发布插件配置模板

    Args:
        bk_tenant_id: 租户ID
        plugin_name: 插件名称
        plugin_version: 插件版本
        name: 模板名称
        version: 模板版本ID
    """
    release_plugin_config_template_client(
        bk_tenant_id=bk_tenant_id,
        params={"plugin_name": plugin_name, "plugin_version": plugin_version, "name": name, "version": version},
    )


def create_export_plugin_task(
    bk_tenant_id: str, category: str, query_params: dict[str, Any], bk_app_code: str, creator: str
) -> int:
    """创建导出插件任务

    Args:
        bk_tenant_id: 租户ID
        category: 插件分类
        query_params: 查询参数, {"project": "test_plugin", "version": "1.1"}
        bk_app_code: 应用编码
        creator: 任务创建者

    Returns:
        任务ID

    Raises:
        BkApiError: 接口调用失败
    """
    result = create_export_plugin_task_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "category": category,
            "query_params": query_params,
            "bk_app_code": bk_app_code,
            "creator": creator,
        },
    )
    return result["job_id"]


class QueryExportPluginTaskResult(TypedDict):
    """查询导出插件任务 返回值"""

    is_finish: bool
    is_failed: bool
    error_message: NotRequired[str]
    download_url: str


def query_export_plugin_task(bk_tenant_id: str, job_id: int) -> QueryExportPluginTaskResult:
    """查询导出插件任务

    Args:
        bk_tenant_id: 租户ID
        job_id: 任务ID

    Returns:
        is_finish: 是否完成
        is_failed: 是否失败
        error_message: 错误信息
        download_url: 下载链接

    Raises:
        BkApiError: 接口调用失败
    """
    result = query_export_plugin_task_client(
        bk_tenant_id=bk_tenant_id,
        params={"job_id": job_id},
    )
    return result


class StartPluginDebugParams(TypedDict):
    """启动插件调试 参数

    Attributes:
        plugin_id: 插件ID
        plugin_name: 插件名称
        version: 插件版本, 1.0
        config_ids: 配置文件ID列表
        host_info: 主机信息, {"bk_host_id": 1}
    """

    plugin_id: NotRequired[int]
    plugin_name: str
    version: str
    config_ids: list[int]
    host_info: dict[str, Any]


def start_plugin_debug(bk_tenant_id: str, params: StartPluginDebugParams) -> int:
    """启动插件调试

    Args:
        bk_tenant_id: 租户ID
        params: 启动插件调试参数

    Returns:
        任务ID

    Raises:
        BkApiError: 接口调用失败
    """
    result = start_plugin_debug_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    # API 返回格式为 {"task_id": <int>}，需要提取实际的整数值
    return result["task_id"]


class QueryPluginDebugResult(TypedDict):
    """查询插件调试返回值

    Attributes:
        status: 任务状态
            - PENDING: 等待执行
            - RUNNING: 正在执行
            - SUCCESS: 执行成功
            - FAILED: 执行失败
            - PART_FAILED: 部分失败
            - TERMINATED: 已终止
            - REMOVED: 已移除
            - FILTERED: 被过滤
            - IGNORED: 已忽略
        step: 当前执行的步骤名称，调试插件(DEBUG_PLUGIN)流程的步骤如下：
            - preparing: 任务准备中（特殊值，任务未就绪时返回）
            - transfer_package: 下发安装包
            - install_package: 安装插件包
            - render_and_push_config: 渲染下发配置
            - DEBUG_PROCESS: 调试插件（注意：此ID监控需要使用，请勿随意修改）
            - STOP_DEBUG_PROCESS: 停止调试插件（注意：此ID监控需要使用，请勿随意修改）
            - update_host_process_status: 更新插件部署状态
        message: 日志内容（多行日志以换行符连接）

        ********* 开始初始化进程状态 **********
        开始 初始化进程状态.
        初始化进程状态 成功
        ********** 开始下发安装包 ***********
        开始 下发安装包.
        从 [第三方文件源文件-节点管理[biz:9991001]蓝鲸制品库文件源] 下发文件 [blueking/bknodeman/data/bkee/public/bknodeman/download/linux/x86_64/test-1.1.tgz] 到目标机器路径 [/tmp]
        作业任务ID为 [16]，点击跳转到 <a href="https://job.example.com/api_execute/16" target="_blank">[作业平台]</a>
        下发安装包 成功
        ********** 开始安装插件包 ***********
        开始 安装插件包.
        快速执行脚本 update_binary
        作业任务ID为 [17]，点击跳转到 <a href="https://job.example.com/api_execute/17" target="_blank">[作业平台]</a>
        安装插件包 成功
        ********** 开始渲染下发配置 **********
        开始 渲染下发配置.
        下发配置文件 [bkmonitorbeat_debug.yaml] 到目标机器路径 [/usr/local/gse/external_plugins/sub_115480_host_1/test/etc]，若下发失败，请检查作业平台所部署的机器是否已安装AGENT
        作业任务ID为 [18]，点击跳转到 <a href="https://job.example.com/api_execute/18" target="_blank">[作业平台]</a>
        下发配置文件 [env.yaml] 到目标机器路径 [/usr/local/gse/external_plugins/sub_115480_host_1/test/etc]，若下发失败，请检查作业平台所部署的机器是否已安装AGENT
        作业任务ID为 [22]，点击跳转到 <a href="https://job.example.com/api_execute/22" target="_blank">[作业平台]</a>
        渲染下发配置 成功
        *********** 开始调试插件 ***********
        开始 调试插件.
        快速执行脚本 operate_plugin
        作业任务ID为 [23]，点击跳转到 <a href="https://job.example.com/api_execute/23" target="_blank">[作业平台]</a>
        {"@timestamp":"2025-09-02T04:14:53.492Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"dataid":1,"dimensions":{"status":0,"version":"","bk_host_id":"0"},"metrics":{"config_load_at":1756786493,"published":0,"errors":0,"config_error_code":111,"error_tasks":0,"uptime":0,"tasks":1},"time":1756786493}


        {"@timestamp":"2025-09-02T04:15:10.503Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"usertime":"2025-09-02 04:15:10","ip":"127.0.0.1","exemplar":{},"task_id":0,"dimensions":{"disk_name":"/data","bk_biz_id":0},"task_type":"script","type":"script","message":"success","utctime":"2025-09-02 04:15:10","bk_cloud_id":0,"bk_biz_id":0,"localtime":"2025-09-02 12:15:10","group_info":[],"bk_cmdb_level":[{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":15},{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":19}],"error_code":0,"cost_time":7,"dataid":0,"time":1756786510,"metrics":{"disk_usage":8},"node_id":"0:127.0.0.1"}
        {"@timestamp":"2025-09-02T04:15:10.504Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"type":"status","dataid":0,"data":[{"timestamp":1756786510503,"metrics":{"bkm_gather_up":2},"dimension":{"bk_collect_type":"script","bk_biz_id":"0","bkm_up_code":"0","bkm_up_code_name":"Ok","task_id":"0"}}],"node_id":"0:127.0.0.1","bk_cloud_id":0,"ip":"127.0.0.1"}

        {"@timestamp":"2025-09-02T04:15:20.504Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"time":1756786520,"exemplar":{},"dataid":0,"type":"script","task_id":0,"task_type":"script","message":"success","group_info":[],"bk_cloud_id":0,"bk_biz_id":0,"localtime":"2025-09-02 12:15:20","dimensions":{"disk_name":"/data","bk_biz_id":0},"metrics":{"disk_usage":8},"cost_time":7,"ip":"127.0.0.1","utctime":"2025-09-02 04:15:20","node_id":"0:127.0.0.1","bk_cmdb_level":[{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":15},{"bk_biz_id":2,"bk_set_id":5,"bk_module_id":19}],"error_code":0,"usertime":"2025-09-02 04:15:20"}
        {"@timestamp":"2025-09-02T04:15:20.504Z","@metadata":{"beat":"bkmonitorbeat","type":"_doc","version":"3.72.3657"},"type":"status","dataid":0,"data":[{"metrics":{"bkm_gather_up":2},"dimension":{"bkm_up_code_name":"Ok","task_id":"0","bk_collect_type":"script","bk_biz_id":"0","bkm_up_code":"0"},"timestamp":1756786520504}],"node_id":"0:127.0.0.1","bk_cloud_id":0,"ip":"127.0.0.1"}

    Examples:
        任务准备中::

            {"status": "PENDING", "step": "preparing", "message": "调试任务准备中"}

        正在调试插件::

            {"status": "RUNNING", "step": "DEBUG_PROCESS", "message": "****** 开始调试插件 ******\\n执行调试命令中..."}

        调试成功完成::

            {"status": "SUCCESS", "step": "update_host_process_status", "message": "...\\n状态更新成功"}

        调试失败::

            {"status": "FAILED", "step": "DEBUG_PROCESS", "message": "...\\n执行调试脚本失败: 进程异常退出, exit code: 1"}
    """

    status: Literal[
        "PENDING", "RUNNING", "SUCCESS", "FAILED", "PART_FAILED", "TERMINATED", "REMOVED", "FILTERED", "IGNORED"
    ]
    step: Literal[
        "preparing",
        "transfer_package",
        "install_package",
        "render_and_push_config",
        "DEBUG_PROCESS",
        "STOP_DEBUG_PROCESS",
        "update_host_process_status",
    ]
    message: str


def query_plugin_debug(bk_tenant_id: str, task_id: int) -> QueryPluginDebugResult:
    """查询插件调试

    Args:
        bk_tenant_id: 租户ID
        task_id: 任务ID

    Returns:
        插件调试结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = query_plugin_debug_client(
        bk_tenant_id=bk_tenant_id,
        params={"task_id": task_id},
    )
    return result


def stop_plugin_debug(bk_tenant_id: str, task_id: int) -> None:
    """停止插件调试

    Args:
        bk_tenant_id: 租户ID
        task_id: 任务ID

    Raises:
        BkApiError: 接口调用失败
    """
    stop_plugin_debug_client(
        bk_tenant_id=bk_tenant_id,
        params={"task_id": task_id},
    )


class RenderPluginConfigTemplateResult(TypedDict):
    """渲染插件配置模板 返回值"""

    id: int
    md5: str


def render_plugin_config_template(
    bk_tenant_id: str,
    plugin_name: str,
    plugin_version: str,
    name: str,
    version: str,
    data: dict[str, Any],
) -> RenderPluginConfigTemplateResult:
    """渲染插件配置模板

    Args:
        bk_tenant_id: 租户ID
        plugin_name: 插件名称
        plugin_version: 插件版本
        name: 模板名称
        version: 模板版本
        data: 渲染上下文

    Returns:
        id: 渲染后的配置实例ID
        md5: 渲染后的配置实例MD5

    Raises:
        BkApiError: 接口调用失败
    """
    result = render_plugin_config_template_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "plugin_name": plugin_name,
            "plugin_version": plugin_version,
            "name": name,
            "version": version,
            "data": data,
        },
    )
    return result


def switch_subscription(
    bk_tenant_id: str,
    subscription_id: int,
    action: Literal["enable", "disable"],
) -> None:
    """启停订阅"""
    switch_subscription_client(
        bk_tenant_id=bk_tenant_id,
        params={"subscription_id": subscription_id, "action": action},
    )


class ScopeParams(TypedDict):
    """
    操作范围参数
    """

    object_type: NotRequired[str]
    node_type: str
    nodes: list[dict[str, Any]]
    bk_biz_id: NotRequired[int]


def run_subscription(
    bk_tenant_id: str,
    subscription_id: int,
    actions: dict[str, Any],
    scope: ScopeParams | None = None,
) -> Any:
    """启停订阅

    Args:
        bk_tenant_id: 租户ID
        subscription_id: 订阅ID
        actions: 操作
        scope: 操作范围参数
    """
    params: dict[str, Any] = {"subscription_id": subscription_id, "actions": actions}
    if scope:
        params["scope"] = scope

    return run_subscription_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


class CreateSubscriptionScopeParams(TypedDict):
    """
    操作范围参数
    """

    object_type: Literal["HOST", "SERVICE"]
    node_type: Literal["TOPO", "INSTANCE"]
    nodes: list[dict[str, Any]]
    bk_biz_id: NotRequired[int]


class CreateSubscriptionParams(TypedDict):
    """创建订阅 参数"""

    steps: list[dict[str, Any]]
    run_immediately: bool
    scope: ScopeParams
    target_hosts: NotRequired[list[dict[str, Any]]]


class CreateSubscriptionResult(TypedDict):
    """创建订阅 返回值"""

    subscription_id: int
    task_id: int


def create_subscription(bk_tenant_id: str, params: CreateSubscriptionParams) -> CreateSubscriptionResult:
    """创建订阅"""
    return create_subscription_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


class UpdateSubscriptionParams(TypedDict):
    """更新订阅 参数"""

    subscription_id: int
    steps: list[dict[str, Any]]
    run_immediately: bool
    scope: ScopeParams | None


def update_subscription(bk_tenant_id: str, params: UpdateSubscriptionParams) -> Any:
    """更新订阅"""

    return update_subscription_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


def retry_subscription(
    bk_tenant_id: str,
    subscription_id: int,
    instance_ids: list[Any] | None = None,
):
    """重试订阅"""

    params: dict[str, Any] = {"subscription_id": subscription_id}
    if instance_ids:
        params["instance_id_list"] = instance_ids

    return retry_subscription_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


def revoke_subscription(
    bk_tenant_id: str,
    subscription_id: int,
    instance_ids: list[Any] | None = None,
):
    """终止订阅"""
    params: dict[str, Any] = {"subscription_id": subscription_id}
    if instance_ids:
        params["instance_id_list"] = instance_ids

    return revoke_subscription_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


class SubscriptionStep(TypedDict):
    """订阅步骤"""

    id: str
    type: str
    config: dict[str, Any]
    params: dict[str, Any]


class SubscriptionInfo(TypedDict):
    """订阅信息"""

    id: int
    name: str
    enable: bool
    category: str | None
    plugin_name: str | None
    bk_biz_scope: list[int]
    scope: ScopeParams
    pid: int
    target_hosts: list[dict[str, Any]] | None
    steps: list[SubscriptionStep]


def get_subscription_info(bk_tenant_id: str, subscription_id_list: list[int]) -> list[SubscriptionInfo]:
    """获取订阅信息

    Args:
        bk_tenant_id: 租户ID
        subscription_id_list: 订阅ID列表

    Returns:
        订阅信息列表
    """
    return get_subscription_info_client(
        bk_tenant_id=bk_tenant_id,
        params={"subscription_id_list": subscription_id_list},
    )


class SubscriptionTaskResultHostInfo(TypedDict):
    """主机信息"""

    bk_biz_id: int
    bk_host_id: int
    bk_biz_name: str
    bk_cloud_id: int
    bk_host_name: str
    bk_cloud_name: str
    bk_host_innerip: str
    bk_supplier_account: str


class SubscriptionTaskResultServiceInfo(TypedDict):
    """服务实例信息"""

    id: int
    name: str
    bk_host_id: int
    bk_module_id: int


class SubscriptionTaskResultInstanceInfo(TypedDict):
    """实例信息"""

    host: SubscriptionTaskResultHostInfo
    service: NotRequired[SubscriptionTaskResultServiceInfo | None]

    # 以下字段仅在详细模式下存在
    meta: NotRequired[dict[str, Any]]
    scope: NotRequired[list[dict[str, Any]]]
    process: NotRequired[dict[str, Any]]


class SubscriptionTaskResultSubStep(TypedDict):
    """子步骤（仅在详细模式下存在）"""

    index: int
    node_name: str
    step_code: str
    log: str
    ex_data: dict[str, Any] | None
    status: str
    start_time: str | None
    finish_time: str | None
    inputs: dict[str, Any]


class SubscriptionTaskResultTargetHost(TypedDict):
    """目标主机（仅在详细模式下存在）"""

    node_name: str
    status: str
    start_time: str | None
    finish_time: str | None
    sub_steps: list[SubscriptionTaskResultSubStep]


class SubscriptionTaskResultStep(TypedDict):
    """步骤（仅在详细模式下存在）"""

    id: str
    type: str
    index: int
    action: str
    node_name: str
    extra_info: dict[str, Any]
    status: str
    start_time: str | None
    finish_time: str | None
    target_hosts: list[SubscriptionTaskResultTargetHost]


class SubscriptionTaskResult(TypedDict):
    """订阅任务结果（支持精简模式和详细模式）"""

    task_id: int
    instance_id: str
    create_time: str
    instance_info: SubscriptionTaskResultInstanceInfo
    start_time: str
    finish_time: str
    status: str

    # 仅在详细模式下存在
    steps: NotRequired[list[SubscriptionTaskResultStep]]


class SubscriptionTaskResultResponse(TypedDict):
    """订阅任务结果响应"""

    list: list[SubscriptionTaskResult]
    total: int


def get_subscription_task_result_detail(
    bk_tenant_id: str,
    subscription_id: int,
    instance_id: str,
    task_id_list: list[int] | None = None,
) -> SubscriptionTaskResult:
    """获取订阅任务结果详情

    Args:
        bk_tenant_id: 租户ID
        subscription_id: 订阅配置id
        instance_id: 实例ID
        task_id_list: 任务ID列表, 不设置则返回所有任务结果

    Returns:
        订阅任务结果详情

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "subscription_id": subscription_id,
        "instance_id": instance_id,
    }
    if task_id_list:
        params["task_id_list"] = task_id_list

    return get_subscription_task_result_detail_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


class GetSubscriptionTaskResultParams(TypedDict):
    """获取订阅任务结果 参数"""

    subscription_id: int  # 订阅配置id

    task_id_list: NotRequired[list[int]]  # 任务id列表
    need_detail: NotRequired[bool]  # 是否需要详细log, 默认为 false
    need_aggregate_all_tasks: NotRequired[bool]  # 是否要合并任务, 默认为 true
    need_out_of_scope_snapshots: NotRequired[bool]  # 是否需要已移除的记录, 默认为 true
    return_all: NotRequired[bool]  # 是否返回所有任务结果, 默认为 false

    page: NotRequired[int]  # 页数，默认为 1
    page_size: NotRequired[int]  # 单页数量，不设置则返回所有任务结果


def get_subscription_task_result(
    bk_tenant_id: str, params: GetSubscriptionTaskResultParams
) -> SubscriptionTaskResultResponse:
    """获取订阅任务结果

    Args:
        bk_tenant_id: 租户ID
        params: 获取订阅任务结果参数

    Returns:
        订阅任务结果响应

    Raises:
        BkApiError: 接口调用失败
    """
    request_params: dict[str, Any] = dict(params)
    if "page_size" in request_params:
        request_params["pagesize"] = request_params["page_size"]
    request_params["need_aggregate_all_tasks"] = request_params.get("need_aggregate_all_tasks", True)

    return get_subscription_task_result_client(bk_tenant_id=bk_tenant_id, params=request_params)


class BatchGetSubscriptionTaskResultParams(TypedDict):
    """批量获取订阅任务结果 参数"""

    subscription_id: int  # 订阅配置id

    task_id_list: NotRequired[list[int]]  # 任务id列表
    need_detail: NotRequired[bool]  # 是否需要详细log, 默认为 false
    need_aggregate_all_tasks: NotRequired[bool]  # 是否要合并任务, 默认为 true
    need_out_of_scope_snapshots: NotRequired[bool]  # 是否需要已移除的记录, 默认为 true
    return_all: NotRequired[bool]  # 是否返回所有任务结果, 默认为 false


def check_subscription_task_ready(
    bk_tenant_id: str,
    subscription_id: int,
    task_id_list: list[int] | None = None,
) -> bool:
    """批量检查订阅任务是否就绪

    Args:
        bk_tenant_id: 租户ID
        subscription_id: 订阅配置id
        task_id_list: 任务ID列表【可选】，不设置则最新任务结果

    Returns:
        是否就绪

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "subscription_id": subscription_id,
    }
    if task_id_list:
        params["task_id_list"] = task_id_list
    result = subscription_check_task_ready_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    return bool(result)


def batch_get_subscription_task_result(
    bk_tenant_id: str,
    params: BatchGetSubscriptionTaskResultParams,
    batch_size: int = 1000,
    concurrent_count: int = 5,
    limit: int = 1000,
) -> tuple[list[SubscriptionTaskResult], int]:
    """批量获取订阅任务结果


    Args:
        bk_tenant_id: 租户ID
        params: 批量获取订阅任务结果参数
        batch_size: 分页大小
        concurrent_count: 并发数
        limit: 限制返回的最大记录数

    Returns:
        订阅任务结果响应
    """
    _, result, total = get_subscription_task_result_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=batch_size,
        concurrent_count=concurrent_count,
        pagination_mode="page",
        first_page_or_start_value=1,
        page_or_offset_key="page",
        page_size_or_limit_key="pagesize",
        total_key="total",
        data_list_key="list",
        total_limit=limit,
    )
    return result, total


def get_proxies(bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
    """查询云区域下的proxy列表

    Args:
        bk_tenant_id: 租户ID
        bk_cloud_id: 云区域ID

    Returns:
        云区域下的proxy列表

    Raises:
        BkApiError: 接口调用失败
    """

    return get_proxies_client(bk_tenant_id=bk_tenant_id, params={"bk_cloud_id": bk_cloud_id})


def get_proxies_by_biz(bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
    """通过业务查询业务所使用的所有云区域下的ProxyIP

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID

    Returns:
        业务所使用的所有云区域下的ProxyIP

    Raises:
        BkApiError: 接口调用失败
    """

    return get_proxies_by_biz_client(bk_tenant_id=bk_tenant_id, params={"bk_biz_id": bk_biz_id})


class PluginOperateParams(TypedDict):
    """插件管理 参数"""

    class PluginInfo(TypedDict):
        name: str
        version: str
        keep_config: NotRequired[bool]
        no_restart: NotRequired[bool]

    job_type: Literal[
        "MAIN_START_PLUGIN",
        "MAIN_STOP_PLUGIN",
        "MAIN_RESTART_PLUGIN",
        "MAIN_RELOAD_PLUGIN",
        "MAIN_DELEGATE_PLUGIN",
        "MAIN_UNDELEGATE_PLUGIN",
        "MAIN_INSTALL_PLUGIN",
    ]
    bk_biz_id: NotRequired[list[int]]
    bk_cloud_id: NotRequired[list[int]]
    version: NotRequired[list[str]]
    plugin_params: PluginInfo
    conditions: NotRequired[list[dict[str, Any]]]
    bk_host_id: NotRequired[list[int]]
    exclude_hosts: NotRequired[list[int]]


def plugin_operate(bk_tenant_id: str, params: PluginOperateParams) -> Any:
    """插件管理接口

    Args:
        bk_tenant_id: 租户ID
        params: 插件管理参数

    Returns:


    Raises:
        BkApiError: 接口调用失败
    """
    if not params["plugin_params"].get("version"):
        params["plugin_params"]["version"] = "latest"

    return plugin_operate_client(bk_tenant_id=bk_tenant_id, params=params)


class PluginSearchParams(TypedDict):
    """插件查询 参数"""

    bk_biz_id: NotRequired[list[int]]
    conditions: NotRequired[list[dict[str, Any]]]
    bk_host_id: NotRequired[list[int]]
    exclude_hosts: NotRequired[list[int]]
    only_ip: NotRequired[bool]
    detail: NotRequired[bool]
    page: int
    pagesize: int


def plugin_search(bk_tenant_id: str, params: PluginSearchParams) -> Any:
    """插件查询接口

    Args:
        bk_tenant_id: 租户ID
        params: 插件查询参数

    Returns:


    Raises:
        BkApiError: 接口调用失败
    """

    return plugin_search_client(bk_tenant_id=bk_tenant_id, params=params)


class IpchooserHostDetailsHostMeta(TypedDict):
    """主机所在资源范围信息。"""

    scope_type: str
    scope_id: str
    bk_biz_id: int


class IpchooserHostDetailsHost(TypedDict):
    """ipchooser_host/details 请求中的主机参数。"""

    host_id: int
    meta: IpchooserHostDetailsHostMeta


class IpchooserHostDetailsScope(TypedDict):
    """ipchooser_host/details 请求中的资源范围参数。"""

    scope_type: str
    scope_id: str


class IpchooserHostDetailsParams(TypedDict):
    """查询主机详情参数。"""

    host_list: list[IpchooserHostDetailsHost]
    scope_list: list[IpchooserHostDetailsScope]
    agent_realtime_state: NotRequired[bool]
    all_scope: NotRequired[bool]


class IpchooserHostDetailCloudArea(TypedDict):
    """云区域信息。"""

    id: int
    name: str


class IpchooserHostDetailBiz(TypedDict):
    """业务信息。"""

    id: int
    name: str


class IpchooserHostDetail(TypedDict):
    """主机详情。"""

    meta: IpchooserHostDetailsHostMeta
    host_id: int
    agent_id: str
    ip: str
    ipv6: str
    host_name: str
    os_name: str
    os_type: str
    alive: int
    cloud_area: IpchooserHostDetailCloudArea
    biz: IpchooserHostDetailBiz
    bk_host_id: int
    bk_biz_id: int
    bk_agent_id: str
    bk_agent_alive: int
    bk_cloud_id: int


def get_ipchooser_host_details(
    bk_tenant_id: str,
    params: IpchooserHostDetailsParams,
) -> list[IpchooserHostDetail]:
    """查询主机详情及 Agent 状态。"""

    return ipchooser_host_details_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
