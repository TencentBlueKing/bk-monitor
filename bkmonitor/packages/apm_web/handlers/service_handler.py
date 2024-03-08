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
import copy
import logging
import operator
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _

from apm_web.constants import (
    APM_APPLICATION_DEFAULT_METRIC,
    APM_APPLICATION_METRIC,
    APM_APPLICATION_METRIC_DEFAULT_EXPIRED_TIME,
    ApdexCategoryMapping,
    CategoryEnum,
    CustomServiceMatchType,
    TopoNodeKind,
)
from apm_web.metrics import APPLICATION_LIST
from apm_web.models import ApdexServiceRelation, ApplicationCustomService
from apm_web.utils import group_by
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import api

logger = logging.getLogger(__name__)


class ServiceHandler:
    @classmethod
    def build_cache_key(cls, application):
        return APM_APPLICATION_METRIC.format(
            settings.PLATFORM, settings.ENVIRONMENT, application.get("bk_biz_id"), application.get("application_id")
        )

    @classmethod
    def refresh_application_cache_data(cls, applications):
        service_count_mapping = cls.batch_query_service_count(applications)
        metric_data = APPLICATION_LIST(applications)

        data_map = {}
        for app in applications:
            application_id = str(app["application_id"])
            app_metric = metric_data.get(application_id, copy.deepcopy(APM_APPLICATION_DEFAULT_METRIC))
            app_metric["service_count"] = service_count_mapping.get(application_id, 0)
            key = cls.build_cache_key(app)
            data_map[key] = app_metric
        cache.set_many(data_map, timeout=APM_APPLICATION_METRIC_DEFAULT_EXPIRED_TIME)

    @classmethod
    def batch_query_service_count(cls, applications):
        def get_service_count_by_application(item_id, application):
            return {str(item_id): len(cls.list_services(application))}

        futures = []
        pool = ThreadPool()
        for app in applications:
            futures.append(pool.apply_async(get_service_count_by_application, args=(app["application_id"], app)))

        service_map = defaultdict(dict)
        for future in futures:
            try:
                service_map.update(future.get())
            except Exception as e:
                logger.exception(e)
        return service_map

    @classmethod
    def list_services(cls, application):
        """
        获取应用的服务列表 =
            已发现的服务(service, remote_service)
            + 未发现的自定义服务
            + 服务下的组件(component)
            + 无 Trace 上报的 Profiling 服务
        """
        if isinstance(application, dict):
            bk_biz_id = application["bk_biz_id"]
            app_name = application["app_name"]
        else:
            bk_biz_id = application.bk_biz_id
            app_name = application.app_name

        resp = api.apm_api.query_topo_node({"bk_biz_id": bk_biz_id, "app_name": app_name})

        # step1: 获取已发现的服务
        trace_services = [item for item in resp if item["extra_data"]["kind"] in ["service", "remote_service"]]
        for r in trace_services:
            r["from_service"] = r["topo_key"]

        found_service_names = [i["topo_key"] for i in trace_services if i["extra_data"]["kind"] == "remote_service"]
        # step2: 额外补充手动配置的自定义服务
        custom_services = ApplicationCustomService.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, match_type=CustomServiceMatchType.MANUAL
        )
        for cs in custom_services:
            topo_key = f"{cs.type}:{cs.name}"
            if topo_key in found_service_names:
                continue

            trace_services.append(
                {
                    "topo_key": topo_key,
                    "extra_data": {
                        "category": cs.type,
                        "kind": "remote_service",
                        "predicate_value": "",
                        "service_language": "",
                        "instance": {},
                    },
                    "from_service": topo_key,
                }
            )

        # step3: 计算服务下组件
        trace_services += cls.list_service_components(bk_biz_id, app_name, resp)

        # step4: 获取 Profile 服务
        profile_services = api.apm_api.query_profile_services_detail(**{"bk_biz_id": bk_biz_id, "app_name": app_name})

        # step5: 将 Profile 服务和 Trace 服务重名的结合
        return cls._combine_profile_trace_service(trace_services, profile_services)

    @classmethod
    def _combine_profile_trace_service(cls, trace_services, profile_services):
        """合并 TraceService 和 ProfileService"""
        res = copy.deepcopy(trace_services)
        trace_names_mapping = group_by(res, operator.itemgetter("topo_key"))
        visited = []
        for profile_svr in profile_services:
            if profile_svr["name"] not in trace_names_mapping and profile_svr["name"] not in visited:
                # 如果没有 Trace 数据 则单独开一个服务
                res.append(
                    {
                        "topo_key": profile_svr["name"],
                        "extra_data": {
                            "category": CategoryEnum.PROFILING,
                            "kind": "profiling",
                            "predicate_value": None,
                            "service_language": None,
                            "instance": {},
                        },
                    }
                )
                visited.append(profile_svr["name"])

        return res

    @classmethod
    def list_service_components(cls, bk_biz_id, app_name, services):
        topo_keys = [i["topo_key"] for i in services]
        service_components = api.apm_api.query_topo_relation(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            filters={"from_topo_key__in": topo_keys, "to_topo_key_kind": TopoNodeKind.COMPONENT},
        )

        # 根据service_name分类 相同的category合为一类展示
        from_keys_mapping = group_by(service_components, operator.itemgetter("from_topo_key"))

        service_component_mappings = {}
        for from_topo_key, to_components in from_keys_mapping.items():
            predicate_value_mappings = {}
            for to_component in to_components:
                to_topo_key = to_component["to_topo_key"]
                to_topo_kind = to_component["to_topo_key_kind"]
                to_topo_category = to_component["to_topo_key_category"]

                key_composition = to_topo_key.split(":")
                # 兼容旧版topo_relation中间件发现逻辑生成了无:拼接的数据
                if len(key_composition) <= 1:
                    continue

                predicate_value = key_composition[1]
                predicate_value_mappings.setdefault(predicate_value, []).append(
                    {
                        "topo_key": to_topo_key,
                        "extra_data": {
                            "category": to_topo_category,
                            "kind": to_topo_kind,
                            "predicate_value": predicate_value,
                            "service_language": "",
                            "instance": {},
                        },
                    }
                )

            service_component_mappings[from_topo_key] = predicate_value_mappings

        res = []
        for from_service, component_mappings in service_component_mappings.items():
            for predicate_value, items in component_mappings.items():
                res.append(
                    {
                        "topo_key": f"{from_service}-{predicate_value}",
                        "extra_data": {
                            "category": items[0]["extra_data"]["category"],
                            "kind": items[0]["extra_data"]["kind"],
                            "predicate_value": predicate_value,
                            "service_language": "",
                            "instance": {},
                        },
                        "from_service": from_service,
                    }
                )

        return res

    @classmethod
    def is_remote_service(cls, bk_biz_id, app_name, node_topo_key) -> bool:
        """判断topo_key是否是远程服务"""
        nodes = api.apm_api.query_topo_node(bk_biz_id=bk_biz_id, app_name=app_name, topo_key=node_topo_key)

        if nodes:
            return nodes[0]["extra_data"]["kind"] == TopoNodeKind.REMOTE_SERVICE

        return False

    @classmethod
    def get_service_node_detail(cls, bk_biz_id, app_name, node_topo_key):
        """获取服务详细信息"""
        nodes = api.apm_api.query_topo_node(bk_biz_id=bk_biz_id, app_name=app_name, topo_key=node_topo_key)

        if nodes:
            return nodes[0]

        return None

    @classmethod
    def get_apdex_relation_info(cls, bk_biz_id, app_name, service_name, nodes=None):
        """
        获取服务apdex配置
        """
        if not nodes:
            nodes = api.apm_api.query_topo_node(bk_biz_id=bk_biz_id, app_name=app_name)

        instance = ApdexServiceRelation.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        ).first()

        if not instance:
            # 填充默认值 判断服务类型得出Apdex类型
            apdex_key = cls.get_service_apdex_key(bk_biz_id, app_name, service_name, nodes)
            apdex_value = ApdexCategoryMapping.get_apdex_default_value_by_category(apdex_key)

            instance = ApdexServiceRelation.objects.create(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                service_name=service_name,
                apdex_key=apdex_key,
                apdex_value=apdex_value,
            )

        return instance

    @classmethod
    def get_service_apdex_key(cls, bk_biz_id, app_name, service_name, nodes=None):
        if not nodes:
            nodes = api.apm_api.query_topo_node(bk_biz_id=bk_biz_id, app_name=app_name)

        node = next((i for i in nodes if i["topo_key"] == service_name), None)
        if not node:
            raise ValueError(_("此服务不存在或暂时未被发现"))

        category = node["extra_data"]["category"]
        return ApdexCategoryMapping.get_apdex_by_category(category)
