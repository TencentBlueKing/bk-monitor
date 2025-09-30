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
MONITOR 模块，调用接口汇总
"""
from django.conf import settings
from django.utils.translation import gettext_lazy as _  # noqa

from apps.api.base import DataAPI  # noqa
from apps.api.modules.utils import add_esb_info_before_request, biz_to_tenant_getter  # noqa
from config.domains import MONITOR_APIGATEWAY_ROOT, MONITOR_APIGATEWAY_ROOT_NEW  # noqa


class _MonitorApi:
    MODULE = _("Monitor监控平台")

    def __init__(self):
        self.search_user_groups = DataAPI(
            method="POST",
            url=self._build_url("user_group/search/", "search_user_groups/"),
            module=self.MODULE,
            description="查询通知组",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(key=lambda p: p["bk_biz_ids"][0]),
        )
        self.save_notice_group = DataAPI(
            method="POST",
            url=self._build_url("user_group/save/", "save_notice_group/"),
            module=self.MODULE,
            description="保存通知组",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.delete_alarm_strategy_v3 = DataAPI(
            method="POST",
            url=self._build_url("alarm_strategy/delete/", "delete_alarm_strategy_v3/"),
            module=self.MODULE,
            description="删除告警策略V3",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.search_alarm_strategy_v3 = DataAPI(
            method="POST",
            url=self._build_url("alarm_strategy/search/", "search_alarm_strategy_v3"),
            module=self.MODULE,
            description="查询告警策略V3",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.save_alarm_strategy_v3 = DataAPI(
            method="POST",
            url=self._build_url("alarm_strategy/save/", "save_alarm_strategy_v3/"),
            module=self.MODULE,
            description="保存告警策略V3",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.query_log_relation = DataAPI(
            method="POST",
            url=self._build_url("apm/query_log_relation/", "query_log_relation"),
            module=self.MODULE,
            description="根据索引集id获取服务关联",
            default_return_value=None,
            before_request=add_esb_info_before_request,
        )
        self.create_or_update_report = DataAPI(
            method="POST",
            url=self._build_url("new_report/create_or_update_report/", "create_or_update_report/"),
            module=self.MODULE,
            description="创建或更新订阅报表",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.send_report = DataAPI(
            method="POST",
            url=self._build_url("new_report/send_report/", "send_report/"),
            module=self.MODULE,
            description="发送阅报表",
            default_return_value=None,
            before_request=add_esb_info_before_request,
        )
        self.get_reports = DataAPI(
            method="GET",
            url=self._build_url("new_report/get_exist_reports/", "get_exist_reports/"),
            module=self.MODULE,
            description="获取已存在的订阅报表",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.get_report_variables = DataAPI(
            method="GET",
            url=self._build_url("new_report/get_report_variables/", "get_report_variables/"),
            module=self.MODULE,
            description="获取订阅报表的变量列表",
            default_return_value=None,
            before_request=add_esb_info_before_request,
        )
        self.search_alert = DataAPI(
            method="POST",
            url=self._build_url("alert/search/", "search_alert/"),
            module=self.MODULE,
            description="查询告警",
            default_return_value=None,
            before_request=add_esb_info_before_request,
            bk_tenant_id=biz_to_tenant_getter(key=lambda p: p["bk_biz_ids"][0]),
        )
        self.get_alert_detail = DataAPI(
            method="GET",
            url=self._build_url("alert/detail/", "get_alert_detail/"),
            module=self.MODULE,
            description="获取告警详情",
            default_return_value=None,
            before_request=add_esb_info_before_request,
        )

    @property
    def use_apigw(self):
        return settings.USE_NEW_MONITOR_APIGATEWAY or settings.ENABLE_MULTI_TENANT_MODE

    def _build_url(self, new_path, old_path):
        return (
            f"{MONITOR_APIGATEWAY_ROOT_NEW}app/{new_path}" if self.use_apigw else f"{MONITOR_APIGATEWAY_ROOT}{old_path}"
        )


MonitorApi = _MonitorApi()
