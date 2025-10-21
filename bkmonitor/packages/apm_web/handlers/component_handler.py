"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import TopoNodeKind
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metrics import COMPONENT_LIST
from bkmonitor.utils.cache import CacheType, using_cache
from constants.apm import OtlpKey
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class ComponentHandler:
    component_filter_params_mapping = {
        "db": {
            "key": OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM),
            "op": "=",
            "value": ["{predicate_value}"],
            "condition": "and",
        },
        "messaging": {
            "key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
            "op": "=",
            "value": ["{predicate_value}"],
            "condition": "and",
        },
    }
    filed_to_dimension_mapping = {
        "attributes.db.system": "db_system",
        "attributes.messaging.system": "messaging_system",
        "attributes.net.peer.name": "net_peer_name",
        "attributes.net.peer.ip": "net_peer_ip",
        "attributes.net.peer.port": "net_peer_port",
    }

    unify_query_operator = {"method": "eq"}
    filter_params_operator = {"op": "="}

    @classmethod
    def is_component_by_node(cls, node_info):
        """通过 topo_node 节点的信息判断是否为组件类节点"""
        if not node_info:
            return False
        return node_info.get("extra_data", {}).get("kind") == TopoNodeKind.COMPONENT

    @classmethod
    @using_cache(CacheType.APM(60 * 10))
    def is_component(cls, bk_biz_id, app_name, service_name):
        """判断是否是存储类节点"""
        try:
            response = api.apm_api.query_topo_node(bk_biz_id=bk_biz_id, app_name=app_name, topo_key=service_name)
            if not response:
                return False
            return cls.is_component_by_node(response[0])
        except BKAPIError as e:
            logger.warning(
                f"[ComponentHandler] query topo node failed, ({bk_biz_id}){app_name}: {service_name}, exception: {e}",
            )
            return False

    @classmethod
    def generate_component_name(cls, service_name, predicate_value):
        """获取组件类服务名称"""
        return f"{service_name}-{predicate_value}"

    @classmethod
    def get_component_belong_service(cls, name: str) -> str:
        """
        获取组件归属的服务名称 需要先确保此服务名城为组件类服务
        如：{service_name}-mysql -> {service_name}
        """
        # 去除最后一个 "-" 符号
        return name.rsplit("-", 1)[0]

    @classmethod
    def get_component_belong_predicate_value(cls, name: str) -> str:
        """
        获取组件归属的组件名称
        如：{service_name}-mysql -> mysql
        """
        # 去除最后一个 "-" 符号
        return name.rsplit("-", 1)[-1]

    @classmethod
    def get_component_predicate_value(cls, node):
        return node.get("extra_data", {}).get("predicate_value")

    @classmethod
    def get_component_instance_query_params(
        cls, bk_biz_id, app_name, kind, category, component_instance_id, exists_where, template, key_generator
    ):
        """获取组件的 filter_params 参数"""
        rules = api.apm_api.query_discover_rules(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            filters={
                "topo_kind": kind,
                "category_id": category,
            },
        )

        if not rules:
            raise ValueError("拓扑发现规则为空")

        rule = rules[0]
        res = []

        if isinstance(component_instance_id, list):
            for instance_index, instance_id in enumerate(component_instance_id):
                tmp_res = []
                composition = instance_id.split(":")

                for index, key in enumerate(rule["instance_key"].split(",")):
                    v = composition[index]
                    if v:
                        condition = "and"

                        if instance_index != 0 and index == 0:
                            condition = "or"

                        tmp_res.append(
                            {
                                "key": key_generator(key),
                                "value": [v],
                                "condition": condition,
                                **template,
                            }
                        )

                if instance_index != 0:
                    res += tmp_res + exists_where
                else:
                    res += tmp_res

        else:
            composition = component_instance_id.split(":")

            for index, key in enumerate(rule["instance_key"].split(",")):
                v = composition[index]
                if v:
                    item = {
                        "key": key_generator(key),
                        "value": [v],
                        "condition": "and",
                        **template,
                    }
                    if item in exists_where:
                        continue

                    res.append(item)

        return res

    @classmethod
    def get_component_instance_query_dict(cls, bk_biz_id, app_name, kind, category, component_instance_id):
        """
        获取组件的 filter_dict 参数 (附带组件实例 Id)
        只支持传入单个 组件实例ID(component_instance_id)
        """
        rules = api.apm_api.query_discover_rules(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            filters={
                "topo_kind": kind,
                "category_id": category,
            },
        )

        if not rules:
            raise ValueError("拓扑发现规则为空")

        rule = rules[0]
        res = {}

        composition = component_instance_id.split(":")
        for index, key in enumerate(rule["instance_key"].split(",")):
            v = composition[index]
            if v:
                res[key] = v
        return res

    @classmethod
    def build_component_filter(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        filter_params: list[dict[str, Any]],
        component_instance_id: list[str] | str | None,
    ) -> Q:
        """构建组件查询条件"""
        cls.build_component_filter_params(
            bk_biz_id,
            app_name,
            service_name,
            filter_params,
            component_instance_id=component_instance_id,
        )
        q: Q = Q()
        for filter_param in filter_params:
            q &= Q(**{filter_param["key"]: filter_param["value"]})
        return q

    @classmethod
    def get_component_metric_filter_params(cls, bk_biz_id, app_name, service_name, component_instance_id=None):
        """构建组件节点的指标查询参数"""
        # 指标查询里面不一定所有 attributes 都是维度 这里如果包含了实例 id 尽量将有维度的都放入条件中

        filter_params = []
        cls.build_component_filter_params(
            bk_biz_id,
            app_name,
            service_name,
            filter_params,
            component_instance_id,
        )
        res = []
        for item in filter_params:
            dimension = cls.filed_to_dimension_mapping.get(item["key"])
            if not dimension:
                continue
            res.append({"key": dimension, "method": "eq", "value": item["value"]})

        return res

    @classmethod
    def build_component_filter_params(
        cls, bk_biz_id, app_name, service_name, filter_params, component_instance_id=None
    ):
        """
        构件组件节点的APM API查询参数
        filter_params: [{key: "", op: "", value:[]}]
        """
        component_node = ServiceHandler.get_node(bk_biz_id, app_name, service_name, raise_exception=False)

        if not cls.is_component_by_node(component_node):
            return

        extra_data = component_node["extra_data"]
        if component_instance_id:
            # 指定组件实例时 查询条件根据发现规则组装
            component_instance_filter = cls.get_component_instance_query_params(
                bk_biz_id,
                app_name,
                extra_data["kind"],
                extra_data["category"],
                component_instance_id,
                filter_params,
                template=cls.filter_params_operator,
                key_generator=lambda i: i,
            )

            filter_params += component_instance_filter
        else:
            # 没有指定组件实例 单独添加组件类型条件
            if extra_data["category"] not in cls.component_filter_params_mapping:
                raise ValueError(_("不支持查询此分类的统计数据: {}").format(extra_data["category"]))

            where = cls.component_filter_params_mapping[extra_data["category"]]
            if extra_data["predicate_value"]:
                filter_params.append(
                    json.loads(
                        json.dumps(where).replace(
                            "{predicate_value}",
                            extra_data["predicate_value"],
                        )
                    )
                )

        cls.replace_or_add_service_filter(service_name, filter_params)

    @classmethod
    def get_dimension_key(cls, node):
        """获取节点的维度 key"""
        category = node["extra_data"]["category"]
        if category not in cls.component_filter_params_mapping:
            raise ValueError(_("不支持查询此分类的统计数据: {}").format(category))
        return OtlpKey.get_metric_dimension_key(cls.component_filter_params_mapping[category]["key"])

    @classmethod
    def get_predicate_value_from_flow_metric_category_value(cls, category_value):
        """从 flow 指标的 category_value 维度中获取 predicate_value 的值"""
        return category_value.rsplit("-")[-1]

    @classmethod
    def replace_or_add_service_filter(cls, service_name, filter_params):
        has_service_condition = next(
            (i for i in filter_params if i["key"] == OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)),
            None,
        )
        if has_service_condition:
            # 如果已经有服务名称过滤 则替换服务名称

            filter_params.remove(has_service_condition)

        filter_params.append(
            {
                "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                "op": "=",
                "value": [ComponentHandler.get_component_belong_service(service_name)],
                "condition": "and",
            }
        )

    @classmethod
    def get_service_component_metrics(cls, app, start_time, end_time, metric_clz=None, metric_handler_cls: list = None):
        """
        获取service服务下属的组件指标值
        """

        if not metric_clz:
            metric_clz = COMPONENT_LIST

        if metric_handler_cls:
            metric_info = metric_clz(
                app, start_time=start_time, end_time=end_time, metric_handler_cls=metric_handler_cls
            )
        else:
            metric_info = metric_clz(app, start_time=start_time, end_time=end_time)

        res = {}
        for key, info in metric_info.items():
            composition = key.split("|")
            service_name = composition[0]

            for system in composition[1:]:
                if system:
                    res.setdefault(service_name, {})[system] = info
                    break

        return res

    @classmethod
    def get_service_component_instance_metrics(cls, app, service_name, kind, category, start_time, end_time):
        """
        获取组件实例的指标值
        """

        rules = api.apm_api.query_discover_rules(
            bk_biz_id=app.bk_biz_id,
            app_name=app.app_name,
            filters={
                "topo_kind": kind,
                "category_id": category,
            },
        )

        if not rules:
            raise ValueError("拓扑发现规则为空")

        rule = rules[0]

        group_by_keys = [OtlpKey.get_metric_dimension_key(i) for i in rule["instance_key"].split(",")]

        res = {}
        # 组件类服务除了 group_by 实例字段 还需要固定 service_name
        metrics = COMPONENT_LIST(
            app,
            group_key=group_by_keys,
            start_time=start_time,
            end_time=end_time,
            where=[{"key": "service_name", "method": "eq", "value": [service_name]}],
        )
        for k, v in metrics.items():
            res[k.replace("|", ":")] = v

        return res
