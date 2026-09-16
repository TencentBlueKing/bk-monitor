"""
拨测模块任务管理测试

测试内容:
- TaskManager: 任务部署、启动、停止、删除
- 异步任务: update_task_running_status, check_single_task_status
"""

from unittest.mock import ANY, patch

import pytest

from bk_monitor_base.domains.uptime_check.define import UptimeCheckTaskStatus
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckGroupModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskCollectorLog,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)
from bk_monitor_base.domains.uptime_check.services.task_manager import TaskManager
from bk_monitor_base.domains.uptime_check.tasks import (
    CollectStatus,
    check_single_task_status,
    update_task_running_status,
)

pytestmark = pytest.mark.django_db(databases=["default"])

# =============================================================================
# TaskManager 测试
# =============================================================================


class TestTaskManager:
    """TaskManager测试"""

    def test_init(self, sample_task):
        """测试初始化"""
        manager = TaskManager(task=sample_task)

        assert manager.task == sample_task
        assert manager.subscription_service is not None
        assert manager.data_access_service is not None


class TestPrepareNodes:
    """测试节点数据准备"""

    @pytest.fixture
    def task_with_nodes(self, db):
        """创建带节点的任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
        )

        node1 = UptimeCheckNodeModel.objects.create(
            bk_biz_id=2,
            name="节点1",
            ip="192.168.1.1",
            bk_host_id=100,
            plat_id=0,
        )
        node2 = UptimeCheckNodeModel.objects.create(
            bk_biz_id=3,
            name="节点2",
            ip="8.142.255.129",
            bk_host_id=200,
            plat_id=1,
        )

        task.nodes.add(node1, node2)
        return task


class TestGetTaskGroupId:
    """测试获取任务分组ID"""

    @pytest.fixture
    def task_with_groups(self, db):
        """创建带分组的任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )

        group1 = UptimeCheckGroupModel.objects.create(name="分组1", bk_biz_id=2)
        group2 = UptimeCheckGroupModel.objects.create(name="分组2", bk_biz_id=2)

        group1.tasks.add(task)
        group2.tasks.add(task)

        return task

    def test_get_task_group_id_with_groups(self, task_with_groups):
        """测试有分组时获取分组ID"""
        manager = TaskManager(task=task_with_groups)

        group_id = manager._get_task_group_id()

        assert "," in group_id or group_id.isdigit()

    def test_get_task_group_id_without_groups(self, db):
        """测试无分组时返回默认值"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )

        manager = TaskManager(task=task)

        group_id = manager._get_task_group_id()

        assert group_id == "0"


class TestGetExistingSubscriptions:
    """测试获取现有订阅"""

    @pytest.fixture
    def task_with_subscriptions(self, db):
        """创建带订阅的任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )

        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=task.pk,
            subscription_id=111,
            bk_biz_id=2,
        )
        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=task.pk,
            subscription_id=222,
            bk_biz_id=3,
        )

        return task

    def test_get_existing_subscriptions(self, task_with_subscriptions):
        """测试获取现有订阅"""
        manager = TaskManager(task=task_with_subscriptions)

        subscriptions = manager._get_existing_subscriptions()

        assert len(subscriptions) == 2
        assert 111 in subscriptions
        assert 222 in subscriptions


class TestDeploy:
    """测试任务部署"""

    @pytest.fixture
    def deploy_task(self, db):
        """创建用于部署的任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
            status=UptimeCheckTaskStatus.NEW_DRAFT.value,
            config={"url_list": ["https://www.example.com"], "period": 60},
        )

        node = UptimeCheckNodeModel.objects.create(
            bk_biz_id=2,
            name="节点",
            ip="192.168.1.1",
            bk_host_id=12345,
        )
        task.nodes.add(node)

        return task

    @patch.object(TaskManager, "_handle_create_subscriptions")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    @patch(
        "bk_monitor_base.domains.uptime_check.services.subscription.SubscriptionService.generate_subscription_config"
    )
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    def test_deploy_new_task(
        self,
        mock_get_data_id,
        mock_gen_config,
        mock_get_subs,
        mock_handle_create,
        deploy_task,
    ):
        """测试部署新任务"""
        mock_get_data_id.return_value = (False, 1011)
        mock_gen_config.return_value = [{"scope": {"bk_biz_id": 2}}]
        mock_get_subs.return_value = []

        manager = TaskManager(task=deploy_task)

        result = manager.deploy()

        assert result == "success"
        mock_get_data_id.assert_called_once()
        mock_handle_create.assert_called_once()

        deploy_task.refresh_from_db()
        assert deploy_task.status == UptimeCheckTaskStatus.STARTING.value

    @patch("bk_monitor_base.domains.uptime_check.tasks.update_task_running_status")
    @patch.object(TaskManager, "_handle_update_subscriptions")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    @patch(
        "bk_monitor_base.domains.uptime_check.services.subscription.SubscriptionService.generate_subscription_config"
    )
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    def test_deploy_existing_task(
        self,
        mock_get_data_id,
        mock_gen_config,
        mock_get_subs,
        mock_handle_update,
        mock_update_status,
        deploy_task,
    ):
        """测试更新现有任务"""
        mock_get_data_id.return_value = (False, 1011)
        mock_gen_config.return_value = [{"scope": {"bk_biz_id": 2}}]
        mock_get_subs.return_value = [111]

        manager = TaskManager(task=deploy_task)

        result = manager.deploy()

        assert result == "success"
        mock_handle_update.assert_called_once()

    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    def test_deploy_failure(self, mock_get_data_id, deploy_task):
        """测试部署失败"""
        mock_get_data_id.side_effect = Exception("拨测数据接入失败")

        manager = TaskManager(task=deploy_task)

        with pytest.raises(Exception, match="拨测数据接入失败"):
            manager.deploy()

        deploy_task.refresh_from_db()
        assert deploy_task.status == UptimeCheckTaskStatus.START_FAILED.value

    @pytest.fixture
    def cross_biz_deploy_task(self, db):
        """创建跨业务节点任务，验证最终订阅配置渲染"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="跨业务拨测任务",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
            status=UptimeCheckTaskStatus.NEW_DRAFT.value,
            labels={"env": "prod"},
            config={
                "ip_list": ["192.168.10.1"],
                "period": 60,
                "timeout": 3000,
                "port": 80,
                "request": "ping",
                "response": "pong",
                "response_format": "nin",
            },
        )
        node = UptimeCheckNodeModel.objects.create(
            bk_biz_id=3,
            name="跨业务节点",
            ip="192.168.10.1",
            bk_host_id=99901,
            plat_id=0,
        )
        task.nodes.add(node)
        return task

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.create_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    def test_deploy_render_subscription_from_task(
        self,
        mock_get_data_id,
        mock_create_subscription,
        mock_switch_subscription,
        cross_biz_deploy_task,
    ):
        """测试从task到订阅配置的关键字段渲染"""
        mock_get_data_id.return_value = (False, 1009)
        mock_create_subscription.return_value = {"subscription_id": 9527}

        manager = TaskManager(task=cross_biz_deploy_task)
        result = manager.deploy()

        assert result == "success"
        assert mock_create_subscription.call_count == 1
        mock_switch_subscription.assert_called_once()

        subscription_params = mock_create_subscription.call_args.kwargs["params"]
        context = subscription_params["steps"][0]["params"]["context"]

        # scope 按目标节点业务分组
        assert subscription_params["scope"]["bk_biz_id"] == 3
        # context.bk_biz_id 维持历史逻辑，使用任务所属业务ID
        assert context["bk_biz_id"] == 2
        # timeout 维持历史默认基线 15000ms
        assert context["timeout"] == "15000ms"
        assert context["max_timeout"] == "15000ms"
        assert context["target_port"] == 80
        assert context["request"] == "'ping'"
        assert context["response"] == "'pong'"
        assert context["response_format"] == "nin"
        assert context["labels"]["$body"] == {"task_group_id": "0"}

        # 自定义 labels 仅保留在 tasks，不注入 subscription labels 模板
        task_config = context["tasks"][0]
        assert task_config["labels"] == {"env": "prod"}


class TestStart:
    """测试任务启动"""

    @pytest.fixture
    def start_task(self, db):
        """创建用于启动的任务"""
        return UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
            status=UptimeCheckTaskStatus.STOPED.value,
        )

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.batch_get_subscription_task_result")
    @patch.object(TaskManager, "deploy")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    def test_start_without_subscriptions(
        self,
        mock_get_subs,
        mock_deploy,
        mock_batch_result,
        start_task,
    ):
        """测试无订阅时启动（执行完整部署）"""
        mock_get_subs.return_value = []
        mock_batch_result.return_value = ([], 0)
        mock_deploy.return_value = "success"

        manager = TaskManager(task=start_task)

        result = manager.start(operator="test_user")

        assert result == "success"
        mock_deploy.assert_called_once_with()

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.batch_get_subscription_task_result")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.run_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    def test_start_with_subscriptions(
        self,
        mock_switch,
        mock_run,
        mock_get_subs,
        mock_batch_result,
        start_task,
    ):
        """测试有订阅时启动"""
        mock_get_subs.return_value = [111, 222]
        mock_batch_result.return_value = ([], 0)

        manager = TaskManager(task=start_task)

        result = manager.start(operator="test_user")

        assert result == "success"
        assert mock_switch.call_count == 2
        assert mock_run.call_count == 2

        start_task.refresh_from_db()
        assert start_task.status == UptimeCheckTaskStatus.RUNNING.value

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.batch_get_subscription_task_result")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    def test_start_with_running_task(self, mock_get_subs, mock_batch_result, start_task):
        """测试有运行中任务时启动失败"""
        mock_get_subs.return_value = [111]
        mock_batch_result.return_value = ([{"status": "RUNNING"}], 1)

        manager = TaskManager(task=start_task)

        with pytest.raises(Exception, match="存在运行中的启停任务"):
            manager.start(operator="test_user")


class TestStop:
    """测试任务停止"""

    @pytest.fixture
    def stop_task(self, db):
        """创建用于停止的任务"""
        return UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
            status=UptimeCheckTaskStatus.RUNNING.value,
        )

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.batch_get_subscription_task_result")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    def test_stop_without_subscriptions(self, mock_get_subs, mock_batch_result, stop_task):
        """测试无订阅时停止失败"""
        mock_get_subs.return_value = []

        manager = TaskManager(task=stop_task)

        with pytest.raises(Exception, match="订阅信息不存在"):
            manager.stop(operator="test_user")

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.batch_get_subscription_task_result")
    @patch.object(TaskManager, "_get_existing_subscriptions")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.run_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    def test_stop_success(
        self,
        mock_switch,
        mock_run,
        mock_get_subs,
        mock_batch_result,
        stop_task,
    ):
        """测试成功停止任务"""
        mock_get_subs.return_value = [111]
        mock_batch_result.return_value = ([{"status": "SUCCESS"}], 1)

        manager = TaskManager(task=stop_task)

        result = manager.stop(operator="test_user")

        assert result == "success"
        mock_switch.assert_called_with(bk_tenant_id=ANY, subscription_id=111, action="disable")
        mock_run.assert_called_with(bk_tenant_id=ANY, subscription_id=111, actions={"bkmonitorbeat_http": "STOP"})

        stop_task.refresh_from_db()
        assert stop_task.status == UptimeCheckTaskStatus.STOPED.value


class TestDelete:
    """测试任务删除"""

    @pytest.fixture
    def delete_task(self, db):
        """创建用于删除的任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
        )

        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=task.pk,
            subscription_id=111,
            bk_biz_id=2,
        )

        return task

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.run_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    def test_delete_task(self, mock_switch, mock_run, delete_task):
        """测试删除任务"""
        manager = TaskManager(task=delete_task)

        manager.delete(operator="test_user")

        mock_switch.assert_called_with(bk_tenant_id=ANY, subscription_id=111, action="disable")
        mock_run.assert_called_with(
            bk_tenant_id=ANY, subscription_id=111, actions={"bkmonitorbeat_tcp": "UNINSTALL_AND_DELETE"}
        )

        subscription = UptimeCheckTaskSubscription.objects.get(subscription_id=111)
        assert subscription.is_deleted is True


class TestHandleCreateSubscriptions:
    """测试创建订阅处理"""

    @pytest.fixture
    def create_sub_task(self, db):
        """创建用于测试订阅创建的任务"""
        return UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.create_subscription")
    def test_handle_create_subscriptions(self, mock_create, mock_switch, create_sub_task):
        """测试创建订阅"""
        mock_create.return_value = {"subscription_id": 333}

        manager = TaskManager(task=create_sub_task)

        configs = [{"scope": {"bk_biz_id": 2}, "steps": [], "run_immediately": True}]
        manager._handle_create_subscriptions(configs)

        mock_create.assert_called_once()

        subscription = UptimeCheckTaskSubscription.objects.get(
            uptimecheck_id=create_sub_task.pk,
        )
        assert subscription.subscription_id == 333
        assert subscription.bk_biz_id == 2

        mock_switch.assert_called_with(bk_tenant_id=ANY, subscription_id=333, action="enable")


class TestHandleUpdateSubscriptions:
    """测试更新订阅处理"""

    @pytest.fixture
    def update_sub_task(self, db):
        """创建用于测试订阅更新的任务"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="测试任务",
            protocol=UptimeCheckTaskModel.Protocol.HTTP,
        )

        UptimeCheckTaskSubscription.objects.create(
            uptimecheck_id=task.pk,
            subscription_id=111,
            bk_biz_id=2,
        )

        return task

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.update_subscription")
    def test_handle_update_existing_subscription(
        self,
        mock_update,
        mock_switch,
        update_sub_task,
    ):
        """测试更新现有订阅"""
        manager = TaskManager(task=update_sub_task)

        configs = [{"scope": {"bk_biz_id": 2}, "steps": []}]
        existing_subs = [111]

        manager._handle_update_subscriptions(configs, existing_subs)

        mock_update.assert_called_once()


# =============================================================================
# 异步任务测试
# =============================================================================


class TestCollectStatus:
    """CollectStatus常量测试"""

    def test_status_values(self):
        """测试状态常量值"""
        assert CollectStatus.RUNNING == "RUNNING"
        assert CollectStatus.PENDING == "PENDING"
        assert CollectStatus.FAILED == "FAILED"


class TestCheckSingleTaskStatus:
    """测试单个任务状态检查"""

    @patch("bk_monitor_base.domains.uptime_check.tasks.time.sleep")
    @patch("bk_monitor_base.domains.uptime_check.tasks.node_man_v2_api.batch_get_subscription_task_result")
    def test_check_status_starting(self, mock_batch_result, mock_sleep):
        """测试任务正在启动中"""
        mock_batch_result.return_value = ([], 0)

        status, log, task_id = check_single_task_status(
            subscription_id=12345,
            bk_tenant_id="default",
        )

        assert status == UptimeCheckTaskStatus.STARTING.value
        assert log == []
        assert task_id == 0

    @patch("bk_monitor_base.domains.uptime_check.tasks.time.sleep")
    @patch("bk_monitor_base.domains.uptime_check.tasks.node_man_v2_api.batch_get_subscription_task_result")
    def test_check_status_running(self, mock_batch_result, mock_sleep):
        """测试任务运行中"""
        mock_batch_result.return_value = (
            [
                {"status": "SUCCESS", "instance_id": "inst1"},
            ],
            1,
        )

        status, log, task_id = check_single_task_status(
            subscription_id=12345,
            bk_tenant_id="default",
        )

        assert status == UptimeCheckTaskStatus.RUNNING.value
        assert log == []

    @patch("bk_monitor_base.domains.uptime_check.tasks.time.sleep")
    @patch("bk_monitor_base.domains.uptime_check.tasks.node_man_v2_api.get_subscription_task_result_detail")
    @patch("bk_monitor_base.domains.uptime_check.tasks.node_man_v2_api.batch_get_subscription_task_result")
    def test_check_status_failed(self, mock_batch_result, mock_detail, mock_sleep):
        """测试任务启动失败"""
        mock_batch_result.return_value = (
            [
                {"status": "FAILED", "instance_id": "inst1"},
            ],
            1,
        )
        mock_detail.return_value = {
            "task_id": "123",
            "steps": [
                {
                    "status": "FAILED",
                    "target_hosts": [
                        {
                            "sub_steps": [
                                {"ex_data": "连接超时错误"},
                            ]
                        }
                    ],
                }
            ],
        }

        status, log, task_id = check_single_task_status(
            subscription_id=12345,
            bk_tenant_id="default",
        )

        assert status == UptimeCheckTaskStatus.START_FAILED.value
        assert len(log) > 0
        assert "连接超时错误" in log[0]  # log 现在存储 JSON 字符串
        assert task_id == 123

    @patch("bk_monitor_base.domains.uptime_check.tasks.time.sleep")
    @patch("bk_monitor_base.domains.uptime_check.tasks.node_man_v2_api.batch_get_subscription_task_result")
    def test_check_status_api_error(self, mock_batch_result, mock_sleep):
        """测试API调用失败"""
        from bk_monitor_base.infras.exception import BaseError as BKAPIError

        mock_batch_result.side_effect = BKAPIError("API错误")

        status, log, task_id = check_single_task_status(
            subscription_id=12345,
            bk_tenant_id="default",
        )

        assert status == UptimeCheckTaskStatus.STARTING.value
        assert log == []


class TestUpdateTaskRunningStatus:
    """测试更新任务运行状态异步任务"""

    @patch("bk_monitor_base.domains.uptime_check.tasks.bk_biz_id_to_bk_tenant_id")
    @patch("bk_monitor_base.domains.uptime_check.tasks.check_single_task_status")
    def test_update_status_success(
        self,
        mock_check_status,
        mock_biz_to_tenant,
        task_with_subscription,
    ):
        """测试更新状态为运行中"""
        mock_biz_to_tenant.return_value = "default"
        mock_check_status.return_value = (UptimeCheckTaskStatus.RUNNING.value, [], 0)

        update_task_running_status(task_with_subscription.pk)

        task_with_subscription.refresh_from_db()
        assert task_with_subscription.status == UptimeCheckTaskStatus.RUNNING.value

    @patch("bk_monitor_base.domains.uptime_check.tasks.bk_biz_id_to_bk_tenant_id")
    @patch("bk_monitor_base.domains.uptime_check.tasks.check_single_task_status")
    def test_update_status_failed(
        self,
        mock_check_status,
        mock_biz_to_tenant,
        task_with_subscription,
    ):
        """测试更新状态为失败"""
        mock_biz_to_tenant.return_value = "default"
        mock_check_status.return_value = (
            UptimeCheckTaskStatus.START_FAILED.value,
            ["错误日志1", "错误日志2"],
            123,  # 改为 int 类型
        )

        update_task_running_status(task_with_subscription.pk)

        task_with_subscription.refresh_from_db()
        assert task_with_subscription.status == UptimeCheckTaskStatus.START_FAILED.value

        logs = UptimeCheckTaskCollectorLog.objects.filter(task_id=task_with_subscription.pk)
        assert logs.count() == 2
