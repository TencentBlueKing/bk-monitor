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


from alarm_backends.management.base.protocol import AbstractDispatchMixin
from alarm_backends.management.hashring import HashRing


class DefaultDispatchMixin(AbstractDispatchMixin):
    def dispatch_all_hosts(self, hosts):
        if isinstance(hosts, (list, tuple)):
            hosts = {host: 1 for host in hosts}

        targets = self.query_host_targets()

        host_targets_dict = {host: list() for host in hosts}
        if targets:
            host_ring = HashRing(hosts)
            for target in targets:
                host = host_ring.get_node(target)
                host_targets_dict[host].append(target)

        return targets, host_targets_dict

    def dispatch_for_host(self, hosts):
        targets, host_targets_dict = self.dispatch_all_hosts(hosts)

        return targets, host_targets_dict[self.host_addr]

    def dispatch_for_instance(self, hosts, instances, target_instance=None):
        if target_instance is None:
            target_instance = "{}/{}".format(self.host_addr, self.pid)

        _, host_targets = self.dispatch_for_host(hosts)
        instance_targets = []

        if target_instance in instances:
            targets = self.query_instance_targets(host_targets)

            if targets:
                index = instances.index(target_instance)
                for i, target in enumerate(targets):
                    if (i % len(instances)) == index:
                        instance_targets.append(target)

        return host_targets, instance_targets

    def query_instance_targets(self, host_targets):
        return host_targets
