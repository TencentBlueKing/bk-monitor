# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

from django.utils.translation import ugettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import TopoNodeKind
from apm_web.metrics import COMPONENT_LIST
from constants.apm import OtlpKey
from core.drf_resource import api


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

    unify_query_operator = {"method": "eq"}
    filter_params_operator = {"op": "="}

    @classmethod
    def is_component(cls, service_params):
        """判断是否是存储类节点"""
        if not service_params:
            return False

        return (
            service_params.get("kind")
            and service_params.get("category")
            and service_params.get("predicate_value")
            and service_params.get("kind") == TopoNodeKind.COMPONENT
        )

    @classmethod
    def get_component_belong_service(cls, name: str, predicate_value: str) -> str:
        """
        获取组件归属的服务名称
        如：{service_name}-mysql -> {service_name}
        """
        if not predicate_value:
            return name
        return name.replace(f"-{predicate_value}", "", 1)

    @classmethod
    def build_component_instance_filter_params(
        cls, bk_biz_id, app_name, filter_params, service_params, component_instance_id
    ):
        if not component_instance_id:
            return

        instance_id = component_instance_id[0]

        if not service_params or not cls.is_component(service_params):
            return

        rules = api.apm_api.query_discover_rules(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            filters={
                "topo_kind": service_params["kind"],
                "category_id": service_params["category"],
            },
        )

        if not rules:
            raise ValueError(f"拓扑发现规则为空")

        rule = rules[0]
        composition = instance_id.split(":")

        for index, key in enumerate(rule["instance_key"].split(",")):
            v = composition[index]
            if v:
                filter_params[key] = composition[index]

    @classmethod
    def get_component_instance_query_params(
        cls, bk_biz_id, app_name, kind, category, component_instance_id, exists_where, template, key_generator
    ):
        rules = api.apm_api.query_discover_rules(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            filters={
                "topo_kind": kind,
                "category_id": category,
            },
        )

        if not rules:
            raise ValueError(f"拓扑发现规则为空")

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
    def build_component_filter_params(
        cls, bk_biz_id, app_name, filter_params, service_params, component_instance_id=None
    ):
        """
        构件组件节点的查询参数
        filter_params: [{key: "", op: "", value:[]}]
        """
        if not service_params or not cls.is_component(service_params):
            return

        if component_instance_id:
            # 指定组件实例时 查询条件根据发现规则组装
            component_instance_filter = cls.get_component_instance_query_params(
                bk_biz_id,
                app_name,
                service_params["kind"],
                service_params["category"],
                component_instance_id,
                filter_params,
                template=cls.filter_params_operator,
                key_generator=lambda i: i,
            )

            filter_params += component_instance_filter
        else:
            # 没有指定组件实例 单独添加组件类型条件
            if service_params["category"] not in cls.component_filter_params_mapping:
                raise ValueError(_("不支持的分类: {}").format(service_params['category']))

            where = cls.component_filter_params_mapping[service_params["category"]]
            if service_params["predicate_value"]:
                filter_params.append(
                    json.loads(json.dumps(where).replace("{predicate_value}", service_params["predicate_value"]))
                )

        cls.replace_service(filter_params, service_params["predicate_value"])

    @classmethod
    def replace_service(cls, filter_params, predicate_value):
        has_service_condition = next(
            (i for i in filter_params if i["key"] == OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)),
            None,
        )
        if has_service_condition:
            filter_params.append(
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "op": "=",
                    "value": [
                        ComponentHandler.get_component_belong_service(
                            has_service_condition["value"][0], predicate_value
                        )
                    ],
                    "condition": "and",
                }
            )
            filter_params.remove(has_service_condition)

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
    def get_service_component_name_metrics(cls, app, start_time, end_time, metric_clz=None):
        """
        获取service服务下属的组件指标值
        返回 xxx-redis: {"request_count": "0"}
        """
        data = cls.get_service_component_metrics(app, start_time, end_time, metric_clz)

        res = {}
        for service_name, item in data.items():
            for k, v in item.items():
                name = f"{service_name}-{k}"
                res[name] = v

        return res

    @classmethod
    def get_service_component_instance_metrics(cls, app, kind, category, start_time, end_time):
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
            raise ValueError(f"拓扑发现规则为空")

        rule = rules[0]

        group_by_keys = [OtlpKey.get_metric_dimension_key(i) for i in rule["instance_key"].split(",")]

        res = {}
        # TODO 因为metrics通过|拼接，这里临时替换一下
        metrics = COMPONENT_LIST(app, group_key=group_by_keys, start_time=start_time, end_time=end_time)
        for k, v in metrics.items():
            res[k.replace("|", ":")] = v

        return res
