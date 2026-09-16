"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.snmp_trap import SNMPTrapPluginManager


class TestSNMPTrapPluginManager:
    """测试 SNMPTrapPluginManager 类"""

    def setup_method(self):
        """设置测试数据"""
        self.plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_snmp_trap_plugin",
            type="snmp_trap",
            name="测试SNMP Trap插件",
            description_md="测试SNMP Trap插件",
            version=VersionTuple(1, 0),
            status=MetricPluginStatus.DEBUG,
            created_by="admin",
            updated_by="admin",
            define={},
            params=[
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="community",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="团体名",
                    default="",
                    required=False,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="listen_ip",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="绑定地址",
                    default="0.0.0.0",
                    required=False,
                ),
                # TEXT + COLLECTOR
                MetricPluginParams(
                    name="server_port",
                    type=NodemanPluginParamsType.TEXT,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="Trap服务端口",
                    default="162",
                    required=False,
                ),
                # FILE + COLLECTOR
                MetricPluginParams(
                    name="Yaml配置文件",
                    type=NodemanPluginParamsType.FILE,
                    mode=NodemanPluginParamsMode.COLLECTOR,
                    description="Yaml配置文件",
                    default="",
                    required=True,
                ),
            ],
            metrics=[
                MetricPluginMetricGroup(
                    table_name="snmptrap_metric",
                    fields=[MetricPluginMetricField(name="test_metric1", type="double", monitor_type="metric")],
                )
            ],
        )
        self.plugin_manager = SNMPTrapPluginManager(self.plugin)

    def test_get_target(self):
        """测试获取目标标识"""
        # 测试SERVICE类型
        service_target = self.plugin_manager._get_target("SERVICE")
        assert service_target == "{{ cmdb_instance.service.id }}"

        # 测试其他类型
        host_target = self.plugin_manager._get_target("HOST")
        expected_host_target = (
            "{{ '{}:{}'.format(cmdb_instance.host.bk_cloud_id[0].id, cmdb_instance.host.bk_host_innerip) "
            "if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string "
            "else '{}:{}'.format(cmdb_instance.host.bk_cloud_id, cmdb_instance.host.bk_host_innerip) }}"
        )
        assert host_target == expected_host_target

    def test_get_deploy_steps_params(self):
        """测试获取部署步骤参数"""
        bk_biz_id = 1
        collect_task_id = 2
        bk_data_ids = {"bk_data_id": 3}
        collect_params = {
            "period": 300,
            "timeout": 30,
            "labels": "component",
            "target_object_type": "SERVICE",
        }

        #  1. 测试v1版本(v1和v2版本的认证只有一个字段，即community)
        plugin_params_v1 = {
            "community": "public",
            "listen_ip": "0.0.0.0",
            "server_port": 162,
            "version": "v1",
            "aggregate": True,
            "yaml": {
                "value": """snmptrap: {metrics: [{name: snmpTrapOID, oid: 1.3.6.1.6.3.1.1.4.1.0, type: gauge, help: "SNMP Trap OID"}], report_oid_dimensions: [1.3.6.1.6.3.1.1.4.1.0], raw_byte_oids: [1.3.6.1.2.1.1.3.0], encode: utf-8, hide_agent_port: false}"""
            },
        }

        steps_params_v1 = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=bk_biz_id,
            collect_task_id=collect_task_id,
            bk_data_ids=bk_data_ids,
            collect_params=collect_params,
            plugin_params=plugin_params_v1,
        )

        expected_steps_params_v1 = [
            # bkmonitorbeat子配置文件
            {
                "id": "test_snmp_trap_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_snmptrap.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "tasks": [
                            {
                                "task_id": "2",
                                "bk_biz_id": "1",
                                "dataid": 3,
                                "community": "public",
                                "listen_ip": "0.0.0.0",
                                "listen_port": 162,
                                "snmp_version": "v1",
                                "aggregate": True,
                                "period": "300s",
                                "oids": {"1.3.6.1.6.3.1.1.4.1.0": "snmpTrapOID"},
                                "report_oid_dimensions": ["1.3.6.1.6.3.1.1.4.1.0"],
                                "raw_byte_oids": ["1.3.6.1.2.1.1.3.0"],
                                "use_display_name_oid": False,
                                "encode": "utf-8",
                                "hide_agent_port": False,
                                "usm_info": [
                                    {
                                        "context_name": "",
                                        "msg_flags": "noAuthNoPriv",
                                        "usm_config": {
                                            "username": "",
                                            "authentication_protocol": "MD5",
                                            "authentication_passphrase": "",
                                            "privacy_protocol": "DES",
                                            "privacy_passphrase": "",
                                            "authoritative_engineID": "",
                                            "authoritative_engineboots": 1,
                                            "authoritative_enginetime": 1,
                                        },
                                    }
                                ],
                                "labels": "component",
                                "target": "{{ cmdb_instance.service.id }}",
                            }
                        ],
                    }
                },
            },
        ]

        assert steps_params_v1 == expected_steps_params_v1

        #  2. 测试v3版本(认证相对复杂，增加了一系列安全参数, 详见参数usm_info，可以有多个认证)
        plugin_params_v1 = {
            "community": "public",
            "listen_ip": "0.0.0.0",
            "server_port": 162,
            "version": "v3",
            "aggregate": True,
            "yaml": {
                "value": """snmptrap: {metrics: [{name: snmpTrapOID, oid: 1.3.6.1.6.3.1.1.4.1.0, type: gauge, help: "SNMP Trap OID"}], report_oid_dimensions: [1.3.6.1.6.3.1.1.4.1.0], raw_byte_oids: [1.3.6.1.2.1.1.3.0], encode: utf-8, hide_agent_port: false}"""
            },
            "auth_info": [
                {
                    "security_level": "authPriv",
                    "security_name": "test_user",
                    "context_name": "test_context",
                    "authentication_protocol": "SHA",
                    "authentication_passphrase": "auth_pass",
                    "privacy_protocol": "AES",
                    "privacy_passphrase": "priv_pass",
                    "authoritative_engineID": "test_engine_id",
                }
            ],
        }

        steps_params_v3 = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=bk_biz_id,
            collect_task_id=collect_task_id,
            bk_data_ids=bk_data_ids,
            collect_params=collect_params,
            plugin_params=plugin_params_v1,
        )

        expected_steps_params_v3 = [
            # bkmonitorbeat子配置文件
            {
                "id": "test_snmp_trap_plugin",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_snmptrap.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "tasks": [
                            {
                                "task_id": "2",
                                "bk_biz_id": "1",
                                "dataid": 3,
                                "community": "public",
                                "listen_ip": "0.0.0.0",
                                "listen_port": 162,
                                "snmp_version": "v3",
                                "aggregate": True,
                                "period": "300s",
                                "oids": {"1.3.6.1.6.3.1.1.4.1.0": "snmpTrapOID"},
                                "report_oid_dimensions": ["1.3.6.1.6.3.1.1.4.1.0"],
                                "raw_byte_oids": ["1.3.6.1.2.1.1.3.0"],
                                "use_display_name_oid": False,
                                "encode": "utf-8",
                                "hide_agent_port": False,
                                "usm_info": [
                                    {
                                        "context_name": "test_context",
                                        "msg_flags": "authPriv",
                                        "usm_config": {
                                            "username": "test_user",
                                            "authentication_protocol": "SHA",
                                            "authentication_passphrase": "auth_pass",
                                            "privacy_protocol": "AES",
                                            "privacy_passphrase": "priv_pass",
                                            "authoritative_engineID": "test_engine_id",
                                            "authoritative_engineboots": 1,
                                            "authoritative_enginetime": 1,
                                        },
                                    }
                                ],
                                "labels": "component",
                                "target": "{{ cmdb_instance.service.id }}",
                            }
                        ],
                    }
                },
            },
        ]

        assert steps_params_v3 == expected_steps_params_v3
