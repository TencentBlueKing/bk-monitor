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

from core.errors.bkmonitor import DataFlowError


class DataFlowNotExists(DataFlowError):
    code = 3361001
    name = _lazy("DataFlow不存在")
    message_tpl = _lazy("DataFlow{flow_id}不存在")


class DataFlowCreateFailed(DataFlowError):
    code = 3361002
    name = _lazy("DataFlow创建失败")
    message_tpl = _lazy("DataFlow创建失败，名称({flow_name})")


class DataFlowNodeCreateFailed(DataFlowError):
    code = 3361003
    name = _lazy("DataFlow节点创建失败")
    message_tpl = _lazy("DataFlow节点创建失败，节点名称({node_name}): {err}")


class DataFlowNodeUpdateFailed(DataFlowError):
    code = 3361004
    name = _lazy("DataFlow节点更新失败")
    message_tpl = _lazy("DataFlow节点更新失败，节点名称({node_name}): {err}")


class DataFlowStartFailed(DataFlowError):
    code = 3361005
    name = _lazy("DataFlow启动失败")
    message_tpl = _lazy("DataFlow({flow_name}({flow_id}))启动失败: {err}")
