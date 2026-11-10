"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.conf import settings
from django.db import models

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.db import JsonField
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models.bk_collector import BkCollectorDeployPolicy, BkCollectorDeployScene

logger = logging.getLogger("metadata")

DEFAULT_DATA_REPORT_INTERVAL = 60  # 数据上报周期，单位: 秒
DEFAULT_EXEC_TOTAL_NUM = 3  # 单个周期内执行的ping次数
DEFAULT_MAX_BATCH_SIZE = (
    20  # 单次最多同时ping的IP数量，默认20，尽可能的单次少一点ip，避免瞬间包量太多，导致网卡直接丢包
)
DEFAULT_PING_SIZE = 16  # ping的大小  默认16个字节
DEFAULT_PING_TIMEOUT = 3  # ping的rtt  默认3秒
PING_SERVER_CONFIG_TEMPLATE_NAME = "bkmonitorproxy_ping.conf"


class PingServerSubscriptionConfig(models.Model):
    """Ping Server  订阅配置"""

    bk_tenant_id = models.CharField(verbose_name="租户ID", default=DEFAULT_TENANT_ID, max_length=128)
    subscription_id = models.IntegerField("节点管理订阅ID", primary_key=True)
    bk_cloud_id = models.IntegerField(verbose_name="云区域ID")
    ip = models.CharField(verbose_name="IP地址", default="", blank=True, max_length=32)
    bk_host_id = models.IntegerField(verbose_name="主机ID", default=None, null=True, db_index=True)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, db_index=True)
    config = JsonField(verbose_name="订阅配置")
    plugin_name = models.CharField(verbose_name="插件名称", default="bkmonitorproxy", max_length=32)

    class Meta:
        verbose_name = "PingServer下发订阅配置"
        verbose_name_plural = "PingServer下发订阅配置"
        unique_together = (("bk_host_id", "bk_cloud_id", "ip", "plugin_name", "bk_tenant_id", "bk_biz_id"),)

    @classmethod
    def create_subscription(
        cls,
        bk_tenant_id: str,
        bk_cloud_id: int,
        items,
        target_hosts,
        plugin_name: str,
        bk_biz_id: int | None = None,
        bk_data_id: int | None = None,
    ):
        """
        创建或更新PingServer订阅配置
        :param bk_tenant_id: 租户ID
        :param bk_cloud_id: 云区域ID
        :param items: 订阅配置
        :param target_hosts: 目标主机列表
        :param plugin_name: 插件名称
        :param bk_biz_id: 多租户目标业务ID，单租户为空时使用Proxy所属业务刷新记录
        :param bk_data_id: Ping Server 上报 DataID，单租户默认使用 settings.PING_SERVER_DATAID
        """
        bk_data_id = bk_data_id or settings.PING_SERVER_DATAID
        logger.info(
            "update or create ping server subscription task, bk_cloud_id(%s), target_hosts(%s), plugin(%s), "
            "bk_biz_id(%s), bk_data_id(%s)",
            bk_cloud_id,
            target_hosts,
            plugin_name,
            bk_biz_id,
            bk_data_id,
        )
        if plugin_name == BkCollectorDeployPolicy.PLUGIN_NAME and BkCollectorDeployPolicy.is_enabled():
            cls.create_deploy_policies(
                bk_tenant_id=bk_tenant_id,
                bk_cloud_id=bk_cloud_id,
                items=items,
                target_hosts=target_hosts,
                bk_biz_id=bk_biz_id,
                bk_data_id=bk_data_id,
            )
            return
        configs = PingServerSubscriptionConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id, plugin_name=plugin_name
        )
        if bk_biz_id is not None:
            configs = configs.filter(bk_biz_id=bk_biz_id)
        config_ips = [config.ip for config in configs if not config.bk_host_id and config.ip]
        ip_hosts = api.cmdb.get_host_without_biz(bk_tenant_id=bk_tenant_id, ips=config_ips, bk_cloud_ids=[bk_cloud_id])[
            "hosts"
        ]
        ip_to_id = {h["bk_host_innerip"]: h["bk_host_id"] for h in ip_hosts}
        host_configs = {}
        for config in configs:
            if config.bk_host_id:
                host_configs[config.bk_host_id] = config
            elif config.ip:
                # 存量pingserver订阅配置如果相关ip已无对应主机实例id，则使用ip作为config键值进行管理
                host_key = ip_to_id.get(config.ip, config.ip)
                host_configs[host_key] = config

        for host in target_hosts:
            bk_host_id = host["bk_host_id"]
            proxy_bk_biz_id = host["bk_biz_id"]
            record_bk_biz_id = bk_biz_id if bk_biz_id is not None else proxy_bk_biz_id
            ip = host["ipv6"] if is_ipv6_biz(proxy_bk_biz_id) else host["ip"]
            scope = {"object_type": "HOST", "node_type": "INSTANCE", "nodes": [{"bk_host_id": bk_host_id}]}
            subscription_params = {
                "scope": scope,
                "steps": [
                    {
                        "id": plugin_name,
                        "type": "PLUGIN",
                        "config": {
                            "plugin_name": plugin_name,
                            "plugin_version": "latest",
                            "config_templates": [{"name": "bkmonitorproxy_ping.conf", "version": "latest"}],
                        },
                        "params": {
                            "context": {
                                "dataid": bk_data_id,
                                "period": DEFAULT_DATA_REPORT_INTERVAL,
                                "total_num": DEFAULT_EXEC_TOTAL_NUM,
                                "max_batch_size": DEFAULT_MAX_BATCH_SIZE,
                                "ping_size": DEFAULT_PING_SIZE,
                                "ping_timeout": DEFAULT_PING_TIMEOUT,
                                "server_ip": "{{ cmdb_instance.host.bk_host_innerip_v6 }}"
                                if is_ipv6_biz(proxy_bk_biz_id)
                                else "{{ cmdb_instance.host.bk_host_innerip }}",
                                "server_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "server_cloud_id": bk_cloud_id,
                                "ip_to_items": {bk_host_id: items.get(bk_host_id, [])},
                            }
                        },
                    }
                ],
            }

            config = (
                host_configs.pop(bk_host_id, None) or host_configs.pop(ip, None) or host_configs.pop(host["ip"], None)
            )
            if config and not config.bk_host_id:
                config.bk_host_id = bk_host_id
                config.save()
            if config and config.bk_biz_id != record_bk_biz_id:
                config.bk_biz_id = record_bk_biz_id
                config.save(update_fields=["bk_biz_id"])

            if config:
                try:
                    logger.info(f"ping server subscription task(ip:{ip}, host_id: {bk_host_id}) already exists.")
                    subscription_params["subscription_id"] = config.subscription_id
                    subscription_params["run_immediately"] = True

                    old_subscription_params_md5 = count_md5(config.config)
                    new_subscription_params_md5 = count_md5(subscription_params)
                    if old_subscription_params_md5 != new_subscription_params_md5:
                        logger.info("ping server subscription task config has changed, update it.")
                        result = api.node_man.update_subscription(bk_tenant_id=bk_tenant_id, **subscription_params)
                        logger.info(f"update ping server subscription successful, result:{result}")
                        config.config = subscription_params
                        config.save()
                        api.node_man.switch_subscription(
                            bk_tenant_id=bk_tenant_id, subscription_id=config.subscription_id, action="enable"
                        )
                except Exception as e:  # noqa
                    logger.exception(f"update ping server subscription error:{e}, params:{subscription_params}")
            else:
                try:
                    logger.info("ping server subscription task not exists, create it.")
                    result = api.node_man.create_subscription(bk_tenant_id=bk_tenant_id, **subscription_params)
                    logger.info(f"create ping server subscription successful, result:{result}")

                    # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                    subscription_id = result["subscription_id"]
                    PingServerSubscriptionConfig.objects.create(
                        bk_tenant_id=bk_tenant_id,
                        bk_cloud_id=bk_cloud_id,
                        bk_biz_id=record_bk_biz_id,
                        bk_host_id=bk_host_id,
                        config=subscription_params,
                        ip=ip,
                        subscription_id=subscription_id,
                        plugin_name=plugin_name,
                    )

                    result = api.node_man.run_subscription(
                        bk_tenant_id=bk_tenant_id, subscription_id=subscription_id, actions={plugin_name: "INSTALL"}
                    )
                    api.node_man.switch_subscription(
                        bk_tenant_id=bk_tenant_id, subscription_id=subscription_id, action="enable"
                    )
                    logger.info(f"run ping server subscription result:{result}")
                except Exception as e:  # noqa
                    logger.exception(f"create ping server subscription error{e}, params:{subscription_params}")

        # 停用未使用的节点
        for host_id, config in host_configs.items():
            if config.config.get("status") == "STOP":
                continue

            api.node_man.switch_subscription(
                bk_tenant_id=bk_tenant_id, subscription_id=config.subscription_id, action="disable"
            )
            result = api.node_man.run_subscription(
                bk_tenant_id=bk_tenant_id, subscription_id=config.subscription_id, actions={plugin_name: "STOP"}
            )
            config.config["status"] = "STOP"
            config.save()
            logger.info(f"stop ping server({host_id}) subscription({config.subscription_id}) result:{result}")

    @staticmethod
    def build_context(bk_data_id: int, bk_cloud_id: int, bk_host_id: int, proxy_bk_biz_id: int, items) -> dict:
        """V3 部署策略的 PingServer 渲染上下文，与 V2 订阅 params.context 保持一致"""
        return {
            "dataid": bk_data_id,
            "period": DEFAULT_DATA_REPORT_INTERVAL,
            "total_num": DEFAULT_EXEC_TOTAL_NUM,
            "max_batch_size": DEFAULT_MAX_BATCH_SIZE,
            "ping_size": DEFAULT_PING_SIZE,
            "ping_timeout": DEFAULT_PING_TIMEOUT,
            # 依赖节点管理对上下文中的主机变量做二次渲染，V3 需节点管理支持后才能生效
            "server_ip": "{{ cmdb_instance.host.bk_host_innerip_v6 }}"
            if is_ipv6_biz(proxy_bk_biz_id)
            else "{{ cmdb_instance.host.bk_host_innerip }}",
            "server_host_id": "{{ cmdb_instance.host.bk_host_id }}",
            "server_cloud_id": bk_cloud_id,
            "ip_to_items": {bk_host_id: items.get(bk_host_id, [])},
        }

    @staticmethod
    def build_policy_resource_key(bk_cloud_id: int, bk_host_id: int, bk_biz_id: int | None = None) -> str:
        # 多租户按目标业务拆分，同一台 Proxy 可能对应多份配置
        if bk_biz_id is None:
            return f"cloud{bk_cloud_id}-host{bk_host_id}"
        return f"biz{bk_biz_id}-cloud{bk_cloud_id}-host{bk_host_id}"

    @classmethod
    def create_deploy_policies(
        cls,
        bk_tenant_id: str,
        bk_cloud_id: int,
        items,
        target_hosts,
        bk_biz_id: int | None,
        bk_data_id: int,
    ):
        """
        bk-collector 走节点管理 V3 部署策略下发 PingServer 配置

        与 V2 一致每台 Proxy 一份配置；不再使用的 Proxy 清空策略范围，由节点管理删除该子配置，
        不像 V2 那样停止插件（bk-collector 还承载其他子配置）。
        """
        policies = BkCollectorDeployPolicy.objects.filter(
            bk_tenant_id=bk_tenant_id, scene=BkCollectorDeployScene.PING_SERVER, bk_cloud_id=bk_cloud_id
        )
        if bk_biz_id is not None:
            policies = policies.filter(bk_biz_id=bk_biz_id)
        unused_policies = {policy.resource_key: policy for policy in policies}

        for host in target_hosts:
            bk_host_id = host["bk_host_id"]
            proxy_bk_biz_id = host["bk_biz_id"]
            resource_key = cls.build_policy_resource_key(bk_cloud_id, bk_host_id, bk_biz_id)
            unused_policies.pop(resource_key, None)
            try:
                BkCollectorDeployPolicy.deploy(
                    bk_tenant_id=bk_tenant_id,
                    scene=BkCollectorDeployScene.PING_SERVER,
                    resource_key=resource_key,
                    template_name=PING_SERVER_CONFIG_TEMPLATE_NAME,
                    context=cls.build_context(bk_data_id, bk_cloud_id, bk_host_id, proxy_bk_biz_id, items),
                    bk_host_ids=[bk_host_id],
                    bk_biz_id=bk_biz_id if bk_biz_id is not None else proxy_bk_biz_id,
                    bk_cloud_id=bk_cloud_id,
                )
            except Exception as e:  # noqa
                logger.exception(f"deploy ping server config by nodeman v3 error: {e}, host_id: {bk_host_id}")

        for resource_key, policy in unused_policies.items():
            try:
                policy.withdraw()
                logger.info(f"withdraw ping server deploy policy({policy.deploy_policy_id}) of {resource_key}")
            except Exception as e:  # noqa
                logger.exception(f"withdraw ping server deploy policy of {resource_key} error: {e}")
