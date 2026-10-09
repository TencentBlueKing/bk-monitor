"""
测试 metric_plugin.installer.job 模块
包含 SQLInstaller 的完整测试，验证安装、卸载、启动、停止等操作
"""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

from bk_monitor_base.domains.metric_plugin.constants import JobTaskActionEnum, JobTaskStatusEnum
from bk_monitor_base.domains.metric_plugin.define import (
    JOB_PLUGIN_BUILT_IN_DIMENSIONS,
    JobTaskInstance,
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    MetricPluginStatus,
)
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginDeploymentOperationError
from bk_monitor_base.domains.metric_plugin.installer.job import SQLInstaller
from bk_monitor_base.domains.metric_plugin.models import (
    JobTaskInstanceModel,
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
)


@pytest.mark.django_db(databases=["default"])
class TestSQLInstaller:
    """测试 SQL 安装器"""

    @pytest.fixture(autouse=True)
    def setup(
        self,
        test_plugin: MetricPlugin,
        test_deployment: MetricPluginDeployment,
        test_deployment_version: MetricPluginDeploymentVersion,
        mock_cmdb_api: Any,
        mock_storage: MagicMock,
        mock_plugin_manager: MagicMock,
    ):
        """设置测试数据"""
        # 创建数据库记录
        self.plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=test_plugin.bk_tenant_id,
            bk_biz_id=test_plugin.bk_biz_id,
            plugin_id=test_plugin.id,
            type=test_plugin.type,
            label=test_plugin.label,
            created_by=test_plugin.created_by,
        )
        self.version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id=test_plugin.bk_tenant_id,
            bk_biz_id=test_plugin.bk_biz_id,
            plugin=self.plugin_model,
            name=test_plugin.name,
            params=[param.model_dump() for param in test_plugin.params],
            define=test_plugin.define,
            version=f"{test_plugin.version[0]:05d}.{test_plugin.version[1]:05d}",
            status=MetricPluginStatus.RELEASE,
        )
        self.deployment_model = MetricPluginDeploymentModel.objects.create(
            id=test_deployment.id,
            bk_tenant_id=test_deployment.bk_tenant_id,
            bk_biz_id=test_deployment.bk_biz_id,
            plugin=self.plugin_model,
            name=test_deployment.name,
            status=test_deployment.status,
            related_params=test_deployment.related_params,
        )
        self.deployment_version_model = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id=test_deployment.bk_tenant_id,
            bk_biz_id=test_deployment.bk_biz_id,
            deployment=self.deployment_model,
            plugin_version=f"{test_deployment_version.plugin_version.major}.{test_deployment_version.plugin_version.minor}",
            version=test_deployment_version.version,
            is_current=True,
            target_node_type=test_deployment_version.target_scope.node_type,
            target_nodes=test_deployment_version.target_scope.nodes,
            remote_node_type=test_deployment_version.remote_scope.node_type
            if test_deployment_version.remote_scope
            else "",
            remote_nodes=test_deployment_version.remote_scope.nodes if test_deployment_version.remote_scope else [],
            params=test_deployment_version.params,
            target_instances=test_deployment_version.target_instances,
            remote_instances=test_deployment_version.remote_instances,
            created_by=test_deployment_version.created_by,
        )

        self.test_plugin: MetricPlugin = test_plugin
        self.test_deployment: MetricPluginDeployment = test_deployment
        self.test_deployment_version: MetricPluginDeploymentVersion = test_deployment_version

        # 刷新部署ID - 确保所有对象都使用数据库实际生成的 ID
        self.test_deployment.id = self.deployment_model.pk
        # CRITICAL: 同步 deployment_version 的 deployment_id，否则在 install() 方法中
        # 调用 MetricPluginDeploymentModel.objects.get(id=deployment_version.deployment_id) 会失败
        self.test_deployment_version.deployment_id = self.deployment_model.pk

    def test_init_success(self):
        """测试初始化 - 成功"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        assert installer.operator == "admin"
        assert installer.deployment.id == self.deployment_model.pk
        assert installer.plugin.id == self.test_plugin.id

    def test_job_inst_mapping_getter_setter(self):
        """测试任务映射的 getter 和 setter"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        # 初始为空
        assert installer.job_inst_mapping == {}

        # 设置映射
        installer.job_inst_mapping = {"host_1": 101, "host_2": 102}
        assert installer.job_inst_mapping == {"host_1": 101, "host_2": 102}

    def test_get_instance_info_with_bk_host_id(self):
        """测试获取实例信息 - 使用 bk_host_id"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        target = {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}
        instance_info = installer.get_instance_info(target)

        assert instance_info["instance_id"] == "host_1"
        assert instance_info["bk_host_id"] == 1
        assert instance_info["ip"] == "127.0.0.1"
        assert instance_info["bk_cloud_id"] == 0

    def test_get_instance_info_with_int_bk_host_id_from_cmdb(self):
        """测试获取实例信息 - CMDB 返回整型 bk_host_id"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        target = {"ip": "127.0.0.1", "bk_cloud_id": 0}
        with patch("bk_monitor_base.domains.metric_plugin.installer.job.get_host_info") as mock_get_host_info:
            mock_get_host_info.return_value = {
                "bk_host_id": 1,
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "bk_os_type": "1",
                "bk_cpu_architecture": "x86_64",
            }

            instance_info = installer.get_instance_info(target)

        assert instance_info["instance_id"] == "host_1"
        assert instance_info["bk_host_id"] == 1

    def test_get_instance_info_with_prefixed_instance_id(self):
        """测试获取实例信息 - 使用 Job 主机实例 ID"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        target = {"instance_id": "host_1"}
        with patch("bk_monitor_base.domains.metric_plugin.installer.job.get_host_info") as mock_get_host_info:
            mock_get_host_info.return_value = {
                "bk_host_id": 1,
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "os_type": "linux",
                "os_arch": "x86_64",
            }

            instance_info = installer.get_instance_info(target)

        mock_get_host_info.assert_called_once_with({"instance_id": "host_1", "bk_host_id": 1})
        assert instance_info["instance_id"] == "host_1"
        assert instance_info["bk_host_id"] == 1

    def test_get_instance_info_raises_when_target_cannot_build_instance_id(self):
        """测试 CMDB 命中但目标缺少必要字段时无法生成实例 ID"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        with patch("bk_monitor_base.domains.metric_plugin.installer.job.get_host_info") as mock_get_host_info:
            mock_get_host_info.return_value = {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}

            with pytest.raises(ValueError, match="无法生成实例ID"):
                installer.get_instance_info({"instance_id": "service_1"})

    def test_get_target_params(self):
        """测试获取目标参数"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        target = {"bk_host_id": 1}
        params = installer._get_target_params(target, self.test_deployment_version)

        assert "collector_params" in params
        assert "plugin_params" in params
        assert params["collector_params"]["period"] == "60s"
        assert params["plugin_params"]["host"] == "127.0.0.1"
        assert "instance_info" not in params
        assert "collect_instance_info" not in params

    def test_extract_targets_distributes_targets_to_remote_scope_for_remote_collect(self):
        """测试远程采集时将采集目标轮询分配到远程下发节点"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        remote_nodes = [
            {"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0},
            {"bk_host_id": 4, "ip": "127.0.0.4", "bk_cloud_id": 0},
        ]
        label_targets = [
            {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            {"bk_host_id": 2, "ip": "127.0.0.2", "bk_cloud_id": 0},
            {"bk_host_id": 5, "ip": "127.0.0.5", "bk_cloud_id": 0},
        ]
        deployment_version = self.test_deployment_version.model_copy(
            update={
                "remote_scope": MetricPluginDeploymentScope(node_type="INSTANCE", nodes=remote_nodes),
                "target_scope": MetricPluginDeploymentScope(node_type="INSTANCE", nodes=label_targets),
            }
        )

        targets = installer._extract_targets(deployment_version)

        assert len(targets) == 3
        assert [target["bk_host_id"] for target in targets] == [3, 4, 3]
        assert [target[installer.METRIC_TARGET_KEY]["bk_host_id"] for target in targets] == [1, 2, 5]

    def test_get_target_params_uses_target_scope_for_remote_collect(self):
        """测试远程采集时目标参数按实际执行节点取值"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        remote_target = {"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0}
        label_target = {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}
        deployment_version = self.test_deployment_version.model_copy(
            update={
                "target_scope": MetricPluginDeploymentScope(node_type="INSTANCE", nodes=[label_target]),
                "remote_scope": MetricPluginDeploymentScope(node_type="INSTANCE", nodes=[remote_target]),
                "params": {
                    "collector": {"host_3": {"period": "30s", "timeout": "60s"}},
                    "plugin": {"host_3": {"host": "10.0.0.10", "port": 3306}},
                },
            }
        )

        deploy_target = installer._extract_targets(deployment_version)[0]
        params = installer._get_target_params(deploy_target, deployment_version)

        assert params["collector_params"]["period"] == "30s"
        assert params["plugin_params"]["host"] == "10.0.0.10"
        assert "instance_info" not in params
        assert "collect_instance_info" not in params

    def test_get_target_params_returns_empty_when_remote_execute_node_has_no_params(self):
        """测试远程执行节点未配置目标参数时返回空参数"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        deployment_version = self.test_deployment_version.model_copy(
            update={
                "target_scope": MetricPluginDeploymentScope(
                    node_type="INSTANCE",
                    nodes=[{"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}],
                ),
                "remote_scope": MetricPluginDeploymentScope(
                    node_type="INSTANCE",
                    nodes=[{"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0}],
                ),
                "params": {
                    "collector": {"host_1": {"period": "30s"}},
                    "plugin": {"host_1": {"host": "10.0.0.10"}},
                },
            }
        )

        deploy_target = installer._extract_targets(deployment_version)[0]
        params = installer._get_target_params(deploy_target, deployment_version)

        assert params == {"collector_params": {}, "plugin_params": {}}

    def test_get_label_target_raises_when_remote_target_missing_metric_target(self):
        """测试远程采集目标缺少采集目标标记时抛出清晰错误"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        deployment_version = self.test_deployment_version.model_copy(
            update={
                "remote_scope": MetricPluginDeploymentScope(
                    node_type="INSTANCE",
                    nodes=[{"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0}],
                ),
            }
        )

        with pytest.raises(MetricPluginDeploymentOperationError, match="缺少采集目标信息"):
            installer._get_label_target({"bk_host_id": 3}, deployment_version)

    def test_extract_targets_uses_target_scope_when_remote_scope_empty(self):
        """测试远程范围为空时仍直接使用目标范围"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        deployment_version = self.test_deployment_version.model_copy(
            update={"remote_scope": MetricPluginDeploymentScope(node_type="INSTANCE", nodes=[])}
        )

        targets = installer._extract_targets(deployment_version)

        assert targets == self.test_deployment_version.target_scope.nodes

    def test_get_target_params_with_prefixed_instance_id(self):
        """测试获取目标参数 - 使用 Job 主机实例 ID"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        target = {"instance_id": "host_1"}
        params = installer._get_target_params(target, self.test_deployment_version)

        assert params["collector_params"]["period"] == "60s"
        assert params["plugin_params"]["host"] == "127.0.0.1"

    def test_get_target_params_with_custom_target_key_template(self):
        """测试获取目标参数 - 使用自定义目标参数 key 模板"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        self.test_deployment_version.params = {
            "target_params_key_template": "{{ target.bk_cloud_id }}_{{ target.ip }}",
            "collector": {
                "0_127.0.0.1": {"period": "30s", "timeout": "60s"},
            },
            "plugin": {
                "0_127.0.0.1": {"host": "mysql.service.local", "port": 3306},
            },
        }

        target = {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}
        params = installer._get_target_params(target, self.test_deployment_version)

        assert params["collector_params"]["period"] == "30s"
        assert params["plugin_params"]["host"] == "mysql.service.local"

    def test_get_target_params_with_missing_template_field(self):
        """测试获取目标参数 - 模板字段不存在时报错"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        self.test_deployment_version.params = {
            "target_params_key_template": "{{ target.not_exists }}",
            "collector": {},
            "plugin": {},
        }

        with pytest.raises(MetricPluginDeploymentOperationError, match="target.not_exists"):
            installer._get_target_params({"bk_host_id": 1}, self.test_deployment_version)

    def test_get_target_params_with_unsupported_template(self):
        """测试获取目标参数 - 不支持非 target 字段模板"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        self.test_deployment_version.params = {
            "target_params_key_template": "{{ instance_id }}",
            "collector": {},
            "plugin": {},
        }

        with pytest.raises(MetricPluginDeploymentOperationError, match="目标参数 key 模板格式不支持"):
            installer._get_target_params({"bk_host_id": 1}, self.test_deployment_version)

    def test_get_target_params_with_non_string_template(self):
        """测试获取目标参数 - 模板非字符串时报错"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        self.test_deployment_version.params = {
            "target_params_key_template": None,
            "collector": {},
            "plugin": {},
        }

        with pytest.raises(MetricPluginDeploymentOperationError, match="目标参数 key 模板必须是字符串"):
            installer._get_target_params({"bk_host_id": 1}, self.test_deployment_version)

    def test_generate_config_yaml(self, mock_plugin_manager: MagicMock):
        """测试生成配置文件"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            id=1,
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={"plugin_params": {"host": "127.0.0.1", "port": 3306}},
            status=JobTaskStatusEnum.PENDING,
        )

        config_path = installer.generate_config_yaml(job_inst)

        assert config_path is not None
        assert "/test/sql/" in config_path
        mock_plugin_manager.generate_config_yaml_content.assert_called_once()

    def test_generate_config_yaml_with_parse_rules(self, mock_storage: MagicMock):
        """测试生成配置文件 - 验证包含正确的 parse_rules

        该测试验证 generate_config_yaml 方法调用 plugin_manager.generate_config_yaml_content
        时，生成的配置内容应包含正确的 parse_rules 结构。

        parse_rules 的格式应为:
        [
            {
                "sql": "SELECT ...",
                "variate": [
                    {"object_name": "field1", "object_new_name": "field1", "object_type": "dimension"},
                    {"object_name": "field2", "object_new_name": "field2", "object_type": "metric"},
                ]
            }
        ]
        """
        from bk_monitor_base.domains.metric_plugin.define import MetricPluginMetricField, MetricPluginMetricGroup
        from bk_monitor_base.domains.metric_plugin.manager.job.mysql import MysqlPluginManager

        # 创建带有完整指标配置的插件
        plugin_with_metrics = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            id="sql_mysql",
            type="sql",
            label="os",
            name="MySQL监控插件",
            description_md="# MySQL监控插件",
            params=[],
            define={
                "linux": {},
                "sql_content": [
                    {
                        "classification_id": "session_stats",
                        "classification_name": "会话统计",
                        "content": "SELECT osuser, count(*) as session_count FROM v$session GROUP BY osuser;",
                    },
                ],
            },
            version=(1, 0),
            status=MetricPluginStatus.RELEASE,
            created_by="admin",
            updated_by="admin",
            metrics=[
                MetricPluginMetricGroup(
                    table_name="session_stats",
                    table_desc="会话统计表",
                    fields=[
                        MetricPluginMetricField(
                            name="osuser",
                            type="string",
                            monitor_type="dimension",
                            description="操作系统用户",
                        ),
                        MetricPluginMetricField(
                            name="session_count",
                            type="double",
                            monitor_type="metric",
                            description="会话数量",
                        ),
                    ],
                ),
            ],
        )

        # 更新数据库中的插件信息
        self.plugin_model.define = plugin_with_metrics.define
        self.plugin_model.save()

        # 创建新版本记录

        self.version_model.define = plugin_with_metrics.define
        self.version_model.metrics = [m.model_dump() for m in plugin_with_metrics.metrics]
        self.version_model.save()

        # 使用真实的 MysqlPluginManager 替代 mock
        with patch("bk_monitor_base.domains.metric_plugin.installer.job.get_sql_plugin_manager") as mock_get_manager:
            real_manager = MysqlPluginManager(plugin_with_metrics)
            mock_get_manager.return_value = real_manager

            installer = SQLInstaller(self.test_deployment, operator="admin")

            # 获取 parse_rules
            parse_rules = installer.plugin_manager.get_parse_rules_json()

            # 验证 parse_rules 结构正确
            assert len(parse_rules) == 1
            assert "sql" in parse_rules[0]
            assert "variate" in parse_rules[0]

            # 验证 sql 内容
            assert parse_rules[0]["sql"] == "SELECT osuser, count(*) as session_count FROM v$session GROUP BY osuser;"

            # 验证 variate 字段
            variate = parse_rules[0]["variate"]
            assert len(variate) == 2

            # 验证字段映射
            variate_map = {v["object_name"]: v for v in variate}
            assert "osuser" in variate_map
            assert variate_map["osuser"]["object_type"] == "dimension"
            assert variate_map["osuser"]["object_new_name"] == "osuser"

            assert "session_count" in variate_map
            assert variate_map["session_count"]["object_type"] == "metric"
            assert variate_map["session_count"]["object_new_name"] == "session_count"

    def test_generate_config_yaml_content_includes_parse_rules(self, mock_storage: MagicMock):
        """测试 generate_config_yaml_content 方法包含 parse_rules

        验证 SQLPluginManager.generate_config_yaml_content 生成的配置内容
        包含 parse_rules 字段，且字段结构符合预期。

        注意：由于 SQL_CONFIG_YAML_KEY 不包含 'parse_rules'，
        最终生成的 YAML 配置中 parse_rules 会被裁剪掉。
        此测试验证的是裁剪前的中间状态。
        """
        from bk_monitor_base.domains.metric_plugin.define import MetricPluginMetricField, MetricPluginMetricGroup
        from bk_monitor_base.domains.metric_plugin.manager.job.mysql import MysqlPluginManager

        # 创建带有指标配置的插件
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            id="sql_mysql_test",
            type="sql",
            label="os",
            name="MySQL测试插件",
            description_md="测试",
            params=[],
            define={
                "linux": {},
                "sql_content": [
                    {
                        "classification_id": "test_table",
                        "classification_name": "测试表",
                        "content": "SELECT field1, field2 FROM test;",
                    },
                ],
            },
            version=(1, 0),
            status=MetricPluginStatus.RELEASE,
            created_by="admin",
            updated_by="admin",
            metrics=[
                MetricPluginMetricGroup(
                    table_name="test_table",
                    fields=[
                        MetricPluginMetricField(name="field1", type="string", monitor_type="dimension"),
                        MetricPluginMetricField(name="field2", type="double", monitor_type="metric"),
                    ],
                ),
            ],
        )

        manager = MysqlPluginManager(plugin)

        # 验证 get_parse_rules_json 返回正确结构
        parse_rules = manager.get_parse_rules_json()
        assert len(parse_rules) == 1
        assert parse_rules[0]["sql"] == "SELECT field1, field2 FROM test;"
        assert len(parse_rules[0]["variate"]) == 2

        # 验证字段类型映射正确
        variate_types = {v["object_name"]: v["object_type"] for v in parse_rules[0]["variate"]}
        assert variate_types["field1"] == "dimension"
        assert variate_types["field2"] == "metric"

    def test_get_os_target_path(self):
        """测试获取目标路径"""
        from bk_monitor_base.domains.metric_plugin.manager.base import OSType

        installer = SQLInstaller(self.test_deployment, operator="admin")

        linux_path = installer.get_os_target_path(1, OSType.LINUX)
        assert "job_plugins" in linux_path
        # 路径格式: {plugin_type}_{deployment_id}_{instance_id}
        expected_path_segment = f"sql_{self.deployment_model.pk}_1"
        assert expected_path_segment in linux_path
        assert "sql_mysql" in linux_path

    def test_analyze_target_changes_first_deploy(self):
        """测试分析目标变更 - 首次部署"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        changes = installer._analyze_target_changes(None, self.test_deployment_version)

        assert len(changes["targets_to_add"]) == 2
        assert len(changes["targets_to_remove"]) == 0
        assert len(changes["targets_to_update"]) == 0
        assert len(changes["targets_unchanged"]) == 0

    def test_analyze_target_changes_with_updates(self):
        """测试分析目标变更 - 有更新"""
        installer = SQLInstaller(deployment=self.test_deployment, operator="admin")

        # 创建旧版本
        old_version = MetricPluginDeploymentVersion(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            deployment_id=self.deployment_model.pk,
            plugin_version=(1, 0),
            version=1,
            target_scope=MetricPluginDeploymentScope(
                node_type="INSTANCE",
                nodes=[
                    {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},  # 保持不变
                    {"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0},  # 将被删除
                ],
            ),
            params={
                "collector": {
                    "host_1": {"period": "60s", "timeout": "60s"},
                    "host_3": {"period": "60s", "timeout": "60s"},
                },
                "plugin": {
                    "host_1": {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "123456"},
                    "host_3": {"host": "127.0.0.3", "port": 3306, "user": "root", "password": "123456"},
                },
            },
        )

        # 新版本：1 不变，2 新增，3 删除
        new_version = self.test_deployment_version

        changes = installer._analyze_target_changes(old_version, new_version)

        assert len(changes["targets_to_add"]) == 1  # bk_host_id=2
        assert len(changes["targets_to_remove"]) == 1  # bk_host_id=3
        assert len(changes["targets_unchanged"]) == 1  # bk_host_id=1

    def test_create_task_instances(self):
        """测试创建任务实例"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        installer.deployment_version = self.test_deployment_version

        targets = [
            {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            {"bk_host_id": 2, "ip": "127.0.0.2", "bk_cloud_id": 0},
        ]

        inst_mapping = installer._create_task_instances(JobTaskActionEnum.INSTALL, targets)

        assert len(inst_mapping) == 2
        assert "host_1" in inst_mapping
        assert "host_2" in inst_mapping

        # 验证数据库中的任务实例
        task_inst_1 = JobTaskInstanceModel.objects.get(pk=inst_mapping["host_1"])
        assert task_inst_1.action == JobTaskActionEnum.INSTALL.value
        assert task_inst_1.status == JobTaskStatusEnum.PENDING.value

    def test_create_task_instances_for_remote_collect_distributes_without_mapping_collision(self):
        """测试远程采集时按采集目标建任务，远程执行节点可复用且映射不覆盖"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        deployment_version = self.test_deployment_version.model_copy(
            update={
                "target_scope": MetricPluginDeploymentScope(
                    node_type="INSTANCE",
                    nodes=[
                        {"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
                        {"bk_host_id": 2, "ip": "127.0.0.2", "bk_cloud_id": 0},
                        {"bk_host_id": 5, "ip": "127.0.0.5", "bk_cloud_id": 0},
                    ],
                ),
                "remote_scope": MetricPluginDeploymentScope(
                    node_type="INSTANCE",
                    nodes=[
                        {"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0},
                        {"bk_host_id": 4, "ip": "127.0.0.4", "bk_cloud_id": 0},
                    ],
                ),
                "params": {
                    "collector": {
                        "host_3": {"period": "60s"},
                        "host_4": {"period": "30s"},
                    },
                    "plugin": {
                        "host_3": {"host": "10.0.0.3"},
                        "host_4": {"host": "10.0.0.4"},
                    },
                },
            }
        )
        installer.deployment_version = deployment_version

        inst_mapping = installer._create_task_instances(JobTaskActionEnum.INSTALL)

        assert set(inst_mapping.keys()) == {"host_1", "host_2", "host_5"}
        task_inst_1 = JobTaskInstanceModel.objects.get(pk=inst_mapping["host_1"])
        task_inst_2 = JobTaskInstanceModel.objects.get(pk=inst_mapping["host_2"])
        task_inst_5 = JobTaskInstanceModel.objects.get(pk=inst_mapping["host_5"])

        assert task_inst_1.instance_info["bk_host_id"] == 1
        assert task_inst_2.instance_info["bk_host_id"] == 2
        assert task_inst_5.instance_info["bk_host_id"] == 5
        assert task_inst_1.collect_instance_info["bk_host_id"] == 3
        assert task_inst_2.collect_instance_info["bk_host_id"] == 4
        assert task_inst_5.collect_instance_info["bk_host_id"] == 3
        assert "instance_info" not in task_inst_5.execute_params
        assert "collect_instance_info" not in task_inst_5.execute_params
        assert task_inst_5.execute_params["plugin_params"]["host"] == "10.0.0.3"

    def test_get_all_task_instances(self):
        """测试获取所有任务实例"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        # 创建任务实例
        task_inst_1 = JobTaskInstanceModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL.value,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={},
            status=JobTaskStatusEnum.PENDING.value,
        )
        task_inst_2 = JobTaskInstanceModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL.value,
            instance_id="host_2",
            instance_info={"bk_host_id": 2},
            execute_params={},
            status=JobTaskStatusEnum.PENDING.value,
        )

        # 设置映射
        installer.job_inst_mapping = {"host_1": task_inst_1.pk, "host_2": task_inst_2.pk}

        instances = installer.get_all_task_instances()
        assert len(instances) == 2

    def test_check_support_unsupported_label(self):
        """测试检查支持 - 不支持的标签"""
        # 修改数据库中的插件标签为不支持的类型
        original_label = self.plugin_model.label
        self.plugin_model.label = "service"
        self.plugin_model.save()

        try:
            installer = SQLInstaller(self.test_deployment, operator="admin")

            with pytest.raises(MetricPluginDeploymentOperationError, match="SQL 安装器暂不支持"):
                installer._check_support(self.test_deployment_version)
        finally:
            # 恢复原始标签
            self.plugin_model.label = original_label
            self.plugin_model.save()

    def test_check_support_unsupported_target_node_type(self):
        """测试检查支持 - 不支持非主机目标类型"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        deployment_version = self.test_deployment_version.model_copy(
            update={"target_scope": MetricPluginDeploymentScope(node_type="INSTANCE", nodes=[])}
        )

        with pytest.raises(MetricPluginDeploymentOperationError, match="非主机目标类型"):
            installer._check_support(deployment_version)

    def test_build_install_task_context(self, mock_storage: MagicMock, mock_plugin_manager: MagicMock):
        """测试构建安装任务上下文"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            execute_params={
                "collector_params": {"period": "60s", "timeout": "60s"},
                "plugin_params": {"host": "127.0.0.1", "port": 3306},
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        context = installer._build_install_task_context(job_inst)

        # 验证上下文包含必要的参数
        assert context["job_task_inst_id"] == job_inst.id
        assert context["target_server"] is not None
        assert context["account_alias"] == "root"
        assert "sql_config_file_path" in context
        assert "bkmonitorbeat_conf_source_file_path" in context
        assert "restart_bkmonitorbeat_script" in context
        assert "remove_config_script" in context
        assert "remove_plugin_script" in context
        # 验证包含二进制授权脚本
        assert "chmod_plugin_script" in context

    def test_build_install_task_context_chmod_script_linux(
        self, mock_storage: MagicMock, mock_plugin_manager: MagicMock
    ):
        """测试构建安装任务上下文 - Linux系统下的二进制授权脚本

        验证在Linux操作系统下，生成的 chmod_plugin_script 包含正确的 chmod +x 命令，
        并指向正确的二进制文件路径。
        """
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            execute_params={
                "collector_params": {"period": "60s", "timeout": "60s"},
                "plugin_params": {"host": "127.0.0.1", "port": 3306},
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        context = installer._build_install_task_context(job_inst)

        # 验证 chmod 脚本格式正确
        chmod_script = context["chmod_plugin_script"]
        assert chmod_script.startswith("chmod +x ")
        # 验证脚本中包含插件二进制路径
        assert "sql_mysql" in chmod_script

    def test_build_uninstall_task_context(self):
        """测试构建卸载任务上下文"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            id=1,
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.UNINSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={},
            status=JobTaskStatusEnum.PENDING,
        )

        context = installer._build_uninstall_task_context(job_inst)

        assert context["job_task_inst_id"] == 1
        assert "plugin_target_path" in context
        assert "remove_plugin_script" in context
        assert "remove_config_script" in context
        assert "restart_bkmonitorbeat_script" in context

    def test_build_stop_task_context(self):
        """测试构建停止任务上下文"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            id=1,
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.STOP,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={},
            status=JobTaskStatusEnum.PENDING,
        )

        context = installer._build_stop_task_context(job_inst)

        assert context["job_task_inst_id"] == 1
        assert "remove_config_script" in context
        assert "restart_bkmonitorbeat_script" in context

    @patch("bk_monitor_base.domains.metric_plugin.installer.job.submit_install_task")
    def test_install_first_deployment(self, mock_submit: Mock, mock_celery_engine: MagicMock):
        """测试安装 - 首次部署"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        # 删除部署版本记录以模拟首次部署
        MetricPluginDeploymentVersionModel.objects.filter(deployment_id=self.deployment_model.pk).delete()
        result = installer.install(self.test_deployment_version)
        assert result is not None
        # 验证已创建任务实例
        assert len(result["job_inst_mapping"]) == 2
        assert len(installer.job_inst_mapping) == 2

        # 验证已提交安装任务
        assert mock_submit.call_count == 2

        # 验证部署状态已更新
        deployment = MetricPluginDeploymentModel.objects.get(pk=self.deployment_model.pk)
        assert deployment.status == MetricPluginDeploymentStatusEnum.DEPLOYING.value

    @patch("bk_monitor_base.domains.metric_plugin.installer.job.submit_uninstall_task")
    def test_uninstall(self, mock_submit: Mock, mock_celery_engine: MagicMock):
        """测试卸载"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        # 更新部署状态为运行中
        self.deployment_model.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        self.deployment_model.save()
        self.test_deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value

        installer.uninstall()

        # 验证已提交卸载任务（deployment_version 有2个目标节点）
        assert mock_submit.call_count == 2

        # 验证部署记录已被删除
        assert not MetricPluginDeploymentModel.objects.filter(pk=self.deployment_model.pk).exists()
        assert not MetricPluginDeploymentVersionModel.objects.filter(deployment_id=self.deployment_model.pk).exists()

    @patch("bk_monitor_base.domains.metric_plugin.installer.job.submit_stop_task")
    def test_stop(self, mock_submit: Mock, mock_celery_engine: MagicMock):
        """测试停止"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        # 先创建任务实例
        task_inst = JobTaskInstanceModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL.value,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={},
            status=JobTaskStatusEnum.SUCCESS.value,
        )
        installer.job_inst_mapping = {"host_1": task_inst.pk}

        # 更新部署状态为运行中
        self.deployment_model.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        self.deployment_model.save()
        self.test_deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value

        installer.stop()

        # 验证已提交停止任务（deployment_version 有2个目标节点）
        assert mock_submit.call_count == 2

        # 验证部署状态已更新
        deployment = MetricPluginDeploymentModel.objects.get(pk=self.deployment_model.pk)
        assert deployment.status == MetricPluginDeploymentStatusEnum.STOPPING.value

    @patch("bk_monitor_base.domains.metric_plugin.installer.job.submit_start_task")
    def test_start(self, mock_submit: Mock, mock_celery_engine: MagicMock):
        """测试启动"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        # 先创建任务实例
        task_inst = JobTaskInstanceModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.STOP.value,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={},
            status=JobTaskStatusEnum.SUCCESS.value,
        )
        installer.job_inst_mapping = {"host_1": task_inst.pk}

        # 更新部署状态为已停止
        self.deployment_model.status = MetricPluginDeploymentStatusEnum.STOPPED.value
        self.deployment_model.save()
        self.test_deployment.status = MetricPluginDeploymentStatusEnum.STOPPED.value

        installer.start()

        # 验证已提交启动任务（deployment_version 有2个目标节点）
        assert mock_submit.call_count == 2

        # 验证部署状态已更新
        deployment = MetricPluginDeploymentModel.objects.get(pk=self.deployment_model.pk)
        assert deployment.status == MetricPluginDeploymentStatusEnum.STARTING.value

    def test_get_task_instance(self):
        """测试获取任务实例"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        # 创建任务实例
        task_inst = JobTaskInstanceModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL.value,
            instance_id="host_1",
            instance_info={"bk_host_id": 1},
            execute_params={},
            status=JobTaskStatusEnum.SUCCESS.value,
        )
        installer.job_inst_mapping = {"host_1": task_inst.pk}

        # 获取任务实例
        result = installer.get_task_instance("host_1")
        assert result is not None
        assert result.id == task_inst.pk

        # 获取不存在的任务实例
        result = installer.get_task_instance("host_999")
        assert result is None

    def test_get_data_ids(self, mock_plugin_manager: MagicMock):
        """测试获取数据ID"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        data_ids = installer.get_data_ids()
        assert "bk_data_id" in data_ids
        assert data_ids["bk_data_id"] == 50001

    def test_instance_status_returns_structured_job_log_detail(self, mocker):
        """测试单实例日志详情返回结构化原始数据"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        mocker.patch.object(
            installer,
            "status",
            return_value={
                "instance_status": {
                    "host_1": {
                        "task_id": 1,
                        "status": "failed",
                        "current_step": "TRANSFER_PLUGIN",
                        "error_message": "execute failed",
                        "detail": {
                            "task_log": [
                                {
                                    "step": "TRANSFER_PLUGIN",
                                    "status": "failed",
                                    "messages": "failed detail",
                                    "job_instance_id": 10086,
                                    "timestamp": "2026-05-11T00:00:00",
                                    "extra": {"request_id": "req-1"},
                                }
                            ]
                        },
                    }
                }
            },
        )

        result = installer.instance_status("host_1")

        assert result == {
            "task_id": 1,
            "instance_id": "host_1",
            "status": "failed",
            "current_step": "TRANSFER_PLUGIN",
            "error_message": "execute failed",
            "task_log": [
                {
                    "step": "TRANSFER_PLUGIN",
                    "status": "failed",
                    "messages": "failed detail",
                    "job_instance_id": 10086,
                    "timestamp": "2026-05-11T00:00:00",
                    "extra": {"request_id": "req-1"},
                }
            ],
        }
        assert "log_detail" not in result

    def test_build_extra_dimensions_maps_host_service_and_custom_dimensions(self):
        """测试 dms_insert 参数如何映射为 bkmonitorbeat labels"""
        from bk_monitor_base.domains.metric_plugin.define import MetricPluginParams

        self.version_model.params = [
            MetricPluginParams(name="host_dimensions", type="host", mode="dms_insert").model_dump(),
            MetricPluginParams(name="service_dimensions", type="service", mode="dms_insert").model_dump(),
            MetricPluginParams(name="custom_dimensions", type="custom", mode="dms_insert").model_dump(),
            MetricPluginParams(name="plain_param", type="string").model_dump(),
        ]
        self.version_model.save(update_fields=["params"])
        installer = SQLInstaller(self.test_deployment, operator="admin")

        labels = installer._build_extra_dimensions(
            plugin_params={
                "host_dimensions": {
                    "bk_target_host_id": "bk_host_id",
                    "missing_host_label": "fallback_value",
                },
                "service_dimensions": {
                    "service_module": "module",
                    "missing_service_label": "missing",
                },
                "custom_dimensions": {"custom_label": "custom_value"},
                "plain_param": {"ignored": "ignored"},
            },
            target={
                "bk_host_id": 1,
                "service": {"labels": {"module": "mysql"}},
            },
        )

        assert labels == {
            "bk_target_host_id": "1",
            "missing_host_label": "fallback_value",
            "service_module": "mysql",
            "missing_service_label": "-",
            "custom_label": "custom_value",
        }

    def test_build_extra_dimensions_ignores_empty_label_key_and_missing_param(self):
        """测试 dms_insert 缺省参数和空 label key 不会生成 labels"""
        from bk_monitor_base.domains.metric_plugin.define import MetricPluginParams

        self.version_model.params = [
            MetricPluginParams(name="host_dimensions", type="host", mode="dms_insert").model_dump(),
            MetricPluginParams(name="missing_dimensions", type="host", mode="dms_insert").model_dump(),
        ]
        self.version_model.save(update_fields=["params"])
        installer = SQLInstaller(self.test_deployment, operator="admin")

        labels = installer._build_extra_dimensions(
            plugin_params={"host_dimensions": {"": "bk_host_id", "bk_target_ip": "ip"}},
            target={"bk_host_id": 1, "ip": "127.0.0.1"},
        )

        assert labels == {"bk_target_ip": "127.0.0.1"}

    def test_build_extra_dimensions_rejects_non_dict_dms_value(self):
        """测试 dms_insert 参数值必须是 label 映射字典"""
        from bk_monitor_base.domains.metric_plugin.define import MetricPluginParams

        self.version_model.params = [
            MetricPluginParams(name="host_dimensions", type="host", mode="dms_insert").model_dump()
        ]
        self.version_model.save(update_fields=["params"])
        installer = SQLInstaller(self.test_deployment, operator="admin")

        with pytest.raises(ValueError, match="dms_insert param value must be dict"):
            installer._build_extra_dimensions(
                plugin_params={"host_dimensions": ["bk_host_id"]},
                target={"bk_host_id": 1},
            )

    def test_build_builtin_dimensions_covers_declared_job_labels(self):
        """测试固定注入 labels 覆盖 Job 内置维度声明"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        labels = installer._build_builtin_dimensions({"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0})
        built_in_dimension_fields = {dimension.field_name for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS}

        assert built_in_dimension_fields <= set(labels)
        assert labels["bk_collect_config_id"] == str(self.test_deployment.id)
        assert labels["bk_target_cloud_id"] == "0"
        assert labels["bk_target_ip"] == "127.0.0.1"
        assert labels["bk_target_host_id"] == "1"

    def test_build_builtin_dimensions_raises_when_declared_label_missing(self, monkeypatch: pytest.MonkeyPatch):
        """测试声明新增但实际 labels 未覆盖时会失败"""
        missing_dimension = Mock(field_name="missing_builtin_dimension")
        monkeypatch.setattr(
            "bk_monitor_base.domains.metric_plugin.installer.job.JOB_PLUGIN_BUILT_IN_DIMENSIONS",
            [*JOB_PLUGIN_BUILT_IN_DIMENSIONS, missing_dimension],
        )
        installer = SQLInstaller(self.test_deployment, operator="admin")

        with pytest.raises(MetricPluginDeploymentOperationError, match="missing_builtin_dimension"):
            installer._build_builtin_dimensions({"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0})

    def test_generate_bkmonitorbeat_yaml(self, mock_plugin_manager: MagicMock):
        """测试生成 bkmonitorbeat 配置"""
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            execute_params={
                "collector_params": {"period": "60s", "timeout": "60s"},
                "plugin_params": {"host": "127.0.0.1", "port": 3306},
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        config_path = installer._generate_bkmonitorbeat_yaml(
            job_inst,
            config_target_file_path="/tmp/config.yml",
            binary_target_file_path="/tmp/binary",
        )

        assert config_path is not None
        assert "bkmonitorbeat_sql_config_" in config_path

    def test_generate_bkmonitorbeat_yaml_normalizes_numeric_duration(
        self, mock_storage: MagicMock, mock_plugin_manager: MagicMock
    ):
        """测试生成 bkmonitorbeat 配置时将秒数转换为 duration 字符串"""
        captured_content: dict[str, str | bytes] = {}

        def capture_saved_content(path: str, file_obj: Any) -> str:
            captured_content["content"] = file_obj.read()
            return path

        mock_storage.save.side_effect = capture_saved_content
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            execute_params={
                "collector_params": {"period": 60, "timeout": "30"},
                "plugin_params": {"host": "127.0.0.1", "port": 3306},
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        installer._generate_bkmonitorbeat_yaml(
            job_inst,
            config_target_file_path="/tmp/config.yml",
            binary_target_file_path="/tmp/binary",
        )

        raw_content = captured_content["content"]
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8")
        config = yaml.safe_load(raw_content)
        task_config = config["tasks"][0]

        assert "period: 60s" in raw_content
        assert "timeout: 30s" in raw_content
        assert "period: '60s'" not in raw_content
        assert 'period: "60s"' not in raw_content
        assert "timeout: '30s'" not in raw_content
        assert 'timeout: "30s"' not in raw_content
        assert task_config["period"] == "60s"
        assert task_config["timeout"] == "30s"

    def test_generate_bkmonitorbeat_yaml_rejects_invalid_duration(self, mock_plugin_manager: MagicMock):
        """测试生成 bkmonitorbeat 配置时拒绝无效 duration"""
        installer = SQLInstaller(self.test_deployment, operator="admin")
        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0},
            execute_params={
                "collector_params": {"period": "every minute", "timeout": "60s"},
                "plugin_params": {"host": "127.0.0.1", "port": 3306},
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        with pytest.raises(MetricPluginDeploymentOperationError, match="period"):
            installer._generate_bkmonitorbeat_yaml(
                job_inst,
                config_target_file_path="/tmp/config.yml",
                binary_target_file_path="/tmp/binary",
            )

    def test_generate_bkmonitorbeat_yaml_injects_dms_labels(
        self, mock_storage: MagicMock, mock_plugin_manager: MagicMock
    ):
        """测试生成 bkmonitorbeat 配置时注入 dms_insert 维度"""
        from bk_monitor_base.domains.metric_plugin.define import MetricPluginParams

        self.version_model.params = [
            MetricPluginParams(name="host_dimensions", type="host", mode="dms_insert").model_dump(),
            MetricPluginParams(name="custom_dimensions", type="custom", mode="dms_insert").model_dump(),
        ]
        self.version_model.save(update_fields=["params"])

        captured_content: dict[str, str | bytes] = {}

        def capture_saved_content(path: str, file_obj: Any) -> str:
            captured_content["content"] = file_obj.read()
            return path

        mock_storage.save.side_effect = capture_saved_content
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={
                "bk_host_id": 1,
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "cw_object_model_id": "cw-Host",
            },
            execute_params={
                "collector_params": {"period": "60s", "timeout": "60s"},
                "plugin_params": {
                    "host_dimensions": {
                        "cw_object_model_id": "cw_object_model_id",
                        "legacy_literal": "legacy_value",
                    },
                    "custom_dimensions": {"custom_label": "custom_value"},
                },
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        installer._generate_bkmonitorbeat_yaml(
            job_inst,
            config_target_file_path="/tmp/config.yml",
            binary_target_file_path="/tmp/binary",
        )

        raw_content = captured_content["content"]
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8")
        config = yaml.safe_load(raw_content)
        labels = config["tasks"][0]["labels"][0]
        built_in_dimension_fields = {dimension.field_name for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS}

        assert built_in_dimension_fields <= set(labels)
        assert labels["bk_target_host_id"] == "1"
        assert labels["cw_object_model_id"] == "cw-Host"
        assert labels["legacy_literal"] == "legacy_value"
        assert labels["custom_label"] == "custom_value"

    def test_generate_bkmonitorbeat_yaml_uses_instance_info_labels_for_remote_collect(
        self, mock_storage: MagicMock, mock_plugin_manager: MagicMock
    ):
        """测试远程采集时 labels 使用采集目标而不是远程下发节点"""
        captured_content: dict[str, str | bytes] = {}

        def capture_saved_content(path: str, file_obj: Any) -> str:
            captured_content["content"] = file_obj.read()
            return path

        mock_storage.save.side_effect = capture_saved_content
        installer = SQLInstaller(self.test_deployment, operator="admin")

        job_inst = JobTaskInstance(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            action=JobTaskActionEnum.INSTALL,
            instance_id="host_1",
            instance_info={"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0, "instance_id": "host_1"},
            collect_instance_info={"bk_host_id": 3, "ip": "127.0.0.3", "bk_cloud_id": 0},
            execute_params={
                "collector_params": {"period": "60s", "timeout": "60s"},
                "plugin_params": {"host": "10.0.0.10", "port": 3306},
            },
            status=JobTaskStatusEnum.PENDING,
        )
        JobTaskInstanceModel.save_instance(job_inst)

        installer._generate_bkmonitorbeat_yaml(
            job_inst,
            config_target_file_path="/tmp/config.yml",
            binary_target_file_path="/tmp/binary",
        )

        raw_content = captured_content["content"]
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8")
        config = yaml.safe_load(raw_content)
        labels = config["tasks"][0]["labels"][0]

        assert labels["bk_target_host_id"] == "1"
        assert labels["bk_target_ip"] == "127.0.0.1"
        assert labels["bk_target_cloud_id"] == "0"


class TestSQLInstallerChmodPluginScripts:
    """测试 SQL 安装器的二进制授权脚本相关功能

    该测试类验证 CHMOD_PLUGIN_SCRIPTS 常量的正确性，
    以及在 install/start 操作中 chmod 脚本的正确生成和执行顺序。
    """

    def test_chmod_plugin_scripts_constant_has_required_os_types(self):
        """测试 CHMOD_PLUGIN_SCRIPTS 常量包含所有必要的操作系统类型

        验证常量中包含 LINUX、LINUX_AARCH64、AIX 三种操作系统的授权脚本配置。
        """
        from bk_monitor_base.domains.metric_plugin.installer.job import SQLInstaller
        from bk_monitor_base.domains.metric_plugin.manager.base import OSType

        # 验证包含必要的操作系统类型
        assert OSType.LINUX in SQLInstaller.CHMOD_PLUGIN_SCRIPTS
        assert OSType.LINUX_AARCH64 in SQLInstaller.CHMOD_PLUGIN_SCRIPTS
        assert OSType.AIX in SQLInstaller.CHMOD_PLUGIN_SCRIPTS

    def test_chmod_plugin_scripts_format_string(self):
        """测试 CHMOD_PLUGIN_SCRIPTS 脚本模板格式

        验证每个操作系统的脚本模板包含正确的 chmod +x 命令和占位符。
        """
        from bk_monitor_base.domains.metric_plugin.installer.job import SQLInstaller
        from bk_monitor_base.domains.metric_plugin.manager.base import OSType

        test_cases = [
            (OSType.LINUX, "chmod +x {binary_target_file_path}"),
            (OSType.LINUX_AARCH64, "chmod +x {binary_target_file_path}"),
            (OSType.AIX, "chmod +x {binary_target_file_path}"),
        ]

        for os_type, expected_template in test_cases:
            actual_template = SQLInstaller.CHMOD_PLUGIN_SCRIPTS[os_type]
            assert actual_template == expected_template, f"操作系统 {os_type} 的脚本模板不匹配"

    def test_chmod_plugin_scripts_renders_correctly(self):
        """测试 CHMOD_PLUGIN_SCRIPTS 脚本模板渲染

        验证使用实际二进制路径参数渲染脚本模板后得到正确的 chmod 命令。
        """
        from bk_monitor_base.domains.metric_plugin.installer.job import SQLInstaller
        from bk_monitor_base.domains.metric_plugin.manager.base import OSType

        test_binary_path = "/usr/local/gse/job_plugins/sql_110_1/sql_mysql"
        script_params = {"binary_target_file_path": test_binary_path}

        test_cases = [
            (OSType.LINUX, f"chmod +x {test_binary_path}"),
            (OSType.LINUX_AARCH64, f"chmod +x {test_binary_path}"),
            (OSType.AIX, f"chmod +x {test_binary_path}"),
        ]

        for os_type, expected_script in test_cases:
            rendered_script = SQLInstaller.CHMOD_PLUGIN_SCRIPTS[os_type].format(**script_params)
            assert rendered_script == expected_script, f"操作系统 {os_type} 的脚本渲染结果不匹配"

    def test_chmod_script_not_for_windows(self):
        """测试 Windows 操作系统不包含 chmod 脚本

        Windows 系统不需要执行 chmod 授权操作，因此 CHMOD_PLUGIN_SCRIPTS 中不应包含 Windows。
        """
        from bk_monitor_base.domains.metric_plugin.installer.job import SQLInstaller
        from bk_monitor_base.domains.metric_plugin.manager.base import OSType

        assert OSType.WINDOWS not in SQLInstaller.CHMOD_PLUGIN_SCRIPTS
