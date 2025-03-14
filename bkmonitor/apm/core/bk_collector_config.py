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
from typing import List

from django.conf import settings

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger("apm")


class BkCollectorConfig(object):
    # bk-collector 插件名称
    PLUGIN_NAME = "bk-collector"

    @classmethod
    def get_target_hosts(cls) -> List[int]:
        """
        查询云区域下所有的Proxy机器列表
        """
        bk_host_ids = []

        # 查询监控默认上报机器信息（仅支持在运营租户下配置）
        hosts = api.cmdb.get_host_without_biz(
            bk_tenant_id=DEFAULT_TENANT_ID, ips=settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        )["hosts"]
        hosts = [host for host in hosts if host["bk_cloud_id"] == 0]
        bk_host_ids.extend([host["bk_host_id"] for host in hosts])

        for tenant in api.bk_login.list_tenant():
            cloud_infos = api.cmdb.search_cloud_area(bk_tenant_id=tenant["id"])
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
