import json

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
from bk_monitor_base.domains.metric_plugin.manager.node_man.snmp import SNMPPluginManager


class TestSNMPPluginManager:
    """测试 SNMPPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_snmp_plugin",
            type="SNMP",
            name="测试SNMP插件",
            description_md="测试SNMP插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "config_yaml": "if_mib:\r\n  get:\r\n    - 1.3.6.1.2.1.1.3.0\r\n    - 1.3.6.1.4.1.9.2.1.58.0\r\n  "
                "metrics:\r\n    - name: cw_CiscoSwitch_sysUpTime\r\n      "
                "oid: 1.3.6.1.2.1.1.3\r\n      "
                'type: gauge\r\n      help: "设备运行时间"\r\n\r\n    ',
                "filename": "snmp.yaml",
                "snmp_version": "1",
            },
            params=[
                # TEXT + OPT_CMD
                MetricPluginParams(
                    name="community",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.OPT_CMD,
                    description="团体名",
                    default="public",
                    required=False,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="host",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="绑定地址",
                    default="0.0.0.0",
                    required=False,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="port",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="监听端口",
                    default="",
                    required=False,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="snmp_port",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="设备端口",
                    default="",
                    required=False,
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="snmp_metric",
                    fields=[MetricPluginMetricField(name="ifInOctets", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = SNMPPluginManager(self.plugin)

    def test_make_package(self):
        """测试制作SNMP插件包"""
        package_dir = self.plugin_manager.make_package(is_compress=True)
        # 检查插件压缩包
        assert package_dir.exists() and package_dir.is_file()

        # 检查插件目录
        for os_type in self.plugin_manager.get_supported_os_types():
            plugin_dir = package_dir.parent / "test_snmp_plugin" / OSTypeToPluginDirName[os_type] / "test_snmp_plugin"
            assert plugin_dir.exists() and plugin_dir.is_dir()

            assert (plugin_dir / "info" / "description.md").read_text(encoding="utf-8") == "测试SNMP插件"
            assert (plugin_dir / "info" / "config.json").read_text(encoding="utf-8") == json.dumps(
                [param.model_dump() for param in self.plugin.params], ensure_ascii=False, indent=4
            )
            assert (plugin_dir / "info" / "metrics.json").read_text(encoding="utf-8") == json.dumps(
                [self.plugin.metrics[0].model_dump()], ensure_ascii=False, indent=4
            )

    def test_get_supported_os_types(self):
        """测试获取支持的操作系统类型"""
        supported_os_types = self.plugin_manager.get_supported_os_types()
        actual_os_types = [os_type.value for os_type in supported_os_types]

        # 根据SNMP插件实现，应该只支持linux
        expected_os_types = ["linux"]

        assert set(actual_os_types) == set(expected_os_types)

    def test_get_package_context(self):
        """测试获取插件包上下文"""
        package_context = self.plugin_manager._get_package_context()

        expected_package_context = {
            "metric_json": [
                {
                    "fields": [
                        {
                            "description": "",
                            "is_active": True,
                            "is_diff_metric": False,
                            "monitor_type": "metric",
                            "name": "ifInOctets",
                            "source_name": "",
                            "type": "double",
                            "unit": "none",
                        }
                    ],
                    "rules": [],
                    "table_desc": "",
                    "table_name": "snmp_metric",
                }
            ],
            "plugin_id": "test_snmp_plugin",
            "plugin_display_name": "测试SNMP插件",
            "version": "1.0",
            "config_version": 1,
            "plugin_type": "SNMP",
            "port_range": "10000-65535",
            "tag": "",
            "label": "",
            "description_md": "测试SNMP插件",
            "config_json": [
                {
                    "alias": "",
                    "default": "public",
                    "description": "团体名",
                    "election": [],
                    "file_base64": "",
                    "mode": "opt_cmd",
                    "name": "community",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": True,
                },
                {
                    "alias": "",
                    "default": "0.0.0.0",
                    "description": "绑定地址",
                    "election": [],
                    "file_base64": "",
                    "mode": "collector",
                    "name": "host",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": True,
                },
                {
                    "alias": "",
                    "default": "",
                    "description": "监听端口",
                    "election": [],
                    "file_base64": "",
                    "mode": "collector",
                    "name": "port",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": True,
                },
                {
                    "alias": "",
                    "default": "",
                    "description": "设备端口",
                    "election": [],
                    "file_base64": "",
                    "mode": "collector",
                    "name": "snmp_port",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": True,
                },
            ],
            "collector_json": {
                "config_yaml": "if_mib:\r\n  get:\r\n    - 1.3.6.1.2.1.1.3.0\r\n    - 1.3.6.1.4.1.9.2.1.58.0\r\n  "
                "metrics:\r\n    - name: cw_CiscoSwitch_sysUpTime\r\n      "
                "oid: 1.3.6.1.2.1.1.3\r\n      "
                'type: gauge\r\n      help: "设备运行时间"\r\n\r\n    ',
                "filename": "snmp.yaml",
                "snmp_version": "1",
            },
            "signature": "",
            "is_support_remote": False,
            "version_log": "",
        }

        assert package_context == expected_package_context

    def test_debug_context(self):
        """测试调试上下文"""
        collect_params = {
            "host": "127.0.0.1",
            "port": 8080,
            "period": 300,
            "snmp_port": 161,
        }
        plugin_params = {
            "community": "public",
            "security_level": "authPriv",
            "security_name": "test_user",
            "authentication_passphrase": "auth_pass",
            "authentication_protocol": "MD5",
            "privacy_passphrase": "priv_pass",
            "privacy_protocol": "DES",
            "context_name": "test_context",
        }
        target_nodes = [{"ip": "127.0.0.2"}, {"ip": "127.0.0.3"}]

        # 测试_get_debug_config_context方法
        debug_context = self.plugin_manager._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=target_nodes,
        )

        expected_debug_context = {
            "config.yaml": {
                "community": "public",
                "security_level": "authPriv",
                "context_name": "test_context",
                "username": "test_user",
                "password": "auth_pass",
                "auth_protocol": "MD5",
                "priv_protocol": "DES",
                "priv_password": "priv_pass",
            },
            "env.yaml": {
                "host": "127.0.0.1",
                "port": 8080,
            },
            "bkmonitorbeat_debug.yaml": {
                "host": "127.0.0.1",
                "port": 8080,
                "period": 300,
                "target_nodes": ["127.0.0.2", "127.0.0.3"],
                "metric_url": "127.0.0.1:8080/snmp?target=",
            },
        }

        assert debug_context == expected_debug_context, f"调试配置上下文不匹配: {debug_context}"

    def test_get_deploy_steps_params(self):
        """测试获取部署步骤参数"""
        collect_params = {
            "host": "127.0.0.1",
            "port": 8080,
            "snmp_port": 161,
            "period": 300,
            "timeout": 30,
        }
        plugin_params = {
            "community": "public",
        }
        target_nodes = [{"ip": "127.0.0.2"}, {"ip": "127.0.0.3"}]

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=target_nodes,
        )

        expected_steps_params = [
            # 配置文件下发
            {
                "id": "test_snmp_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "test_snmp_plugin",
                    "plugin_version": "1.0",
                    "config_templates": [
                        {"name": "config.yaml", "version": "1"},
                        {"name": "env.yaml", "version": "1"},
                    ],
                },
                "params": {
                    "context": {
                        "community": "public",
                        "security_level": "",
                        "context_name": "",
                        "username": "",
                        "password": "",
                        "auth_protocol": "",
                        "priv_protocol": "",
                        "priv_password": "",
                        "host": "127.0.0.1",
                        "port": 8080,
                    }
                },
            },
            # bkmonitorbeat子配置文件
            {
                "id": "test_snmp_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_prometheus_remote.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "host": "127.0.0.1",
                        "port": 8080,
                        "snmp_port": 161,
                        "tasks": [
                            {
                                "task_id": "2",
                                "bk_biz_id": "1",
                                "dataid": 3,
                                "period": "300",
                                "timeout": "30",
                                "metric_url": "127.0.0.1:8080/snmp?target=127.0.0.2:161",
                                "config_name": "test_snmp_plugin",
                                "diff_metrics": [],
                                "labels": {
                                    "$for": "cmdb_instance.scope",
                                    "$item": "scope",
                                    "$body": {
                                        "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                        "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                        "bk_target_cloud_id": (
                                            "{{ cmdb_instance.host.bk_cloud_id[0].id "
                                            "if cmdb_instance.host.bk_cloud_id is iterable and "
                                            "cmdb_instance.host.bk_cloud_id is not string "
                                            "else cmdb_instance.host.bk_cloud_id }}"
                                        ),
                                        "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                        "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                        "bk_target_service_category_id": (
                                            "{{ cmdb_instance.service.service_category_id | default('', true) }}"
                                        ),
                                        "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                        "bk_collect_config_id": 2,
                                        "bk_target_device_ip": "127.0.0.2",
                                    },
                                },
                            },
                            {
                                "task_id": "2",
                                "bk_biz_id": "1",
                                "dataid": 3,
                                "period": "300",
                                "timeout": "30",
                                "metric_url": "127.0.0.1:8080/snmp?target=127.0.0.3:161",
                                "config_name": "test_snmp_plugin",
                                "diff_metrics": [],
                                "labels": {
                                    "$for": "cmdb_instance.scope",
                                    "$item": "scope",
                                    "$body": {
                                        "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                        "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                        "bk_target_cloud_id": (
                                            "{{ cmdb_instance.host.bk_cloud_id[0].id "
                                            "if cmdb_instance.host.bk_cloud_id is iterable and "
                                            "cmdb_instance.host.bk_cloud_id is not string "
                                            "else cmdb_instance.host.bk_cloud_id }}"
                                        ),
                                        "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                        "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                        "bk_target_service_category_id": (
                                            "{{ cmdb_instance.service.service_category_id | default('', true) }}"
                                        ),
                                        "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                        "bk_collect_config_id": 2,
                                        "bk_target_device_ip": "127.0.0.3",
                                    },
                                },
                            },
                        ],
                        "config_version": "1.0",
                        "namespace": "test_snmp_plugin",
                        "max_timeout": "30",
                    }
                },
            },
        ]

        assert steps_params == expected_steps_params
