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
from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Any, Literal, Union

from jinja2.sandbox import SandboxedEnvironment as Environment
from django.conf import settings
from django.db import models

from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig, BkCollectorConfig
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.db.fields import JsonField
from constants.bk_collector import BkCollectorComp
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.models.constants import LOG_REPORT_MAX_QPS
from metadata.models.custom_report.log import LogGroup
from utils.redis_client import RedisClient

logger = logging.getLogger("metadata")

MAX_REQ_LENGTH = 500 * 1024  # 最大请求Body大小，500KB
MAX_REQ_THROUGHPUT = 4000  # 最大的请求数(单位：秒)
MAX_DATA_ID_THROUGHPUT = 1000  # 单个dataid最大的上报频率(条/min)、在bk-collector模式下，是 条/秒
MAX_FUTURE_TIME_OFFSET = 3600  # 支持的最大未来时间，超过这个偏移值，则丢弃
jinja_env = Environment()

if TYPE_CHECKING:
    from metadata.models.custom_report.event import EventGroup
    from metadata.models.custom_report.time_series import TimeSeriesGroup


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

    # 上报协议与配置文件模板名称的映射关系
    SUB_CONFIG_MAP = {
        "json": "bk-collector-report-v2.conf",
        "prometheus": "bk-collector-application.conf",
    }

    @classmethod
    def create_subscription(
        cls,
        bk_tenant_id: str,
        bk_biz_id: int,
        data_id_configs: list[tuple[dict[str, Any], str]],
        bk_host_ids: list[int],
        op_type: str = "add",
    ):
        available_host_ids = bk_host_ids

        if op_type != "remove" and not available_host_ids:
            # 目标主机 bkmonitorproxy 全部为手动停止或未部署时，暂不下发
            # 业务背景：bkmonitorproxy 的功能将被 bk-collector 取代，为了版本兼容目前采取两边下发的逻辑
            #         当 bkmonitorproxy 被停止或未部署时，说明 bkmonitorproxy 已下线，无需进行下发
            logger.info("[custom_report] skipped because no available nodes: bk_biz_id(%s)", bk_biz_id)
            return

        if op_type == "remove":
            # 使用 Proxy 插件卸除配置时，针对 Proxy 状态为手动停止的机器进行卸载
            bk_host_ids = available_host_ids

        logger.info(
            "update or create subscription task, bk_biz_id(%s), target_hosts(%s)",
            bk_biz_id,
            bk_host_ids,
        )
        for item, protocol in data_id_configs:
            subscription_params = {
                "scope": {
                    "object_type": "HOST",
                    "node_type": "INSTANCE",
                    "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids],
                },
                "steps": [
                    {
                        "id": "bk-collector",
                        "type": "PLUGIN",
                        "config": {
                            "plugin_name": "bk-collector",
                            "plugin_version": "latest",
                            "config_templates": [{"name": cls.SUB_CONFIG_MAP[protocol], "version": "latest"}],
                        },
                        "params": {"context": {"bk_biz_id": bk_biz_id, **item}},
                    },
                ],
            }

            try:
                cls.create_or_update_config(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    subscription_params=subscription_params,
                    bk_data_id=item["bk_data_id"],
                )
            except Exception as e:
                logger.exception(
                    f"create or update subscription config error, bk_biz_id({bk_biz_id}), bk_data_id({item['bk_data_id']}), error: {e}"
                )

    @classmethod
    def get_protocol(cls, bk_data_id) -> str:
        from alarm_backends.core.cache.models.custom_ts_group import (
            CustomTSGroupCacheManager,
        )

        return CustomTSGroupCacheManager.get(bk_data_id) or "json"

    @classmethod
    def get_custom_config(
        cls,
        query_set: models.QuerySet[Union["EventGroup", "TimeSeriesGroup"]],
        group_table_name: str,
        data_source_table_name: str,
        datatype: Literal["event", "time_series"] = "event",
    ) -> dict[int, list[tuple[dict[str, Any], str]]]:
        """
        获取业务下自定义上报配置
        """
        # 1. 从数据库查询到bk_biz_id到自定义上报配置的数据
        result = (
            query_set.extra(
                select={"token": f"{data_source_table_name}.token"},
                tables=[data_source_table_name],
                where=[f"{group_table_name}.bk_data_id={data_source_table_name}.bk_data_id"],
            )
            .values("bk_biz_id", "bk_data_id", "token", "max_rate", "max_future_time_offset")
            .distinct()
        )
        biz_id_to_data_id_config: dict[int, list[tuple[dict[str, Any], str]]] = {}
        if not result:
            logger.info("no custom report config in database")
            return biz_id_to_data_id_config

        # 无效的prometheus上报分组id
        redis_client = RedisClient.from_envs(prefix="BK_MONITOR_TRANSFER")
        disabled_ts_group_ids = list(map(int, redis_client.hgetall("bkmonitor:disabled_ts_group").keys()))

        for r in result:
            max_rate = int(r.get("max_rate", MAX_DATA_ID_THROUGHPUT))
            # 数据库：
            # 小于 -1 表示全部限制，-1 是默认值 MAX_DATA_ID_THROUGHPUT，0 表示不限制，大于 0 为实际的 qps
            # 采集器：
            # 小于 0 表示全部限制, 0 表示不限制，大于 0 为实际的 qps
            # 因此这里只需要特殊转换一下 -1 的值，将 -1 转换为 MAX_DATA_ID_THROUGHPUT
            if max_rate == -1:
                max_rate = MAX_DATA_ID_THROUGHPUT

            max_future_time_offset = int(r.get("max_future_time_offset", MAX_FUTURE_TIME_OFFSET))
            if max_future_time_offset < 0:
                max_future_time_offset = MAX_FUTURE_TIME_OFFSET
            protocol = cls.get_protocol(r["bk_data_id"])
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
                        "max_future_time_offset": max_future_time_offset,
                    },
                }
            else:
                from metadata.models.custom_report.time_series import TimeSeriesGroup

                group = TimeSeriesGroup.objects.get(bk_data_id=r["bk_data_id"])
                try:
                    if group.custom_group_id in disabled_ts_group_ids:
                        continue
                    group_info = api.monitor.custom_time_series_detail(
                        bk_biz_id=group.bk_biz_id, time_series_group_id=group.custom_group_id
                    )
                except BKAPIError as e:
                    logger.warning(
                        f"[{r['bk_data_id']}]get custom time series group[{group.custom_group_id}] detail error"
                    )
                    if e.data.get("code") == 400 and "custom time series table not found" in (
                        e.data.get("message") or ""
                    ):
                        redis_client.hset("bkmonitor:disabled_ts_group", str(group.custom_group_id), 1)
                    continue

                # prometheus格式: bk-collector-application.conf
                item = {
                    "bk_data_token": group_info["access_token"],
                    "bk_biz_id": r["bk_biz_id"],
                    "bk_data_id": r["bk_data_id"],
                    "bk_app_name": "prometheus_report",
                    "qps_config": {
                        "name": "rate_limiter/token_bucket",
                        "type": "token_bucket",
                        "qps": max_rate,
                    },
                }
            data_id_config: tuple[dict[str, Any], str] = (item, protocol)
            biz_id_to_data_id_config.setdefault(r["bk_biz_id"], []).append(data_id_config)
        return biz_id_to_data_id_config

    @classmethod
    def get_custom_event_config(
        cls, bk_tenant_id: str, bk_biz_id: int | None = None
    ) -> dict[int, list[tuple[dict[str, Any], str]]]:
        """
        获取业务下自定义事件配置
        """
        logger.info("get custom event config, bk_biz_id(%s)", bk_biz_id)
        from metadata.models.custom_report.event import EventGroup
        from metadata.models.data_source import DataSource

        qs = EventGroup.objects.filter(is_enable=True, is_delete=False, bk_tenant_id=bk_tenant_id)
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)

        # 1. 从数据库查询到bk_biz_id到自定义上报配置的数据
        event_group_table_name = EventGroup._meta.db_table
        data_source_table_name = DataSource._meta.db_table
        return cls.get_custom_config(qs, event_group_table_name, data_source_table_name, "event")

    @classmethod
    def get_custom_time_series_config(
        cls, bk_tenant_id: str, bk_biz_id: int | None = None
    ) -> dict[int, list[tuple[dict[str, Any], str]]]:
        """
        获取业务下自定义指标配置
        """
        logger.info("get custom time_series config, bk_biz_id(%s)", bk_biz_id)
        from metadata.models.custom_report.time_series import TimeSeriesGroup
        from metadata.models.data_source import DataSource

        qs = TimeSeriesGroup.objects.filter(is_enable=True, is_delete=False, bk_tenant_id=bk_tenant_id)
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)

        ts_group_table_name = TimeSeriesGroup._meta.db_table
        data_source_table_name = DataSource._meta.db_table
        biz_id_to_data_id_config = cls.get_custom_config(qs, ts_group_table_name, data_source_table_name, "time_series")
        logger.info(
            "get custom time_series config success, bk_biz_id(%s), len(config)=>(%s)",
            bk_biz_id,
            len(biz_id_to_data_id_config),
        )
        return biz_id_to_data_id_config

    @classmethod
    def _refresh_k8s_custom_config_by_biz(
        cls,
        bk_biz_id: int,
        data_id_configs: list[tuple[dict[str, Any], str]],
    ):
        cluster_mapping = BkCollectorClusterConfig.get_cluster_mapping()
        if settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            # 补充中心化集群
            for cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
                cluster_mapping[cluster_id] = [BkCollectorClusterConfig.GLOBAL_CONFIG_BK_BIZ_ID]

        for cluster_id, cc_bk_biz_ids in cluster_mapping.items():
            if str(bk_biz_id) not in cc_bk_biz_ids and int(bk_biz_id) not in cc_bk_biz_ids:
                continue

            # 按协议分组收集配置
            protocol_config_maps = {}
            try:
                protocol_tpl = {}
                for config_context, protocol in data_id_configs:
                    tpl_name = BkCollectorComp.CONFIG_MAP_NAME_MAP.get(protocol)
                    if tpl_name is None:
                        logger.info(f"can not find protocol({protocol}) sub config template name")
                        continue

                    if protocol not in protocol_tpl:
                        tpl_str = BkCollectorClusterConfig.sub_config_tpl(cluster_id, tpl_name)
                        if not tpl_str:
                            protocol_tpl[protocol] = None
                        else:
                            protocol_tpl[protocol] = jinja_env.from_string(tpl_str)

                    compiled_template = protocol_tpl.get(protocol)
                    if not compiled_template:
                        continue

                    try:
                        config_id = int(config_context.get("bk_data_id"))
                        config_context.setdefault("bk_biz_id", bk_biz_id)
                        config_content = compiled_template.render(config_context)
                        protocol_config_maps.setdefault(protocol, {})[config_id] = config_content
                    except Exception:  # pylint: disable=broad-except
                        # 单个失败，继续渲染模板
                        logger.exception(f"render config({config_context})")

                # 分别按协议调用deploy_to_k8s_with_hash
                for protocol, config_map in protocol_config_maps.items():
                    BkCollectorClusterConfig.deploy_to_k8s_with_hash(cluster_id, config_map, protocol)

            except Exception as e:  # pylint: disable=broad-except
                logger.exception(f"refresh custom report ({bk_biz_id}) config to k8s({cluster_id}) error({e})")

    @classmethod
    def _refresh_collect_custom_config_by_biz(
        cls,
        bk_tenant_id: str,
        bk_biz_id: int,
        op_type: str,
        data_id_configs: list[tuple[dict[str, Any], str]],
    ):
        """
        刷新指定业务ID的collector自定义上报配置
        """
        # 1. 获取业务下所有proxy
        proxy_host_ids: list[int] = []
        if bk_biz_id == 0:
            proxy_ips = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
            hosts = api.cmdb.get_host_without_biz(bk_tenant_id=bk_tenant_id, ips=proxy_ips)["hosts"]
            proxy_host_ids = [host["bk_host_id"] for host in hosts if host["bk_cloud_id"] == 0]
        else:
            proxies = api.node_man.get_proxies_by_biz(bk_biz_id=bk_biz_id)
            proxy_biz_ids = {proxy["bk_biz_id"] for proxy in proxies}
            for proxy_biz_id in proxy_biz_ids:
                current_proxy_hosts = api.cmdb.get_host_by_ip(
                    bk_tenant_id=bk_tenant_id,
                    ips=[
                        {
                            "ip": proxy.get("inner_ip", "") or proxy.get("inner_ipv6", ""),
                            "bk_cloud_id": proxy["bk_cloud_id"],
                        }
                        for proxy in proxies
                        if proxy["bk_biz_id"] == proxy_biz_id
                    ],
                    bk_biz_id=proxy_biz_id,
                )
                proxy_host_ids.extend([host["bk_host_id"] for host in current_proxy_hosts])

        # 如果proxy_host_ids为空，则不进行下发
        if not proxy_host_ids:
            logger.warning(f"refresh custom report config to proxy on bk_biz_id({bk_biz_id}) error, No proxy found")
            return

        # 2. 下发配置
        cls.create_subscription(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            data_id_configs=data_id_configs,
            bk_host_ids=proxy_host_ids,
            op_type=op_type,
        )

    @classmethod
    def refresh_collector_custom_conf(cls, bk_tenant_id: str, bk_biz_id: int | None = None, op_type: str = "add"):
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
            bk-collector: 单个data_id对应创建单个订阅
        """
        logger.info("refresh custom report config to proxy on bk_biz_id(%s)", bk_biz_id)

        # 获取业务的自定义事件/指标配置
        biz_id_to_data_id_config: dict[int, list[tuple[dict, str]]] = defaultdict(list)
        custom_event_config = cls.get_custom_event_config(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        custom_time_series_config = cls.get_custom_time_series_config(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

        # 合并自定义事件和指标配置
        for k, v in chain(custom_event_config.items(), custom_time_series_config.items()):
            biz_id_to_data_id_config[k].extend(v)

        # 判断是否下发全部业务配置
        if bk_biz_id is None:
            all_bk_biz_ids = {b.bk_biz_id for b in api.cmdb.get_business(bk_tenant_id=bk_tenant_id)}
            bk_biz_ids = {
                bk_biz_id
                for bk_biz_id in biz_id_to_data_id_config.keys()
                if bk_biz_id in all_bk_biz_ids or bk_biz_id < 0
            }
        else:
            bk_biz_ids = {bk_biz_id}

        # 增加默认业务
        bk_biz_ids.add(0)

        for bk_biz_id in bk_biz_ids:
            # 0业务下发全部配置，其他业务下发指定业务配置
            if bk_biz_id == 0:
                data_id_configs: list[tuple[dict[str, Any], str]] = list(
                    chain(*list(biz_id_to_data_id_config.values()))
                )
            else:
                data_id_configs = biz_id_to_data_id_config.get(bk_biz_id, [])
            try:
                # 1. 下发配置（走节点管理下发至主机）
                cls._refresh_collect_custom_config_by_biz(
                    bk_tenant_id=bk_tenant_id if bk_biz_id != 0 else DEFAULT_TENANT_ID,
                    bk_biz_id=bk_biz_id,
                    op_type=op_type,
                    data_id_configs=data_id_configs,
                )
            except Exception as e:
                logger.exception(f"refresh custom report config to proxy on bk_biz_id({bk_biz_id}) error, {e}")

            try:
                # 2. 下发配置（走 K8S 下发至集群）
                cls._refresh_k8s_custom_config_by_biz(
                    bk_biz_id=bk_biz_id,
                    data_id_configs=data_id_configs,
                )
            except Exception as e:
                logger.exception(f"refresh k8s custom report config to proxy on bk_biz_id({bk_biz_id}) error, {e}")

    @classmethod
    def create_or_update_config(cls, bk_tenant_id: str, bk_biz_id: int, subscription_params, bk_data_id=0):
        # 若订阅存在则判定是否更新，若不存在则创建
        # 使用proxy下发bk_data_id为默认值0，一个业务下的多个data_id对应一个订阅
        qs = CustomReportSubscription.objects.filter(bk_biz_id=bk_biz_id, bk_data_id=bk_data_id)
        sub_config_obj = qs.first()

        # 如果订阅存在，则更新订阅
        if sub_config_obj:
            logger.info("subscription task already exists.")
            # 更新订阅巡检开启
            api.node_man.switch_subscription(
                bk_tenant_id=bk_tenant_id, subscription_id=sub_config_obj.subscription_id, action="enable"
            )
            subscription_params["subscription_id"] = sub_config_obj.subscription_id
            subscription_params["run_immediately"] = True

            # bkmonitorproxy原订阅scope配置为空则不再管理该订阅
            old_subscription_params_md5 = count_md5(sub_config_obj.config)
            new_subscription_params_md5 = count_md5(subscription_params)
            if old_subscription_params_md5 != new_subscription_params_md5:
                logger.info(
                    "subscription task config has changed, update it."
                    f"\n【old】: {sub_config_obj.config}"
                    f"\n【new】: {subscription_params}"
                )
                result = api.node_man.update_subscription(bk_tenant_id=bk_tenant_id, **subscription_params)
                logger.info(f"update subscription successful, result:{result}")
                qs.update(config=subscription_params)
            return sub_config_obj.subscription_id

        # 创建订阅
        logger.info("subscription task not exists, create it.")
        result = api.node_man.create_subscription(bk_tenant_id=bk_tenant_id, **subscription_params)
        logger.info(f"create subscription successful, result:{result}")

        # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
        subscription_id = result["subscription_id"]
        CustomReportSubscription.objects.create(
            bk_biz_id=bk_biz_id,
            config=subscription_params,
            subscription_id=subscription_id,
            bk_data_id=bk_data_id,
        )
        # 创建的订阅默认开启巡检
        api.node_man.switch_subscription(bk_tenant_id=bk_tenant_id, subscription_id=subscription_id, action="enable")
        result = api.node_man.run_subscription(
            bk_tenant_id=bk_tenant_id, subscription_id=subscription_id, actions={"bk-collector": "INSTALL"}
        )
        logger.info(f"run subscription result:{result}")
        return subscription_id


class LogSubscriptionConfig(models.Model):
    """
    Subscription Config for Custom Log Report
    """

    bk_tenant_id = models.CharField(verbose_name="租户ID", default=DEFAULT_TENANT_ID, max_length=128)

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
    def refresh(cls, log_group: "LogGroup") -> None:
        """
        Refresh Config
        """
        bk_tenant_id = log_group.bk_tenant_id
        bk_biz_id = log_group.bk_biz_id

        # 1.1 获取指定租户指定业务下的主机
        proxy_target_hosts = BkCollectorConfig.get_target_host_ids_by_biz_id(bk_tenant_id, bk_biz_id)

        # 1.2 获取默认租户下全局配置中主机配置列表
        default_target_hosts = BkCollectorConfig.get_target_host_in_default_cloud_area()
        if not default_target_hosts and not proxy_target_hosts:
            logger.info("no bk-collector node, otlp is disabled")
            return

        # 2. 获取配置
        log_config = cls.get_log_config(log_group)

        # 3. 下发配置
        try:
            if bk_tenant_id == DEFAULT_TENANT_ID:
                cls.deploy(bk_tenant_id, log_group, log_config, default_target_hosts + proxy_target_hosts)
            else:
                cls.deploy(DEFAULT_TENANT_ID, log_group, log_config, default_target_hosts)
                cls.deploy(bk_tenant_id, log_group, log_config, proxy_target_hosts)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"auto deploy bk-collector log config error ({e})")

    @classmethod
    def refresh_k8s(cls, log_groups: list["LogGroup"]) -> None:
        """批量刷新多个 log_group 的 k8s 配置"""
        if not log_groups:
            return

        # 按业务ID分组，因为不同业务可能需要部署到不同的集群
        biz_log_groups = {}
        for log_group in log_groups:
            bk_biz_id = log_group.bk_biz_id
            biz_log_groups.setdefault(bk_biz_id, []).append(log_group)

        cluster_mapping: dict = BkCollectorClusterConfig.get_cluster_mapping()
        if settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            # 补充中心化集群
            for cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
                cluster_mapping[cluster_id] = [BkCollectorClusterConfig.GLOBAL_CONFIG_BK_BIZ_ID]

        # 按集群分组配置，实现批量下发
        for cluster_id, cc_bk_biz_ids in cluster_mapping.items():
            try:
                tpl = BkCollectorClusterConfig.sub_config_tpl(
                    cluster_id, BkCollectorComp.CONFIG_MAP_APPLICATION_TPL_NAME
                )
                if not tpl:
                    continue

                # 收集该集群需要部署的所有配置
                cluster_config_map = {}
                compiled_template = jinja_env.from_string(tpl)
                for bk_biz_id, biz_log_group_list in biz_log_groups.items():
                    need_deploy_bk_biz_ids = {
                        str(bk_biz_id),
                        int(bk_biz_id),
                        BkCollectorClusterConfig.GLOBAL_CONFIG_BK_BIZ_ID,
                    }
                    if not set(need_deploy_bk_biz_ids) & set(cc_bk_biz_ids):
                        continue

                    # 为该业务下的所有 log_group 生成配置
                    for log_group in biz_log_group_list:
                        try:
                            config_context = cls.get_log_config(log_group)
                            config_content = compiled_template.render(config_context)
                            config_id = int(log_group.bk_data_id)
                            cluster_config_map[config_id] = config_content
                        except Exception:  # pylint: disable=broad-except
                            # 单个失败，继续渲染模板
                            logger.exception(f"generate config for log_group({log_group.log_group_name})")

                # 批量下发该集群的所有配置
                BkCollectorClusterConfig.deploy_to_k8s_with_hash(cluster_id, cluster_config_map, "log")
                logger.info(f"batch deploy {len(cluster_config_map)} log configs to k8s cluster({cluster_id})")

            except Exception:  # pylint: disable=broad-except
                logger.exception(f"batch refresh custom report config to k8s({cluster_id})")

    @classmethod
    def get_log_config(cls, log_group: "LogGroup") -> dict:
        # 数据库：
        # 小于 -1 表示全部限制，-1 是默认值 MAX_DATA_ID_THROUGHPUT，0 表示不限制，大于 0 为实际的 qps
        # 采集器：
        # 小于 0 表示全部限制, 0 表示不限制，大于 0 为实际的 qps
        # 因此这里只需要特殊转换一下 -1 的值，将 -1 转换为 MAX_DATA_ID_THROUGHPUT
        max_rate = int(log_group.max_rate)
        if max_rate == -1:
            max_rate = LOG_REPORT_MAX_QPS
        return {
            "bk_data_token": log_group.get_bk_data_token(),
            "bk_biz_id": log_group.bk_biz_id,
            "bk_app_name": log_group.log_group_name,
            "log_data_id": log_group.bk_data_id,
            "qps_config": {
                "name": "rate_limiter/token_bucket",
                "type": "token_bucket",
                "qps": max_rate,
            },
        }

    @classmethod
    def deploy(cls, bk_tenant_id: str, log_group: "LogGroup", log_config: dict, bk_host_ids: list[int]) -> None:
        """
        Deploy Custom Log Config
        """
        # Build Subscription Params
        subscription_params = {
            "scope": {
                "object_type": "HOST",
                "node_type": "INSTANCE",
                "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids],
            },
            "steps": [
                {
                    "id": cls.PLUGIN_NAME,
                    "type": "PLUGIN",
                    "config": {
                        "plugin_name": cls.PLUGIN_NAME,
                        "plugin_version": "latest",
                        "config_templates": [{"name": cls.PLUGIN_LOG_CONFIG_TEMPLATE_NAME, "version": "latest"}],
                    },
                    "params": {"context": log_config},
                }
            ],
        }

        log_subscription = cls.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=log_group.bk_biz_id, log_name=log_group.log_group_name
        )
        sub_config_obj = log_subscription.first()

        if sub_config_obj:
            logger.info("custom log config subscription task already exists.")
            subscription_params["subscription_id"] = sub_config_obj.subscription_id
            subscription_params["run_immediately"] = True

            old_subscription_params_md5 = count_md5(sub_config_obj.config)
            new_subscription_params_md5 = count_md5(subscription_params)
            if old_subscription_params_md5 != new_subscription_params_md5:
                logger.info("custom log config subscription task config has changed, update it.")
                result = api.node_man.update_subscription(bk_tenant_id=bk_tenant_id, **subscription_params)
                logger.info(f"update custom log config subscription successful, result:{result}")
                log_subscription.update(config=subscription_params)
            return sub_config_obj.subscription_id
        else:
            logger.info("custom log config subscription task not exists, create it.")
            result = api.node_man.create_subscription(bk_tenant_id=bk_tenant_id, **subscription_params)
            logger.info(f"create custom log config subscription successful, result:{result}")

            # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
            subscription_id = result["subscription_id"]
            LogSubscriptionConfig.objects.create(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=log_group.bk_biz_id,
                log_name=log_group.log_group_name,
                config=subscription_params,
                subscription_id=subscription_id,
            )

            result = api.node_man.run_subscription(
                bk_tenant_id=bk_tenant_id,
                subscription_id=subscription_id,
                actions={cls.PLUGIN_NAME: "INSTALL"},
            )
            logger.info(f"run custom log config subscription result:{result}")
            return subscription_id
