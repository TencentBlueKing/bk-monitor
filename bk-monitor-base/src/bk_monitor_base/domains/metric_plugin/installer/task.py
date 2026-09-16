import base64
import logging
from abc import ABC
from dataclasses import dataclass
from typing import Any, cast

from blue_krill.async_utils.poll_task import CallbackHandler, CallbackResult, PollingResult, TaskPoller
from typing_extensions import override

from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.domains.metric_plugin.constants import (
    JOB_TIMEOUT,
    JobTaskActionEnum,
    JobTaskLogStatusEnum,
    JobTaskStatusEnum,
)
from bk_monitor_base.domains.metric_plugin.define import JobTaskInstance
from bk_monitor_base.domains.metric_plugin.installer.define import TaskDeployStep
from bk_monitor_base.domains.metric_plugin.models import JobTaskInstanceModel
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
    fast_execute_script,
    fast_transfer_file,
    get_job_instance_status,
)

logger = logging.getLogger(__name__)


@dataclass
class DeployContext:
    """
    部署上下文数据类
    """

    job_task_inst_id: int
    job_task_inst: JobTaskInstance
    bk_tenant_id: str
    current_step: TaskDeployStep
    job_instance_id: int | None = None
    target_server: dict[str, Any] | None = None
    account_alias: str = "root"


def get_deploy_context(context: dict[str, Any], require_job_instance: bool = False) -> DeployContext:
    job_task_inst_id_raw = context.get("job_task_inst_id")
    current_step = context.get("CURRENT_STEP", TaskDeployStep.TRANSFER_PLUGIN)

    if job_task_inst_id_raw is None or job_task_inst_id_raw == "":
        logger.error(f"job_task_inst_id 为空或缺失，Current Step: {current_step}")
        raise RuntimeError("上下文中缺少必需的 job_task_inst_id（应为正整数），无法继续执行部署任务")
    try:
        job_task_inst_id = int(job_task_inst_id_raw)
    except (TypeError, ValueError) as exc:
        logger.error(
            f"job_task_inst_id 类型或格式不正确，当前值为({job_task_inst_id_raw!r})，Current Step: {current_step}"
        )
        raise RuntimeError(f"上下文中 job_task_inst_id 无效（{job_task_inst_id_raw!r}），应为正整数") from exc

    if job_task_inst_id <= 0:
        logger.error(f"job_task_inst_id 必须为正整数，当前值为({job_task_inst_id})，Current Step: {current_step}")
        raise RuntimeError(f"上下文中 job_task_inst_id 无效（{job_task_inst_id}），应为正整数")

    try:
        job_task_inst = JobTaskInstanceModel.objects.get(pk=job_task_inst_id).to_instance()
    except JobTaskInstanceModel.DoesNotExist as err:
        logger.error(f"Not Found job task inst in job_task_inst_id({job_task_inst_id})")
        raise RuntimeError(f"上下文中部署任务实例不存在({job_task_inst_id})") from err

    job_instance_id = context.get("job_instance_id")
    if require_job_instance and not job_instance_id:
        logger.error(f"Not Found job_instance_id in context for job_task_inst_id({job_task_inst_id})")
        raise RuntimeError(f"上下文中未找到作业实例ID({job_task_inst_id})")

    return DeployContext(
        job_task_inst_id=job_task_inst_id,
        job_task_inst=job_task_inst,
        bk_tenant_id=job_task_inst.bk_tenant_id,
        current_step=current_step,
        job_instance_id=job_instance_id,
        target_server=context.get("target_server"),
        account_alias=context.get("account_alias", "root"),
    )


@dataclass
class JobStepResult:
    success: bool
    status_code: int
    step_instance_id: int
    error_message: str = ""


def check_deploy_job_status(ctx: DeployContext, step_name: str) -> PollingResult | JobStepResult:
    if not ctx.job_instance_id:
        raise RuntimeError(f"{step_name}任务 job_instance_id 为空")

    step_status: GetJobInstanceStatusResult = get_job_instance_status(
        bk_tenant_id=ctx.bk_tenant_id,
        job_instance_id=ctx.job_instance_id,
        bk_biz_id=JOB_API_BIZ,
    )

    if not step_status.get("finished"):
        return PollingResult.doing()

    step_instances = step_status.get("step_instance_list", [])
    if not step_instances:
        raise RuntimeError(f"{step_name}任务步骤信息不存在")

    step_instance = step_instances[0]
    status_code = step_instance.get("status", 4)  # 默认为执行失败

    return JobStepResult(
        success=(status_code in JOB_STEP_SUCCESS_STATUS),
        status_code=status_code,
        step_instance_id=step_instance.get("step_instance_id", 0),
        error_message=JOB_STEP_STATUS_MAP.get(status_code, "未知错误"),
    )


def execute_deploy_script_task(
    ctx: DeployContext, script_content: str, timeout: int = JOB_TIMEOUT, task_name: str | None = None
) -> int:
    if not ctx.target_server:
        raise RuntimeError("未找到目标服务器信息")

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
        bk_tenant_id=ctx.bk_tenant_id,
        params=task_params,
    )

    return result.get("job_instance_id")


class DeployAsyncHandler(CallbackHandler):
    def _get_job_inst(self, context: dict[str, Any]) -> JobTaskInstance | None:
        job_task_inst_id = context.get("job_task_inst_id")
        if not job_task_inst_id:
            return None
        try:
            return JobTaskInstanceModel.objects.get(pk=job_task_inst_id).to_instance()
        except JobTaskInstanceModel.DoesNotExist:
            return None

    def failed_handle(self, result: CallbackResult, context: dict[str, Any]):
        job_inst = self._get_job_inst(context)
        if job_inst:
            # 获取当前步骤，添加失败日志
            current_step = context.get("CURRENT_STEP", "failed_handle")
            job_instance_id = context.get("job_instance_id")
            error_message = result.message or "任务执行失败"

            # 记录失败日志
            job_inst.add_log_entry(
                step=current_step,
                status=JobTaskLogStatusEnum.FAILED,
                messages=f"执行失败: {error_message}",
                job_instance_id=job_instance_id,
            )

            # 标记任务失败
            job_inst.fail_task(error_message)
            JobTaskInstanceModel.save_instance(job_inst)

    @override
    def handle(self, result: CallbackResult, poller: TaskPoller):
        task_cls = AsyncPollTaskManager.get(cast(str, poller.params.get("query_name")))
        context: dict[str, Any] | None = cast(dict[str, Any], poller.params.get("context"))

        if not context:
            return

        if not result.is_exception:
            task_cls.post_query(result.data, context)
            return

        self.failed_handle(result, context)
        task_cls.except_task(result, context)


def submit_deploy_query_task(task_cls: type[AsyncPollTask], context: dict[str, Any] | None = None) -> None:
    engine = cast(CeleryEngine, EngineRegistry.get_engine_class(ControllerTaskEngine.CELERY)())
    engine.query_task(
        task_cls=task_cls,
        context=context,
        callback_handler_cls=DeployAsyncHandler,
    )


class DeployTaskPoller(AsyncPollTask, ABC):
    """部署任务轮询基类"""

    _abstract: bool = True

    @override
    @staticmethod
    def except_task(result: CallbackResult, context: dict[str, Any]) -> None:
        """异常处理函数， 循环任务出错（如超时，抛出异常）后执行的函数"""
        # TODO 仅启动清理环境的任务，不更新状态(是否合理且必要？)


class InitialTransferPluginFilesTask(DeployTaskPoller):
    """
    下发插件文件任务

    该任务负责调用作业平台 API 将插件文件传输到目标主机，
    是安装流程的第一个异步任务。
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """
        执行文件传输任务

        Args:
            context: 任务上下文，需包含 file_source_list、plugin_target_path、target_server 等参数

        Returns:
            PollingResult.done(job_instance_id): 传输任务提交成功，返回作业实例ID
        """
        ctx = get_deploy_context(context)

        # 准备下发插件
        plugin_file_path = context.get("binary_path")
        plugin_config_path = context.get("sql_config_file_path")
        target_path = context.get("target_path")

        if not plugin_file_path or not plugin_config_path or not target_path:
            raise RuntimeError("缺少插件文件路径参数")

        storage = get_bkrepo_storage(StorageName.JOB)
        file_list = handle_file_source_list_to_job_file_source_list(
            file_source_list=[{"file_list": [plugin_file_path, plugin_config_path]}],
            storage=storage,
        )
        if not file_list:
            raise RuntimeError("上下文中未找到文件源列表，无法继续执行部署任务")

        if ctx.target_server is None:
            raise RuntimeError("缺少目标服务器信息，无法继续下发插件文件")

        params: FastTransferFileParams = {
            "bk_biz_id": JOB_API_BIZ,
            "file_target_path": target_path,
            "transfer_mode": 2,
            "file_source_list": file_list,
            "target_server": ctx.target_server,
            "account_alias": ctx.account_alias,
            "timeout": JOB_TIMEOUT,
            "task_name": f"下发插件({ctx.job_task_inst_id})",
        }

        result = fast_transfer_file(bk_tenant_id=ctx.bk_tenant_id, params=params)
        job_instance_id = result.get("job_instance_id")
        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.TRANSFER_PLUGIN,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始下发插件, JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)
        return PollingResult.done(job_instance_id)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """
        文件传输任务提交后的处理

        Args:
            data: query 返回的 job_instance_id
            context: 任务上下文
        """
        job_instance_id = data
        context["job_instance_id"] = job_instance_id

        # 触发下一个任务：轮询文件传输状态
        submit_deploy_query_task(TransferPluginTask, context)


class InitialExecuteRemovePluginScriptTask(DeployTaskPoller):
    """
    执行删除插件脚本任务

    该任务负责调用作业平台 API 执行删除插件脚本，
    是卸载流程的第一个异步任务。
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """
        执行删除插件脚本

        Args:
            context: 任务上下文，需包含 remove_plugin_script、target_server 等参数

        Returns:
            PollingResult.done(job_instance_id): 脚本执行任务提交成功，返回作业实例ID
        """
        script_content = context.get("remove_plugin_script")
        if not script_content:
            raise RuntimeError("缺少删除插件脚本")

        ctx = get_deploy_context(context)

        script_content = context.get("remove_plugin_script")
        if not script_content:
            raise RuntimeError("缺少删除插件脚本")

        job_instance_id = execute_deploy_script_task(ctx, script_content, task_name=f"删除插件({ctx.job_task_inst_id})")
        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.REMOVE_PLUGIN,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始删除插件, JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)
        return PollingResult.done(job_instance_id)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """
        删除插件脚本提交后的处理

        Args:
            data: query 返回的 job_instance_id
            context: 任务上下文
        """
        job_instance_id = data
        context["job_instance_id"] = job_instance_id
        # 触发下一个任务：轮询脚本执行状态
        submit_deploy_query_task(RemovePluginTask, context)


class InitialExecuteRemoveConfigScriptTask(DeployTaskPoller):
    """
    执行删除配置脚本任务

    该任务负责调用作业平台 API 执行删除配置脚本，
    是停止采集流程的第一个异步任务。
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """
        执行删除配置脚本

        Args:
            context: 任务上下文，需包含 remove_config_script、target_server 等参数

        Returns:
            PollingResult.done(job_instance_id): 脚本执行任务提交成功，返回作业实例ID
        """
        script_content = context.get("remove_config_script")
        if not script_content:
            raise RuntimeError("缺少删除配置脚本")

        ctx = get_deploy_context(context)

        script_content = context.get("remove_config_script")
        if not script_content:
            raise RuntimeError("缺少删除配置脚本")

        job_instance_id = execute_deploy_script_task(
            ctx, script_content, task_name=f"停止采集-删除配置({ctx.job_task_inst_id})"
        )
        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.REMOVE_CONFIG,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始停止采集(删除配置), JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)
        return PollingResult.done(job_instance_id)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """
        删除配置脚本提交后的处理

        Args:
            data: query 返回的 job_instance_id
            context: 任务上下文
        """
        job_instance_id = data
        context["job_instance_id"] = job_instance_id

        # 触发下一个任务：轮询脚本执行状态
        submit_deploy_query_task(RemoveConfigTask, context)


class InitialTransferConfigFilesTask(DeployTaskPoller):
    """
    下发配置文件任务

    该任务负责调用作业平台 API 将配置文件传输到目标主机，
    是启动采集流程的第一个异步任务。
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """
        执行配置文件传输任务

        Args:
            context: 任务上下文，需包含 file_source_list、bkmonitorbeat_target_path、target_server 等参数

        Returns:
            PollingResult.done(job_instance_id): 传输任务提交成功，返回作业实例ID
        """
        # 准备下发插件
        bkmonitorbeat_conf_source_file_path = context.get("bkmonitorbeat_conf_source_file_path")
        target_path = context.get("bkmonitorbeat_target_path")
        if not bkmonitorbeat_conf_source_file_path or not target_path:
            raise RuntimeError("缺少配置目标路径")
        storage = get_bkrepo_storage(StorageName.JOB)
        file_list = handle_file_source_list_to_job_file_source_list(
            file_source_list=[{"file_list": [bkmonitorbeat_conf_source_file_path]}], storage=storage
        )

        # 将处理好的文件列表存入上下文，供异步任务使用
        context["file_source_list"] = file_list
        ctx = get_deploy_context(context)

        if ctx.target_server is None:
            raise RuntimeError("缺少目标服务器信息，无法继续下发配置文件")

        file_list = context.get("file_source_list")
        if not file_list:
            raise RuntimeError("上下文中未找到文件源列表，无法继续执行部署任务")

        params: FastTransferFileParams = {
            "bk_biz_id": JOB_API_BIZ,
            "file_target_path": target_path,
            "transfer_mode": 2,
            "file_source_list": file_list,
            "target_server": ctx.target_server,
            "account_alias": ctx.account_alias,
            "timeout": JOB_TIMEOUT,
            "task_name": f"启动采集-下发配置({ctx.job_task_inst_id})",
        }

        result = fast_transfer_file(bk_tenant_id=ctx.bk_tenant_id, params=params)
        job_instance_id = result.get("job_instance_id")

        ctx.job_task_inst.add_log_entry(
            step=context["CURRENT_STEP"],
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始启动采集(下发配置), JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)
        return PollingResult.done(job_instance_id)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """
        配置文件传输任务提交后的处理

        Args:
            data: query 返回的 job_instance_id
            context: 任务上下文
        """
        job_instance_id = data
        context["job_instance_id"] = job_instance_id

        # 触发下一个任务：轮询文件传输状态
        submit_deploy_query_task(TransferBkmonitorbeatConfigTask, context)


class RestartBkmonitorbeatTask(DeployTaskPoller):
    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "重启bkmonitorbeat")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(result.error_message)

        return PollingResult.done()

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="重启bkmonitorbeat成功",
            job_instance_id=ctx.job_instance_id,
        )
        ctx.job_task_inst.status = JobTaskStatusEnum.SUCCESS
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)


class TransferBkmonitorbeatConfigTask(DeployTaskPoller):
    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "下发bkmonitorbeat配置")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(result.error_message)

        return PollingResult.done()

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="下发bkmonitorbeat配置成功",
            job_instance_id=ctx.job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        # 检查是否需要执行 chmod 授权（install/start 流程需要，stop/uninstall 不需要）
        chmod_plugin_script = context.get("chmod_plugin_script")
        if chmod_plugin_script and ctx.job_task_inst.action in [
            JobTaskActionEnum.INSTALL,
            JobTaskActionEnum.START,
            JobTaskActionEnum.UPDATE,
            JobTaskActionEnum.RETRY,
        ]:
            # 提交 chmod 授权任务
            context["CURRENT_STEP"] = TaskDeployStep.CHMOD_PLUGIN
            job_instance_id = execute_deploy_script_task(
                ctx, chmod_plugin_script, task_name=f"插件二进制授权({ctx.job_task_inst_id})"
            )
            context["job_instance_id"] = job_instance_id

            ctx.job_task_inst.add_log_entry(
                step=TaskDeployStep.CHMOD_PLUGIN,
                status=JobTaskLogStatusEnum.RUNNING,
                messages=f"开始对插件二进制授权, JobID: {job_instance_id}",
                job_instance_id=job_instance_id,
            )
            JobTaskInstanceModel.save_instance(ctx.job_task_inst)

            submit_deploy_query_task(ChmodPluginTask, context)
        else:
            # 直接提交重启任务（stop/uninstall 流程或无 chmod 脚本时）
            context["CURRENT_STEP"] = TaskDeployStep.RESTART_BKMONITORBEAT
            script_content = context.get("restart_bkmonitorbeat_script")
            if not script_content:
                raise RuntimeError("缺少重启bkmonitorbeat脚本")

            job_instance_id = execute_deploy_script_task(ctx, script_content)
            context["job_instance_id"] = job_instance_id

            ctx.job_task_inst.add_log_entry(
                step=TaskDeployStep.RESTART_BKMONITORBEAT,
                status=JobTaskLogStatusEnum.RUNNING,
                messages=f"开始重启bkmonitorbeat, JobID: {job_instance_id}",
                job_instance_id=job_instance_id,
            )
            JobTaskInstanceModel.save_instance(ctx.job_task_inst)

            submit_deploy_query_task(RestartBkmonitorbeatTask, context)


class ChmodPluginTask(DeployTaskPoller):
    """执行插件二进制授权任务

    该任务负责在下发 bkmonitorbeat 配置完成后，对插件二进制文件执行 chmod +x 授权操作，
    确保插件具有可执行权限。仅在 install/start 流程中执行，在重启 bkmonitorbeat 之前。
    """

    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """轮询 chmod 授权任务执行状态

        Args:
            context: 任务上下文

        Returns:
            PollingResult: 任务执行状态
        """
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "插件二进制授权")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(result.error_message)

        return PollingResult.done()

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """chmod 授权任务完成后的处理

        Args:
            data: query 返回的数据
            context: 任务上下文
        """
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="插件二进制授权成功",
            job_instance_id=ctx.job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        # 提交重启 bkmonitorbeat 任务
        context["CURRENT_STEP"] = TaskDeployStep.RESTART_BKMONITORBEAT
        script_content = context.get("restart_bkmonitorbeat_script")
        if not script_content:
            raise RuntimeError("缺少重启bkmonitorbeat脚本")

        job_instance_id = execute_deploy_script_task(
            ctx, script_content, task_name=f"重启bkmonitorbeat({ctx.job_task_inst_id})"
        )
        context["job_instance_id"] = job_instance_id

        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.RESTART_BKMONITORBEAT,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始重启bkmonitorbeat, JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        submit_deploy_query_task(RestartBkmonitorbeatTask, context)


class TransferPluginTask(DeployTaskPoller):
    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "下发插件")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(result.error_message)

        return PollingResult.done()

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="下发插件成功",
            job_instance_id=ctx.job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        # 提交下发配置任务
        context["CURRENT_STEP"] = TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG

        bkmonitorbeat_conf_source_file_path = context.get("bkmonitorbeat_conf_source_file_path")
        target_path = context.get("bkmonitorbeat_target_path")
        if not bkmonitorbeat_conf_source_file_path or not target_path:
            raise RuntimeError("缺少配置路径参数")

        storage = get_bkrepo_storage(StorageName.JOB)
        file_list = handle_file_source_list_to_job_file_source_list(
            storage=storage, file_source_list=[{"file_list": [bkmonitorbeat_conf_source_file_path]}]
        )
        if ctx.target_server is None:
            raise RuntimeError("缺少目标服务器信息，无法继续下发配置文件")
        params: FastTransferFileParams = {
            "bk_biz_id": JOB_API_BIZ,
            "file_target_path": target_path,
            "transfer_mode": 2,
            "file_source_list": file_list,
            "target_server": ctx.target_server,
            "account_alias": ctx.account_alias,
            "timeout": JOB_TIMEOUT,
            "task_name": f"下发bkmonitorbeat配置({ctx.job_task_inst_id})",
        }

        result = fast_transfer_file(bk_tenant_id=ctx.bk_tenant_id, params=params)
        job_instance_id = result.get("job_instance_id")
        context["job_instance_id"] = job_instance_id

        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始下发bkmonitorbeat配置, JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        submit_deploy_query_task(TransferBkmonitorbeatConfigTask, context)


class RemoveConfigTask(DeployTaskPoller):
    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "删除配置")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(result.error_message)
        return PollingResult.done(None)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="删除配置成功",
            job_instance_id=ctx.job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        # 如果是卸载/停止流程，接下来重启bkmonitorbeat

        context["CURRENT_STEP"] = TaskDeployStep.RESTART_BKMONITORBEAT
        script_content = context.get("restart_bkmonitorbeat_script")
        if not script_content:
            raise RuntimeError("缺少重启bkmonitorbeat脚本")

        job_instance_id = execute_deploy_script_task(
            ctx, script_content, task_name=f"重启bkmonitorbeat({ctx.job_task_inst_id})"
        )
        context["job_instance_id"] = job_instance_id

        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.RESTART_BKMONITORBEAT,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始重启bkmonitorbeat, JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        if ctx.job_task_inst.action in [JobTaskActionEnum.RETRY, JobTaskActionEnum.UPDATE]:
            submit_deploy_query_task(RetryRestartBkmonitorbeatTask, context)
        else:
            submit_deploy_query_task(RestartBkmonitorbeatTask, context)


class RetryRestartBkmonitorbeatTask(DeployTaskPoller):
    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "重启bkmonitorbeat(重试卸载阶段)")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            raise RuntimeError(result.error_message)

        return PollingResult.done()

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="重启bkmonitorbeat成功(重试卸载阶段)",
            job_instance_id=ctx.job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        # 卸载阶段完成，开始安装阶段
        submit_install_task(ctx.job_task_inst_id, context)


class RemovePluginTask(DeployTaskPoller):
    @override
    @staticmethod
    def query(context: dict[str, Any]) -> PollingResult:
        ctx = get_deploy_context(context, require_job_instance=True)
        result = check_deploy_job_status(ctx, "删除插件")

        if isinstance(result, PollingResult):
            return result

        if not result.success:
            # 抛出异常
            raise RuntimeError(result.error_message)

        return PollingResult.done(None)

    @override
    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        ctx = get_deploy_context(context)
        ctx.job_task_inst.add_log_entry(
            step=ctx.current_step,
            status=JobTaskLogStatusEnum.SUCCESS,
            messages="删除插件成功",
            job_instance_id=ctx.job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        # 提交删除配置任务
        context["CURRENT_STEP"] = TaskDeployStep.REMOVE_CONFIG
        script_content = context.get("remove_config_script")
        if not script_content:
            raise RuntimeError("缺少删除配置脚本")

        job_instance_id = execute_deploy_script_task(ctx, script_content)
        context["job_instance_id"] = job_instance_id

        ctx.job_task_inst.add_log_entry(
            step=TaskDeployStep.REMOVE_CONFIG,
            status=JobTaskLogStatusEnum.RUNNING,
            messages=f"开始删除配置, JobID: {job_instance_id}",
            job_instance_id=job_instance_id,
        )
        JobTaskInstanceModel.save_instance(ctx.job_task_inst)

        submit_deploy_query_task(RemoveConfigTask, context)


def submit_install_task(job_inst_id: int, context: dict[str, Any]) -> None:
    """
    插件安装任务提交入口

    该函数负责校验必要参数并准备上下文，然后触发异步任务执行文件传输。
    实际的作业平台 API 调用在 InitialTransferPluginFilesTask 中异步执行。

    Args:
        job_inst_id: 部署任务实例ID
        context: 任务上下文
    """
    context["job_task_inst_id"] = job_inst_id
    context["CURRENT_STEP"] = TaskDeployStep.TRANSFER_PLUGIN

    get_deploy_context(context)  # 校验上下文

    # 提交异步任务执行文件传输
    submit_deploy_query_task(InitialTransferPluginFilesTask, context)


def submit_uninstall_task(job_inst_id: int, context: dict[str, Any]) -> None:
    """
    插件卸载任务提交入口

    该函数负责校验必要参数并准备上下文，然后触发异步任务执行删除插件脚本。
    实际的作业平台 API 调用在 InitialExecuteRemovePluginScriptTask 中异步执行。

    Args:
        job_inst_id: 部署任务实例ID
        context: 任务上下文
    """
    context["job_task_inst_id"] = job_inst_id
    context["CURRENT_STEP"] = TaskDeployStep.REMOVE_PLUGIN

    get_deploy_context(context)  # 校验上下文

    # 提交异步任务执行删除插件脚本
    submit_deploy_query_task(InitialExecuteRemovePluginScriptTask, context)


def submit_stop_task(job_inst_id: int, context: dict[str, Any]) -> None:
    """
    停止采集任务提交入口

    该函数负责校验必要参数并准备上下文，然后触发异步任务执行删除配置脚本。
    实际的作业平台 API 调用在 InitialExecuteRemoveConfigScriptTask 中异步执行。

    Args:
        job_inst_id: 部署任务实例ID
        context: 任务上下文
    """
    context["job_task_inst_id"] = job_inst_id
    context["CURRENT_STEP"] = TaskDeployStep.REMOVE_CONFIG

    get_deploy_context(context)  # 校验上下文

    # 提交异步任务执行删除配置脚本
    submit_deploy_query_task(InitialExecuteRemoveConfigScriptTask, context)


def submit_start_task(job_inst_id: int, context: dict[str, Any]) -> None:
    """
    启动采集任务提交入口

    该函数负责校验必要参数并准备上下文，然后触发异步任务执行配置文件传输。
    实际的作业平台 API 调用在 InitialTransferConfigFilesTask 中异步执行。

    Args:
        job_inst_id: 部署任务实例ID
        context: 任务上下文
    """
    context["job_task_inst_id"] = job_inst_id
    context["CURRENT_STEP"] = TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG

    get_deploy_context(context)  # 校验上下文

    # 提交异步任务执行配置文件传输
    submit_deploy_query_task(InitialTransferConfigFilesTask, context)
