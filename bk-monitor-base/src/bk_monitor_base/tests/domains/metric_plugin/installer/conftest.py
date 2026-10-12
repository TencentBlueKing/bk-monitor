"""
installer 测试配置和 fixtures

注意：不要在模块级别 patch Redis，会影响其他需要真实 Redis 的测试。
使用 mock_redis fixture 来按需 mock Redis 连接。
"""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from bk_monitor_base.domains.metric_plugin.constants import (
    JobTaskActionEnum,
    JobTaskStatusEnum,
)
from bk_monitor_base.domains.metric_plugin.define import (
    JobTaskInstance,
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    MetricPluginParams,
    MetricPluginStatus,
)


@pytest.fixture
def mock_redis():
    """提供 Redis mock 实例供测试使用

    按需 mock Redis 连接，避免影响其他需要真实 Redis 的测试。
    """
    redis_mock = MagicMock()
    redis_mock.incr.return_value = 1
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True

    with patch("django_redis.get_redis_connection", return_value=redis_mock):
        yield redis_mock


@pytest.fixture
def test_plugin() -> MetricPlugin:
    """创建测试插件"""
    return MetricPlugin(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        id="sql_mysql",
        type="sql",
        label="os",
        name="MySQL监控插件",
        description_md="# MySQL监控插件\n测试用MySQL监控插件",
        params=[
            MetricPluginParams(name="host", type="string", required=True),
            MetricPluginParams(name="port", type="int", default=3306),
            MetricPluginParams(name="user", type="string", required=True),
            MetricPluginParams(name="password", type="string", required=True),
        ],
        define={"sql": "SELECT 1"},
        version=(1, 0),
        version_log="初始版本",
        status=MetricPluginStatus.RELEASE,
        created_by="admin",
        updated_by="admin",
    )


@pytest.fixture
def test_deployment(test_plugin: MetricPlugin) -> MetricPluginDeployment:
    """创建测试部署项"""
    return MetricPluginDeployment(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        id=110,
        name="MySQL监控部署",
        plugin_id=test_plugin.id,
        status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        related_params={"job_inst_mapping": {}},
    )


@pytest.fixture
def test_deployment_version(test_deployment: MetricPluginDeployment) -> MetricPluginDeploymentVersion:
    """创建测试部署版本"""
    return MetricPluginDeploymentVersion(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        deployment_id=test_deployment.id,
        plugin_version=(1, 0),
        version=1,
        target_scope=MetricPluginDeploymentScope(
            node_type="HOST",
            nodes=[
                {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
                {"bk_host_id": 2, "ip": "127.0.0.2", "bk_cloud_id": 0},
            ],
        ),
        remote_scope=None,
        params={
            "collector": {
                "host_1": {"period": "60s", "timeout": "60s"},
                "host_2": {"period": "60s", "timeout": "60s"},
            },
            "plugin": {
                "host_1": {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "123456"},
                "host_2": {"host": "127.0.0.2", "port": 3306, "user": "root", "password": "123456"},
            },
        },
    )


@pytest.fixture
def test_job_task_instance() -> JobTaskInstance:
    """创建测试任务实例

    注意：id 设置为 None，这样 save_instance 会创建新记录而不是尝试更新不存在的记录
    """
    return JobTaskInstance(
        id=None,  # None 表示这是一个新对象，save_instance 会创建新记录
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        action=JobTaskActionEnum.INSTALL,
        deployment_id=1,
        plugin_id="sql_mysql",
        instance_id="host_1",
        instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0, "os_type": "linux"},
        execute_params={
            "collector_params": {"period": "60s", "timeout": "60s"},
            "plugin_params": {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "123456"},
        },
        status=JobTaskStatusEnum.PENDING,
        current_step="",
        error_message="",
        logs=[],
    )


@pytest.fixture
def mock_job_api():
    """Mock 作业平台 API"""
    with pytest.MonkeyPatch.context() as m:
        # Mock fast_execute_script
        fast_execute_script = Mock(return_value={"job_instance_id": 12345})
        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.task.fast_execute_script",
            fast_execute_script,
        )

        # Mock fast_transfer_file
        fast_transfer_file = Mock(return_value={"job_instance_id": 12346})
        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.task.fast_transfer_file",
            fast_transfer_file,
        )

        # Mock get_job_instance_status - 默认返回成功
        # 使用 step_instance 级别状态码：3=执行成功，4=执行失败
        get_job_instance_status = Mock(
            return_value={
                "finished": True,
                "step_instance_list": [
                    {
                        "step_instance_id": 1,
                        "status": 3,  # 3 表示执行成功（step_instance 级别状态码）
                    }
                ],
            }
        )
        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.task.get_job_instance_status",
            get_job_instance_status,
        )

        yield {
            "fast_execute_script": fast_execute_script,
            "fast_transfer_file": fast_transfer_file,
            "get_job_instance_status": get_job_instance_status,
        }


@pytest.fixture
def mock_cmdb_api():
    """Mock CMDB API"""
    with pytest.MonkeyPatch.context() as m:
        # Mock get_host_info
        def mock_get_host_info(target: dict[str, Any]) -> dict[str, Any] | None:
            bk_host_id = target.get("bk_host_id")
            if bk_host_id:
                return {
                    "bk_host_id": bk_host_id,
                    "ip": target.get("ip", f"127.0.0.{bk_host_id}"),
                    "bk_cloud_id": target.get("bk_cloud_id", 0),
                    "bk_os_type": "1",  # Linux
                    "bk_cpu_architecture": "x86_64",
                }
            return None

        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.job.get_host_info",
            mock_get_host_info,
        )

        # Mock get_os_type_by_collect_host
        from bk_monitor_base.domains.metric_plugin.manager.base import OSType

        def mock_get_os_type(collect_host: int) -> OSType:
            return OSType.LINUX

        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.job.get_os_type_by_collect_host",
            mock_get_os_type,
        )

        yield


@pytest.fixture
def mock_storage():
    """Mock 存储服务"""
    with pytest.MonkeyPatch.context() as m:
        storage_mock = MagicMock()
        storage_mock.handle_file_source_list_to_job_file_source_list.return_value = [
            {
                "file_type": 3,
                "file_list": [
                    {
                        "file_source_code": "bkrepo",
                        "file_path": "/test/path/file.tar.gz",
                    }
                ],
            }
        ]
        storage_mock.save.return_value = "/test/repo/path/file.yml"

        # get_bkrepo_storage 需要传入 StorageName 参数，返回 storage_mock
        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.job.get_bkrepo_storage",
            lambda _: storage_mock,
        )
        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.task.get_bkrepo_storage",
            lambda _: storage_mock,
        )

        yield storage_mock


@pytest.fixture
def mock_plugin_manager():
    """Mock 插件管理器"""
    with pytest.MonkeyPatch.context() as m:
        manager_mock = MagicMock()
        manager_mock.type = "sql"
        manager_mock.basic_file_path = "/test/sql"
        manager_mock.get_data_ids.return_value = {"bk_data_id": 50001}
        manager_mock.get_binary_path.return_value = "/test/repo/sql_mysql/linux_x86_64/sql_mysql"
        manager_mock.get_extra_file_source_paths.return_value = []
        manager_mock.generate_config_yaml_content.return_value = "test: yaml\ncontent: true"
        manager_mock.parse_target_server.return_value = {"ip_list": [{"bk_cloud_id": 0, "ip": "127.0.0.1"}]}

        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.job.get_sql_plugin_manager",
            lambda plugin: manager_mock,
        )

        yield manager_mock


@pytest.fixture
def mock_celery_engine():
    """Mock Celery 引擎，避免真正提交异步任务"""
    with pytest.MonkeyPatch.context() as m:
        engine_mock = MagicMock()
        m.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.task.EngineRegistry.get_engine_class",
            lambda engine_type: lambda: engine_mock,
        )
        yield engine_mock
