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


import copy

import mock  # noqa
from mock import MagicMock, call, patch  # noqa

from alarm_backends.core.control.item import Item


class MockItem(Item):
    def __init__(self, item_config, strategy=None, data_sources=None):
        for key, value in list(item_config.items()):
            setattr(self, key, value)
        self.strategy = strategy
        self.data_sources = data_sources


class MockStrategy(object):
    def __init__(self, strategy_config):
        self.id = strategy_config["id"]
        self.config = strategy_config
        self.bk_biz_id = strategy_config["bk_biz_id"]
        self.scenario = strategy_config["scenario"]
        self.items = [MockItem(item_config, self) for item_config in strategy_config["items"]]

    @property
    def is_service_target(self):
        return self.config.get("scenario") in ("component", "service_module", "service_process")

    @property
    def is_host_target(self):
        return self.config.get("scenario") in ("os", "host_process")


class MockTopoNode(object):
    def __init__(self, id, **kwargs):
        self.id = id
        for key, value in list(kwargs.items()):
            setattr(self, key, value)


class MockHost(object):
    def __init__(self, info):
        self.id = "{}|{}".format(info["bk_host_innerip"], info["bk_cloud_id"])
        for key, value in list(info.items()):
            setattr(self, key, value)
        topo_link = {}
        for topo in info["topo"]:
            one = []
            for node in topo:
                node_id = node.pop("id")
                one.append(MockTopoNode(node_id, **node))
            topo_link.update({one[0].id: one})
        setattr(self, "topo_link", topo_link)


def generate_mock_hosts(host_info):
    host_info = copy.deepcopy(host_info)
    hosts = {}
    for host in host_info:
        mock_host = MockHost(host)
        hosts.update({mock_host.id: mock_host})
    return hosts


class MockServiceInstance(object):
    def __init__(self, info):
        for key, value in list(info.items()):
            setattr(self, key, value)
        topo_link = {}
        for topo in info["topo"]:
            one = []
            for node in topo:
                node_id = node.pop("id")
                one.append(MockTopoNode(node_id, **node))
            topo_link.update({one[0].id: one})
        setattr(self, "topo_link", topo_link)


def generate_mock_services(service_info):
    service_info = copy.deepcopy(service_info)
    services = {}
    for service in service_info:
        mock_service = MockServiceInstance(service)
        services.update({mock_service.service_instance_id: mock_service})
    return services


class MockCheckResult(object):
    def __init__(self, dimensions):
        self.dimensions = copy.deepcopy(dimensions)

    def get_dimensions_keys(self, **kwargs):
        return list(self.dimensions.keys())

    def get_dimension_by_key(self, service_type: str, strategy_id: int, item_id: int, dimensions_md5):
        return self.dimensions.get(dimensions_md5)

    def remove_dimension_by_key(self, service_type: str, strategy_id: int, item_id: int, dimensions_md5):
        self.dimensions.pop(dimensions_md5)
