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
from collections import defaultdict
from itertools import chain
from operator import methodcaller

from django.conf import settings
from django.db import models

from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.db.fields import JsonField
from core.drf_resource import api
from metadata.models.constants import LOG_REPORT_MAX_QPS

logger = logging.getLogger("metadata")

MAX_REQ_LENGTH = 500 * 1024  # 最大请求Body大小，500KB
MAX_REQ_THROUGHPUT = 4000  # 最大的请求数(单位：秒)
MAX_DATA_ID_THROUGHPUT = 1000  # 单个dataid最大的上报频率(条/min)、在bk-collector模式下，是 条/秒
MAX_FUTURE_TIME_OFFSET = 3600  # 支持的最大未来时间，超过这个偏移值，则丢弃


def get_proxy_host_ids(bk_host_ids):
    # 校验proxy插件状态
    all_plugin = api.node_man.plugin_search(
        {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
    )["list"]
    proxy_host_ids = []
    remove_host_ids = []
    for plugin in all_plugin:
        proxy_plugin = list(filter(lambda x: x["name"] == "bkmonitorproxy", plugin["plugin_status"]))
        # 如果 bkmonitorproxy 插件存在，且状态为未停用，则下发子配置文件
        if proxy_plugin and proxy_plugin[0].get("status", "") != "MANUAL_STOP":
            proxy_host_ids.append(plugin["bk_host_id"])
        else:
            remove_host_ids.append(plugin["bk_host_id"])
    if remove_host_ids:
        logger.info(f"target_hosts({remove_host_ids}): No bkmonitorproxy found or bkmonitorproxy status is MANUAL_STOP")
    return proxy_host_ids


class CustomReportSubscriptionConfig(models.Model):
    """自定义上报  订阅配置（已废弃）"""

    bk_biz_id = models.IntegerField(verbose_name="业务ID", primary_key=True)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)

    config = JsonField(verbose_name="订阅配置")

    class Meta:
        verbose_name = "自定义上报订阅配置"
        verbose_name_plural = "自定义上报订阅配置"


class CustomReportSubscription(models.Model):
    """自定义上报  订阅配置v2"""

    bk_biz_id = models.IntegerField(verbose_name="业务ID")
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    bk_data_id = models.IntegerField("数据ID", default=0)

    config = JsonField(verbose_name="订阅配置")

    class Meta:
        verbose_name = "自定义上报订阅配置v2"
        verbose_name_plural = "自定义上报订阅配置v2"
        unique_together = (("bk_biz_id", "bk_data_id"),)
        db_table = "custom_report_subscription_config_v2"

    @classmethod
    def create_subscription(cls, bk_biz_id, items, bk_host_ids, plugin_name, op_type="add"):

        available_host_ids = get_proxy_host_ids(bk_host_ids) if plugin_name == "bkmonitorproxy" else bk_host_ids

        if op_type != "remove" and not available_host_ids:
            # 目标主机 bkmonitorproxy 全部为手动停止或未部署时，暂不下发
            # 业务背景：bkmonitorproxy 的功能将被 bk-collector 取代，为了版本兼容目前采取两边下发的逻辑
            #         当 bkmonitorproxy 被停止或未部署时，说明 bkmonitorproxy 已下线，无需进行下发
            logger.info(
                "[custom_report] skipped because no available nodes: bk_biz_id(%s), plugin(%s)", bk_biz_id, plugin_name
            )
            return

        if op_type == "remove":
            # 使用 Proxy 插件卸除配置时，针对 Proxy 状态为手动停止的机器进行卸载
            bk_host_ids = available_host_ids

        logger.info(
            "update or create subscription task, bk_biz_id(%s), target_hosts(%s), plugin(%s)",
            bk_biz_id,
            bk_host_ids,
            plugin_name,
        )
        scope = {
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids],
        }
        if plugin_name == "bkmonitorproxy":
            subscription_params = {
                "scope": scope,
                "steps": [
                    {
                        "id": "bkmonitorproxy",
                        "type": "PLUGIN",
                        "config": {
                            "plugin_name": plugin_name,
                            "plugin_version": "latest",
                            "config_templates": [{"name": "bkmonitorproxy_report.conf", "version": "latest"}],
                        },
                        "params": {
                            "context": {
                                "listen_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                "listen_port": settings.BK_MONITOR_PROXY_LISTEN_PORT,
                                "max_length": MAX_REQ_LENGTH,
                                "max_throughput": MAX_REQ_THROUGHPUT,
                                "items": items,
                            }
                        },
                    }
                ],
            }
            return cls.create_or_update_config(subscription_params, bk_biz_id)
        for item in items:
            # bk-collector 默认自定义事件，和json的自定义指标使用bk-collector-report-v2.conf
            sub_config_name = "bk-collector-report-v2.conf"

            is_ts_item = isinstance(item, tuple)
            if is_ts_item:
                # 自定义指标，对应json和Prometheus 两种格式
                item, sub_config_name = item

            subscription_params = {
                "scope": scope,
                "steps": [
                    {
                        "id": plugin_name,
                        "type": "PLUGIN",
                        "config": {
                            "plugin_name": plugin_name,
                            "plugin_version": "latest",
                            "config_templates": [{"name": sub_config_name, "version": "latest"}],
                        },
                        "params": {"context": {"bk_biz_id": bk_biz_id, **item}},
                    },
                ],
            }

            cls.create_or_update_config(subscription_params, bk_biz_id, plugin_name, item["bk_data_id"])

    @classmethod
    def get_protocol(cls, bk_data_id):
        from alarm_backends.core.cache.models.custom_ts_group import (
            CustomTSGroupCacheManager,
        )

        return CustomTSGroupCacheManager.get(bk_data_id) or "json"

    @classmethod
    def get_custom_config(
        cls, query_set, group_table_name, data_source_table_name, datatype="event", plugin_name="bkmonitorproxy"
    ):
        # 0. 定义不同上报格式对应配置文件模板关系
        SUB_CONFIG_MAP = {
            "json": "bk-collector-report-v2.conf",
            "prometheus": "bk-collector-application.conf",
        }
        # 1. 从数据库查询到bk_biz_id到自定义上报配置的数据
        result = (
            query_set.extra(
                select={"token": "{}.token".format(data_source_table_name)},
                tables=[data_source_table_name],
                where=["{}.bk_data_id={}.bk_data_id".format(group_table_name, data_source_table_name)],
            )
            .values("bk_biz_id", "bk_data_id", "token", "max_rate")
            .distinct()
        )
        if not result:
            logger.info("no custom report config in database")
            return

        biz_id_to_data_id_config = {}
        for r in result:
            max_rate = int(r.get("max_rate", MAX_DATA_ID_THROUGHPUT))
            if max_rate < 0:
                max_rate = MAX_DATA_ID_THROUGHPUT
            # 后续版本计划移除
            # bkmonitorproxy插件
            # bkmonitorproxy_report.conf
            data_id_config = {
                "dataid": r["bk_data_id"],
                "datatype": datatype,
                "version": "v2",
                "access_token": r["token"],
                "max_rate": max_rate,
                "max_future_time_offset": MAX_FUTURE_TIME_OFFSET,
            }
            if plugin_name == "bk-collector":
                protocol = cls.get_protocol(r["bk_data_id"])
                sub_config_name = SUB_CONFIG_MAP[protocol]
                # 根据格式决定使用那种配置
                if protocol == "json":
                    # json格式: bk-collector-report-v2.conf
                    item = {
                        "bk_data_token": r["token"],
                        "bk_data_id": r["bk_data_id"],
                        "token_config": {
                            "name": "token_checker/proxy",
                            "proxy_dataid": r["bk_data_id"],
                            "proxy_token": r["token"],
                        },
                        "qps_config": {
                            "name": "rate_limiter/token_bucket",
                            "type": "token_bucket",
                            "qps": max_rate,
                        },
                        "validator_config": {
                            "name": "proxy_validator/common",
                            "type": datatype,
                            "version": "v2",
                            "max_future_time_offset": MAX_FUTURE_TIME_OFFSET,
                        },
                    }
                else:
                    # prometheus格式: bk-collector-application.conf
                    item = {
                        "bk_data_token": transform_data_id_to_token(r["bk_data_id"]),
                        "bk_biz_id": r["bk_biz_id"],
                        "bk_data_id": r["bk_data_id"],
                        "bk_app_name": "prometheus_report",
                        "qps_config": {
                            "name": "rate_limiter/token_bucket",
                            "type": "token_bucket",
                            "qps": max_rate,
                        },
                    }
                data_id_config = (item, sub_config_name)

            biz_id_to_data_id_config.setdefault(r["bk_biz_id"], []).append(
                data_id_config,
            )
        return biz_id_to_data_id_config

    @classmethod
    def get_custom_event_config(cls, bk_biz_id=None, plugin_name="bkmonitorproxy"):
        logger.info("get custom event config, bk_biz_id(%s)", bk_biz_id)
        from metadata.models.custom_report.event import EventGroup
        from metadata.models.data_source import DataSource

        qs = EventGroup.objects.filter(is_enable=True, is_delete=False)
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)

        # 1. 从数据库查询到bk_biz_id到自定义上报配置的数据
        event_group_table_name = EventGroup._meta.db_table
        data_source_table_name = DataSource._meta.db_table
        biz_id_to_data_id_config = cls.get_custom_config(
            qs, event_group_table_name, data_source_table_name, "event", plugin_name
        )
        return biz_id_to_data_id_config

    @classmethod
    def get_custom_time_series_config(cls, bk_biz_id=None, plugin_name="bkmonitorproxy"):
        logger.info("get custom time_series config, bk_biz_id(%s)", bk_biz_id)
        from metadata.models.custom_report.time_series import TimeSeriesGroup
        from metadata.models.data_source import DataSource

        qs = TimeSeriesGroup.objects.filter(is_enable=True, is_delete=False)
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)

        ts_group_table_name = TimeSeriesGroup._meta.db_table
        data_source_table_name = DataSource._meta.db_table
        biz_id_to_data_id_config = cls.get_custom_config(
            qs, ts_group_table_name, data_source_table_name, "time_series", plugin_name
        )
        logger.info(
            "get custom time_series config success, bk_biz_id(%s), len(config)=>(%s)",
            bk_biz_id,
            len(biz_id_to_data_id_config),
        )
        return biz_id_to_data_id_config

    @classmethod
    def refresh_collector_custom_conf(cls, bk_biz_id=None, plugin_name="bkmonitorproxy", op_type="add"):
        """
        指定业务ID更新，或者更新全量业务

        Steps:
            - Metadata
                0. 从EventGroup, TimeSeriesGroup表查询到bk_biz_id到bk_data_id的对应关系
                1. 从DataSource上查询到bk_data_id到的token
                3. 根据上面的查询结果生成bk_biz_id的相关自定义上报dataid的对应关系配置列表

            - Nodeman
                0. 从api.node_man.get_proxies_by_biz接口获取到业务下所有使用到的proxyip
                1. 根据上面的查询结果生成业务ID到目标Proxy的对应关系

            按业务ID将上面的任务下发到机器上，通过节点管理的订阅接口，其中0业务为直连云区域，下发所有data_id配置
            不同插件下发模式：
            - bk-collector: 单个data_id对应创建单个订阅
            - bkmonitorproxy: 多个data_id对应创建单个订阅，proxy_ip存在proxy插件则下发
        """
        logger.info("refresh custom report config to proxy on bk_biz_id(%s)", bk_biz_id)

        all_biz_ids = [b.bk_biz_id for b in api.cmdb.get_business()]
        custom_event_config = cls.get_custom_event_config(bk_biz_id, plugin_name)
        custom_time_series_config = cls.get_custom_time_series_config(bk_biz_id, plugin_name)

        biz_id_to_data_id_config = defaultdict(list)

        dict_items_list = []
        if custom_event_config is not None:
            dict_items_list.append(custom_event_config)

        if custom_time_series_config is not None:
            dict_items_list.append(custom_time_series_config)

        dict_items = map(methodcaller("items"), dict_items_list)
        for k, v in chain.from_iterable(dict_items):
            biz_id_to_data_id_config[k].extend(v)

        is_all_biz_refresh = bk_biz_id is None

        biz_id_to_proxy = defaultdict(list)

        for biz_id in all_biz_ids:
            if not is_all_biz_refresh and bk_biz_id != biz_id:
                # 如果仅仅是只刷新一个业务，则跳过其他业务的proxy获取
                continue
            proxies = api.node_man.get_proxies_by_biz(bk_biz_id=biz_id)
            proxy_biz_ids = {proxy["bk_biz_id"] for proxy in proxies}
            proxy_hosts = []
            for proxy_biz_id in proxy_biz_ids:
                current_proxy_hosts = api.cmdb.get_host_by_ip(
                    ips=[
                        {"ip": proxy.get("inner_ip", ""), "bk_cloud_id": proxy["bk_cloud_id"]}
                        for proxy in proxies
                        if proxy["bk_biz_id"] == proxy_biz_id
                    ],
                    bk_biz_id=proxy_biz_id,
                )
                proxy_hosts.extend(current_proxy_hosts)
            biz_id_to_proxy[biz_id] = [proxy.bk_host_id for proxy in proxy_hosts]

        for biz_id, items in biz_id_to_data_id_config.items():
            if biz_id not in all_biz_ids and biz_id > 0:
                # 如果cmdb不存在这个业务，那么需要跳过这个业务的下发
                logger.info("biz_id({}) does not exists in cmdb".format(biz_id))
                continue

            if not is_all_biz_refresh and bk_biz_id != biz_id:
                # 如果仅仅是只刷新一个业务，则跳过其他业务的下发
                continue

            # 2. 从节点管理查询到biz_id下的Proxy机器
            bk_host_ids = biz_id_to_proxy[biz_id]
            if not bk_host_ids:
                logger.warning("Update custom report config to biz_id({}) error, No proxy found".format(biz_id))
                continue

            # 3. 通过节点管理下发配置
            cls.create_subscription(biz_id, items, bk_host_ids, plugin_name, op_type)

        # 4. 通过节点管理下发直连区域配置，下发全部bk_data_id
        items = list(chain(*list(biz_id_to_data_id_config.values())))
        proxy_ips = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        hosts = api.cmdb.get_host_without_biz(ips=proxy_ips)["hosts"]
        hosts = [host for host in hosts if host["bk_cloud_id"] == 0]
        if not hosts:
            logger.warning(
                "Update custom report config to default cloud area error, The default cloud area is not deployed"
            )
            return
        cls.create_subscription(0, items, [host["bk_host_id"] for host in hosts], plugin_name, op_type)

    @classmethod
    def create_or_update_config(cls, subscription_params, bk_biz_id, plugin_name="bkmonitorproxy", bk_data_id=0):
        # 若订阅存在则判定是否更新，若不存在则创建
        # 使用proxy下发bk_data_id为默认值0，一个业务下的多个data_id对应一个订阅
        qs = CustomReportSubscription.objects.filter(bk_biz_id=bk_biz_id, bk_data_id=bk_data_id)
        if qs.exists():
            try:
                logger.info("subscription task already exists.")
                sub_config_obj = qs.first()
                subscription_params["subscription_id"] = sub_config_obj.subscription_id
                subscription_params["run_immediately"] = True

                # bkmonitorproxy原订阅scope配置为空则不再管理该订阅
                old_nodes = sub_config_obj.config["scope"].get("nodes", [])
                if plugin_name == "bkmonitorproxy" and not old_nodes:
                    logger.info("[bkmonitorproxy]: target_hosts is None, don't need to update subscription task.")
                    return

                old_subscription_params_md5 = count_md5(sub_config_obj.config)
                new_subscription_params_md5 = count_md5(subscription_params)
                if old_subscription_params_md5 != new_subscription_params_md5:
                    logger.info("subscription task config has changed, update it.")
                    result = api.node_man.update_subscription(subscription_params)
                    logger.info("update subscription successful, result:{}".format(result))
                    qs.update(config=subscription_params)
                return sub_config_obj.subscription_id
            except Exception as e:  # noqa
                logger.exception("update subscription error:{}, params:{}".format(e, subscription_params))
        else:
            try:
                logger.info("subscription task not exists, create it.")
                result = api.node_man.create_subscription(subscription_params)
                logger.info("create subscription successful, result:{}".format(result))

                # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                subscription_id = result["subscription_id"]
                CustomReportSubscription.objects.create(
                    bk_biz_id=bk_biz_id,
                    config=subscription_params,
                    subscription_id=subscription_id,
                    bk_data_id=bk_data_id,
                )

                result = api.node_man.run_subscription(
                    subscription_id=subscription_id, actions={plugin_name: "INSTALL"}
                )
                logger.info("run subscription result:{}".format(result))
                return subscription_id
            except Exception as e:  # noqa
                logger.exception("create subscription error{}, params:{}".format(e, subscription_params))


class LogSubscriptionConfig(models.Model):
    """
    Subscription Config for Custom Log Report
    """

    bk_biz_id = models.IntegerField("业务id", default=int)
    log_name = models.CharField("日志名称", max_length=128, blank=True)
    subscription_id = models.IntegerField("节点管理订阅ID", default=int)
    config = JsonField("订阅配置")

    class Meta:
        verbose_name = "自定义日志订阅"
        verbose_name_plural = verbose_name
        index_together = [["bk_biz_id", "log_name"]]

    # Plugin Name
    PLUGIN_NAME = "bk-collector"
    # Template Name
    PLUGIN_LOG_CONFIG_TEMPLATE_NAME = "bk-collector-application.conf"

    @classmethod
    def get_target_hosts(cls):
        """
        查询云区域下所有的Proxy机器列表
        """
        target_hosts = [
            {"ip": proxy_ip, "bk_cloud_id": 0, "bk_supplier_id": 0}
            for proxy_ip in settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        ]

        cloud_infos = api.cmdb.search_cloud_area()
        for cloud_info in cloud_infos:
            bk_cloud_id = cloud_info.get("bk_cloud_id", -1)
            if int(bk_cloud_id) == 0:
                continue

            proxy_list = api.node_man.get_proxies(bk_cloud_id=bk_cloud_id)
            for p in proxy_list:
                if p["status"] != "RUNNING":
                    logger.warning("proxy({}) can not be use with bk-collector, it's not running".format(p["inner_ip"]))
                else:
                    target_hosts.append(
                        {"ip": p["inner_ip"], "bk_cloud_id": p.get("bk_cloud_id", 0), "bk_supplier_id": 0}
                    )

        return target_hosts

    @classmethod
    def refresh(cls, log_group) -> None:
        """
        Refresh Config
        """

        # Get Hosts
        bk_host_ids = cls.get_target_hosts()
        if not bk_host_ids:
            logger.info("no bk-collector node, otlp is disabled")
            return

        # Initial Config
        log_config = cls.get_log_config(log_group)

        # Deploy Config
        try:
            cls.deploy(log_group, log_config, bk_host_ids)
        except Exception:
            logger.exception("auto deploy bk-collector log config error")

    @classmethod
    def get_log_config(cls, log_group) -> dict:
        """
        Get Log Config
        """

        return {
            "bk_data_token": log_group.get_bk_data_token(),
            "bk_biz_id": log_group.bk_biz_id,
            "bk_app_name": log_group.log_group_name,
            "qps_config": cls.get_qps_config(log_group),
        }

    @classmethod
    def get_qps_config(cls, log_group) -> dict:
        """
        Log QPS
        """

        return {
            "name": "rate_limiter/token_bucket",
            "type": "token_bucket",
            "qps": log_group.max_rate if log_group.max_rate > 0 else LOG_REPORT_MAX_QPS,
        }

    @classmethod
    def deploy(cls, log_group, platform_config, bk_host_ids) -> None:
        """
        Deploy Custom Log Config
        """
        # Build Subscription Params
        scope = {
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids],
        }
        subscription_params = {
            "scope": scope,
            "steps": [
                {
                    "id": cls.PLUGIN_NAME,
                    "type": "PLUGIN",
                    "config": {
                        "plugin_name": cls.PLUGIN_NAME,
                        "plugin_version": "latest",
                        "config_templates": [{"name": cls.PLUGIN_LOG_CONFIG_TEMPLATE_NAME, "version": "latest"}],
                    },
                    "params": {"context": platform_config},
                }
            ],
        }

        log_subscription = cls.objects.filter(bk_biz_id=log_group.bk_biz_id, log_name=log_group.log_group_name)
        if log_subscription.exists():
            try:
                logger.info("custom log config subscription task already exists.")
                sub_config_obj = log_subscription.first()
                subscription_params["subscription_id"] = sub_config_obj.subscription_id
                subscription_params["run_immediately"] = True

                old_subscription_params_md5 = count_md5(sub_config_obj.config)
                new_subscription_params_md5 = count_md5(subscription_params)
                if old_subscription_params_md5 != new_subscription_params_md5:
                    logger.info("custom log config subscription task config has changed, update it.")
                    result = api.node_man.update_subscription(subscription_params)
                    logger.info("update custom log config subscription successful, result:{}".format(result))
                    log_subscription.update(config=subscription_params)
                return sub_config_obj.subscription_id
            except Exception as e:
                logger.exception(
                    "update custom log config subscription error:{}, params:{}".format(e, subscription_params)
                )
        else:
            try:
                logger.info("custom log config subscription task not exists, create it.")
                result = api.node_man.create_subscription(subscription_params)
                logger.info("create custom log config subscription successful, result:{}".format(result))

                # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                subscription_id = result["subscription_id"]
                LogSubscriptionConfig.objects.create(
                    bk_biz_id=log_group.bk_biz_id,
                    log_name=log_group.log_group_name,
                    config=subscription_params,
                    subscription_id=subscription_id,
                )

                result = api.node_man.run_subscription(
                    subscription_id=subscription_id, actions={cls.PLUGIN_NAME: "INSTALL"}
                )
                logger.info("run custom log config subscription result:{}".format(result))
            except Exception as e:
                logger.exception(
                    "create custom log config subscription error{}, params:{}".format(e, subscription_params)
                )
