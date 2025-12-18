"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from api.cmdb.define import Host
from apm_web.handlers.host_handler import HostHandler
from apm_web.strategy.dispatch.entity import EntitySet
from bkmonitor.documents import AlertDocument
from constants.alert import APMTargetType, K8STargetType, K8S_RESOURCE_TYPE, EventTargetType
from core.drf_resource import Resource, resource, api
from fta_web.alert.resources import AlertDetailResource as BaseAlertDetailResource
from monitor_web.data_explorer.event.resources import EventLogsResource

from metadata import models


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


class AlertEventsResource(Resource):
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
        alert_id = validated_request_data["alert_id"]
        # 根据告警ID获取告警文档对象
        alert = AlertDocument.get(alert_id)
        target_type = alert.event.target_type

        # 设置事件查询的时间范围
        self.time_range_params = {
            # 告警开始前五分钟，扩大查询范围以获取相关事件
            "start_time": alert.first_anomaly_time - 5 * 60,
            # 告警结束时间，如果未结束则取告警开始后24小时
            "end_time": alert.end_time if alert.end_time else alert.first_anomaly_time + 24 * 60 * 60,
        }

        if target_type == EventTargetType.HOST:
            # 主机对象告警，查询主机相关事件
            return self.query_events_by_host(validated_request_data, alert, target_type)
        elif target_type.startswith("K8S"):
            # 容器对象告警，target_type示例: K8S:Pod, K8S:Node等
            return self.query_events_by_k8s_target(validated_request_data, alert, target_type)

        # 不支持的告警目标类型
        raise ValueError(f"unsupported alert target type: {target_type}")

    def query_events_by_host(self, validated_request_data, alert, target_type):
        """
        根据主机告警对象获取主机关联的事件

        查询GSE系统事件表，获取指定主机在告警时间范围内的相关事件

        Args:
            validated_request_data: 验证后的请求参数
            alert: AlertDocument
            target_type: 目标类型（host）

        Returns:
            dict: 主机事件查询结果
        """
        # GSE系统事件表ID
        host_event_table_id = "gse_system_event"

        # 构建事件查询参数
        query_params = {
            "query_configs": [
                {
                    "data_source_label": "custom",  # 自定义数据源
                    "data_type_label": "event",  # 事件类型数据
                    "table": host_event_table_id,  # 查询表名
                    "query_string": "",  # 查询字符串（空表示查询所有）
                    "where": [
                        {
                            "condition": "and",
                            "key": "target",
                            "method": "eq",
                            # 目标主机格式: bk_cloud_id:ip
                            "value": [f"{alert.event.bk_cloud_id}:{alert.event.ip}"],
                        }
                    ],
                    "group_by": ["type"],  # 按事件类型分组
                    "filter_dict": {},  # 额外过滤条件
                }
            ],
            "bk_biz_id": alert.event.bk_biz_id,  # 业务ID
            "limit": validated_request_data["limit"],  # 限制返回数量
            "offset": validated_request_data["offset"],  # 分页偏移
            "sort": [],  # 排序规则
        }

        # 添加时间范围参数
        query_params.update(self.time_range_params)

        # 调用事件日志资源进行查询
        return EventLogsResource()(query_params)

    def query_events_by_k8s_target(self, validated_request_data, alert, target_type, target=None):
        """
        根据K8S容器告警对象获取容器关联的事件

        查询BCS事件表，获取指定K8S资源在告警时间范围内的相关事件

        Args:
            validated_request_data: 验证后的请求参数
            alert: AlertDocument
            target_type: K8S目标类型（K8S-POD、K8S_NODE、K8S-WORKLOAD、K8S-SERVICE）
            target: 目标对象（可选）

        Returns:
            dict: K8S事件查询结果，如果无法获取集群信息则返回空列表
        """
        # 空事件结果
        empty_events = {"list": []}

        # 如果未提供目标对象，从告警中获取
        if target is None:
            target_list = AlertK8sTargetResource.k8s_target_list(alert)["target_list"]
            if target_list:
                target = target_list[0]

        # 获取BCS集群ID
        bcs_cluster_id = target.get("bcs_cluster_id", "")
        if not bcs_cluster_id:
            # 没有集群ID，无法查询事件
            return empty_events

        # 获取BCS事件表ID
        table_id = self._get_bcs_event_table_id(bcs_cluster_id)

        # 根据不同的目标类型构建查询条件
        # 工作负载类型，需要按kind和name查询
        where = []
        workload = target.pop("workload", "")
        if workload and target_type == K8STargetType.WORKLOAD:
            kind, name = workload.split(":")
            where += [
                {"condition": "and", "key": "kind", "method": "eq", "value": [kind]},
                {"condition": "and", "key": "name", "method": "eq", "value": [name]},
            ]
        else:
            # 其他类型（Pod、Node、Service等），按资源类型字段查询
            where += [
                {"condition": "and", "key": key, "method": "eq", "value": [value]} for key, value in target.items()
            ]

        # 构建K8S事件查询参数
        query_params = {
            "query_configs": [
                {
                    "data_source_label": "custom",  # 自定义数据源
                    "data_type_label": "event",  # 事件类型数据
                    "table": table_id,  # BCS事件表ID
                    "query_string": "",  # 查询字符串
                    "where": where,  # 查询条件
                    "group_by": ["type"],  # 按事件类型分组
                    "filter_dict": {},  # 额外过滤条件
                }
            ],
            "bk_biz_id": alert.event.bk_biz_id,  # 业务ID
            "limit": validated_request_data["limit"],  # 限制返回数量
            "offset": validated_request_data["offset"],  # 分页偏移
            "sort": [],  # 排序规则
        }

        # 添加时间范围参数
        query_params.update(self.time_range_params)

        # 调用事件日志资源进行查询
        return EventLogsResource()(query_params)

    def _get_bcs_event_table_id(self, bcs_cluster_id):
        """
        根据BCS集群ID获取对应的事件表ID

        通过集群信息查找对应的K8S事件数据源，并获取结果表ID

        Args:
            bcs_cluster_id: BCS集群ID

        Returns:
            str: 事件表ID，如果未找到则返回空字符串
        """
        # 查询BCS集群信息，只获取必要字段以提高性能
        cluster = (
            models.BCSClusterInfo.objects.filter(
                cluster_id=bcs_cluster_id,
            )
            .only("cluster_id", "K8sEventDataID")
            .first()
        )

        result_table_id = ""
        if cluster:
            # 根据K8S事件数据ID查找对应的结果表
            data_source_result = models.DataSourceResultTable.objects.filter(bk_data_id=cluster.K8sEventDataID).first()
            if data_source_result:
                result_table_id = data_source_result.table_id

        return result_table_id


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

    @classmethod
    def k8s_target_list(cls, alert):
        """
        从告警对象中提取K8S目标信息

        解析告警的标签信息，构建K8S资源目标对象

        Args:
            alert: 告警文档对象

        Returns:
            dict: 包含资源类型和目标列表的字典
                {
                    "resource_type": "pod",  # 资源类型
                    "target_list": [         # 目标对象列表
                        {
                            "pod": "xxx",
                            "bcs_cluster_id": "xxx",
                            "namespace": "xxx",
                            "workload": "Deployment:xxx"
                        }
                    ]
                }
        """
        # 从告警事件标签中提取维度信息
        alert_dimensions = {tag["key"]: tag["value"] for tag in alert.event.tags}

        # 如果存在工作负载信息，组合成workload字段
        if "workload_kind" in alert_dimensions and "workload_name" in alert_dimensions:
            alert_dimensions["workload"] = f"{alert_dimensions['workload_kind']}:{alert_dimensions['workload_name']}"

        # 获取目标类型和对应的资源字段名
        target_type = alert.event.target_type
        resource_type = K8S_RESOURCE_TYPE[target_type]

        # 构建目标信息结构
        target_info = {"resource_type": resource_type, "target_list": []}

        # 构建单个目标对象
        target = {
            resource_type: alert.event.target,  # 资源名称
            "bcs_cluster_id": alert_dimensions.get("bcs_cluster_id", ""),  # 集群ID
        }

        # 补充资源限定范围
        if "namespace" in alert_dimensions:
            target["namespace"] = alert_dimensions["namespace"]
        if "workload_kind" in alert_dimensions and "workload_name" in alert_dimensions:
            target["workload"] = f"{alert_dimensions['workload_kind']}:{alert_dimensions['workload_name']}"

        # 将目标对象添加到列表中
        target_info["target_list"].append(target)
        return target_info

    @classmethod
    def apm_target_list(cls, alert: AlertDocument) -> dict:
        """
        获取 APM 服务关联的容器负载目标信息

        注：APM 场景下资源类型都为 workload。

        :param alert: 告警文档对象
        :type alert: AlertDocument
        :return: 包含资源类型和目标对象列表的字典
        :rtype: dict

        返回示例:

            {
                "resource_type": "workload",
                "target_list": [
                    {
                        "workload": "Deployment:xxx",
                        "bcs_cluster_id": "xxx",
                        "namespace": "xxx"
                    }
                ]
            }
        """
        # 构建目标信息结构，APM 场景下资源类型固定为 workload
        target_info: dict = {"resource_type": K8S_RESOURCE_TYPE[K8STargetType.WORKLOAD], "target_list": []}

        app_name, service_name = APMTargetType.parse_target(alert.event.target)

        # 获取 APM 服务关联的容器负载，构建目标对象资源列表
        entity_set: EntitySet = EntitySet(
            bk_biz_id=alert.event.bk_biz_id,
            app_name=app_name,
            service_names=[service_name],
        )
        for workload in entity_set.get_workloads(service_name):
            bcs_cluster_id: str = workload.get("bcs_cluster_id", "")
            namespace: str = workload.get("namespace", "")
            workload_kind: str = workload.get("kind", "")
            workload_name: str = workload.get("name", "")

            if not all([bcs_cluster_id, namespace, workload_kind, workload_name]):
                continue

            target_info["target_list"].append(
                {
                    "workload": f"{workload_kind}:{workload_name}",
                    "bcs_cluster_id": bcs_cluster_id,
                    "namespace": namespace,
                }
            )

        return target_info

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
        target_type: str = alert.event.target_type

        # 检查是否为支持的K8S目标类型
        if target_type in [
            K8STargetType.POD,
            K8STargetType.WORKLOAD,
            K8STargetType.NODE,
            K8STargetType.SERVICE,
        ]:
            target_list = self.k8s_target_list(alert)
            return target_list

        # 检查是否为 APM 目标类型
        if target_type == APMTargetType.SERVICE:
            return self.apm_target_list(alert)

        # 不支持的类型返回空字典
        return {}


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
        target_type: str = alert.event.target_type

        # 检查是否为主机目标类型
        if target_type == EventTargetType.HOST:
            try:
                target_list = self.host_target_list(alert)
            except AttributeError:
                target_list = []
            return target_list

        # 检查是否为 APM 目标类型
        if target_type == APMTargetType.SERVICE:
            return self.apm_host_target_list(alert)

        # 不支持的类型返回空列表
        return []

    @classmethod
    def host_target_list(cls, alert):
        """
        从告警对象中提取主机目标信息

        解析告警的标签信息，构建主机目标对象

        Args:
            alert: 告警文档对象

        Returns:
            dict: 包含主机IP和云区域ID的字典
        """
        target_info = {
            "bk_host_id": alert.event.bk_host_id,
            "bk_target_ip": alert.event.ip,
            "bk_cloud_id": alert.event.bk_cloud_id,
            "display_name": alert.event.ip,
            "bk_host_name": "",
        }
        hosts = api.cmdb.get_host_by_id(bk_biz_id=alert.event.bk_biz_id, bk_host_ids=[alert.event.bk_host_id])
        if not hosts:
            return [target_info]

        return cls.flat_host_info(hosts, alert)

    @classmethod
    def apm_host_target_list(cls, alert: AlertDocument) -> list[dict[str, str | int]]:
        """
        获取 APM 服务关联的主机目标信息

        :param alert: 告警文档对象
        :type alert: AlertDocument
        :return: 扁平化后的主机信息列表
        :rtype: list[dict[str, str | int]]

        返回示例:
            [
                {
                    "bk_host_id": 123,
                    "bk_target_ip": "127.0.0.1",
                    "bk_cloud_id": 123,
                    "display_name": "xxx / k8s-node / 127.0.0.1",
                    "bk_host_name": "xxx"
                }
            ]
        """
        app_name, service_name = APMTargetType.parse_target(alert.event.target)

        # 调用 HostHandler 获取 APM 应用关联的主机列表
        host_list: list[dict] = HostHandler.list_application_hosts(
            bk_biz_id=alert.event.bk_biz_id,
            app_name=app_name,
            service_name=service_name,
        )

        # 若无关联的主机，则返回空列表
        if not host_list:
            return []

        # 提取主机 id 列表，将字符串格式的主机 id 转换为整数
        target_hosts: list[dict[str, str | int]] = []
        bk_host_ids: list[int] = []
        for host in host_list:
            bk_host_id: str | None = host.get("bk_host_id")
            if not bk_host_id or not str(bk_host_id).isdigit():
                continue
            target_hosts.append(
                {
                    "bk_host_id": int(bk_host_id),
                    "bk_target_ip": host["bk_host_innerip"],
                    "bk_cloud_id": int(host["bk_cloud_id"]),
                    "display_name": host["bk_host_innerip"],
                    "bk_host_name": "",
                }
            )
            bk_host_ids.append(int(bk_host_id))

        # 若无有效的主机 id，则返回空列表
        if not bk_host_ids:
            return []

        # 调用 CMDB API 获取主机详细信息
        hosts: list[Host] = api.cmdb.get_host_by_id(bk_biz_id=alert.event.bk_biz_id, bk_host_ids=bk_host_ids)
        if not hosts:
            return target_hosts

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
