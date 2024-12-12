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
from abc import ABC
from enum import Enum

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class DataSourceSerializer(serializers.Serializer, ABC):
    class DataType(Enum):
        time_series = _("时序型数据")
        table = _("表格")

    datasource = serializers.CharField(label="数据源")
    data_type = serializers.ChoiceField(label="数据类型", choices=tuple((r.name, r.value) for r in DataType))


class TimeSeriesDataSourceSerializer(DataSourceSerializer):
    datasource = "time_series"
    data_type = "time_series"


class LogDataSourceSerializer(DataSourceSerializer):
    datasource = "log"
    data_type = "table"


class SceneViewSerializer(serializers.Serializer):
    class VariableSerializer(serializers.Serializer):
        field = serializers.CharField()
        where = serializers.ListField(child=serializers.DictField())

    class RowSerializer(serializers.Serializer):
        class PanelSerializer(serializers.Serializer):
            id = serializers.CharField()
            title = serializers.CharField()
            hidden = serializers.BooleanField()

        id = serializers.CharField()
        title = serializers.CharField()
        panels = serializers.ListField(child=PanelSerializer())

    bk_biz_id = serializers.IntegerField(label="业务ID")
    scene_id = serializers.CharField(label="场景ID", max_length=32)
    id = serializers.CharField(label="视图ID", max_length=32)
    name = serializers.CharField(label="名称", max_length=64)
    variables = serializers.ListField(label="变量配置", allow_empty=True, child=RowSerializer())
    type = serializers.ChoiceField(label="视图类型", choices=(("overview", _("概览")), ("detail", _("详情"))))
    mode = serializers.ChoiceField(label="运行模式", choices=(("tile", _("平铺")), ("custom", _("自定义"))))
    order = serializers.ListField(label="排序配置(平铺模式专用)", default=list)
    panels = serializers.ListField(label="图表配置", default=list)
    options = serializers.DictField(label="视图配置", default=dict)
