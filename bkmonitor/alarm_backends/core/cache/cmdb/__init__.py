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


from .business import BusinessManager
from .host import HostIPManager, HostManager
from .module import ModuleManager
from .service_instance import ServiceInstanceManager
from .service_template import ServiceTemplateManager
from .set import SetManager
from .set_template import SetTemplateManager
from .topo import TopoManager

__all__ = [
    "BusinessManager",
    "HostManager",
    "ModuleManager",
    "SetManager",
    "ServiceInstanceManager",
    "TopoManager",
    "ServiceTemplateManager",
    "SetTemplateManager",
    "HostIPManager",
]

__doc__ = """
CMDB缓存模块

>>> from alarm_backends.core.cache.cmdb import BusinessManager, HostManager, ModuleManager, ServiceInstanceManager

# 刷新缓存
>>> BusinessManager.refresh()
>>> HostManager.refresh()
>>> ModuleManager.refresh()
>>> SetManager.refresh()
>>> ServiceInstanceManager.refresh()

>>> BusinessManager.get(bk_biz_id=2)   # 获取单个业务
>>> BusinessManager.all()  # 获取全部业务
>>> BusinessManager.keys()  # 获取业务ID列表
>>> HostManager.get(ip='127.0.0.1', bk_cloud_id=0)  # 获取单个主机
>>> HostManager.all()  # 获取主机列表
>>> ModuleManager.get(bk_module_id=1)  # 获取单个模块
>>> ServiceInstanceManager.get(service_instance_id=1)  # 获取单个服务实例ID
"""
