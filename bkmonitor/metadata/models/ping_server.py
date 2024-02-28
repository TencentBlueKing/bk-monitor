# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
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
from core.drf_resource import api

logger = logging.getLogger("metadata")

DEFAULT_DATA_REPORT_INTERVAL = 60  # 数据上报周期，单位: 秒
DEFAULT_EXEC_TOTAL_NUM = 3  # 单个周期内执行的ping次数
DEFAULT_MAX_BATCH_SIZE = 20  # 单次最多同时ping的IP数量，默认20，尽可能的单次少一点ip，避免瞬间包量太多，导致网卡直接丢包
DEFAULT_PING_SIZE = 16  # ping的大小  默认16个字节
DEFAULT_PING_TIMEOUT = 3  # ping的rtt  默认3秒


class PingServerSubscriptionConfig(models.Model):
    """Ping Server  订阅配置"""

    subscription_id = models.IntegerField("节点管理订阅ID", primary_key=True)
    bk_cloud_id = models.IntegerField(verbose_name="云区域ID")
    ip = models.CharField(verbose_name="IP地址", default="", blank=True, max_length=32)
    bk_host_id = models.IntegerField(verbose_name="主机ID", default=None, null=True, db_index=True)
    config = JsonField(verbose_name="订阅配置")
    plugin_name = models.CharField(verbose_name="插件名称", default="bkmonitorproxy", max_length=32)

    class Meta:
        verbose_name = "PingServer下发订阅配置"
        verbose_name_plural = "PingServer下发订阅配置"
        unique_together = (("bk_host_id", "bk_cloud_id", "ip", "plugin_name"),)

    @classmethod
    def create_subscription(cls, bk_cloud_id, items, target_hosts, plugin_name):
        logger.info(
            "update or create ping server subscription task, bk_cloud_id(%s), target_hosts(%s), plugin(%s)",
            bk_cloud_id,
            target_hosts,
            plugin_name,
        )
        configs = PingServerSubscriptionConfig.objects.filter(bk_cloud_id=bk_cloud_id, plugin_name=plugin_name)
        config_ips = [config.ip for config in configs if not config.bk_host_id and config.ip]
        ip_hosts = api.cmdb.get_host_without_biz(ips=config_ips, bk_cloud_ids=[bk_cloud_id])["hosts"]
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
            bk_biz_id = host["bk_biz_id"]
            ip = host["ipv6"] if is_ipv6_biz(bk_biz_id) else host["ip"]
            scope = {"object_type": "HOST", "node_type": "INSTANCE", "nodes": [{"bk_host_id": bk_host_id}]}
            # 当bk-collector暂未升级时，使用proxy旧版参数下发，ip作为key
            # bk-collector升级后将使用collector新版参数下发，host_id作为key
            ip_to_items = {bk_host_id: items[bk_host_id]} if plugin_name == "bk-collector" else {ip: items[bk_host_id]}
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
                                "dataid": settings.PING_SERVER_DATAID,
                                "period": DEFAULT_DATA_REPORT_INTERVAL,
                                "total_num": DEFAULT_EXEC_TOTAL_NUM,
                                "max_batch_size": DEFAULT_MAX_BATCH_SIZE,
                                "ping_size": DEFAULT_PING_SIZE,
                                "ping_timeout": DEFAULT_PING_TIMEOUT,
                                "server_ip": "{{ cmdb_instance.host.bk_host_innerip_v6 }}"
                                if is_ipv6_biz(bk_biz_id)
                                else "{{ cmdb_instance.host.bk_host_innerip }}",
                                "server_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "server_cloud_id": bk_cloud_id,
                                "ip_to_items": ip_to_items,
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

            if config:
                try:
                    logger.info(f"ping server subscription task(ip:{ip}, host_id: {bk_host_id}) already exists.")
                    subscription_params["subscription_id"] = config.subscription_id
                    subscription_params["run_immediately"] = True

                    old_subscription_params_md5 = count_md5(config.config)
                    new_subscription_params_md5 = count_md5(subscription_params)
                    if old_subscription_params_md5 != new_subscription_params_md5:
                        logger.info("ping server subscription task config has changed, update it.")
                        result = api.node_man.update_subscription(subscription_params)
                        logger.info("update ping server subscription successful, result:{}".format(result))
                        config.config = subscription_params
                        config.save()
                        # A1：目标 - 确保每次更新时都会主动触发一次订阅执行
                        # Q：为什么去掉执行订阅的逻辑
                        # A2：run_immediately=True 时更新订阅会「同时触发订阅执行」，如果订阅此刻在执行中便会失败
                        # A3：更新订阅失败 - 最新配置不保存，下个周期对比差异恒定成功，会继续触发订阅更新和执行
                        # A4：更新订阅成功 - 最新配置保存，符合预期
                        # A5：综上 run_subscription 的调用是冗余且恒定失败的，由此移除
                        # api.node_man.run_subscription(subscription_id=config.subscription_id)
                except Exception as e:  # noqa
                    logger.exception(
                        "update ping server subscription error:{}, params:{}".format(e, subscription_params)
                    )
            else:
                try:
                    logger.info("ping server subscription task not exists, create it.")
                    result = api.node_man.create_subscription(subscription_params)
                    logger.info("create ping server subscription successful, result:{}".format(result))

                    # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                    subscription_id = result["subscription_id"]
                    PingServerSubscriptionConfig.objects.create(
                        bk_cloud_id=bk_cloud_id,
                        bk_host_id=bk_host_id,
                        config=subscription_params,
                        ip=ip,
                        subscription_id=subscription_id,
                        plugin_name=plugin_name,
                    )

                    result = api.node_man.run_subscription(
                        subscription_id=subscription_id, actions={plugin_name: "INSTALL"}
                    )
                    logger.info("run ping server subscription result:{}".format(result))
                except Exception as e:  # noqa
                    logger.exception(
                        "create ping server subscription error{}, params:{}".format(e, subscription_params)
                    )

        # 停用未使用的节点
        for host_id, config in host_configs.items():
            if config.config.get("status") == "STOP":
                continue

            api.node_man.switch_subscription(subscription_id=config.subscription_id, action="disable")
            result = api.node_man.run_subscription(
                subscription_id=config.subscription_id, actions={plugin_name: "STOP"}
            )
            config.config["status"] = "STOP"
            config.save()
            logger.info(
                "stop ping server({}) subscription({}) result:{}".format(host_id, config.subscription_id, result)
            )
