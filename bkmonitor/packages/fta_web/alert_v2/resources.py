"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
from typing import Any
from collections.abc import Callable, Iterable

from django.db.models import Q
from rest_framework import serializers

from api.cmdb.define import Host
from bkmonitor.data_source import q_to_conditions
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.documents import AlertDocument
from bkmonitor.utils.thread_backend import ThreadPool
from constants.alert import APMTargetType, K8STargetType
from constants.data_source import DataTypeLabel, DataSourceLabel
from core.drf_resource import Resource, resource, api
from fta_web.alert.resources import AlertDetailResource as BaseAlertDetailResource
from fta_web.alert_v2.target import BaseTarget, get_target_instance
from monitor_web.data_explorer.event.constants import EventSource
from monitor_web.data_explorer.event.resources import (
    EventLogsResource,
    EventTotalResource,
    EventTagDetailResource,
    EventTimeSeriesResource,
)
from apm_web.event.resources import (
    EventLogsResource as APMEventLogsResource,
    EventTotalResource as APMEventTotalResource,
    EventTagDetailResource as APMEventTagDetailResource,
    EventTimeSeriesResource as APMEventTimeSeriesResource,
)

from monitor_web.data_explorer.event.utils import get_cluster_table_map


class AlertDetailResource(BaseAlertDetailResource):
    """
    告警详情资源类

    继承自BaseAlertDetailResource，提供告警详情信息的获取功能
    主要用于获取告警的详细信息，包括异常时间戳等额外信息
    """

    @classmethod
    def add_graph_extra_info(cls, alert, data):
        """
        添加图形额外信息

        从告警数据中提取异常ID列表，并解析出时间戳信息
        用于在前端展示告警的时间轴图表

        Args:
            alert: AlertDocument
            data: 告警数据字典

        Returns:
            dict: 包含异常时间戳的告警数据
        """
        try:
            # 异常ID格式示例:
            # ['f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554140.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554200.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554260.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554320.2860.2978.2']
            # 从告警触发信息中获取异常ID列表
            anomaly_ids = data["extra_info"]["origin_alarm"]["trigger"]["anomaly_ids"]
        except KeyError:
            # 如果获取失败，使用空列表
            anomaly_ids = []

        # 从异常ID中提取时间戳（第二个点分隔的部分）并排序
        # 异常ID格式: hash.timestamp.other.info.data
        data["anomaly_timestamps"] = sorted(int(i.split(".", 2)[1]) for i in anomaly_ids)
        return data


class AlertEventBaseResource(Resource, abc.ABC):
    """告警事件基础资源类。

    为告警关联事件查询提供通用的查询构建逻辑。
    """

    @classmethod
    def _get_q(cls, target: BaseTarget) -> QueryConfigBuilder:
        using: tuple[str, str] = (DataTypeLabel.EVENT, DataSourceLabel.CUSTOM)
        if cls.is_apm_target(target):
            using = (DataTypeLabel.EVENT, DataSourceLabel.BK_APM)

        return QueryConfigBuilder(using).time_field("time")

    @classmethod
    def is_apm_target(cls, target: BaseTarget) -> bool:
        """判断是否为 APM 目标"""
        return target.TARGET_TYPE == APMTargetType.SERVICE

    @classmethod
    def build_host_query(
        cls, alert: AlertDocument, target: BaseTarget, q: QueryConfigBuilder
    ) -> QueryConfigBuilder | None:
        """构建主机事件查询。

        :param alert: 告警文档对象
        :param target: 目标对象
        :param q: 查询构建器
        :return: 查询配置，如果无关联主机则返回 None
        """
        related_targets: list[str] = [
            f"{host['bk_cloud_id']}:{host['bk_target_ip']}" for host in target.list_related_host_targets()
        ]
        if not related_targets:
            return None

        return q.table("gse_system_event").conditions(q_to_conditions(Q(target=related_targets)))

    @classmethod
    def build_k8s_query(
        cls, alert: AlertDocument, target: BaseTarget, q: QueryConfigBuilder
    ) -> QueryConfigBuilder | None:
        """
        构建 K8S 事件查询。
        :param alert: 告警文档对象
        :param target: 目标对象
        :param q: 查询构建器
        :return: 构建好的查询配置，如果无关联 K8S 资源则返回 None
        """
        related_targets: list[dict[str, Any]] = target.list_related_k8s_targets().get("target_list", [])
        if not related_targets:
            return None

        # 非服务类告警只有一个 k8s 目标，服务类告警直接复用服务关联事件检索，不走此逻辑。
        related_k8s_target: dict[str, Any] = related_targets[0]

        bcs_cluster_id: str = related_k8s_target.get("bcs_cluster_id", "")
        if not bcs_cluster_id:
            # 没有集群 ID，无法查询事件
            return None

        table: str = get_cluster_table_map((bcs_cluster_id,)).get(bcs_cluster_id, "")
        if not table:
            return None

        filter_q: Q = Q()
        workload: str | None = related_k8s_target.pop("workload", "")
        if workload and target.TARGET_TYPE == K8STargetType.WORKLOAD:
            # 工作负载类型，按 kind 和 name 查询
            kind, name = workload.split(":")
            filter_q &= Q(kind=kind, name=name)
            if related_k8s_target.get("namespace"):
                filter_q &= Q(namespace=related_k8s_target["namespace"])
        else:
            # 其他类型（Pod、Node、Service等），按资源类型字段查询。
            filter_q &= Q(**{key: value for key, value in related_k8s_target.items()})

        return q.table(table).conditions(q_to_conditions(filter_q))

    @classmethod
    def build_apm_query(
        cls, alert: AlertDocument, target: BaseTarget, q: QueryConfigBuilder
    ) -> QueryConfigBuilder | None:
        """构建 APM 事件查询。

        :param alert: 告警文档对象
        :param target: 目标对象
        :param q: 查询构建器
        :return: 构建好的查询配置
        """
        return q.table("builtin")

    @classmethod
    def build_generic_query(
        cls, alert: AlertDocument, target: BaseTarget, q: QueryConfigBuilder
    ) -> QueryConfigBuilder | None:
        """构建通用事件查询。

        # TODO：事件类告警直接使用结果表 + 策略过滤条件 + 触发告警维度条件进行关联。

        :param alert: 告警文档对象
        :param target: 目标对象
        :param q: 查询构建器
        :return: 构建好的查询配置
        """
        return None

    @classmethod
    def build_queryset(cls, alert: AlertDocument, target: BaseTarget, q: QueryConfigBuilder) -> UnifyQuerySet:
        """构建统一查询集。

        根据目标类型选择合适的查询构建函数组合查询条件。

        :param alert: 告警文档对象
        :param target: 目标对象
        :param q: 查询构建器
        :return: 统一查询集
        """
        build_query_funcs: list[
            Callable[[AlertDocument, BaseTarget, QueryConfigBuilder], QueryConfigBuilder | None]
        ] = [cls.build_k8s_query, cls.build_host_query, cls.build_generic_query]
        if cls.is_apm_target(target):
            build_query_funcs = [cls.build_apm_query]

        queryset: UnifyQuerySet = UnifyQuerySet().scope(bk_biz_id=alert.event.bk_biz_id).start_time(0).end_time(0)
        for build_query_func in build_query_funcs:
            built_q: QueryConfigBuilder | None = build_query_func(alert, target, q)
            if built_q is not None:
                queryset = queryset.add_query(built_q)
        return queryset

    @classmethod
    def build_query_params(cls, alert: AlertDocument, target: BaseTarget, queryset: UnifyQuerySet) -> dict[str, Any]:
        """构建事件类接口查询参数。

        :param alert: 告警文档对象
        :param target: 目标对象
        :param queryset: 目标对象
        :return: 接口查询参数
        """
        query_params: dict[str, Any] = {
            "bk_biz_id": alert.event.bk_biz_id,
            "query_configs": [],
            "start_time": alert.first_anomaly_time - 20 * 60,
            "end_time": alert.end_time if alert.end_time else alert.first_anomaly_time + 24 * 60 * 60,
        }
        if cls.is_apm_target(target):
            # 补充 app_name & service_name 信息。
            query_params.update(target.list_related_apm_targets()[0])

        for query_config in queryset.config.get("query_configs", []):
            query_params["query_configs"].append(query_config)

        return query_params


class AlertEventsResource(AlertEventBaseResource):
    """
    告警关联事件资源类

    根据告警ID获取告警的关联事件信息
    支持主机类型和K8S容器类型的告警事件查询
    """

    # 时间范围参数，用于限制事件查询的时间窗口
    time_range_params = None

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警ID")
        # 不传 / 为空代表全部
        sources = serializers.ListSerializer(
            child=serializers.ChoiceField(label="事件来源", choices=EventSource.choices()),
            required=False,
            default=[],
        )
        limit = serializers.IntegerField(label="数量限制", required=False, default=10, help_text="返回事件的最大数量")
        offset = serializers.IntegerField(label="偏移量", required=False, default=0, help_text="分页偏移量")

    def perform_request(self, validated_request_data):
        """
        执行告警关联事件查询请求

        根据告警类型（主机或K8S容器）调用不同的查询方法

        Args:
            validated_request_data: 验证后的请求参数

        Returns:
            dict: 包含事件列表的响应数据

        Raises:
            ValueError: 当告警目标类型不支持时抛出异常
        """
        alert_id: str = validated_request_data["alert_id"]
        alert: AlertDocument = AlertDocument.get(alert_id)
        target: BaseTarget = get_target_instance(alert)
        q: QueryConfigBuilder = self._get_q(target)
        if validated_request_data.get("sources"):
            q: QueryConfigBuilder = q.conditions(q_to_conditions(Q(source=validated_request_data["sources"])))

        queryset: UnifyQuerySet = self.build_queryset(alert, target, q)
        query_params: dict[str, Any] = self.build_query_params(alert, target, queryset)
        query_params["limit"] = validated_request_data["limit"]
        query_params["offset"] = validated_request_data["offset"]

        if self.is_apm_target(target):
            return APMEventLogsResource().request(query_params)

        result: dict[str, Any] = EventLogsResource().request(query_params)
        if result.get("query_config") and result["query_config"].get("query_configs"):
            # 事件检索仅支持单数据源查询，取第一个用于前端跳转。
            result["query_config"]["query_configs"] = result["query_config"]["query_configs"][0]
        return result


class AlertEventTotalResource(AlertEventBaseResource):
    """告警关联事件总数统计资源类。

    根据告警 ID 统计关联事件的总数，并按事件来源（主机、容器、蓝盾、业务上报）分组统计。
    """

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警 ID")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """执行告警关联事件总数统计请求

        :param validated_request_data: 验证后的请求参数
        :return: 包含总数和分组统计的响应数据
        """
        alert: AlertDocument = AlertDocument.get(validated_request_data["alert_id"])
        target: BaseTarget = get_target_instance(alert)
        return self._count_all_sources(alert, target)

    def _count_all_sources(self, alert: AlertDocument, target: BaseTarget) -> dict[str, Any]:
        """统计所有事件来源的总数。

        使用多线程并发查询所有事件来源（主机、容器、蓝盾、业务上报）的事件数量

        :param alert: 告警文档对象
        :param target: 目标对象
        :return: 包含总数和分组统计的响应数据
        """
        event_total_resource_cls: type[EventTotalResource] = (
            APMEventTotalResource if self.is_apm_target(target) else EventTotalResource
        )

        # 在线程外构建基础查询，避免在每个线程中重复构建
        base_q: QueryConfigBuilder = self._get_q(target)

        def _get_total_info_by_source(source: str) -> dict[str, Any]:
            # 在线程内基于 base_q 添加 source 条件，然后构建查询参数并发起请求
            q_with_source: QueryConfigBuilder = base_q.conditions(q_to_conditions(Q(source=source)))
            queryset: UnifyQuerySet = self.build_queryset(alert, target, q_with_source)
            query_params: dict[str, Any] = self.build_query_params(alert, target, queryset)
            count: int = event_total_resource_cls().request(query_params).get("total", 0)

            return {
                "value": source,
                "alias": EventSource.from_value(source).label,
                "total": count,
            }

        sources: list[str] = [source for source, _ in EventSource.choices()]
        pool = ThreadPool(min(len(sources), 8))
        source_counts_iter: Iterable[dict[str, Any]] = pool.imap_unordered(
            lambda source: _get_total_info_by_source(source), sources
        )
        pool.close()

        total_infos: list[dict[str, Any]] = []
        total: int = 0
        for source_count in source_counts_iter:
            total_infos.append(source_count)
            total += source_count["total"]

        return {"total": total, "list": total_infos}


class AlertEventTSResource(AlertEventBaseResource):
    """告警关联事件时序数据资源类"""

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 ID", help_text="要查询的告警 ID")
        sources = serializers.ListSerializer(
            child=serializers.ChoiceField(label="事件来源", choices=EventSource.choices()),
            required=False,
            default=[],
            help_text="事件来源过滤，不传或为空表示查询所有来源",
        )
        interval = serializers.IntegerField(
            label="时间间隔", required=False, default=300, help_text="时序数据的时间间隔（秒）"
        )
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """执行告警关联事件时序数据查询请求。

        :param validated_request_data: 验证后的请求参数
        :return: 包含时序数据和查询配置的响应数据
        """
        alert: AlertDocument = AlertDocument.get(validated_request_data["alert_id"])
        target: BaseTarget = get_target_instance(alert)

        interval: int = validated_request_data["interval"]
        q: QueryConfigBuilder = self._get_q(target).interval(interval).metric(field="_index", method="SUM", alias="a")
        # 添加 sources 过滤条件
        if validated_request_data.get("sources"):
            q: QueryConfigBuilder = q.conditions(q_to_conditions(Q(source=validated_request_data["sources"])))

        queryset: UnifyQuerySet = self.build_queryset(alert, target, q)
        query_params: dict[str, Any] = self.build_query_params(alert, target, queryset)
        query_params["expression"] = "a"

        # 如果传入了自定义时间范围，则覆盖默认的时间范围
        if validated_request_data.get("start_time") is not None:
            query_params["start_time"] = validated_request_data["start_time"]
        if validated_request_data.get("end_time") is not None:
            query_params["end_time"] = validated_request_data["end_time"]

        event_ts_resource_cls: type[EventTimeSeriesResource] = (
            APMEventTimeSeriesResource if self.is_apm_target(target) else EventTimeSeriesResource
        )
        return event_ts_resource_cls().request(query_params)


class AlertEventTagDetailResource(AlertEventBaseResource):
    """告警关联事件气泡详情资源类"""

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 ID", help_text="要查询的告警 ID")
        sources = serializers.ListSerializer(
            child=serializers.ChoiceField(label="事件来源", choices=EventSource.choices()),
            required=False,
            default=[],
            help_text="事件来源过滤，不传或为空表示查询所有来源",
        )
        interval = serializers.IntegerField(label="汇聚周期", required=False, default=60, help_text="汇聚周期（秒）")
        start_time = serializers.IntegerField(label="开始时间", help_text="查询的开始时间戳")
        limit = serializers.IntegerField(label="数量限制", required=False, default=5, help_text="返回事件的最大数量")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """执行告警关联事件气泡详情查询请求。

        :param validated_request_data: 验证后的请求参数
        :return: 包含事件详情和查询配置的响应数据
        """
        alert: AlertDocument = AlertDocument.get(validated_request_data["alert_id"])
        target: BaseTarget = get_target_instance(alert)

        interval: int = validated_request_data["interval"]
        q: QueryConfigBuilder = self._get_q(target).interval(interval).metric(field="_index", method="SUM", alias="a")
        # 添加 sources 过滤条件
        if validated_request_data.get("sources"):
            q: QueryConfigBuilder = q.conditions(q_to_conditions(Q(source=validated_request_data["sources"])))

        queryset: UnifyQuerySet = self.build_queryset(alert, target, q)
        query_params: dict[str, Any] = self.build_query_params(alert, target, queryset)

        # 添加 EventTagDetailResource 类所需的参数
        query_params["expression"] = "a"
        query_params["start_time"] = validated_request_data["start_time"]
        query_params["end_time"] = validated_request_data["start_time"] + interval
        query_params["interval"] = interval
        query_params["limit"] = validated_request_data["limit"]

        event_tag_detail_resource_cls: type = (
            APMEventTagDetailResource if self.is_apm_target(target) else EventTagDetailResource
        )
        return event_tag_detail_resource_cls().request(query_params)


class AlertK8sScenarioListResource(Resource):
    """
    K8S容器场景列表资源类

    根据告警ID获取告警关联的容器观测场景列表
    不同类型的K8S资源支持不同的观测场景
    """

    # K8S目标类型与观测场景的映射关系
    K8sTargetScenarioMap = {
        K8STargetType.POD: ["performance", "network"],  # Pod支持性能和网络场景
        K8STargetType.WORKLOAD: ["performance", "network"],  # 工作负载支持性能和网络场景
        K8STargetType.NODE: ["capacity"],  # 节点支持容量场景
        K8STargetType.SERVICE: ["network"],  # 服务支持网络场景
    }

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警ID")

    def perform_request(self, validated_request_data):
        """
        执行K8S场景列表查询请求

        根据告警的目标类型返回对应支持的观测场景列表

        Args:
            validated_request_data: 验证后的请求参数

        Returns:
            list: 支持的观测场景列表

        Raises:
            list: 当目标类型不支持时返回空列表
        """
        alert_id: str = validated_request_data["alert_id"]
        # 根据告警ID获取告警文档对象
        alert: AlertDocument = AlertDocument.get(alert_id)
        target_type: str = alert.event.target_type

        # 检查是否为支持的K8S目标类型
        if target_type in [K8STargetType.POD, K8STargetType.WORKLOAD, K8STargetType.NODE, K8STargetType.SERVICE]:
            return self.K8sTargetScenarioMap[target_type]

        # 检查是否为 APM 目标类型
        if target_type == APMTargetType.SERVICE:
            return self.K8sTargetScenarioMap[K8STargetType.WORKLOAD]

        # 目前不支持的类型返回空列表
        return []


class AlertK8sMetricListResource(Resource):
    """
    K8S容器指标列表资源类

    根据容器观测场景获取对应场景配置的指标列表
    用于前端展示特定场景下可用的监控指标
    """

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        bk_biz_id = serializers.IntegerField(label="业务ID", help_text="业务ID")
        scenario = serializers.CharField(
            label="场景", help_text="观测场景名称，如：performance（性能）、network（网络）、capacity（容量）"
        )

    def perform_request(self, validated_request_data):
        """
        执行K8S指标列表查询请求

        调用K8S资源的场景指标列表接口获取指定场景的指标配置

        Args:
            validated_request_data: 验证后的请求参数

        Returns:
            list: 指定场景下的指标列表
        """
        # 调用K8S资源模块的场景指标列表接口
        return resource.k8s.scenario_metric_list(
            bk_biz_id=validated_request_data["bk_biz_id"], scenario=validated_request_data["scenario"]
        )


class AlertK8sTargetResource(Resource):
    """
    K8S容器目标对象资源类

    根据告警ID获取告警关联的容器对象信息
    包括资源类型、目标列表、集群信息等
    """

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警ID")

    def perform_request(self, validated_request_data):
        """
        执行K8S目标对象查询请求

        根据告警ID获取对应的K8S资源目标信息

        Args:
            validated_request_data: 验证后的请求参数

        Returns:
            dict: K8S目标对象信息，如果不支持则返回空列表
        """
        alert_id: str = validated_request_data["alert_id"]
        # 根据告警ID获取告警文档对象
        alert: AlertDocument = AlertDocument.get(alert_id)
        target: BaseTarget = get_target_instance(alert)
        return target.list_related_k8s_targets()


class AlertHostTargetResource(Resource):
    """
    主机目标对象资源类

    根据告警ID获取告警关联的主机对象信息
    包括主机IP、云区域ID等
    """

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警ID")

    def perform_request(self, validated_request_data):
        """
        执行主机目标对象查询请求

        根据告警ID获取对应的主机目标信息

        Args:
            validated_request_data: 验证后的请求参数

        Returns:
            dict: 主机目标对象信息，如果不支持则返回空列表
        """
        alert_id: str = validated_request_data["alert_id"]
        # 根据告警ID获取告警文档对象
        alert: AlertDocument = AlertDocument.get(alert_id)

        target: BaseTarget = get_target_instance(alert)
        return self.process_target_list(alert, target.list_related_host_targets())

    @classmethod
    def process_target_list(cls, alert: AlertDocument, target_list: list[dict[str, Any]]):
        # 经过 Target 清洗后一定有 bk_host_id。
        bk_host_ids: list[int] = [target["bk_host_id"] for target in target_list]
        if not bk_host_ids:
            return []

        # 调用 CMDB API 获取主机详细信息
        hosts: list[Host] = api.cmdb.get_host_by_id(bk_biz_id=alert.event.bk_biz_id, bk_host_ids=bk_host_ids)
        if not hosts:
            return target_list
        return cls.flat_host_info(hosts, alert)

    @classmethod
    def flat_host_info(cls, hosts, alert):
        """
        扁平化主机信息

        将主机信息转换为前端可展示的格式

        Returns:
            list: 扁平化后的主机信息列表
        """
        target_list = []
        topo_links = api.cmdb.get_topo_tree(bk_biz_id=alert.event.bk_biz_id).convert_to_topo_link()
        for host in hosts:
            target = {
                "bk_host_id": host.bk_host_id,
                "bk_target_ip": host.bk_host_innerip,
                "bk_cloud_id": host.bk_cloud_id,
                "display_name": host.bk_host_innerip,
                "bk_host_name": host.bk_host_name,
            }

            topo_links = {
                key: value for key, value in topo_links.items() if int(key.split("|")[1]) in host.bk_module_ids
            }
            topo_display = [
                " / ".join(topo.bk_inst_name for topo in reversed(topo_link) if topo.bk_obj_id != "biz")
                for topo_link in topo_links.values()
            ]
            for topo in topo_display:
                # 如果主机归属多个 topo，则分成多条（虽然主机是同一台）
                flat_target = {}
                flat_target.update(target)
                flat_target["display_name"] = f"{topo} / {target['bk_target_ip']}"
                target_list.append(flat_target)
        return target_list


class AlertLogRelationListResource(Resource):
    """告警关联日志资源类。"""

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警ID")

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        alert_id: str = validated_request_data["alert_id"]
        alert: AlertDocument = AlertDocument.get(alert_id)
        target: BaseTarget = get_target_instance(alert)
        return target.list_related_log_targets()


class AlertTracesResource(Resource):
    """告警关联调用链资源类。

    根据告警 ID 获取关联的调用链信息，包括 Trace 查询配置和调用链列表。
    """

    class RequestSerializer(serializers.Serializer):
        """请求参数序列化器"""

        alert_id = serializers.CharField(label="告警 id", help_text="要查询的告警 ID")
        limit = serializers.IntegerField(label="数量限制", required=False, default=10, help_text="返回调用链的最大数量")
        offset = serializers.IntegerField(label="偏移量", required=False, default=0, help_text="分页偏移量")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """执行告警关联调用链查询请求。

        :param validated_request_data: 验证后的请求参数
        :return: 包含查询配置和调用链列表的响应数据
        """
        # TODO: 实现真实的调用链查询逻辑
        # 当前返回 mock 数据用于前端联调
        return {
            "query_config": {
                "app_name": "tilapia",
                "sceneMode": "span",
                "where": [
                    {
                        "key": "resource.service.name",
                        "operator": "equal",
                        "value": ["example.greeter"],
                    }
                ],
            },
            "list": [
                {
                    "app_name": "tilapia",
                    "trace_id": "84608839c9c45c074d5b0edf96d3ed0f",
                    "root_service": "example.greeter",
                    "root_span_name": "trpc.example.greeter.http/timeout",
                    "root_service_span_name": "/timeout",
                    "error_msg": "http client transport RoundTrip timeout: Get http://trpc-otlp-oteam-demo-service:8080/timeout: context deadline exceeded, cost:2.000525304s",
                }
            ],
        }
