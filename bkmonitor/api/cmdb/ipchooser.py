"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkm_ipchooser.api import AbstractBkApi
from bkmonitor.commons.tools import batch_request

from . import client


class IpChooserApi(AbstractBkApi):
    @staticmethod
    def search_cloud_area(params: dict = None):
        return client.search_cloud_area(params)

    @staticmethod
    def search_business(params: dict = None):
        return client.search_business(params)

    @staticmethod
    def search_biz_inst_topo(params: dict = None):
        return client.search_biz_inst_topo(params)

    @staticmethod
    def get_biz_internal_module(params: dict = None):
        return client.get_biz_internal_module(params)

    @staticmethod
    def find_host_topo_relation(params: dict = None):
        return client.find_host_topo_relation(params)

    @staticmethod
    def list_biz_hosts(params: dict = None):
        return client.list_biz_hosts(params)

    @staticmethod
    def bulk_list_biz_hosts(params: dict = None):
        return batch_request(client.list_biz_hosts, params)

    @staticmethod
    def list_host_total_mainline_topo(params: dict = None):
        return client.get_mainline_object_topo(params)

    @staticmethod
    def get_agent_status(params: dict = None):
        from core.drf_resource import api

        return api.node_man.ipchooser_host_detail(params)

    @staticmethod
    def list_service_template(params: dict = None):
        """查询服务模板"""
        return batch_request(client.list_service_template, params, limit=200)

    @staticmethod
    def list_set_template(params: dict = None):
        """查询集群模板"""
        return batch_request(client.list_set_template, params, limit=200)

    @staticmethod
    def search_set(params: dict = None):
        """查询集群"""
        return client.search_set(params)

    @staticmethod
    def bulk_search_set(params: dict = None):
        """批量查询集群"""
        return batch_request(client.search_set, params)

    @staticmethod
    def search_module(params: dict = None):
        """查询模块"""
        return client.search_module(params)

    @staticmethod
    def bulk_search_module(params: dict = None):
        """批量查询模块"""
        return batch_request(client.search_module, params)

    @staticmethod
    def search_dynamic_group(params: dict = None):
        """查询动态分组"""
        return client.search_dynamic_group(params)

    @staticmethod
    def execute_dynamic_group(params: dict = None):
        """执行动态分组"""
        return client.execute_dynamic_group(params)

    @staticmethod
    def find_host_by_service_template(params: dict = None):
        """分页查询服务模板的主机"""
        return client.find_host_by_service_template(params)

    @staticmethod
    def bulk_find_host_by_service_template(params: dict = None):
        """批量查询服务模板的主机"""
        return batch_request(client.find_host_by_service_template, params)

    @staticmethod
    def find_host_by_set_template(params: dict = None):
        """分页查询集群模板的主机"""
        return client.find_host_by_set_template(params)

    @staticmethod
    def bulk_find_host_by_set_template(params: dict = None):
        """批量查询集群模板的主机"""
        return batch_request(client.find_host_by_set_template, params)

    @staticmethod
    def find_topo_node_paths(params: dict = None):
        """查询拓扑节点所在的拓扑路径"""
        return client.find_topo_node_paths(params)

    @staticmethod
    def list_service_category(params: dict = None):
        """查询服务分类列表"""
        return client.list_service_category(params)

    @staticmethod
    def list_service_instance_detail(params: dict = None):
        """查询服务实例列表"""
        return client.list_service_instance_detail(params)

    @staticmethod
    def list_service_instance_by_set_template(params: dict = None):
        """查询集群模板下的服务实例列表"""
        return client.list_service_instance_by_set_template(params)
