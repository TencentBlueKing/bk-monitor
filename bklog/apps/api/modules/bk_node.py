"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

"""
节点管理调用接口汇总
"""
from apps.api.base import DataAPI  # noqa
from apps.api.modules.utils import biz_to_tenant_getter
from apps.api.modules.utils import (  # noqa
    adapt_non_bkcc_for_bknode,
    add_esb_info_before_request,
)
from config.domains import BK_NODE_APIGATEWAY_ROOT  # noqa
from django.conf import settings


def get_bk_node_request_before(params):
    params = add_esb_info_before_request(params)
    params = adapt_non_bkcc_for_bknode(params)
    return params


class _BKNodeApi:
    MODULE = "节点管理"

    @property
    def use_apigw(self):
        return settings.ENABLE_MULTI_TENANT_MODE

    def _build_url(self, new_path, old_path):
        return (
            f"{settings.PAAS_API_HOST}/api/bk-nodeman/{settings.ENVIRONMENT}/{new_path}"
            if self.use_apigw
            else f"{BK_NODE_APIGATEWAY_ROOT}{old_path}"
        )

    def __init__(self):
        self.create_subscription = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/create/", "backend/api/subscription/create/"),
            module=self.MODULE,
            description="创建订阅配置",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(key=lambda p: p["scope"]["bk_biz_id"]),
        )
        self.update_subscription_info = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/update/", "backend/api/subscription/update/"),
            module=self.MODULE,
            description="更新订阅配置",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(key=lambda p: p["scope"]["bk_biz_id"]),
        )
        self.get_subscription_info = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/info/", "backend/api/subscription/info/"),
            module=self.MODULE,
            description="查询订阅配置信息",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.run_subscription_task = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/run/", "backend/api/subscription/run/"),
            module=self.MODULE,
            description="执行订阅下发任务",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.get_subscription_instance_status = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/instance_status/",
                                "backend/api/subscription/instance_status/"),
            module=self.MODULE,
            description="查询订阅实例状态",
            before_request=get_bk_node_request_before,
            bk_tenant_id=settings.BK_APP_TENANT_ID,
        )
        self.get_subscription_task_status = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/task_result/", "backend/api/subscription/task_result/"),
            module=self.MODULE,
            description="查看订阅任务运行状态",
            before_request=get_bk_node_request_before,
            pagination_style=DataAPI.PaginationStyle.PAGE_NUMBER.value,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.plugin_search = DataAPI(
            method="POST",
            url=self._build_url("system/api/plugin/search/", "api/plugin/search/"),
            module=self.MODULE,
            description="查询插件列表",
            before_request=get_bk_node_request_before,
            pagination_style=DataAPI.PaginationStyle.PAGE_NUMBER.value,
        )
        self.check_subscription_task_ready = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/check_task_ready/",
                                "backend/api/subscription/check_task_ready/"),
            module=self.MODULE,
            description="查看订阅任务是否发起",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.delete_subscription = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/delete/", "backend/api/subscription/delete/"),
            module=self.MODULE,
            description="删除订阅配置",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.get_subscription_task_detail = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/task_result_detail/",
                                "backend/api/subscription/task_result_detail/"),
            module=self.MODULE,
            description="查询订阅任务中实例的详细状态",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.switch_subscription = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/switch/", "backend/api/subscription/switch/"),
            module=self.MODULE,
            description="节点管理订阅功能开关",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )

        self.subscription_statistic = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/statistic/", "backend/api/subscription/statistic/"),
            module=self.MODULE,
            description="节点管理统计订阅任务数据",
            before_request=get_bk_node_request_before,
        )
        self.query_host_subscriptions = DataAPI(
            method="GET",
            url=self._build_url("system/backend/api/subscription/query_host_subscriptions/",
                                "backend/api/subscription/query_host_subscriptions/"),
            module=self.MODULE,
            description="获取主机订阅列表",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.retry_subscription = DataAPI(
            method="POST",
            url=self._build_url("system/backend/api/subscription/retry/", "backend/api/subscription/retry/"),
            module=self.MODULE,
            description="重试失败的任务",
            before_request=get_bk_node_request_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.ipchooser_host_details = DataAPI(
            method="POST",
            url=self._build_url("system/core/api/ipchooser_host/details/", "core/api/ipchooser_host/details/"),
            module=self.MODULE,
            description="获取agent信息",
            before_request=get_bk_node_request_before,
            use_superuser=True,
            bk_tenant_id=biz_to_tenant_getter(key=lambda p: p["scope_list"][0]["scope_id"]),
        )
        self.get_host_biz_proxies = DataAPI(
            method="GET",
            url=self._build_url("system/api/host/biz_proxies/", "api/host/biz_proxies/"),
            module=self.MODULE,
            description="查询业务下管控区域的proxy集合",
            before_request=get_bk_node_request_before,
            use_superuser=True,
            bk_tenant_id=biz_to_tenant_getter(),
        )


BKNodeApi = _BKNodeApi()
