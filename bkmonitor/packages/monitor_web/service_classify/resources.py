"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import collections

from django.db.models import Q
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from monitor_web.commons.cc.utils import CmdbUtil
from monitor_web.models.collecting import CollectConfigMeta

from bkmonitor.models import ItemModel, StrategyModel
from bkmonitor.models.metric_list_cache import MetricListCache
from bkmonitor.views import serializers
from constants.strategy import TargetFieldType
from core.drf_resource import api
from core.drf_resource.base import Resource


class ServiceCategoryList(Resource):
    """
    分类管理页面的服务分类列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    @staticmethod
    def is_topo(target):
        # 对于策略配置，若node不为节点类型，则返回false
        if not target:
            return False
        if not target[0] or target[0][0].get("field") in [TargetFieldType.host_ip, TargetFieldType.host_target_ip]:
            return False
        return True

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        cc_manager = CmdbUtil(bk_biz_id)

        category_result = api.cmdb.search_service_category(bk_biz_id=bk_biz_id)

        # 处理CMDB的返回数据结构，生成category的字典
        category_mapping = collections.OrderedDict()
        for category in category_result:
            category_mapping[category["id"]] = category

        # 找到节点拓扑类型的采集配置和策略配置，并计算出它们包含的category_id
        config_list = list(
            CollectConfigMeta.objects.select_related("deployment_config").filter(
                bk_biz_id=bk_biz_id, deployment_config__target_node_type="TOPO"
            )
        )
        for config in config_list:
            config.category_ids = cc_manager.get_category_list(bk_biz_id, config.deployment_config.target_nodes)

        strategy_list = StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values("id")
        item_list = ItemModel.objects.filter(strategy_id__in=[strategy["id"] for strategy in strategy_list])
        for item in item_list:
            if self.is_topo(item.target):
                item.category_ids = cc_manager.get_category_list(bk_biz_id, item.target[0][0].get("value", []))
            else:
                item.category_ids = []

        # 从指标表里查询与采集配置相关联的所有指标
        metric_list = list(MetricListCache.objects.filter(~Q(collect_config=""), bk_tenant_id=bk_tenant_id))

        # 遍历category, 找到一二级标签，以及包含该category的采集配置数和策略配置数
        result = []
        for category_id, category in list(category_mapping.items()):
            # 过滤掉一级分类，不予显示
            if not category.get("bk_parent_id"):
                continue
            category_info = {"service_category_id": category_id, "second": category.get("name", "")}
            parent_info = category_mapping.get(category["bk_parent_id"], {})
            category_info["first"] = parent_info.get("name", "")

            # 获取服务分类相关联的采集配置和策略配置的数目
            # 该变量后续用来统计关联的指标数
            target_config_list = [x.id for x in config_list if category["id"] in x.category_ids]
            category_info["config_count"] = len(target_config_list)
            category_info["strategy_count"] = len([x for x in item_list if category["id"] in x.category_ids])

            # 获取服务分类相关联的指标
            category_info["metric_count"] = len(
                [x for x in metric_list if set(x.collect_config_ids) & set(target_config_list)]
            )
            result.append(category_info)

        return result
