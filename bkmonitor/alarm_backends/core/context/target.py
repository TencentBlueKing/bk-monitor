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
from typing import Dict, List

from django.utils.functional import cached_property

from alarm_backends.core.cache.cmdb import (
    BusinessManager,
    HostManager,
    ModuleManager,
    ServiceInstanceManager,
    SetManager,
)
from alarm_backends.core.context import BaseContextObject
from api.cmdb.define import Business


class MultiInstanceDisplay:
    def __init__(self, instances):
        self.instances = instances

    def __getattr__(self, item):
        values = []
        for inst in self.instances:
            value = getattr(inst, item, None)

            if value is None:
                continue

            if isinstance(value, (str, float, int)):
                values.append(str(value))
            elif isinstance(value, list) and value and isinstance(value[0], (str, float, int)):
                values.extend([str(v) for v in value])
        return ",".join(values)


class Target(BaseContextObject):
    """
    CMDB目标对象
    """

    @cached_property
    def host(self):
        """
        主机对象
        """
        if not self.parent.alert:
            return

        event = self.parent.alert.event

        try:
            if event.bk_host_id:
                result = HostManager.get_by_id(event.bk_host_id)
            else:
                result = HostManager.get(ip=event.ip, bk_cloud_id=event.bk_cloud_id)
        except Exception:
            # 不存在就接返回
            return

        if not result:
            return
        result.operator_string = ",".join(result.operator)
        result.bk_bak_operator_string = ",".join(result.bk_bak_operator)
        module_names = set()
        set_names = set()
        for topo_id, topo_link in result.topo_link.items():
            if topo_id.startswith("module|") and topo_link:
                module_names.add(topo_link[0].bk_inst_name)
                set_names.add(topo_link[1].bk_inst_name)
        result.module_string = ",".join(module_names)
        result.set_string = ",".join(set_names)
        return result

    @cached_property
    def hosts(self) -> MultiInstanceDisplay:
        hosts = []
        for alert in self.parent.alerts:
            event = alert.event

            try:
                if event.bk_host_id:
                    host = HostManager.get_by_id(event.bk_host_id)
                else:
                    host = HostManager.get(ip=event.ip, bk_cloud_id=event.bk_cloud_id)
            except Exception:
                continue

            if host:
                host.operator_string = host.operator
                host.bk_bak_operator_string = host.bk_bak_operator
                module_names = set()
                set_names = set()
                for topo_id, topo_link in host.topo_link.items():
                    if topo_id.startswith("module|") and topo_link:
                        module_names.add(topo_link[0].bk_inst_name)
                        set_names.add(topo_link[1].bk_inst_name)
                host.module_string = module_names
                host.set_string = set_names
                hosts.append(host)

        return MultiInstanceDisplay(hosts)

    @cached_property
    def process(self):
        """
        进程对象
        :rtype: Process
        """
        return {process["bk_func_name"]: process for process in self.processes}

    @cached_property
    def processes(self) -> List[Dict]:
        """
        进程列表
        """
        processes = []
        if self.service_instance:
            processes = self.service_instance.process_instances or []
        elif self.host:
            service_instance_ids = ServiceInstanceManager.get_service_instance_id_by_host(self.host.bk_host_id)
            for service_instance_id in service_instance_ids:
                service_instance = ServiceInstanceManager.get(service_instance_id)
                if service_instance and service_instance.process_instances:
                    processes.extend(service_instance.process_instances)
        return [process["process"] for process in processes]

    @cached_property
    def service_instance(self):
        """
        实例对象
        """
        if not self.parent.alert:
            return {}
        event = self.parent.alert.event

        if event.bk_service_instance_id:
            return ServiceInstanceManager.get(event.bk_service_instance_id)

    @cached_property
    def service_instances(self) -> MultiInstanceDisplay:
        """
        多个实例对象
        """
        instances = []
        for alert in self.parent.alerts:
            event = alert.event

            if not event.bk_service_instance_id:
                continue

            instance = ServiceInstanceManager.get(event.bk_service_instance_id)

            if instance:
                instances.append(instance)

        return MultiInstanceDisplay(instances)

    @property
    def service(self):
        """
        实例对象
        """
        return self.service_instance

    @property
    def services(self):
        """
        多个实例对象
        """
        return self.service_instances

    @cached_property
    def business(self):
        """
        业务对象
        """
        bk_biz_id = self.parent.alert.event.bk_biz_id or self.parent.action.bk_biz_id

        biz = BusinessManager.get(bk_biz_id)
        if not biz:
            biz = Business(bk_biz_id=bk_biz_id)

        biz.bk_biz_developer_string = ",".join(biz.bk_biz_developer)
        biz.bk_biz_maintainer_string = ",".join(biz.bk_biz_maintainer)
        biz.bk_biz_tester_string = ",".join(biz.bk_biz_tester)
        biz.bk_biz_productor_string = ",".join(biz.bk_biz_productor)
        biz.operator_string = ",".join(biz.operator)
        return biz

    @cached_property
    def sets(self):
        if not self.host:
            return []
        bk_sets = []
        for bk_set_id in self.host.bk_set_ids:
            biz_set = SetManager.get(bk_set_id)
            if biz_set:
                bk_sets.append(SetManager.get(bk_set_id))
        return bk_sets

    @cached_property
    def modules(self):
        if not self.host:
            return []
        bk_modules = []
        for bk_module_id in self.host.bk_module_ids:
            bk_module = ModuleManager.get(bk_module_id)
            if bk_module:
                # 可能出现缓存不存在的情况，仅缓存存在的情况下才进行记录
                bk_modules.append(bk_module)
        return bk_modules
