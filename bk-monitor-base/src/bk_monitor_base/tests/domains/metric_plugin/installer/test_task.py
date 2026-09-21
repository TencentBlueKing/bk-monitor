"""
测试 metric_plugin.installer.task 模块
包含任务流程的完整测试，通过 mock celery 和外部服务来验证任务逻辑
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from blue_krill.async_utils.poll_task import CallbackResult, CallbackStatus, PollingResult, PollingStatus

from bk_monitor_base.domains.metric_plugin.constants import (
    JobTaskActionEnum,
    JobTaskLogStatusEnum,
    JobTaskStatusEnum,
)
from bk_monitor_base.domains.metric_plugin.define import JobTaskInstance
from bk_monitor_base.domains.metric_plugin.installer.define import TaskDeployStep
from bk_monitor_base.domains.metric_plugin.installer.task import (
    DeployAsyncHandler,
    DeployContext,
    RemoveConfigTask,
    RemovePluginTask,
    RestartBkmonitorbeatTask,
    RetryRestartBkmonitorbeatTask,
    TransferBkmonitorbeatConfigTask,
    TransferPluginTask,
    check_deploy_job_status,
    execute_deploy_script_task,
    get_deploy_context,
    submit_install_task,
    submit_start_task,
    submit_stop_task,
    submit_uninstall_task,
)
from bk_monitor_base.domains.metric_plugin.models import JobTaskInstanceModel


@pytest.mark.django_db(databases=["default"])
class TestDeployContext:
    """测试部署上下文"""

    def test_get_deploy_context_success(self, test_job_task_instance: JobTaskInstance):
        """测试获取部署上下文 - 成功"""
        # 保存任务实例到数据库
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.TRANSFER_PLUGIN,
            "job_instance_id": 12345,
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
        }

        ctx = get_deploy_context(context, require_job_instance=True)

        assert ctx.job_task_inst_id == test_job_task_instance.id
        assert ctx.current_step == TaskDeployStep.TRANSFER_PLUGIN
        assert ctx.job_instance_id == 12345
        assert ctx.target_server == {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]}
        assert ctx.account_alias == "root"

    def test_get_deploy_context_missing_job_task_inst_id(self):
        """测试获取部署上下文 - 缺少任务实例ID"""
        context: dict[str, Any] = {}

        with pytest.raises(RuntimeError, match="上下文中缺少必需的 job_task_inst_id"):
            get_deploy_context(context)

    def test_get_deploy_context_job_task_not_found(self):
        """测试获取部署上下文 - 任务实例不存在"""
        context = {"job_task_inst_id": 99999}

        with pytest.raises(RuntimeError, match="上下文中部署任务实例不存在"):
            get_deploy_context(context)

    def test_get_deploy_context_missing_job_instance_id(self, test_job_task_instance: JobTaskInstance):
        """测试获取部署上下文 - 缺少作业实例ID"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {"job_task_inst_id": test_job_task_instance.id}

        with pytest.raises(RuntimeError, match="上下文中未找到作业实例ID"):
            get_deploy_context(context, require_job_instance=True)


@pytest.mark.django_db(databases=["default"])
class TestCheckDeployJobStatus:
    """测试检查部署作业状态"""

    def test_check_deploy_job_status_running(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试检查部署作业状态 - 运行中"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        # 修改 mock 返回值为运行中
        mock_job_api["get_job_instance_status"].return_value = {"finished": False}

        ctx = DeployContext(
            job_task_inst_id=test_job_task_instance.id,
            job_task_inst=test_job_task_instance,
            bk_tenant_id="test_tenant",
            current_step=TaskDeployStep.TRANSFER_PLUGIN,
            job_instance_id=12345,
        )

        result = check_deploy_job_status(ctx, "测试步骤")
        assert isinstance(result, PollingResult)
        assert result.doing

    def test_check_deploy_job_status_success(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试检查部署作业状态 - 成功"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        ctx = DeployContext(
            job_task_inst_id=test_job_task_instance.id,
            job_task_inst=test_job_task_instance,
            bk_tenant_id="test_tenant",
            current_step=TaskDeployStep.TRANSFER_PLUGIN,
            job_instance_id=12345,
        )

        result = check_deploy_job_status(ctx, "测试步骤")
        assert result.success is True
        assert result.status_code == 3  # 3 表示执行成功（step_instance 级别状态码）

    def test_check_deploy_job_status_failed(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试检查部署作业状态 - 失败"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        # 修改 mock 返回值为失败
        # 使用 step_instance 级别状态码：4=执行失败
        mock_job_api["get_job_instance_status"].return_value = {
            "finished": True,
            "step_instance_list": [
                {
                    "step_instance_id": 1,
                    "status": 4,  # 4 表示执行失败（step_instance 级别状态码）
                }
            ],
        }

        ctx = DeployContext(
            job_task_inst_id=test_job_task_instance.id,
            job_task_inst=test_job_task_instance,
            bk_tenant_id="test_tenant",
            current_step=TaskDeployStep.TRANSFER_PLUGIN,
            job_instance_id=12345,
        )

        result = check_deploy_job_status(ctx, "测试步骤")
        assert result.success is False
        assert result.status_code == 4  # 4 表示执行失败（step_instance 级别状态码）

    def test_check_deploy_job_status_no_job_instance_id(self, test_job_task_instance: JobTaskInstance):
        """测试检查部署作业状态 - 缺少作业实例ID"""
        ctx = DeployContext(
            job_task_inst_id=test_job_task_instance.id,
            job_task_inst=test_job_task_instance,
            bk_tenant_id="test_tenant",
            current_step=TaskDeployStep.TRANSFER_PLUGIN,
            job_instance_id=None,
        )

        with pytest.raises(RuntimeError, match="任务 job_instance_id 为空"):
            check_deploy_job_status(ctx, "测试步骤")


@pytest.mark.django_db(databases=["default"])
class TestExecuteDeployScriptTask:
    """测试执行部署脚本任务"""

    def test_execute_deploy_script_task_success(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试执行部署脚本任务 - 成功"""
        ctx = DeployContext(
            job_task_inst_id=test_job_task_instance.id,
            job_task_inst=test_job_task_instance,
            bk_tenant_id="test_tenant",
            current_step=TaskDeployStep.TRANSFER_PLUGIN,
            target_server={"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            account_alias="root",
        )

        script_content = "echo 'test'"
        job_instance_id = execute_deploy_script_task(ctx, script_content)

        assert job_instance_id == 12345
        mock_job_api["fast_execute_script"].assert_called_once()

    def test_execute_deploy_script_task_no_target_server(self, test_job_task_instance: JobTaskInstance):
        """测试执行部署脚本任务 - 缺少目标服务器"""
        ctx = DeployContext(
            job_task_inst_id=test_job_task_instance.id,
            job_task_inst=test_job_task_instance,
            bk_tenant_id="test_tenant",
            current_step=TaskDeployStep.TRANSFER_PLUGIN,
            target_server=None,
        )

        with pytest.raises(RuntimeError, match="未找到目标服务器信息"):
            execute_deploy_script_task(ctx, "echo 'test'")


@pytest.mark.django_db(databases=["default"])
class TestDeployAsyncHandler:
    """测试部署异步处理器"""

    def test_failed_handle_success(self, test_job_task_instance: JobTaskInstance):
        """测试失败处理 - 成功"""
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        handler = DeployAsyncHandler()
        result = CallbackResult(status=CallbackStatus.EXCEPTION, message="测试错误")
        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.TRANSFER_PLUGIN,
            "job_instance_id": 12345,
        }

        handler.failed_handle(result, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert updated_inst.status == JobTaskStatusEnum.FAILED
        assert updated_inst.error_message == "测试错误"
        assert len(updated_inst.task_log) == 1
        assert updated_inst.task_log[0].status == JobTaskLogStatusEnum.FAILED
        assert updated_inst.task_log[0].step == TaskDeployStep.TRANSFER_PLUGIN
        assert "测试错误" in updated_inst.task_log[0].messages

    def test_failed_handle_no_job_inst(self):
        """测试失败处理 - 任务实例不存在"""
        handler = DeployAsyncHandler()
        result = CallbackResult(status=CallbackStatus.EXCEPTION, message="测试错误")
        context: dict[str, Any] = {}

        # 不应该抛出异常
        handler.failed_handle(result, context)


@pytest.mark.django_db(databases=["default"])
class TestRestartBkmonitorbeatTask:
    """测试重启 bkmonitorbeat 任务"""

    def test_query_running(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试查询 - 运行中"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        # 设置返回值为运行中
        mock_job_api["get_job_instance_status"].return_value = {"finished": False}

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.RESTART_BKMONITORBEAT,
            "job_instance_id": 12345,
        }

        result = RestartBkmonitorbeatTask.query(context)
        assert isinstance(result, PollingResult)
        assert result.doing

    def test_query_success(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试查询 - 成功"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.RESTART_BKMONITORBEAT,
            "job_instance_id": 12345,
        }

        result = RestartBkmonitorbeatTask.query(context)
        assert isinstance(result, PollingResult)
        assert result.status == PollingStatus.DONE

    def test_query_failed(self, test_job_task_instance: JobTaskInstance, mock_job_api: dict):
        """测试查询 - 失败"""
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        # 设置返回值为失败
        # 使用 step_instance 级别状态码：4=执行失败
        mock_job_api["get_job_instance_status"].return_value = {
            "finished": True,
            "step_instance_list": [
                {
                    "step_instance_id": 1,
                    "status": 4,  # 4 表示执行失败（step_instance 级别状态码）
                }
            ],
        }

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.RESTART_BKMONITORBEAT,
            "job_instance_id": 12345,
        }

        with pytest.raises(RuntimeError):
            RestartBkmonitorbeatTask.query(context)

    def test_post_query_success(self, test_job_task_instance: JobTaskInstance):
        """测试后置查询 - 成功"""
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.RESTART_BKMONITORBEAT,
            "job_instance_id": 12345,
        }

        RestartBkmonitorbeatTask.post_query(None, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert updated_inst.status == JobTaskStatusEnum.SUCCESS
        assert len(updated_inst.task_log) == 1
        assert updated_inst.task_log[0].status == JobTaskLogStatusEnum.SUCCESS
        assert updated_inst.task_log[0].step == TaskDeployStep.RESTART_BKMONITORBEAT


@pytest.mark.django_db(databases=["default"])
class TestTransferBkmonitorbeatConfigTask:
    """测试下发 bkmonitorbeat 配置任务"""

    def test_post_query_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_celery_engine: MagicMock,
    ):
        """测试后置查询 - 成功"""
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG,
            "job_instance_id": 12345,
            "restart_bkmonitorbeat_script": "cd /usr/local/gse/plugins/bin && ./restart.sh bkmonitorbeat",
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
        }

        TransferBkmonitorbeatConfigTask.post_query(None, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert len(updated_inst.task_log) == 2  # 一条成功日志，一条运行日志
        assert updated_inst.task_log[0].status == JobTaskLogStatusEnum.SUCCESS
        assert updated_inst.task_log[0].step == TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG
        assert updated_inst.task_log[1].status == JobTaskLogStatusEnum.RUNNING
        assert updated_inst.task_log[1].step == TaskDeployStep.RESTART_BKMONITORBEAT

        # 验证已提交重启任务
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestTransferPluginTask:
    """测试下发插件任务"""

    def test_post_query_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_storage: MagicMock,
        mock_celery_engine: MagicMock,
    ):
        """测试后置查询 - 成功"""
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.TRANSFER_PLUGIN,
            "job_instance_id": 12345,
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "sql_config_file_path": "/test/config.yml",
            "target_path": "/usr/local/gse/plugins/etc/bkmonitorbeat",
            "bkmonitorbeat_target_path": "/usr/local/gse/plugins/etc/bkmonitorbeat",
            "bkmonitorbeat_conf_source_file_path": "job_plugin/job_mysql/12345/bkmonitorbeat_job_mysql_config_22_12345.conf",
            "bkmonitorbeat_config_file": "/usr/local/dev_gse/plugin/etc/bkmonitorbeat/bkmonitorbeat_job_mysql_config_22_12345.conf",
        }

        TransferPluginTask.post_query(None, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert len(updated_inst.task_log) == 2
        assert updated_inst.task_log[0].status == JobTaskLogStatusEnum.SUCCESS
        assert updated_inst.task_log[1].status == JobTaskLogStatusEnum.RUNNING

        # 验证已调用文件下发
        mock_job_api["fast_transfer_file"].assert_called_once()
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestRemoveConfigTask:
    """测试删除配置任务"""

    def test_post_query_for_uninstall(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_celery_engine: MagicMock,
    ):
        """测试后置查询 - 卸载流程"""
        test_job_task_instance.action = JobTaskActionEnum.UNINSTALL
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.REMOVE_CONFIG,
            "job_instance_id": 12345,
            "restart_bkmonitorbeat_script": "cd /usr/local/gse/plugins/bin && ./restart.sh bkmonitorbeat",
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
        }

        RemoveConfigTask.post_query(None, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert len(updated_inst.task_log) == 2

        # 验证已提交重启任务
        mock_celery_engine.query_task.assert_called_once()

    def test_post_query_for_retry(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_celery_engine: MagicMock,
    ):
        """测试后置查询 - 重试流程"""
        test_job_task_instance.action = JobTaskActionEnum.RETRY
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.REMOVE_CONFIG,
            "job_instance_id": 12345,
            "restart_bkmonitorbeat_script": "cd /usr/local/gse/plugins/bin && ./restart.sh bkmonitorbeat",
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
        }

        RemoveConfigTask.post_query(None, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert len(updated_inst.task_log) == 2

        # 验证已提交重试重启任务
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestRetryRestartBkmonitorbeatTask:
    """测试重试重启 bkmonitorbeat 任务"""

    def test_post_query_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_storage: MagicMock,
        mock_celery_engine: MagicMock,
    ):
        """测试后置查询 - 成功"""
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.RESTART_BKMONITORBEAT,
            "job_instance_id": 12345,
            # 补充安装所需的上下文参数
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "binary_path": "/test/plugin.tar.gz",
            "sql_config_file_path": "/test/config.yml",
            "target_path": "/usr/local/gse/job_plugins/sql_110_1/sql_mysql",
        }

        with patch("bk_monitor_base.domains.metric_plugin.installer.task.submit_install_task") as mock_submit:
            RetryRestartBkmonitorbeatTask.post_query(None, context)

            # 验证任务实例已更新
            updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
            assert len(updated_inst.task_log) == 1
            assert updated_inst.task_log[0].status == JobTaskLogStatusEnum.SUCCESS

            # 验证已提交安装任务
            mock_submit.assert_called_once_with(test_job_task_instance.id, context)


@pytest.mark.django_db(databases=["default"])
class TestRemovePluginTask:
    """测试删除插件任务"""

    def test_post_query_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_celery_engine: MagicMock,
    ):
        """测试后置查询 - 成功"""
        test_job_task_instance.status = JobTaskStatusEnum.RUNNING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "job_task_inst_id": test_job_task_instance.id,
            "CURRENT_STEP": TaskDeployStep.REMOVE_PLUGIN,
            "job_instance_id": 12345,
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "remove_config_script": "rm -f /usr/local/gse/plugins/etc/bkmonitorbeat/config.conf",
        }

        RemovePluginTask.post_query(None, context)

        # 验证任务实例已更新
        updated_inst = JobTaskInstanceModel.objects.get(pk=test_job_task_instance.id).to_instance()
        assert len(updated_inst.task_log) == 2
        assert updated_inst.task_log[0].status == JobTaskLogStatusEnum.SUCCESS
        assert updated_inst.task_log[1].status == JobTaskLogStatusEnum.RUNNING

        # 验证已提交删除配置任务
        mock_job_api["fast_execute_script"].assert_called_once()
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestSubmitInstallTask:
    """测试提交安装任务"""

    def test_submit_install_task_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_storage: MagicMock,
        mock_celery_engine: MagicMock,
    ):
        """测试提交安装任务 - 成功

        submit_install_task 已改为异步执行，仅验证参数校验和异步任务提交
        """
        test_job_task_instance.status = JobTaskStatusEnum.PENDING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "plugin_file_path": "/test/plugin.tar.gz",
            "plugin_config_path": "/test/config.yml",
            "plugin_target_path": "/usr/local/gse/job_plugins/sql_110_1/sql_mysql",
        }

        submit_install_task(test_job_task_instance.id, context)

        # 验证上下文已更新
        assert context["job_task_inst_id"] == test_job_task_instance.id
        assert context["CURRENT_STEP"] == TaskDeployStep.TRANSFER_PLUGIN

        # 验证已提交异步任务（实际的 API 调用、file_source_list 准备和日志记录在异步任务中执行）
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestSubmitUninstallTask:
    """测试提交卸载任务"""

    def test_submit_uninstall_task_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_celery_engine: MagicMock,
    ):
        """测试提交卸载任务 - 成功

        submit_uninstall_task 已改为异步执行，仅验证参数校验和异步任务提交
        """
        test_job_task_instance.status = JobTaskStatusEnum.PENDING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "plugin_target_path": "/usr/local/gse/job_plugins/sql_110_1/sql_mysql",
            "remove_plugin_script": "rm -rf /usr/local/gse/job_plugins/sql_110_1/sql_mysql",
        }

        submit_uninstall_task(test_job_task_instance.id, context)

        # 验证上下文已更新
        assert context["job_task_inst_id"] == test_job_task_instance.id
        assert context["CURRENT_STEP"] == TaskDeployStep.REMOVE_PLUGIN

        # 验证已提交异步任务（实际的 API 调用和日志记录在异步任务中执行）
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestSubmitStopTask:
    """测试提交停止任务"""

    def test_submit_stop_task_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_celery_engine: MagicMock,
    ):
        """测试提交停止任务 - 成功

        submit_stop_task 已改为异步执行，仅验证参数校验和异步任务提交
        """
        test_job_task_instance.status = JobTaskStatusEnum.PENDING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "bkmonitorbeat_config_file": "/usr/local/gse/plugins/etc/bkmonitorbeat/config.conf",
            "remove_config_script": "rm -f /usr/local/gse/plugins/etc/bkmonitorbeat/config.conf",
        }

        submit_stop_task(test_job_task_instance.id, context)

        # 验证上下文已更新
        assert context["job_task_inst_id"] == test_job_task_instance.id
        assert context["CURRENT_STEP"] == TaskDeployStep.REMOVE_CONFIG

        # 验证已提交异步任务（实际的 API 调用和日志记录在异步任务中执行）
        mock_celery_engine.query_task.assert_called_once()


@pytest.mark.django_db(databases=["default"])
class TestSubmitStartTask:
    """测试提交启动任务"""

    def test_submit_start_task_success(
        self,
        test_job_task_instance: JobTaskInstance,
        mock_job_api: dict,
        mock_storage: MagicMock,
        mock_celery_engine: MagicMock,
    ):
        """测试提交启动任务 - 成功

        submit_start_task 已改为异步执行，仅验证参数校验和异步任务提交
        """
        test_job_task_instance.status = JobTaskStatusEnum.PENDING
        JobTaskInstanceModel.save_instance(test_job_task_instance)

        context = {
            "target_server": {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]},
            "account_alias": "root",
            "sql_config_file_path": "/test/config.yml",
            "target_path": "/usr/local/gse/plugins/etc/bkmonitorbeat",
        }

        submit_start_task(test_job_task_instance.id, context)

        # 验证上下文已更新
        assert context["job_task_inst_id"] == test_job_task_instance.id
        assert context["CURRENT_STEP"] == TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG

        # 验证已提交异步任务（实际的 API 调用、file_source_list 准备和日志记录在异步任务中执行）
        mock_celery_engine.query_task.assert_called_once()
