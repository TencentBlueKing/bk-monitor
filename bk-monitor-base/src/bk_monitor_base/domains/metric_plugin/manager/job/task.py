import base64
import json
import logging
from abc import ABC
from dataclasses import dataclass
from typing import Any, cast

from blue_krill.async_utils.poll_task import CallbackHandler, CallbackResult, CallbackStatus, PollingResult, TaskPoller
from typing_extensions import override

from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.domains.metric_plugin.define import MetricPlugin, MetricPluginMetricField, MetricPluginMetricGroup
from bk_monitor_base.domains.metric_plugin.errors import DebugInstNotExistError, ParsePluginDebugContentError
from bk_monitor_base.domains.metric_plugin.manager.job.define import TASK_DEBUG_STEP, JobMetricPluginDebugInst
from bk_monitor_base.infras.declaratives.controller.constants import ControllerTaskEngine
from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.async_poller import (
    AsyncPollTask,
    AsyncPollTaskManager,
)
from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.async_task_define import CeleryEngine
from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.task_factory import EngineRegistry
from bk_monitor_base.infras.storage import get_bkrepo_storage, handle_file_source_list_to_job_file_source_list
from bk_monitor_base.infras.third_party_api.job.api import (
    JOB_API_BIZ,
    JOB_STEP_STATUS_MAP,
    JOB_STEP_SUCCESS_STATUS,
    FastExecuteJobResult,
    FastExecuteScriptParams,
    FastTransferFileParams,
    GetJobInstanceStatusResult,
    JobInstanceIpLogResult,
    fast_execute_script,
    fast_transfer_file,
    get_job_instance_ip_log,
    get_job_instance_status,
)
from bk_monitor_base.metadata import config as metadata_config

logger: logging.Logger = logging.getLogger(__name__)


# ============== 辅助数据类和函数 ==============


@dataclass
class DebugContext:
    """
    调试上下文数据类，封装常用的上下文字段

    Args:
        debug_task_inst_id: 调试任务实例ID
        job_debug_inst: 调试任务实例对象
        plugin: 关联的指标插件对象
        current_step: 当前调试步骤
        job_instance_id: 作业实例ID
        target_server: 目标服务器信息
        account_alias: 账号别名
    """

    debug_task_inst_id: int
    job_debug_inst: JobMetricPluginDebugInst
    plugin: MetricPlugin
    current_step: TASK_DEBUG_STEP
    job_instance_id: int | None = None
    target_server: dict[str, Any] | None = None
    account_alias: str = "root"


def get_debug_context(context: dict[str, Any], require_job_instance: bool = False) -> DebugContext:
    """
    从上下文中提取并校验调试相关信息

    Args:
        context: 原始上下文字典
        require_job_instance: 是否要求 job_instance_id 存在

    Returns:
        DebugContext: 封装好的调试上下文

    Raises:
        RuntimeError: 当必要信息缺失时抛出
    """
    debug_task_inst_id = context.get("debug_task_inst_id")
    current_step = context.get("CURRENT_STEP", TASK_DEBUG_STEP.TRANSFER_PLUGIN_TO_HOST)

    if not debug_task_inst_id:
        logger.error(f"debug_task_inst_id 为空，Current Step: {current_step}")
        raise DebugInstNotExistError("上下文中 debug_task_inst_id 为空，无法继续执行调试任务")

    job_debug_inst = JobMetricPluginDebugInst.get(debug_task_inst_id)
    if job_debug_inst is None:
        logger.error(
            f"Not Found debug task inst in debug_task_inst_id({debug_task_inst_id}), Current Step: {current_step}"
        )
        raise DebugInstNotExistError(f"上下文中调试实例不存在，无法继续执行调试任务({debug_task_inst_id})")

    plugin_dict: dict[str, Any] | None = context.get("plugin", None)
    if plugin_dict is None:
        logger.error(
            f"Not Found plugin in context for debug_task_inst_id({debug_task_inst_id}), Current Step: {current_step}"
        )
        raise RuntimeError(f"上下文中未找到插件信息，无法继续执行调试任务({debug_task_inst_id})")
    plugin: MetricPlugin = MetricPlugin.model_validate(plugin_dict)
    job_instance_id = context.get("job_instance_id")
    if require_job_instance and not job_instance_id:
        logger.error(
            f"Not Found job_instance_id in context for debug_task_inst_id({debug_task_inst_id}), Current Step: {current_step}"
        )
        raise RuntimeError(f"上下文中未找到作业实例ID，无法继续执行调试任务({debug_task_inst_id})")

    return DebugContext(
        debug_task_inst_id=debug_task_inst_id,
        job_debug_inst=job_debug_inst,
        plugin=plugin,
        current_step=current_step,
        job_instance_id=job_instance_id,
        target_server=context.get("target_server"),
        account_alias=context.get("account_alias", "root"),
    )


@dataclass
class JobStepResult:
    """Job 步骤执行结果"""

    success: bool
    status_code: int
    step_instance_id: int
    error_message: str = ""


def check_job_status(ctx: DebugContext, step_name: str) -> PollingResult | JobStepResult:
    """
    检查 Job 任务状态的公共方法

    Args:
        ctx: 调试上下文
        step_name: 步骤名称（用于错误信息）

    Returns:
        PollingResult.doing(): 任务未完成时返回
        JobStepResult: 任务完成时返回执行结果
    """
    if not ctx.job_instance_id:
        raise RuntimeError(f"{step_name}任务 job_instance_id 为空，无法继续检查任务状态({ctx.debug_task_inst_id})")
    step_status: GetJobInstanceStatusResult = get_job_instance_status(
        bk_tenant_id=ctx.plugin.bk_tenant_id,
        job_instance_id=ctx.job_instance_id,
        bk_biz_id=JOB_API_BIZ,
    )

    if not step_status.get("finished"):
        return PollingResult.doing()

    step_instances = step_status.get("step_instance_list", [])
    if not step_instances:
        raise RuntimeError(f"{step_name}任务步骤信息不存在({ctx.debug_task_inst_id})")

    step_instance = step_instances[0]
    step_instance_id = step_instance.get("step_instance_id")

    if not step_instance_id:
        raise RuntimeError(f"{step_name}任务步骤id不存在({ctx.debug_task_inst_id})")

    # step_instance 级别状态码：3=执行成功, 4=执行失败, 等
    status_code = step_instance.get("status", 4)

    return JobStepResult(
        success=(status_code in JOB_STEP_SUCCESS_STATUS),
        status_code=status_code,
        step_instance_id=step_instance_id,
        error_message=JOB_STEP_STATUS_MAP.get(status_code, "未知错误"),
    )


def execute_script_task(
    ctx: DebugContext,
    script_content: str,
    timeout: int = 120,
    task_name: str | None = None,
) -> int:
    """
    执行脚本任务的公共方法

    Args:
        ctx: 调试上下文
        script_content: 脚本内容（未编码）
        timeout: 超时时间
        task_name: 任务名称

    Returns:
        job_instance_id: 作业实例ID
    """
    if not ctx.target_server:
        raise RuntimeError(f"未找到目标服务器信息，无法继续执行任务({ctx.debug_task_inst_id})")

    script_content_base64 = base64.b64encode(script_content.encode()).decode()

    task_params: FastExecuteScriptParams = {
        "bk_biz_id": JOB_API_BIZ,
        "script_content": script_content_base64,
        "timeout": timeout,
        "script_language": 1,
        "target_server": ctx.target_server,
        "account_alias": ctx.account_alias,
    }

    if task_name:
        task_params["task_name"] = task_name

    result: FastExecuteJobResult = fast_execute_script(
        bk_tenant_id=ctx.plugin.bk_tenant_id,
        params=task_params,
    )

    return result.get("job_instance_id")


class JobDebugAsyncHandler(CallbackHandler):
    """
    作业平台调试异步轮询结果任务处理器

    context中一定会包含debug_task_inst_id
    """

    def _get_debug_inst(self, context: dict[str, Any]) -> JobMetricPluginDebugInst | None:
        """获取调试实例，失败时记录日志并返回 None"""
        debug_task_inst_id = context.get("debug_task_inst_id")
        if not debug_task_inst_id:
            logger.error(f"context 中 debug_task_inst_id 为空，无法继续执行调试任务,context:{context}")
            return None
        job_debug_inst = JobMetricPluginDebugInst.get(debug_task_inst_id)
        if job_debug_inst is None:
            logger.error(f"Not Found debug task inst in debug_task_inst_id({debug_task_inst_id})")
        return job_debug_inst

    def failed_handle(self, result: CallbackResult, context: dict[str, Any]):
        job_debug_inst = self._get_debug_inst(context)
        if job_debug_inst:
            job_debug_inst.failed(result.message or str(cast(dict[str, Any], result.to_dict())))

    @override
    def handle(self, result: CallbackResult, poller: TaskPoller):
        # celery task不指定就是 default队列
        task_cls = AsyncPollTaskManager.get(cast(str, poller.params.get("query_name")))
        context: dict[str, Any] | None = cast(dict[str, Any], poller.params.get("context"))

        if not context:
            logger.error(f"异步轮询器'{poller.__class__.__name__}' 执行结果处理时，context 为空，无法继续执行调试任务")
            return

        if not context.get("debug_task_inst_id"):
            logger.error(
                f"异步轮询器'{poller.__class__.__name__}' 执行结果处理时，context中 debug_task_inst_id 为空，无法继续执行调试任务"
            )
            return

        if not result.is_exception:
            task_cls.post_query(result.data, context)
            return

        if result.status == CallbackStatus.EXCEPTION:
            logger.warning(f"异步轮询器'{poller.__class__.__name__}' 执行超时，")
        else:
            logger.warning(f"异步轮询器'{poller.__class__.__name__}' 出现异常，异常信息：[ {result.message} ]")
        self.failed_handle(result, context)
        task_cls.except_task(result, context)


def submit_query_task(task_cls: type[AsyncPollTask], context: dict[str, Any] | None = None) -> None:
    """
    提交状态型任务
    """
    engine = cast(CeleryEngine, EngineRegistry.get_engine_class(ControllerTaskEngine.CELERY)())
    engine.query_task(
        task_cls=task_cls,
        context=context,
        callback_handler_cls=JobDebugAsyncHandler,
    )


def submit_debug_task(debug_task_inst_id: int, context: dict[str, Any]) -> None:
    """
    sql插件调试任务提交入口

    该函数负责校验必要参数并准备上下文，然后触发异步任务执行文件传输。
    实际的作业平台 API 调用在 TransferPluginToHostTask 中异步执行。

    Args:
        debug_task_inst_id: 调试实例id
        context: 任务上下文
    """
    context["CURRENT_STEP"] = TASK_DEBUG_STEP.TRANSFER_PLUGIN_TO_HOST
    context["debug_task_inst_id"] = debug_task_inst_id

    ctx = get_debug_context(context)

    ctx.job_debug_inst.add_log_entry(
        task_step=ctx.current_step,
        messages="************ 下发插件到采集主机 -【正在执行】************ \n",
    )

    # 提交异步任务执行文件传输
    submit_query_task(task_cls=TransferPluginToHostTask, context=context)


def submit_env_cleanup_task(debug_task_inst_id: int, context: dict[str, Any]) -> None:
    """
    sql插件调试环境清理任务提交入口

    该函数在异步 Worker 中被调用，直接执行清理脚本并触发后续轮询任务。

    Args:
        debug_task_inst_id: 调试实例id
        context: 任务上下文
    """
    context["CURRENT_STEP"] = TASK_DEBUG_STEP.CLEAN_ENVIRONMENT
    context["debug_task_inst_id"] = debug_task_inst_id

    ctx = get_debug_context(context)

    env_clean_script_content: str | None = context.get("env_clean_script_content")
    if not env_clean_script_content:
        logger.error(f"Not Found env_clean_script_content in context for debug_task_inst_id({debug_task_inst_id})")
        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="未找到清理调试环境脚本内容，跳过清理调试环境任务\n",
        )
        return

    ctx.job_debug_inst.add_log_entry(
        task_step=ctx.current_step,
        messages="************ 清理调试环境 -【正在执行】 ************ \n",
    )

    if not ctx.target_server:
        logger.error(f"Not Found target_server in context for debug_task_inst_id({debug_task_inst_id})")
        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="未找到目标服务器信息，无法继续清理调试环境\n",
        )
        return

    job_instance_id = execute_script_task(
        ctx, env_clean_script_content, task_name=f"清理调试环境({debug_task_inst_id})"
    )
    ctx.job_debug_inst.add_log_entry(
        task_step=ctx.current_step,
        messages=f"\n作业平台任务ID: {job_instance_id}\n",
        job_instance=str(job_instance_id),
    )
    context["job_instance_id"] = job_instance_id
    submit_query_task(task_cls=CleanEnvironment, context=context)


class SQLDebugTaskPoller(AsyncPollTask, ABC):
    """
    SQL插件调试任务
    """

    _abstract: bool = True

    @override
    @staticmethod
    def except_task(result: CallbackResult, context: dict[str, Any]) -> None:
        """异常处理函数， 循环任务出错（如超时，抛出异常）后执行的函数"""
        debug_task_inst_id = context.get("debug_task_inst_id")
        if not debug_task_inst_id:
            logger.error(f"context 中 debug_task_inst_id 为空，无法继续执行调试任务,context:{context}")
            return
        job_debug_inst = JobMetricPluginDebugInst.get(debug_task_inst_id)
        if job_debug_inst is None:
            logger.error(
                f"Not Found debug task inst in debug_task_inst_id({debug_task_inst_id}),Current Step: {context['CURRENT_STEP']}"
            )
            return
        # 触发清理任务
        try:
            submit_env_cleanup_task(debug_task_inst_id, context)
        except Exception:
            logger.exception(f"提交清理调试环境任务失败，debug_task_inst_id({debug_task_inst_id})")


class TransferPluginToHostTask(SQLDebugTaskPoller):
    """
    下发插件到采集主机任务

    该任务负责调用作业平台 API 将插件文件传输到目标主机，
    是调试流程的第一个异步任务。
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """
        执行文件传输任务

        Args:
            context: 任务上下文，需包含 file_source_list、target_path、target_server 等参数

        Returns:
            PollingResult.done(job_instance_id): 传输任务提交成功，返回作业实例ID
        """
        ctx = get_debug_context(context)
        # 必要的文件路径
        binary_file_source_path = context.get("binary_path", "")
        config_file_source_path = context.get("debug_yaml_file_path", "")
        # 额外文件路径列表
        extra_file_source_paths = context.get("extra_file_source_paths", [])

        if not binary_file_source_path:
            logger.error(
                f"Not Found binary_path in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"上下文中未找到插件文件路径，无法继续执行调试任务({ctx.debug_task_inst_id})")

        if not config_file_source_path:
            logger.error(
                f"Not Found debug_yaml_file_path in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"上下文中未找到调试配置文件路径，无法继续执行调试任务({ctx.debug_task_inst_id})")

        # 获取存储并处理文件列表
        storage = get_bkrepo_storage(StorageName.JOB)
        file_source_list: list[str] = [binary_file_source_path, config_file_source_path]
        if extra_file_source_paths:
            file_source_list.extend(extra_file_source_paths)
        file_list = handle_file_source_list_to_job_file_source_list(
            storage=storage, file_source_list=[{"file_list": file_source_list}]
        )
        if not file_list:
            logger.error(
                f"Handle file source list to job file source list is empty for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"处理后的文件源列表为空，无法继续执行调试任务({ctx.debug_task_inst_id})")
        # 将处理好的文件列表存入上下文，供异步任务使用
        context["file_source_list"] = file_list
        # 关键参数判空
        if not ctx.target_server:
            logger.error(
                f"Not Found target_server in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"上下文中未找到目标服务器信息，无法继续执行调试任务({ctx.debug_task_inst_id})")
        if not context.get("target_path"):
            logger.error(
                f"Not Found target_path in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"上下文中未找到目标路径，无法继续执行调试任务({ctx.debug_task_inst_id})")
        file_list = context.get("file_source_list")
        if not file_list:
            raise RuntimeError(f"上下文中未找到文件源列表，无法继续执行调试任务({ctx.debug_task_inst_id})")

        if not ctx.target_server:
            raise RuntimeError(f"上下文中未找到目标服务器信息，无法继续执行调试任务({ctx.debug_task_inst_id})")

        target_path = context.get("target_path")
        if not target_path:
            raise RuntimeError(f"上下文中未找到目标路径，无法继续执行调试任务({ctx.debug_task_inst_id})")

        params: FastTransferFileParams = {
            "bk_biz_id": JOB_API_BIZ,
            "file_target_path": cast(str, target_path),
            "transfer_mode": 2,
            "file_source_list": file_list,
            "target_server": ctx.target_server,
            "account_alias": ctx.account_alias,
            "timeout": 300,
            "task_name": f"下发插件到采集主机({ctx.debug_task_inst_id})",
        }
        result = fast_transfer_file(bk_tenant_id=ctx.plugin.bk_tenant_id, params=params)
        job_instance_id = result.get("job_instance_id")

        return PollingResult.done(job_instance_id)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """
        文件传输任务完成后的处理

        Args:
            data: query 返回的 job_instance_id
            context: 任务上下文
        """
        ctx = get_debug_context(context)
        job_instance_id = data

        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages=f"\n作业平台任务ID: {job_instance_id}\n",
            job_instance=str(job_instance_id),
        )
        context["job_instance_id"] = job_instance_id

        # 触发下一个任务：轮询文件传输状态
        submit_query_task(task_cls=StartDebugMetrics, context=context)


class CleanEnvironment(SQLDebugTaskPoller):
    """
    清理调试环境任务
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_debug_context(context, require_job_instance=True)
        result = check_job_status(ctx, "清理调试环境")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            ctx.job_debug_inst.add_log_entry(
                task_step=ctx.current_step,
                messages=f"\n ************ 清理调试环境 -【执行失败】 ************ \n错误信息：{result.error_message}\n",
            )
            raise RuntimeError(
                f"清理调试环境任务执行失败，错误信息：{result.error_message}，无法继续执行调试任务({ctx.debug_task_inst_id})"
            )

        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="\n ************ 清理调试环境 -【执行成功】 ************ \n",
        )
        return PollingResult.done(None)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """最后一步任务，无后置操作"""
        return

    @override
    @staticmethod
    def except_task(result: CallbackResult, context: dict[str, Any]) -> None:
        """异常处理函数， 清理任务异常仅记录日志"""
        return


class StartDebugMetrics(SQLDebugTaskPoller):
    """
    启动调试采集任务
    last_step: TASK_DEBUG_STEP.TRANSFER_PLUGIN_TO_HOST: 检查并下发插件完成后，启动调试采集任务
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_debug_context(context, require_job_instance=True)
        result = check_job_status(ctx, "调试下发插件")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(
                f"调试下发插件任务执行失败，错误信息：{result.error_message}，无法继续执行调试任务({ctx.debug_task_inst_id})"
            )

        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="\n ************ 下发插件到采集主机 -【执行成功】 ************\n",
        )
        return PollingResult.done(None)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """循环后任务， 循环任务返回done后执行的函数"""
        context["CURRENT_STEP"] = TASK_DEBUG_STEP.START_DEBUG_METRICS
        ctx = get_debug_context(context)

        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="\n************ 调试采集任务 -【正在执行】 ************\n",
        )

        if not ctx.target_server:
            logger.error(
                f"Not Found target_server in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            ctx.job_debug_inst.add_log_entry(
                task_step=ctx.current_step,
                messages="未找到目标服务器信息，无法继续调试\n",
            )
            return

        start_debug_script_content = context.get("start_debug_script_content", "")
        if not start_debug_script_content:
            logger.error(
                f"Not Found start_debug_script_content in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"上下文中未找到调试脚本内容，无法继续执行指标调试任务({ctx.debug_task_inst_id})")

        job_instance_id = execute_script_task(
            ctx, start_debug_script_content, task_name=f"调试采集任务({ctx.debug_task_inst_id})"
        )
        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages=f"\n作业平台任务ID: {job_instance_id}\n",
            job_instance=str(job_instance_id),
        )
        context["job_instance_id"] = job_instance_id
        submit_query_task(task_cls=ParseDebugMetrics, context=context)


class ParseDebugMetrics(SQLDebugTaskPoller):
    """
    解析调试采集结果任务
    last_step: TASK_DEBUG_STEP.START_DEBUG_METRICS: 启动调试采集任务
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_debug_context(context, require_job_instance=True)
        result = check_job_status(ctx, "解析调试采集结果")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise ParsePluginDebugContentError(
                f"解析调试采集结果任务执行失败，错误信息：{result.error_message}，无法继续执行解析调试采集结果任务({ctx.debug_task_inst_id})"
            )
        if ctx.job_instance_id is None:
            raise ParsePluginDebugContentError(
                f"解析调试采集结果任务执行失败，错误信息：作业实例ID(job_instance_id)为空，无法继续执行解析调试采集结果任务({ctx.debug_task_inst_id})"
            )

        # 从 target_server 获取目标主机信息
        if not ctx.target_server:
            raise ParsePluginDebugContentError(
                f"解析调试采集结果任务执行失败，错误信息：目标服务器信息(target_server)为空，无法继续执行解析调试采集结果任务({ctx.debug_task_inst_id})"
            )
        ip_info = ctx.target_server.get("ip_list", [{}])[0]
        ip = ip_info.get("ip", "127.0.0.1")
        bk_cloud_id = ip_info.get("bk_cloud_id", 0)

        # 获取执行结果输出
        log_result: JobInstanceIpLogResult = get_job_instance_ip_log(
            bk_tenant_id=ctx.plugin.bk_tenant_id,
            bk_biz_id=JOB_API_BIZ,
            job_instance_id=int(ctx.job_instance_id),
            step_instance_id=result.step_instance_id,
            ip=ip,
            bk_cloud_id=bk_cloud_id,
        )

        if log_result.get("log_type") != 1:
            ctx.job_debug_inst.add_log_entry(
                task_step=ctx.current_step,
                messages=f"\n解析调试采集结果任务执行失败，错误信息：获取到的日志类型非文本类型，无法继续执行解析调试采集结果任务({ctx.debug_task_inst_id})\n",
            )
            raise RuntimeError(
                f"解析调试采集结果任务执行失败，错误信息：获取到的日志类型非文本类型，无法继续执行解析调试采集结果任务({ctx.debug_task_inst_id})"
            )

        log_content = log_result.get("log_content", "")
        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="\n ************ 调试采集任务 -【执行成功】 ************\n",
        )

        return PollingResult.done(log_content)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """循环后任务， 循环任务返回done后执行的函数"""
        context["CURRENT_STEP"] = TASK_DEBUG_STEP.PARSE_DEBUG_METRICS
        ctx = get_debug_context(context)

        if data is None:
            logger.error(
                f"Not Found debug data in context for debug_task_inst_id({ctx.debug_task_inst_id}), Current Step: {ctx.current_step}"
            )
            raise RuntimeError(f"上下文中未找到调试数据，无法继续执行指标解析任务({ctx.debug_task_inst_id})")

        sql_json_str = str(data)
        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages=f"\n ************ 解析调试采集结果 -【正在执行】 ************\n原始指标：{str(data)}\n",
            log_content=sql_json_str,
        )

        metric_json = ParseDebugMetrics._parse_metrics(sql_json_str, context, ctx)

        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages="\n ************ 解析调试采集结果 -【执行成功】 ************\n",
        )
        ctx.job_debug_inst.metrics = [group.model_dump() for group in metric_json]
        # 调试成功
        ctx.job_debug_inst.success()
        # 触发清理任务
        submit_env_cleanup_task(ctx.debug_task_inst_id, context)

    @staticmethod
    def _parse_metrics(
        sql_json_str: str,
        context: dict[str, Any],
        ctx: DebugContext,
    ) -> list[MetricPluginMetricGroup]:
        """
        解析 SQL 执行结果为指标组

        Args:
            sql_json_str: SQL 执行结果 JSON 字符串
            context: 原始上下文
            ctx: 调试上下文

        Returns:
            解析后的指标组列表
        """
        metric_json: list[MetricPluginMetricGroup] = []

        try:
            sql_json = json.loads(sql_json_str)
            sql_json_map: dict[str, Any] = {content["sql"]: content for content in sql_json}
            sql_content: list[dict[str, Any]] = context.get("sql_content", [])

            for content in sql_content:
                sql_alias = content["classification_id"]
                table_name_zh = content["classification_name"]
                metric_group = MetricPluginMetricGroup(
                    table_name=sql_alias,
                    table_desc=table_name_zh,
                    fields=[],
                )
                metric_json.append(metric_group)

                # 找到对应SQL的结果集
                sql_data = sql_json_map.get(content["content"], {}).get("data", [])
                if not sql_data:
                    continue

                for metric_name, metric_value in sql_data[0].items():
                    ParseDebugMetrics._validate_metric_field_name(metric_name, content, ctx)
                    field = ParseDebugMetrics._create_metric_field(metric_name, metric_value)
                    metric_group.fields.append(field)

        except json.JSONDecodeError as e:
            ctx.job_debug_inst.add_log_entry(
                task_step=ctx.current_step,
                messages=f"\n ************ 解析调试采集结果 -【执行失败】 ************\n错误信息：调试结果解析失败，返回结果非标准JSON格式，错误详情：{str(e)}\n",
            )
            raise RuntimeError(f"调试结果解析失败，返回结果非标准JSON格式，错误详情：{str(e)}") from e
        except ParsePluginDebugContentError:
            raise
        except Exception as e:
            ctx.job_debug_inst.add_log_entry(
                task_step=ctx.current_step,
                messages=f"\n ************ 解析调试采集结果 -【执行失败】 ************\n错误信息：调试结果解析失败，错误详情：{str(e)}\n",
            )
            raise RuntimeError(f"调试结果解析失败，错误详情：{str(e)}") from e

        return metric_json

    @staticmethod
    def _validate_metric_field_name(metric_name: str, sql_content: dict[str, Any], ctx: DebugContext) -> None:
        """校验 SQL 调试返回列名是否命中结果表保留字段。"""
        if metric_name.upper() not in metadata_config.RT_RESERVED_WORD_EXACT:
            return

        sql_id = sql_content.get("classification_id", "")
        sql_name = sql_content.get("classification_name", "")
        message = (
            f"SQL插件调试结果字段[{metric_name}]命中 InfluxDB/结果表保留字，无法作为指标或维度字段。"
            f"SQL规则：{sql_id}({sql_name})。"
            f"修复建议：请在 SQL 中使用 AS 为该列设置非保留字别名，例如将 `{metric_name}` 改为 `{metric_name}_value`，"
            "避免使用 SELECT、FROM、WHERE、TIME、TIMESTAMP 等 InfluxDB 关键字或内置字段名。"
        )
        ctx.job_debug_inst.add_log_entry(
            task_step=ctx.current_step,
            messages=f"\n ************ 解析调试采集结果 -【执行失败】 ************\n错误信息：{message}\n",
        )
        ctx.job_debug_inst.failed(message)
        raise ParsePluginDebugContentError(message)

    @staticmethod
    def _create_metric_field(metric_name: str, metric_value: Any) -> MetricPluginMetricField:
        """根据值类型创建指标或维度字段"""
        is_numeric = isinstance(metric_value, float | int) or ParseDebugMetrics._is_float_string(str(metric_value))

        if is_numeric:
            return MetricPluginMetricField(
                name=metric_name,
                description=metric_name,
                type="double",
                monitor_type="metric",
            )
        else:
            return MetricPluginMetricField(
                name=metric_name,
                description=metric_name,
                type="string",
                monitor_type="dimension",
            )

    @staticmethod
    def _is_float_string(s: Any) -> bool:
        """判断字符串是否表示浮点数"""
        if not isinstance(s, str):
            return False
        parts = s.split(".")
        if len(parts) > 2:
            return False
        return len(parts) > 0 and all(part and part.isdigit() for part in parts)
