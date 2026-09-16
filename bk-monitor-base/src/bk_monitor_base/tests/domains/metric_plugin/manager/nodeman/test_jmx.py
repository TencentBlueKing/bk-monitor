import json
import shutil
from pathlib import Path

import pytest

from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import OSTypeToPluginDirName
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.jmx import JMXPluginManager


class TestJMXPluginManager:
    """测试 JMXPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="JMX",
            name="测试jmx插件",
            description_md="测试jmx插件文档",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={
                "config_yaml": "username: {{ username }}\npassword: {{ password }}\njmxUrl: {{ jmx_url }}\nssl: false\n"
                "startDelaySeconds: 0\nlowercaseOutputName: true\nlowercaseOutputLabelNames: true\n"
                'whitelistObjectNames: ["java.lang:*"]\n',
                "diff_fields": "metric1,metric2,metric3",
            },
            params=[
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="host",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="监听IP",
                    default="127.0.0.1",
                    required=False,
                    visible=False,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="port",
                    alias="监听端口",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="",
                    default="8888",
                    required=False,
                    visible=True,
                ),
                # TEXT + OPT_CMD
                MetricPluginParams(
                    name="jmx_url",
                    alias="连接字符串",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.OPT_CMD,
                    description="",
                    default="",
                    required=False,
                    visible=True,
                ),
                # TEXT + OPT_CMD
                MetricPluginParams(
                    name="username",
                    alias="用户名",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.OPT_CMD,
                    description="",
                    default="",
                    required=False,
                    visible=True,
                ),
                # PASSWORD + OPT_CMD
                MetricPluginParams(
                    name="password",
                    alias="密码",
                    type=NodemanPluginParamsType.PASSWORD,
                    mode=NodemanPluginParamsMode.OPT_CMD,
                    description="",
                    default="",
                    required=False,
                    visible=True,
                ),
                # TEXT + COLLECTOR (SSL)
                MetricPluginParams(
                    name="ssl_enabled",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="启用SSL",
                    default="false",
                    required=False,
                    visible=False,
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="test_metric",
                    fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = JMXPluginManager(self.plugin)

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
                            "name": "metric1",
                            "source_name": "",
                            "type": "double",
                            "unit": "none",
                        }
                    ],
                    "rules": [],
                    "table_desc": "",
                    "table_name": "test_metric",
                }
            ],
            "plugin_id": "test_plugin",
            "plugin_display_name": "测试jmx插件",
            "version": "1.0",
            "config_version": 1,
            "plugin_type": "JMX",
            "port_range": "8888,10000-65535",
            "tag": "",
            "label": "",
            "description_md": "测试jmx插件文档",
            "config_json": [
                {
                    "alias": "",
                    "default": "127.0.0.1",
                    "description": "监听IP",
                    "election": [],
                    "file_base64": "",
                    "mode": "collector",
                    "name": "host",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": False,
                },
                {
                    "alias": "监听端口",
                    "default": "8888",
                    "description": "",
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
                    "alias": "连接字符串",
                    "default": "",
                    "description": "",
                    "election": [],
                    "file_base64": "",
                    "mode": "opt_cmd",
                    "name": "jmx_url",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": True,
                },
                {
                    "alias": "用户名",
                    "default": "",
                    "description": "",
                    "election": [],
                    "file_base64": "",
                    "mode": "opt_cmd",
                    "name": "username",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": True,
                },
                {
                    "alias": "密码",
                    "default": "",
                    "description": "",
                    "election": [],
                    "file_base64": "",
                    "mode": "opt_cmd",
                    "name": "password",
                    "options": {},
                    "required": False,
                    "type": "password",
                    "visible": True,
                },
                {
                    "alias": "",
                    "default": "false",
                    "description": "启用SSL",
                    "election": [],
                    "file_base64": "",
                    "mode": "collector",
                    "name": "ssl_enabled",
                    "options": {},
                    "required": False,
                    "type": "text",
                    "visible": False,
                },
            ],
            "collector_json": {
                "config_yaml": "username: {{ username }}\npassword: {{ password }}\njmxUrl: {{ jmx_url }}\nssl: false\n"
                "startDelaySeconds: 0\nlowercaseOutputName: true\nlowercaseOutputLabelNames: true\n"
                'whitelistObjectNames: ["java.lang:*"]\n',
                "diff_fields": "metric1,metric2,metric3",
            },
            "signature": "",
            "is_support_remote": False,
            "version_log": "",
        }

        assert package_context == expected_package_context

    def test_make_package(self):
        """测试制作插件包"""

        package_dir = self.plugin_manager.make_package(is_compress=True)
        # 检查插件压缩包
        assert package_dir.exists() and package_dir.is_file()

        # 检查插件目录
        for os_type in self.plugin_manager.get_supported_os_types():
            plugin_dir = package_dir.parent / "test_plugin" / OSTypeToPluginDirName[os_type] / "test_plugin"
            assert plugin_dir.exists() and plugin_dir.is_dir()

            assert (plugin_dir / "etc" / "config.yaml.tpl").read_text(encoding="utf-8") == self.plugin.define[
                "config_yaml"
            ]
            assert (plugin_dir / "info" / "description.md").read_text(encoding="utf-8") == "测试jmx插件文档"
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
            "host": "http://test.com",
            "port": "10001",
        }
        plugin_params = {
            "jmx_url": "http://test.com:10001",
            "username": "test_user",
            "password": "test_password",
            "ssl_enabled": "true",
            "ssl_trust_store": "truststore.jks",
            "ssl_trust_store_password": "trust_password",
            "ssl_key_store": "keystore.jks",
            "ssl_key_store_password": "key_password",
        }

        # 测试_get_debug_config_context方法
        debug_context = self.plugin_manager._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params.copy(),
            target_nodes=[],
        )

        expected_debug_context = {
            "config.yaml": {
                "username": "test_user",
                "password": "test_password",
                "jmx_url": "http://test.com:10001",
                "ssl_enabled": "true",
            },
            "env.yaml": {
                "host": "http://test.com",
                "port": "10001",
                "ssl_enabled": "true",
                "ssl_trust_store": "truststore.jks",
                "ssl_trust_store_password": "trust_password",
                "ssl_key_store": "keystore.jks",
                "ssl_key_store_password": "key_password",
            },
            "bkmonitorbeat_debug.yaml": {
                "host": "http://test.com",
                "port": "10001",
                "period": 300,
                "metric_url": "http://test.com:10001",
            },
        }

        # 校验调试配置上下文结果
        assert debug_context == expected_debug_context, f"调试配置上下文不匹配: {debug_context}"

    def test_parse_define_success(self, tmp_path: Path):
        """测试 _parse_define 方法 - 保留带占位符的 config.yaml.tpl 原文"""
        plugin_id = "test_jmx_plugin"
        extract_dir = tmp_path / "extract"
        config_yaml_tpl = extract_dir / OSTypeToPluginDirName[OSType.LINUX] / plugin_id / "etc" / "config.yaml.tpl"
        config_yaml_tpl.parent.mkdir(parents=True)
        config_yaml_content = (
            "username: {{ username }}\n"
            "password: {{ password }}\n"
            "jmx_url: {{ jmx_url }}\n"
            "ssl_enabled: {{ ssl_enabled }}\n"
            "startDelaySeconds: 0\n"
            "rules: []\n"
        )
        config_yaml_tpl.write_text(config_yaml_content, encoding="utf-8")

        result = JMXPluginManager._parse_define(
            bk_tenant_id="test_tenant",
            operator="admin",
            extract_dir=extract_dir,
            plugin_id=plugin_id,
            meta_data={"plugin_id": plugin_id, "plugin_type": "JMX"},
        )

        assert result == {"config_yaml": config_yaml_content}

    def test_get_deploy_steps_params(self):
        """测试获取部署步骤参数"""
        collect_params = {
            "period": 300,
            "host": "http://test.com",
            "port": "10001",
        }
        plugin_params = {
            "jmx_url": "http://test.com:10001",
            "username": "test_user",
            "password": "test_password",
            "ssl_enabled": "true",
            "ssl_trust_store": "truststore.jks",
            "ssl_trust_store_password": "trust_password",
            "ssl_key_store": "keystore.jks",
            "ssl_key_store_password": "key_password",
        }

        steps_params = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=1,
            collect_task_id=2,
            bk_data_ids={"bk_data_id": 3},
            collect_params=collect_params,
            plugin_params=plugin_params.copy(),
            target_nodes=[{"host_ip": "127.0.0.1"}],
        )

        expected_steps_params = [
            {
                "id": "test_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "test_plugin",
                    "plugin_version": "1.0",
                    "config_templates": [
                        {"name": "config.yaml", "version": "1"},
                        {"name": "env.yaml", "version": "1"},
                    ],
                },
                "params": {
                    "context": {
                        "username": "test_user",
                        "password": "test_password",
                        "jmx_url": "http://test.com:10001",
                        "host": "http://test.com",
                        "port": "10001",
                        "ssl_enabled": "true",
                        "ssl_trust_store": "truststore.jks",
                        "ssl_trust_store_password": "trust_password",
                        "ssl_key_store": "keystore.jks",
                        "ssl_key_store_password": "key_password",
                    }
                },
            },
            {
                "id": "bkmonitorbeat",
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
                            },
                        },
                        "host": "http://test.com",
                        "port": "10001",
                        "metric_url": "http://test.com:10001",
                        "diff_metrics": ["metric1", "metric2", "metric3"],
                    }
                },
            },
        ]
        assert steps_params == expected_steps_params
