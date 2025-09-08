# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from calendars import resources
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class CalendarsViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS or self.action in ["item_detail", "item_list"]:
            return []
        return [BusinessActionPermission([ActionEnum.MANAGE_CALENDAR])]

    resource_routes = [
        # 保存日历
        ResourceRoute("POST", resources.SaveCalendarResource, endpoint="save_calendar"),
        # 编辑日历
        ResourceRoute("POST", resources.EditCalendarResource, endpoint="edit_calendar"),
        # 获取单个日历
        ResourceRoute("GET", resources.GetCalendarResource, endpoint="get_calendar"),
        # 批量获取日历
        ResourceRoute("GET", resources.ListCalendarResource, endpoint="list_calendar"),
        # 删除日历
        ResourceRoute("POST", resources.DeleteCalendarResource, endpoint="delete_calendar"),
        # 新增日历事项
        ResourceRoute("POST", resources.SaveItemResource, endpoint="save_item"),
        # 删除日历事项
        ResourceRoute("POST", resources.DeleteItemResource, endpoint="delete_item"),
        # 修改日历事项
        ResourceRoute("POST", resources.EditItemResource, endpoint="edit_item"),
        # 获取某些日历下某个时间点的所有事项
        ResourceRoute("POST", resources.ItemDetailResource, endpoint="item_detail"),
        # 查询规定日期内的所有日历事项列表
        ResourceRoute("POST", resources.ItemListResource, endpoint="item_list"),
        # 获取时区信息
        ResourceRoute("GET", resources.GetTimeZoneResource, endpoint="get_time_zone"),
        # 获取所属日历下所有父类事项列表
        ResourceRoute("GET", resources.GetParentItemListResource, endpoint="get_parent_item_list"),
    ]
