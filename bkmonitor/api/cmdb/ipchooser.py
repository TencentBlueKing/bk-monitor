"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkm_ipchooser.api import AbstractBkApi
from bkm_ipchooser.tools import service_instance_cache
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.nodeman import host_queries
from core.drf_resource import api

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
        return host_queries.details(params)

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
    def get_service_instance_module_index(bk_biz_id: int) -> dict[int, list[int]] | None:
        """
        查询「模块 -> 服务实例 ID」索引，仅含 ID 不含明细

        优先读现成索引；未命中时借 get_service_instance_by_biz 拉取明细后构建，
        该函数带 1 小时 TTL 的缓存，并由每分钟一次的 cron 分环刷新（单业务约 10 分钟
        一轮），且该函数内部会顺带写入索引，因此回退路径通常不是真正的冷请求。

        索引命中时只读 ID 即返回，不加载任何明细。回退路径已经持有全量明细，
        顺带回填列表侧明细缓存，使紧随其后的根节点实例列表直接复用，
        避免同一次打开把同一份全量明细拉两轮。

        回填只使用远短于列表侧自拉的时效（见 service_instance_cache.BACKFILL_CACHE_TIMEOUT）：
        60 秒的意义不是压缩陈旧窗口（cron 正常时来源本就只有几分钟滞后），而是让这份
        副本只服务本次打开的紧邻请求，之后重新取数，不吃「看起来还新鲜」的旧缓存。
        """
        module_index = api.cmdb.ServiceInstanceModuleIndex.get(bk_biz_id)
        if module_index is None:
            service_instances = api.cmdb.get_service_instance_by_biz(bk_biz_id)
            service_instance_cache.backfill_details(bk_biz_id, service_instances)
            module_index = api.cmdb.ServiceInstanceModuleIndex.build(service_instances)
        # 索引持久化时以 str 作为模块 ID 键，此处统一转回 int，便于上层按 bk_inst_id 直接查找
        return {int(module_id): service_instance_ids for module_id, service_instance_ids in module_index.items()}

    @staticmethod
    def refresh_service_instance_module_index(bk_biz_id: int, service_instances: list[dict]) -> None:
        """
        用列表侧刚拉取的全量明细刷新模块索引，使树与列表指向同一份快照

        树统计在明细缓存未命中时读的就是这份索引。若列表自拉明细后只更新明细缓存、
        不更新索引，索引会继续停留在 cron 上一次刷新的状态（cache_cmdb_resource
        每分钟跑、按业务分环，单业务约 10 分钟一轮），于是明细缓存一过期，
        树就拿着旧索引计数，与列表刚展示的条数对不上。
        这里不吞异常：是否「失败不阻塞主流程」由调用方决定。
        """
        api.cmdb.ServiceInstanceModuleIndex.set(bk_biz_id, service_instances)

    @staticmethod
    def list_service_instance_by_set_template(params: dict = None):
        """查询集群模板下的服务实例列表"""
        return client.list_service_instance_by_set_template(params)
