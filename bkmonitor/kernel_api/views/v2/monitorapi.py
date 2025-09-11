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


import django_filters
from rest_framework import serializers

from monitor_api import views


class BaseAlarmViewSet(views.BaseAlarmViewSet):
    """
    基础告警

    list:获取基础告警列表

    count:基础告警计数

    """

    class BaseAlarmSerializer(views.BaseAlarmViewSet.serializer_class):
        pass

    serializer_class = BaseAlarmSerializer

    class BaseAlarmFilterSet(views.BaseAlarmViewSet.filterset_class):
        pass

    filterset_class = BaseAlarmFilterSet


class UserConfigViewSet(views.UserConfigViewSet):
    """
    用户配置信息

    count:用户配置信息计数

    partial_update:部分更新用户配置信息

    list:用户配置信息列表
    """

    class UserConfigSerializer(views.UserConfigViewSet.serializer_class):
        bk_username = serializers.CharField(source="username", help_text="用户名")

    serializer_class = UserConfigSerializer

    class UserConfigFilterSet(views.UserConfigViewSet.filterset_class):
        bk_username = django_filters.CharFilter(name="username", label="用户名")

    filterset_class = UserConfigFilterSet


class ApplicationConfigViewSet(views.ApplicationConfigViewSet):
    """
    业务配置信息

    count:业务配置信息计数

    create:创建业务配置信息
    """

    class ApplicationConfigSerializer(views.ApplicationConfigViewSet.serializer_class):
        bk_biz_id = serializers.IntegerField(source="cc_biz_id", help_text="业务ID")

    serializer_class = ApplicationConfigSerializer

    class ApplicationConfigFilterSet(views.ApplicationConfigViewSet.filterset_class):
        bk_biz_id = django_filters.NumberFilter(name="cc_biz_id", label="业务id")

    filterset_class = ApplicationConfigFilterSet


class GlobalConfigViewSet(views.GlobalConfigViewSet):
    """
    全局配置信息

    count:全局配置信息计数
    """

    class GlobalConfigSerializer(views.GlobalConfigViewSet.serializer_class):
        pass

    serializer_class = GlobalConfigSerializer

    class GlobalConfigFilterSet(views.GlobalConfigViewSet.filterset_class):
        pass

    filterset_class = GlobalConfigFilterSet


class SnapshotHostIndexViewSet(views.SnapshotHostIndexViewSet):
    class SnapshotHostIndexSerializer(views.SnapshotHostIndexViewSet.serializer_class):
        pass

    serializer_class = SnapshotHostIndexSerializer

    class SnapshotHostIndexFilterSet(views.SnapshotHostIndexViewSet.filterset_class):
        pass

    filterset_class = SnapshotHostIndexFilterSet
