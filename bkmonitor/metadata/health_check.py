"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
健康检查
场景化检查链路状态

1. 自定义指标 - bk_data_id
2. 自定义事件 - bk_data_id
3. 服务拨测 - bk_biz_id
4. 主机/进程指标 - bk_biz_id
5. 容器监控 - bcs_cluster_id
6. APM - bk_biz_id, app_name
"""

import enum
import json
from datetime import datetime
from typing import Any

import arrow
from django.conf import settings
from pydantic import BaseModel
from pydantic.fields import Field

from bkm_space.api import Space, SpaceApi
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.models import BCSClusterInfo, DataSource, DataSourceResultTable, ResultTable
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import (
    BKBASE_NAMESPACE_BK_LOG,
    BKBASE_NAMESPACE_BK_MONITOR,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.service import get_data_id_v2
from metadata.models.data_link.utils import compose_bkdata_data_id_name
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    LOG_EVENT_ETL_CONFIGS,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
    SYSTEM_BASE_DATA_ETL_CONFIGS,
)
from metadata.utils.redis_tools import RedisTools
from apm.models import ApmApplication, TraceDataSource, MetricDataSource, LogDataSource, ProfileDataSource
from monitor_web.models.custom_report import CustomEventGroup


class DataScene(enum.Enum):
    """数据场景"""

    UPTIMECHECK = "uptimecheck"
    HOST = "host"
    CUSTOM_METRIC = "custom_metric"
    K8S = "k8s"
    APM = "apm"
    CUSTOM_EVENT = "custom_event"
    LOG = "log"


class DataIdStatus(BaseModel):
    """数据源状态"""

    bk_data_id: int = Field(description="数据源ID", default=0)
    data_name: str = Field(description="数据源名称", default="")
    exists: bool = Field(description="数据源是否存在", default=False)
    created_from: DataIdCreatedFromSystem | None = Field(description="数据源来源", default=None)

    bkbase_data_id_name: str = Field(description="bkbase数据源名称", default="")
    bkbase_status: str = Field(description="bkbase状态", default="")
    bkbase_config: dict[str, Any] = Field(description="bkbase配置", default={})

    kafka_data_exists: bool = Field(description="Kafka是否存在数据", default=False)
    kafka_latest_time: datetime | None = Field(description="Kafka最新数据时间", default=None)
    kafka_latest_data: list[dict[str, Any]] = Field(description="Kafka最新数据", default=[])

    finished: bool = Field(description="是否检查完成", default=False)
    message: str = Field(description="消息", default="")


def get_data_id_status(bk_tenant_id: str, bk_biz_id: int, bk_data_id: int, with_detail: bool = False) -> DataIdStatus:
    """获取数据id状态

    Args:
        bk_tenant_id: 租户id
        bk_biz_id: 业务id
        bk_data_id: 数据id
        with_detail: 是否返回详细信息，如果返回详细信息，则返回bkbase_config和kafka_latest_data

    Returns:
        DataIdStatus: 数据id状态
    """
    data_id_status = DataIdStatus(bk_data_id=bk_data_id)

    ds = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).first()

    # 数据源不存在
    if not ds:
        data_id_status.finished = False
        data_id_status.message = "数据源不存在"
        return data_id_status

    # 数据源存在
    data_id_status.data_name = ds.data_name
    data_id_status.exists = True
    data_id_status.created_from = DataIdCreatedFromSystem(ds.created_from)

    # 数据源来源为bkdata，检查bkbase配置状态
    namespace = BKBASE_NAMESPACE_BK_MONITOR
    if data_id_status.created_from == DataIdCreatedFromSystem.BKDATA:
        is_base = ds.etl_config in SYSTEM_BASE_DATA_ETL_CONFIGS
        event_type = "metric" if ds.etl_config not in LOG_EVENT_ETL_CONFIGS else "log"
        namespace = BKBASE_NAMESPACE_BK_LOG if event_type == "log" else BKBASE_NAMESPACE_BK_MONITOR

        # 组装bkbase数据源名称
        if is_base:  # 如果是基础数据源（1000,1001）,那么沿用固定格式的data_name，会以此name作为bkbase申请时的唯一键
            data_id_name = ds.data_name
        else:  # 用户自定义数据源，需要进行二次处理，主要为避免超过meta长度限制和特殊字符
            data_id_name = compose_bkdata_data_id_name(ds.data_name)
        data_id_status.bkbase_data_id_name = data_id_name

        try:
            data_id_config = get_data_id_v2(
                data_name=ds.data_name,
                is_base=is_base,
                bk_biz_id=bk_biz_id,
                namespace=namespace,
                with_detail=with_detail,
            )
        except BKAPIError as e:
            data_id_status.bkbase_status = "Error"
            data_id_status.message = str(e)
            return data_id_status

        data_id_status.bkbase_status = data_id_config["status"]

        if with_detail:
            data_id_status.bkbase_config = data_id_config["data_id_config"]

    # 检查kafka数据
    try:
        result = api.metadata.kafka_tail(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id, namespace=namespace, size=3)
    except Exception as e:
        data_id_status.kafka_data_exists = False
        data_id_status.message = str(e)
        return data_id_status
    data_id_status.kafka_data_exists = bool(result)
    if isinstance(result, list) and len(result) > 0:
        data_record = result[0]

        if isinstance(data_record, list):
            data_record = data_record[0]

        time_info = (
            data_record.get("timestamp") or data_record.get("data", {}).get("utctime") or data_record.get("utctime")
        )
        if time_info:
            data_id_status.kafka_latest_time = arrow.get(time_info).datetime

    if with_detail:
        data_id_status.kafka_latest_data = result

    data_id_status.finished = True
    return data_id_status


class DataLinkComponentStatus(BaseModel):
    """数据链路组件状态"""

    kind: str = Field(description="组件类型")
    name: str = Field(description="组件名称")
    exists: bool = Field(description="组件是否存在", default=False)
    config: dict[str, Any] = Field(description="组件配置", default={})
    status: str = Field(description="组件状态", default="Unknown")


class BkDataStatus(BaseModel):
    """数据链路状态"""

    data_link_name: str = Field(description="数据链路名称")
    exists: bool = Field(description="数据链路是否存在", default=False)
    component_statuses: list[DataLinkComponentStatus] = Field(description="组件状态列表", default=[])

    message: str = Field(description="消息", default="")
    finished: bool = Field(description="是否检查完成", default=False)


def get_bkdata_status(bk_tenant_id: str, data_link_name: str, with_detail: bool = False) -> BkDataStatus:
    """获取清洗任务状态

    Args:
        bk_tenant_id: 租户id
        data_link_name: 数据链路名称
        with_detail: 是否返回详细信息

    Returns:
        BkDataStatus: 数据链路状态
    """
    datalink_status = BkDataStatus(data_link_name=data_link_name)

    datalink = DataLink.objects.filter(data_link_name=data_link_name, bk_tenant_id=bk_tenant_id).first()
    if not datalink:
        datalink_status.exists = False
        datalink_status.message = f"数据链路{data_link_name}不存在"
        return datalink_status

    datalink_status.exists = True

    # 检查组件配置
    status_ok = True
    for component_cls in datalink.STRATEGY_RELATED_COMPONENTS[datalink.data_link_strategy]:
        components = component_cls.objects.filter(data_link_name=data_link_name, bk_tenant_id=bk_tenant_id)
        for component in components:
            component_status = DataLinkComponentStatus(name=component.name, kind=component.kind)

            # 将组件状态添加到数据链路状态列表
            datalink_status.component_statuses.append(component_status)

            component_config = component.component_config

            # 检查组件配置是否存在
            if not component_config:
                datalink_status.message += f"数据链路组件 Kind:{component.kind} Name:{component.name}配置不存在\n"
                status_ok = False
                continue
            component_status.exists = True

            # 检查组件状态
            phase = component_config.get("status", {}).get("phase")
            component_status.status = phase or "Unknown"
            if phase != DataLinkResourceStatus.OK.value:
                datalink_status.message += f"数据链路组件 Kind:{component.kind} Name:{component.name}状态异常\n"
                status_ok = False
                continue

            # 如果需要详细信息，则返回组件配置
            if with_detail:
                component_status.config = component_config

    # 如果组件状态异常，则认为数据链路状态异常
    if not status_ok:
        return datalink_status

    # 检查结束
    datalink_status.finished = True
    return datalink_status


class QueryRouterStatus(BaseModel):
    """查询路由状态"""

    result_table_id: str = Field(description="结果表ID")
    data_label: str = Field(description="数据标签", default="")
    data_label_exists: bool = Field(description="数据标签是否存在", default=False)
    result_table_exists: bool = Field(description="结果表是否存在", default=False)
    result_table_detail: dict[str, Any] = Field(description="结果表详情", default={})
    space_result_table_exists: bool = Field(description="空间结果表是否存在", default=False)
    messages: list[str] = Field(description="消息", default=[])


def get_query_router_status(
    bk_tenant_id: str, bk_biz_id: int, bk_data_id: int, with_detail: bool = False
) -> list[QueryRouterStatus]:
    """获取查询路由状态

    Args:
        bk_tenant_id: 租户id
        bk_biz_id: 业务id
        bk_data_id: 数据源id
        with_detail: 是否返回详细信息

    Returns:
        list[QueryRouterStatus]: 查询路由状态
    """
    query_router_statuses: list[QueryRouterStatus] = []

    result_table_ids = list(
        DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
        .values_list("table_id", flat=True)
        .distinct()
    )
    if not result_table_ids:
        return []

    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=result_table_ids)

    # 查询空间结果表
    space: Space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
    if settings.ENABLE_MULTI_TENANT_MODE:
        space_result_table_key = f"{space.space_uid}|{bk_tenant_id}"
    else:
        space_result_table_key = f"{space.space_uid}"
    space_result_table_ids = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, space_result_table_key)
    space_result_table_ids = json.loads(space_result_table_ids) if space_result_table_ids else []

    # 检查结果表相关路由
    for result_table in result_tables:
        query_router_status = QueryRouterStatus(result_table_id=result_table.table_id)

        # 检查结果表是否在空间结果表中
        if result_table.table_id in space_result_table_ids:
            query_router_status.space_result_table_exists = True
        else:
            query_router_status.messages.append(f"结果表 {result_table.table_id} 在空间结果表中不存在")

        # 检查结果表是否存在与data_label结果表中
        if result_table.data_label:
            data_label_key = (
                f"{result_table.data_label}|{bk_tenant_id}"
                if settings.ENABLE_MULTI_TENANT_MODE
                else result_table.data_label
            )
            data_label_result_table_ids = RedisTools.hget(DATA_LABEL_TO_RESULT_TABLE_KEY, data_label_key)
            data_label_result_table_ids = json.loads(data_label_result_table_ids) if data_label_result_table_ids else []
            if result_table.table_id in data_label_result_table_ids:
                query_router_status.data_label_exists = True
            else:
                query_router_status.messages.append(
                    f"结果表 {result_table.table_id} 在数据标签 {result_table.data_label} 中不存在"
                )
        else:
            # 如果结果表没有data_label，则默认存在
            query_router_status.data_label_exists = True

        # 检查结果表详情是否存
        result_table_detail_key = (
            f"{result_table.table_id}|{bk_tenant_id}" if settings.ENABLE_MULTI_TENANT_MODE else result_table.table_id
        )
        result_table_detail = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, result_table_detail_key)
        if result_table_detail:
            query_router_status.result_table_exists = True

            result_table_detail = json.loads(result_table_detail)

            # 检查结果表详情中的指标信息
            # 特殊判断：trace 和 log 类型的结果表没有固定的 fields 字段
            # 通过 data_label 判断数据类型
            data_label = result_table_detail.get("data_label", "")
            # trace 和 log 类型的 data_label 通常包含 "trace" 或 "log" 关键字
            is_trace_or_log = "trace" in data_label.lower() or "log" in data_label.lower()

            if not result_table_detail.get("fields", []) and not is_trace_or_log:
                query_router_status.messages.append(f"结果表 {result_table.table_id} 详情中没有指标字段")

            if with_detail:
                query_router_status.result_table_detail = result_table_detail
        else:
            query_router_status.messages.append(f"结果表 {result_table.table_id} 详情不存在")

        query_router_statuses.append(query_router_status)

    return query_router_statuses


class DataLinkStatus(BaseModel):
    """数据链路状态"""

    bk_data_id: int | None = Field(description="数据ID")
    data_name: str = Field(description="数据名称")
    is_platform_data_id: bool = Field(description="是否平台数据ID", default=False)
    data_id_status: DataIdStatus | None = Field(description="数据ID状态")
    bkdata_status: BkDataStatus | None = Field(description="数据平台接入状态")
    query_router_statuses: list[QueryRouterStatus] = Field(description="查询路由状态", default=[])


def get_datalink_status(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    data_names: list[str] | None = None,
    bk_data_ids: list[int] | None = None,
    with_detail: bool = False,
):
    """获取数据链路状态

    data_names 和 bk_data_ids 至少一个不能为空

    Args:
        bk_tenant_id: 租户id
        bk_biz_id: 业务id
        data_names: 数据名称列表
        bk_data_ids: 数据ID列表
        with_detail: 是否返回详细信息

    Returns:
        list[DataLinkStatus]: 数据链路状态
    """
    if not data_names and not bk_data_ids:
        raise ValueError("bk_data_names, bk_data_ids 至少一个不能为空")

    # 获取数据源
    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id)
    if data_names:
        data_sources = data_sources.filter(data_name__in=data_names)
    elif bk_data_ids:
        data_sources = data_sources.filter(bk_data_id__in=bk_data_ids)

    result: list[DataLinkStatus] = []
    for data_source in data_sources:
        # 获取数据ID状态
        data_id_status = get_data_id_status(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id=data_source.bk_data_id
        )

        # 获取数据链路状态
        if data_id_status.finished and data_id_status.created_from == DataIdCreatedFromSystem.BKDATA:
            bkdata_status = get_bkdata_status(
                bk_tenant_id=bk_tenant_id, data_link_name=data_id_status.bkbase_data_id_name, with_detail=with_detail
            )
        else:
            bkdata_status = None

        # 获取查询路由状态
        query_router_statuses = get_query_router_status(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id=data_source.bk_data_id, with_detail=with_detail
        )

        result.append(
            DataLinkStatus(
                bk_data_id=data_source.bk_data_id,
                data_name=data_source.data_name,
                is_platform_data_id=data_source.is_platform_data_id,
                data_id_status=data_id_status,
                bkdata_status=bkdata_status,
                query_router_statuses=query_router_statuses,
            )
        )

    if data_names:
        exists_data_names = [data_source.data_name for data_source in data_sources]
        not_exists_data_names = list(set(data_names) - set(exists_data_names))
        for not_exists_data_name in not_exists_data_names:
            result.append(
                DataLinkStatus(
                    bk_data_id=None,
                    data_name=not_exists_data_name,
                    is_platform_data_id=False,
                    data_id_status=None,
                    bkdata_status=None,
                    query_router_statuses=[],
                )
            )
    elif bk_data_ids:
        exists_bk_data_ids = [data_source.bk_data_id for data_source in data_sources]
        not_exists_bk_data_ids = list(set(bk_data_ids) - set(exists_bk_data_ids))
        for not_exists_bk_data_id in not_exists_bk_data_ids:
            result.append(
                DataLinkStatus(
                    bk_data_id=not_exists_bk_data_id,
                    data_name="",
                    is_platform_data_id=False,
                    data_id_status=None,
                    bkdata_status=None,
                    query_router_statuses=[],
                )
            )
    return result


def explain_datalink_status(data_link_status: DataLinkStatus) -> str:
    """解释数据链路状态

    Args:
        data_link_status: 数据链路状态

    Returns:
        对数据链路状态的解释
    """
    message = "--------------------\n"

    # 数据源不存在
    if not data_link_status.data_id_status:
        if not data_link_status.bk_data_id:
            message = f"数据源不存在: {data_link_status.data_name}"
        elif not data_link_status.data_id_status:
            message = f"数据源不存在: {data_link_status.bk_data_id}"
        return message

    # 数据源基本信息
    message += f"""
数据ID: {data_link_status.bk_data_id}
数据名称: {data_link_status.data_name}
是否平台数据: {data_link_status.is_platform_data_id}
来源: {data_link_status.data_id_status.created_from.value if data_link_status.data_id_status.created_from else "未知"}
Kafka是否有数据: {data_link_status.data_id_status.kafka_data_exists}
kafka最新数据时间: {data_link_status.data_id_status.kafka_latest_time.strftime("%Y-%m-%d %H:%M:%S %Z%z") if data_link_status.data_id_status.kafka_latest_time else "未知"}

"""

    # 无数据平台接入状态
    if not data_link_status.bkdata_status:
        message += "无数据平台接入状态\n"
        return message

    # 未接入数据平台
    if not data_link_status.bkdata_status.exists:
        message += "未接入数据平台，请检查相关接入任务\n"

    # 数据平台接入状态
    message += "数据平台接入状态:\n"
    for component_status in data_link_status.bkdata_status.component_statuses:
        message += f"  类型: {component_status.kind}, 名称: {component_status.name}, 状态: {component_status.status}\n"

    if data_link_status.bkdata_status.finished:
        message += "  数据平台接入正常\n"
    else:
        message += f"  数据平台接入异常\n{data_link_status.bkdata_status.message}\n"

    # 查询路由状态
    message += "\n查询路由状态:\n"
    for query_router_status in data_link_status.query_router_statuses:
        if query_router_status.messages:
            query_router_message = ",".join(query_router_status.messages)
            message += f"  结果表{query_router_status.result_table_id}路由异常, {query_router_message}\n"
        else:
            message += f"  结果表{query_router_status.result_table_id}路由正常\n"

    return message


def get_datalink_status_by_scene(
    *,
    scene: str | DataScene,
    bk_tenant_id: str,
    bk_biz_id: int,
    data_names: list[str] | None = None,
    bk_data_id: int | None = None,
    bcs_cluster_id: str | None = None,
    app_name: str | None = None,
    with_detail: bool = False,
) -> list[DataLinkStatus]:
    """根据场景获取数据链路状态

    Args:
        scene: 场景(uptimecheck, custom_metric, host, k8s, apm, custom_event)
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        data_names: 数据名称列表
        bk_data_id: 数据源ID（custom_metric场景必填）
        bcs_cluster_id: 集群ID（k8s场景必填）
        app_name: 应用名称（apm场景必填）
        with_detail: 是否返回详细信息

    """
    result: list[DataLinkStatus] = []

    # 校验场景
    if isinstance(scene, str):
        try:
            scene = DataScene(scene)
        except ValueError as e:
            raise ValueError(f"不支持的场景: {scene}") from e

    if scene == DataScene.UPTIMECHECK:
        data_names = [
            f"uptimecheck_tcp_{bk_biz_id}",
            f"uptimecheck_udp_{bk_biz_id}",
            f"uptimecheck_http_{bk_biz_id}",
            f"uptimecheck_icmp_{bk_biz_id}",
        ]
        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, data_names=data_names, with_detail=with_detail
        )
    elif scene == DataScene.CUSTOM_METRIC:
        if not bk_data_id:
            raise ValueError("bk_data_id 不能为空")
        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_ids=[bk_data_id], with_detail=with_detail
        )
    elif scene == DataScene.HOST:
        data_names = [
            f"{bk_tenant_id}_{bk_biz_id}_sys_base",
            f"base_{bk_biz_id}_system_proc_port",
            f"base_{bk_biz_id}_system_proc_perf",
        ]
        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, data_names=data_names, with_detail=with_detail
        )
    elif scene == DataScene.K8S:
        cluster = BCSClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, cluster_id=bcs_cluster_id
        ).first()
        if not cluster:
            raise ValueError(f"集群不存在: {bcs_cluster_id}")
        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_ids=[cluster.K8sMetricDataID, cluster.CustomMetricDataID],
            with_detail=with_detail,
        )
    elif scene == DataScene.APM:
        # APM 场景：按应用名称查询，包括 Trace、Metric、Log、Profiling 四种数据源
        if not app_name:
            raise ValueError("app_name 不能为空")

        # 查询 APM 应用
        try:
            application = ApmApplication.objects.get(bk_biz_id=bk_biz_id, app_name=app_name, bk_tenant_id=bk_tenant_id)
        except ApmApplication.DoesNotExist:
            raise ValueError(f"APM应用不存在: {app_name}")

        # 使能开关对应的数据源模型
        datasource_models = [
            (application.is_enabled_trace, TraceDataSource),
            (application.is_enabled_metric, MetricDataSource),
            (application.is_enabled_log, LogDataSource),
            (application.is_enabled_profiling, ProfileDataSource),
        ]

        # 收集所有启用的数据源ID
        bk_data_ids = []
        for is_enabled, model_class in datasource_models:
            if is_enabled:
                data_id = (
                    model_class.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name)
                    .values_list("bk_data_id", flat=True)
                    .first()
                )
                if data_id:
                    bk_data_ids.append(data_id)

        if not bk_data_ids:
            # 应用存在但没有启用任何数据源
            return []

        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_ids=bk_data_ids,
            with_detail=with_detail,
        )
    elif scene == DataScene.CUSTOM_EVENT:
        # 自定义事件场景：按业务查询所有自定义事件组
        # 查询业务下的所有自定义事件组
        event_groups = CustomEventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            is_enable=True,
        )

        if not event_groups.exists():
            # 没有自定义事件组，返回空结果
            return []

        bk_data_ids = [group.bk_data_id for group in event_groups]
        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_ids=bk_data_ids,
            with_detail=with_detail,
        )
    elif scene == DataScene.LOG:
        # 日志场景：从 ResultTable 中查询业务下所有日志类型的结果表
        # 日志表的特征 data_label 包含 "log"
        table_ids = list(
            ResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__startswith=f"{bk_biz_id}_",
                data_label__icontains="log",
            ).values_list("table_id", flat=True)
        )

        if not table_ids:
            # 没有日志结果表，返回空结果
            return []

        # 获取这些结果表对应的数据源ID
        data_source_ids = (
            DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
            .values_list("bk_data_id", flat=True)
            .distinct()
        )

        if not data_source_ids:
            return []

        result = get_datalink_status(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_ids=list(data_source_ids),
            with_detail=with_detail,
        )

    return result


def check_datalink_health(
    *,
    bk_tenant_id: str,
    scene: str | DataScene,
    bk_biz_id: int,
    bk_data_id: int | None = None,
    bcs_cluster_id: str | None = None,
    app_name: str | None = None,
    with_detail: bool = False,
) -> str:
    """
    检查数据链路健康状态

    Args:
        bk_tenant_id: 租户ID
        scene: 场景类型
        bk_biz_id: 业务ID
        bk_data_id: 数据源ID（custom_metric场景必填）
        bcs_cluster_id: 集群ID（k8s场景必填）
        app_name: 应用名称（apm场景必填）
        with_detail: 是否返回详细信息
    """
    if isinstance(scene, str):
        try:
            scene = DataScene(scene)
        except ValueError as e:
            raise ValueError(f"不支持的场景: {scene}") from e

    messages: list[str] = []

    # 获取数据链路状态
    data_link_statuses = get_datalink_status_by_scene(
        bk_tenant_id=bk_tenant_id,
        scene=scene,
        bk_biz_id=bk_biz_id,
        with_detail=with_detail,
        bk_data_id=bk_data_id,
        bcs_cluster_id=bcs_cluster_id,
        app_name=app_name,
    )

    # 服务拨测
    if scene == DataScene.UPTIMECHECK:
        messages.append("服务拨测监控的数据链路是按业务创建，包括 TCP、UDP、HTTP、ICMP 四种类型")
    elif scene == DataScene.HOST:
        messages.append("主机监控的数据链路是按业务创建，包括系统基础指标、进程端口和进程性能指标")
    elif scene == DataScene.K8S:
        messages.append(f"Kubernetes 监控的数据链路是按集群创建（集群ID: {bcs_cluster_id}），包括 K8s 指标和自定义指标")
    elif scene == DataScene.APM:
        messages.append(
            f"APM 监控的数据链路是按应用创建（应用: {app_name}），包括 Trace、Metric、Log、Profiling 四种数据源"
        )
    elif scene == DataScene.CUSTOM_EVENT:
        messages.append("自定义事件的数据链路是按事件组创建，每个事件组对应独立的数据源，支持自定义字段结构")
    elif scene == DataScene.LOG:
        messages.append(
            "日志监控的数据链路是按索引集创建，使用 Elasticsearch 存储，支持自由字段结构（schema_type=free）"
        )

    for data_link_status in data_link_statuses:
        messages.append(explain_datalink_status(data_link_status))

    return "\n".join(messages)
