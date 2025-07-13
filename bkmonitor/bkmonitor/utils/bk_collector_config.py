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

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger(__name__)


class BkCollectorConfig:
    # bk-collector 插件名称
    PLUGIN_NAME = "bk-collector"

    @classmethod
    def get_target_host_in_default_cloud_area(cls) -> list[int]:
        """
        获取全局配置中的主机 ID，这些主机需在默认租户的直连区域下
        """
        bk_host_ids = []
        proxy_ips = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        if not proxy_ips:
            logger.info("no proxy host in direct area, skip it")
            return bk_host_ids

        hosts = api.cmdb.get_host_without_biz(bk_tenant_id=DEFAULT_TENANT_ID, ips=proxy_ips)["hosts"]
        hosts = [host for host in hosts if host["bk_cloud_id"] == 0]
        bk_host_ids.extend([host["bk_host_id"] for host in hosts])
        return bk_host_ids

    @classmethod
    def get_target_host_ids_by_bk_tenant_id(cls, bk_tenant_id) -> list[int]:
        """
        获取指定租户下所有的 Proxy 机器列表 (不包含直连区域)
        """
        bk_host_ids = []
        cloud_infos = api.cmdb.search_cloud_area(bk_tenant_id=bk_tenant_id)
        for cloud_info in cloud_infos:
            bk_cloud_id = cloud_info.get("bk_cloud_id", -1)
            if int(bk_cloud_id) == 0:
                continue

            proxy_list = api.node_man.get_proxies(bk_cloud_id=bk_cloud_id)
            for p in proxy_list:
                if p["status"] != "RUNNING":
                    logger.warning(
                        "proxy({}) can not be use with bk-collector, it's not running".format(p["bk_host_id"])
                    )
                else:
                    bk_host_ids.append(p["bk_host_id"])

        return bk_host_ids

    @classmethod
    def get_target_host_ids_by_biz_id(cls, bk_tenant_id, bk_biz_id) -> list[int]:
        """
        获取指定租户指定业务下所有 Proxy 机器列表
        """
        proxies = api.node_man.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        proxy_biz_ids = {proxy["bk_biz_id"] for proxy in proxies}
        proxy_hosts = []
        for proxy_biz_id in proxy_biz_ids:
            current_proxy_hosts = api.cmdb.get_host_by_ip(
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
            proxy_hosts.extend(current_proxy_hosts)
        return [proxy.bk_host_id for proxy in proxy_hosts]
