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


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class MetricMetaError(Error):
    status_code = 400
    code = 3316001
    name = _lazy("内置指标元数据错误")
    message_tpl = _lazy("指标元数据错误：{msg}")


class MetricMetaNotExist(MetricMetaError):
    code = 3316002
    name = _lazy("该内置指标不存在")
    message_tpl = _lazy("该内置指标不存在：{metric_id}")


class MetricIdError(MetricMetaError):
    code = 3316003
    name = _lazy("metric_id格式错误")
    message_tpl = _lazy("metric_id格式错误：{metric_id}")


class GetMetaParamError(MetricMetaError):
    code = 3316004
    name = _lazy("获取指标元信息参数错误")
    message_tpl = _lazy("获取指标元信息参数错误: metric_id和(result_table_id, metric_name)不可同时为空")


class MetricUnitIdInvalid(MetricMetaError):
    code = 3316005
    name = _lazy("指标单位id无效")
    message_tpl = _lazy("指标单位id无效：{unit_id}")


class MetricUnitCategoryNotExist(MetricMetaError):
    code = 3316005
    name = _lazy("指标单位id对应分类不存在")
    message_tpl = _lazy("指标单位id对应分类不存在：{unit_id}")
