import json
import shutil

from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import OSTypeToPluginDirName
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.pushgateway import PushgatewayPluginManager


class TestPushgatewayPluginManager:
    """测试 PushgatewayPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="Pushgateway",
            name="测试插件",
            description_md="测试pushgateway插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={"diff_fields": "metric1,metric2,metric3"},
            params=[
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="metrics_url",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="测试采集URL参数",
                    default="",
                    required=True,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="username",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="测试采集URL认证用户名参数",
                    default="",
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="password",
                    type=NodemanPluginParamsType.PASSWORD,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="测试采集URL认证密码参数",
                    default="",
                ),
                # SERVICE + DMS_INSERT
                MetricPluginParams(
                    name="服务实例维度注入",
                    type=NodemanPluginParamsType.SERVICE,
                    mode=NodemanPluginParamsMode.DMS_INSERT,
                    description="可以从配置平台获取相应服务实例的标签追加到采集的数据里当成维度",
                    default={},
                    required=False,
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="test_metric",
                    fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = PushgatewayPluginManager(self.plugin)

    def test_make_package(self):
        """测试制作Pushgateway插件包"""
        package_dir = self.plugin_manager.make_package(is_compress=True)
        # 检查插件压缩包
        assert package_dir.exists() and package_dir.is_file()

        # 检查插件目录
        for os_type in self.plugin_manager.get_supported_os_types():
            plugin_dir = package_dir.parent / "test_plugin" / OSTypeToPluginDirName[os_type] / "test_plugin"
            assert plugin_dir.exists() and plugin_dir.is_dir()

            assert (plugin_dir / "info" / "description.md").read_text(encoding="utf-8") == "测试pushgateway插件"
            assert (plugin_dir / "info" / "config.json").read_text(encoding="utf-8") == json.dumps(
                [param.model_dump() for param in self.plugin.params], ensure_ascii=False, indent=4
            )
            assert (plugin_dir / "info" / "metrics.json").read_text(encoding="utf-8") == json.dumps(
                [self.plugin.metrics[0].model_dump()], ensure_ascii=False, indent=4
            )

        # 删除插件包目录
        shutil.rmtree(package_dir.parent)

    def test_debug_context(self):
        """测试调试上下文"""
        collect_params = {
            "period": 300,
            "metrics_url": "http://test.com/metrics",
            "username": "test_user",
            "password": "test_password",
        }
        plugin_params = {"服务实例维度注入": {"env": "prod"}}

        # 测试_get_debug_config_context方法
        debug_context = self.plugin_manager._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[],
        )

        expected_debug_context = {
            "bkmonitorbeat_debug.yaml": {
                "metric_url": "http://test_user:test_password@test.com/metrics",
                "period": 300,
                "labels": {
                    "$for": "cmdb_instance.scope",
                    "$item": "scope",
                    "$body": {"env": "{{ cmdb_instance.service.labels['prod'] or '-' }}"},
                },
            },
            "env.yaml": {},
        }

        # 校验调试配置上下文结果
        assert debug_context == expected_debug_context, f"调试配置上下文不匹配: {debug_context}"

    def test_get_deploy_steps_params(self):
        collect_params = {
            "period": 300,
            "metrics_url": "http://test.com/metrics",
            "username": "test_user",
            "password": "test_password",
        }
        plugin_params = {"服务实例维度注入": {"env": "prod"}}

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        expected_steps_params = [
            {
                "id": "test_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_prometheus.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "period": "300",
                        "task_id": "2",
                        "bk_biz_id": "1",
                        "config_name": "test_plugin",
                        "config_version": "1.0",
                        "namespace": "test_plugin",
                        "timeout": "60",
                        "max_timeout": "60",
                        "dataid": 3,
                        "labels": {
                            "$for": "cmdb_instance.scope",
                            "$item": "scope",
                            "$body": {
                                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                                "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                "bk_collect_config_id": "2",
                                "env": "{{ cmdb_instance.service.labels['prod'] or '-' }}",
                            },
                        },
                        "metric_url": "http://test_user:test_password@test.com/metrics",
                        "diff_metrics": ["metric1", "metric2", "metric3"],
                    }
                },
            },
        ]
        assert steps_params == expected_steps_params
