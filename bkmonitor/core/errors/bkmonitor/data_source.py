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


class DataSourceError(Error):
    code = 3325000
    name = _lazy("公共模块bkmonitor.data_source错误")
    message_tpl = _lazy("公共模块bkmonitor.data_source错误：{msg}")


class CmdbLevelValidateError(DataSourceError):
    code = 3325001
    name = _lazy("cmdb节点聚合配置校验失败")
    message_tpl = _lazy('cmdb聚合不支持多指标计算，请去除维度和条件中的"节点类型"及"节点名称"字段，或使用单指标')


class FunctionNotFoundError(DataSourceError):
    code = 3325002
    name = _lazy("计算函数不存在")
    message_tpl = _lazy("计算函数{func_name}不存在")


class ParamRequiredError(DataSourceError):
    code = 3325003
    name = _lazy("参数为必填项")
    message_tpl = _lazy("计算函数{func_name}的参数{param_name}是必填项")


class MultipleTimeAggregateFunctionError(DataSourceError):
    code = 3325004
    name = _lazy("多个时间聚合函数")
    message_tpl = _lazy("不能存在多个时间聚合函数")


class FunctionNotSupportedError(DataSourceError):
    code = 3325005
    name = _lazy("计算函数不支持")
    message_tpl = _lazy("函数{func_name}不支持在多指标计算中使用")
