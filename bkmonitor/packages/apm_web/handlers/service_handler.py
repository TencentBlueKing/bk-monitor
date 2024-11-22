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
from elasticsearch_dsl import Q
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import (
    APM_APPLICATION_DEFAULT_METRIC,
    APM_APPLICATION_METRIC,
    APM_APPLICATION_METRIC_DEFAULT_EXPIRED_TIME,
    ApdexCategoryMapping,
    CategoryEnum,
    CustomServiceMatchType,
    DataStatus,
    TopoNodeKind,
)
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.metric_handler import RequestCountInstance, ServiceFlowCount
from apm_web.metrics import APPLICATION_LIST
from apm_web.models import ApdexServiceRelation, Application, ApplicationCustomService
from bkmonitor.utils import group_by
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import get_datetime_range
from constants.apm import OtlpKey, TelemetryDataType
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class ServiceHandler:
    # 避免数据量过大 只查询30分钟内数据 超过30分钟数据由拓扑发现获取
    QUERY_FLOW_MAX_TIME_RANGE = 30

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
            is_enabled_profiling = application.get("is_enabled_profiling", False)
        else:
            bk_biz_id = application.bk_biz_id
            app_name = application.app_name
            is_enabled_profiling = application.is_enabled_profiling

        trace_services = cls.list_nodes(bk_biz_id, app_name)

        # step1: 获取已发现的服务
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
                }
            )

        # step3: 计算服务下组件

        # step4: 获取 Profile 服务
        profile_services = []
        if is_enabled_profiling:
            profile_services = api.apm_api.query_profile_services_detail(
                **{"bk_biz_id": bk_biz_id, "app_name": app_name}
            )

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
    def generate_remote_service_name(cls, name, category="http"):
        """将名称变为自定义服务的显示名称"""
        return f"{category}:{name}"

    @classmethod
    def is_remote_service(cls, bk_biz_id, app_name, node_topo_key) -> bool:
        """判断topo_key是否是远程服务"""
        # 无node_topo_key，直接返回
        if not node_topo_key:
            return False

        node = cls.get_node(bk_biz_id, app_name, node_topo_key)
        return cls.is_remote_service_by_node(node)

    @classmethod
    def is_remote_service_by_node(cls, node):
        if not node:
            return False
        return node.get("extra_data", {}).get("kind") == TopoNodeKind.REMOTE_SERVICE

    @classmethod
    def get_remote_service_origin_name(cls, remote_service_name):
        """获取自定义服务的原始名称 http:xxx -> xxx"""
        return remote_service_name.split(":", 1)[-1]

    @classmethod
    def build_remote_service_filter_params(cls, service_name, filter_params):
        """
        获取自定义服务过滤条件
        """
        filter_params.append(
            {
                "key": OtlpKey.get_attributes_key(SpanAttributes.PEER_SERVICE),
                "op": "=",
                "value": [cls.get_remote_service_origin_name(service_name)],
            }
        )
        # 去除 service_name
        index = None
        for item in filter_params:
            if item["key"] == OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME):
                index = filter_params.index(item)

        if index is not None:
            del filter_params[index]
        return filter_params

    @classmethod
    def build_remote_service_es_query_dict(cls, query, service_name, filter_params):
        filter_params = cls.build_remote_service_filter_params(service_name, filter_params)
        for f in filter_params:
            query = query.query("bool", filter=[Q("terms", **{f["key"]: f["value"]})])

        return query

    @classmethod
    def build_service_es_query_dict(cls, query, service_name, filter_params):
        query = query.query(
            "bool", filter=[Q("terms", **{OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME): [service_name]})]
        )
        for f in filter_params:
            query = query.query("bool", filter=[Q("terms", **{f["key"]: f["value"]})])

        return query

    @classmethod
    def get_apdex_relation_info(cls, bk_biz_id, app_name, service_name, nodes=None):
        """
        获取服务apdex配置
        """
        if not nodes:
            nodes = cls.list_nodes(bk_biz_id, app_name)

        instance = ApdexServiceRelation.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        ).first()

        if not instance:
            # 填充默认值 判断服务类型得出Apdex类型
            apdex_key = cls.get_service_apdex_key(bk_biz_id, app_name, service_name, nodes, raise_exception=False)
            if not apdex_key:
                return None
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
    def get_service_apdex_key(cls, bk_biz_id, app_name, service_name, nodes=None, raise_exception=True):
        if not nodes:
            nodes = cls.list_nodes(bk_biz_id, app_name)

        node = next((i for i in nodes if i["topo_key"] == service_name), None)
        if not node:
            if raise_exception:
                raise ValueError(_("此服务不存在或暂时未被发现"))
            else:
                return None

        category = node["extra_data"]["category"]
        return ApdexCategoryMapping.get_apdex_by_category(category)

    @classmethod
    @using_cache(CacheType.APM(60 * 10))
    def _get_node_mapping(cls, bk_biz_id, app_name):
        """
        获取节点集合
        """
        node_mapping = {}

        # Step1: 从 Flow 指标中获取
        application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        s, e = get_datetime_range(period="minute", distance=cls.QUERY_FLOW_MAX_TIME_RANGE, rounding=False)

        flow_response = ServiceFlowCount(
            **{
                "application": application,
                "start_time": int(s.timestamp()),
                "end_time": int(e.timestamp()),
                "where": [],
                "group_by": [
                    "from_apm_service_name",  # index: 0
                    "from_apm_service_category",  # index: 1
                    "from_apm_service_kind",  # index: 2
                    "to_apm_service_name",  # index: 3
                    "to_apm_service_category",  # index: 4
                    "to_apm_service_kind",  # index: 5
                ],
            }
        ).get_instance_values_mapping()

        from apm_web.handlers.component_handler import ComponentHandler

        for keys in flow_response.keys():
            if keys[0]:
                predicate_value = None
                if keys[2] == TopoNodeKind.COMPONENT:
                    predicate_value = ComponentHandler.get_component_belong_predicate_value(keys[0])
                node_mapping[keys[0]] = {
                    "topo_key": keys[0],
                    "extra_data": {
                        "category": keys[1],
                        "kind": keys[2],
                        "predicate_value": predicate_value,
                    },
                }
            if keys[3]:
                predicate_value = None
                if keys[5] == TopoNodeKind.COMPONENT:
                    predicate_value = ComponentHandler.get_component_belong_predicate_value(keys[3])
                node_mapping[keys[3]] = {
                    "topo_key": keys[3],
                    "extra_data": {
                        "category": keys[4],
                        "kind": keys[5],
                        "predicate_value": predicate_value,
                    },
                }

        # Step2: 从 topo_node 指标补充
        node_response = api.apm_api.query_topo_node(bk_biz_id=bk_biz_id, app_name=app_name)
        for i in node_response:
            topo_key = i.get("topo_key")
            if not topo_key:
                continue

            if topo_key in node_mapping:
                node_mapping[topo_key].update(i)
            else:
                node_mapping[topo_key] = i

        return node_mapping

    @classmethod
    def get_node(cls, bk_biz_id, app_name, service_name, raise_exception=True):
        """
        获取 topoNode 节点信息
        先从 topo_node 表获取 如果不存在 则从 flow 指标维度中取然后拼接出数据
        """

        node_mapping = cls._get_node_mapping(bk_biz_id, app_name)
        if service_name in node_mapping:
            return node_mapping[service_name]

        if raise_exception:
            raise ValueError(f"[ServiceHandler] 拓扑节点: {service_name} 不存在，请检查上报数据是否包含此服务")

        return None

    @classmethod
    def list_nodes(cls, bk_biz_id, app_name, service_name=None):
        """获取 topoNode 节点信息列表"""
        params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
        }
        if service_name:
            params["topo_key"] = service_name

        try:
            response = api.apm_api.query_topo_node(**params)
            return response
        except BKAPIError as e:
            raise ValueError(f"[ServiceHandler] 查询拓扑节点列表失败， 错误: {e}")

    @classmethod
    def _combine_metric_data(cls, service_metric, db_metric, messaging_metric, remote_service_metric):
        from apm_web.handlers.component_handler import ComponentHandler

        # 将数据变为普通服务、自定义服务、组件类服务
        res = {}
        for k, info in service_metric.items():
            res[k[0]] = info
        for k, info in db_metric.items():
            service_name = k[0]
            if not service_name:
                continue
            if k[1]:
                res[ComponentHandler.generate_component_name(service_name, k[1])] = info
        for k, info in messaging_metric.items():
            service_name = k[0]
            if not service_name:
                continue
            if k[1]:
                res[ComponentHandler.generate_component_name(service_name, k[1])] = info
        for k, info in remote_service_metric.items():
            if k[0]:
                res[ServiceHandler.generate_remote_service_name(k[0])] = info

        return res

    @classmethod
    def get_service_metric(
        cls,
        metric,
        application,
        start_time,
        end_time,
        service_name,
        bk_instance_id=None,
        raise_exception=True,
    ):
        """获取某个 service 的指标项"""
        # 根据 service 的类型使用不同的逻辑
        from apm_web.handlers.component_handler import ComponentHandler

        endpoint_metrics_param = {
            "application": application,
            "start_time": start_time,
            "end_time": end_time,
        }
        node = ServiceHandler.get_node(application.bk_biz_id, application.app_name, service_name, raise_exception)
        if ComponentHandler.is_component_by_node(node):
            return metric(
                **endpoint_metrics_param,
                where=ComponentHandler.get_component_metric_filter_params(
                    application.bk_biz_id,
                    application.app_name,
                    service_name,
                    bk_instance_id,
                )
                + [
                    {
                        "key": "service_name",
                        "method": "eq",
                        "value": [ComponentHandler.get_component_belong_service(service_name)],
                    }
                ],
            )

        elif ServiceHandler.is_remote_service_by_node(node):
            return metric(
                **endpoint_metrics_param,
                where=[
                    {
                        "key": "peer_service",
                        "method": "eq",
                        "value": [ServiceHandler.get_remote_service_origin_name(service_name)],
                    }
                ],
            )

        else:
            return metric(
                **endpoint_metrics_param,
                where=[{"key": "service_name", "method": "eq", "value": [service_name]}],
            )

    @classmethod
    def get_service_metric_instant_mapping(cls, metric, application, start_time, end_time, ignore_keys=None):
        """获取所有服务的 metric 指标（instant 查询）"""
        metric_id = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
            }
        ).metric_id
        # 查询普通服务
        response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0
                "group_by": ["service_name"],
            }
        ).get_instance_calculate_values_mapping(ignore_keys)
        # 查询组件类服务: DB
        component_db_service_response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0, 1, 2
                "group_by": ["service_name", "db_system"],
            }
        ).get_instance_calculate_values_mapping(ignore_keys)
        # 查询组件类服务: MESSAGING
        component_messaging_service_response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0, 1, 2
                "group_by": ["service_name", "messaging_system"],
            }
        ).get_instance_calculate_values_mapping(ignore_keys)
        # 单独查询自定义服务指标 (因为不同service_name可以访问同一个自定义服务)
        remote_service_response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0
                "group_by": ["peer_service"],
            }
        ).get_instance_calculate_values_mapping(ignore_keys)

        return cls._combine_metric_data(
            {k: v.get(metric_id) for k, v in response.items()},
            {k: v.get(metric_id) for k, v in component_db_service_response.items()},
            {k: v.get(metric_id) for k, v in component_messaging_service_response.items()},
            {k: v.get(metric_id) for k, v in remote_service_response.items()},
        )

    @classmethod
    def get_service_metric_range_mapping(
        cls,
        metric,
        application,
        start_time,
        end_time,
        ignore_keys=None,
        extra_params=None,
    ):
        """获取服务的指标数据(range查询)（兼容自定义服务、组件类服务名称）"""
        if not extra_params:
            extra_params = {}

        # 查询普通服务
        response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0
                "group_by": ["service_name"],
                **extra_params,
            }
        ).get_range_calculate_values_mapping(ignore_keys)
        # 查询组件类服务: DB
        component_db_service_response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0, 1, 2
                "group_by": ["service_name", "db_system"],
                **extra_params,
            }
        ).get_range_calculate_values_mapping(ignore_keys)
        # 查询组件类服务: MESSAGING
        component_messaging_service_response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0, 1, 2
                "group_by": ["service_name", "messaging_system"],
                **extra_params,
            }
        ).get_range_calculate_values_mapping(ignore_keys)
        # 单独查询自定义服务指标 (因为不同service_name可以访问同一个自定义服务)
        remote_service_response = metric(
            **{
                "application": application,
                "start_time": start_time,
                "end_time": end_time,
                # index: 0
                "group_by": ["peer_service"],
                **extra_params,
            }
        ).get_range_calculate_values_mapping(ignore_keys)
        return cls._combine_metric_data(
            response,
            component_db_service_response,
            component_messaging_service_response,
            remote_service_response,
        )

    @classmethod
    def get_service_data_status_mapping(cls, app, start_time, end_time, all_services):
        """获取应用下各个服务的数据状态"""
        if len(all_services) == 0:
            return []

        status = {
            TelemetryDataType.METRIC.value: DataStatus.NO_DATA if app.is_enabled_metric else DataStatus.DISABLED,
            TelemetryDataType.LOG.value: DataStatus.NO_DATA if app.is_enabled_log else DataStatus.DISABLED,
            TelemetryDataType.TRACE.value: DataStatus.NO_DATA if app.is_enabled_trace else DataStatus.DISABLED,
            TelemetryDataType.PROFILING.value: DataStatus.NO_DATA if app.is_enabled_profiling else DataStatus.DISABLED,
        }

        res = defaultdict(lambda: copy.deepcopy(status))
        # Metric 数据状态: 通过 bk_apm_count 指标判断
        if status[TelemetryDataType.METRIC.value] != DataStatus.DISABLED:
            metric_response = cls.get_service_metric_range_mapping(
                RequestCountInstance,
                app,
                start_time,
                end_time,
            )
            for service_name in metric_response.keys():
                res[service_name].update({TelemetryDataType.METRIC.value: DataStatus.NORMAL})

        # Log 数据状态
        if status[TelemetryDataType.LOG.value] != DataStatus.DISABLED:
            log_response = ServiceLogHandler.get_log_count_mapping(app.bk_biz_id, app.app_name, start_time, end_time)
            for service_name, data_status in log_response.items():
                res[service_name].update({TelemetryDataType.LOG.value: data_status})

        # Trace 数据状态: 通过 flow 指标判断
        # (有 flow 指标 证明有 span 并且经过了 collector 处理
        # 但是是否正常被 transfer 消费未知除非查 ES 但是查 ES 太重了这里直接查 flow 指标)
        if status[TelemetryDataType.TRACE.value] != DataStatus.DISABLED:
            trace_response = ServiceFlowCount(
                **{
                    "application": app,
                    "start_time": start_time,
                    "end_time": end_time,
                    "group_by": ["from_apm_service_name", "to_apm_service_name"],
                }
            ).get_instance_values_mapping()
            for keys in trace_response.keys():
                if keys[0]:
                    res[keys[0]].update({TelemetryDataType.TRACE.value: DataStatus.NORMAL})
                if keys[-1]:
                    res[keys[-1]].update({TelemetryDataType.TRACE.value: DataStatus.NORMAL})

        # Profiling 数据状态
        if status[TelemetryDataType.PROFILING.value] != DataStatus.DISABLED:
            services = api.apm_api.query_profile_services_detail(
                bk_biz_id=app.bk_biz_id,
                app_name=app.app_name,
                last_check_time__gt=start_time,
            )
            for i in services:
                res[i["name"]].update({TelemetryDataType.PROFILING.value: DataStatus.NORMAL})

        for i in all_services:
            if i["topo_key"] not in res:
                # 使用默认值
                res[i["topo_key"]].update({})

        return res
