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

import json
from typing import Any

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


class DataIdStatus(BaseModel):
    data_name: str = Field(description="数据源名称", default="")
    exists: bool = Field(description="数据源是否存在", default=False)
    created_from: DataIdCreatedFromSystem | None = Field(description="数据源来源", default=None)

    bkbase_data_id_name: str = Field(description="bkbase数据源名称", default="")
    bkbase_status: str = Field(description="bkbase状态", default="")
    bkbase_config: dict[str, Any] = Field(description="bkbase配置", default={})

    kafka_data_exists: bool = Field(description="Kafka是否存在数据", default=False)
    kafka_latest_timestamp: int = Field(description="Kafka最新数据时间", default=0)
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
    data_id_status = DataIdStatus()

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
        data_id_status.kafka_latest_timestamp = result[0].get("timestamp", 0)
    else:
        data_id_status.kafka_latest_timestamp = 0
    if with_detail:
        data_id_status.kafka_latest_data = result

    data_id_status.finished = True
    return data_id_status


class DataLinkComponentStatus(BaseModel):
    """数据链路组件状态"""

    name: str = Field(description="组件名称")
    exists: bool = Field(description="组件是否存在", default=False)
    config: dict[str, Any] = Field(description="组件配置", default={})
    status: str = Field(description="组件状态", default="Unknown")


class DataLinkStatus(BaseModel):
    """数据链路状态"""

    data_link_name: str = Field(description="数据链路名称")
    exists: bool = Field(description="数据链路是否存在", default=False)
    component_statuses: list[DataLinkComponentStatus] = Field(description="组件状态列表", default=[])

    message: str = Field(description="消息", default="")
    finished: bool = Field(description="是否检查完成", default=False)


def get_datalink_status(bk_tenant_id: str, data_link_name: str, with_detail: bool = False):
    """
    获取清洗任务状态
    """
    datalink_status = DataLinkStatus(data_link_name=data_link_name)

    datalink = DataLink.objects.filter(data_link_name=data_link_name, bk_tenant_id=bk_tenant_id).first()
    if not datalink:
        datalink_status.exists = False
        datalink_status.message = "数据链路不存在"
        return datalink_status

    datalink_status.exists = True

    # 检查组件配置
    status_ok = True
    for component_cls in datalink.STRATEGY_RELATED_COMPONENTS[datalink.data_link_strategy]:
        components = component_cls.objects.filter(data_link_name=data_link_name, bk_tenant_id=bk_tenant_id)
        for component in components:
            component_status = DataLinkComponentStatus(name=component.name)
            component_config = component.component_config
            if not component_config:
                datalink_status.message += f"数据链路 Kind:{component.kind} Name:{component.name}配置不存在\n"
                status_ok = False
                continue

            phase = component_config.get("status", {}).get("phase")

            # 检查组件状态
            if phase != DataLinkResourceStatus.OK.value:
                datalink_status.message += f"数据链路 Kind:{component.kind} Name:{component.name}状态异常\n"
                status_ok = False
                continue

            # 检查组件配置
            component_config: dict[str, Any] | None = component.component_config
            if component_config:
                component_status.config = component_config if with_detail else {}
                component_status.exists = True
            else:
                datalink_status.message += f"数据链路 Kind:{component.kind} Name:{component.name}配置不存在\n"
                status_ok = False
                continue

            datalink_status.component_statuses.append(component_status)

    # 如果组件状态异常，则认为数据链路状态异常
    if not status_ok:
        return datalink_status

    # 如果组件状态列表为空，则认为数据链路不存在
    if not datalink_status.component_statuses:
        datalink_status.message = "数据链路不存在"
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
    """
    获取查询路由状态
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

            # 检查结果表详情中的指标信息
            result_table_detail = json.loads(result_table_detail)
            if with_detail:
                query_router_status.result_table_detail = result_table_detail
        else:
            query_router_status.messages.append(f"结果表 {result_table.table_id} 详情不存在")

        query_router_statuses.append(query_router_status)

    return query_router_statuses


def _get_data_source_status(bk_tenant_id: str, bk_biz_id: int, data_source: DataSource) -> dict[str, Any]:
    data_id_status = get_data_id_status(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id=data_source.bk_data_id
    )
    if data_id_status.finished and data_id_status.created_from == DataIdCreatedFromSystem.BKDATA:
        data_link_status = get_datalink_status(
            bk_tenant_id=bk_tenant_id, data_link_name=data_id_status.bkbase_data_id_name
        )
    else:
        data_link_status = None
    query_router_status = get_query_router_status(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, bk_data_id=data_source.bk_data_id
    )
    return {
        "bk_data_id": data_source.bk_data_id,
        "bk_data_name": data_source.data_name,
        "data_id_status": data_id_status.model_dump(),
        "data_link_status": data_link_status.model_dump() if data_link_status else None,
        "query_router_statuses": [query_router_status.model_dump() for query_router_status in query_router_status],
    }


def check_health(
    scene: str, bk_tenant_id: str, bk_biz_id: int, bk_data_id: int | None = None, bcs_cluster_id: str | None = None
) -> list[dict[str, Any]]:
    """
    检查健康状态
    """
    result: list[dict[str, Any]] = []

    if scene == "uptimecheck":
        data_names = [
            f"uptimecheck_tcp_{bk_biz_id}",
            f"uptimecheck_udp_{bk_biz_id}",
            f"uptimecheck_http_{bk_biz_id}",
            f"uptimecheck_icmp_{bk_biz_id}",
        ]
        data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, data_name__in=data_names)
        for data_source in data_sources:
            result.append(
                _get_data_source_status(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, data_source=data_source)
            )
    elif scene == "custom_metric":
        if not bk_data_id:
            raise ValueError("bk_data_id 不能为空")
        data_source = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).first()
        if not data_source:
            raise ValueError(f"数据源不存在: {bk_data_id}")
        result.append(_get_data_source_status(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, data_source=data_source))
    elif scene == "custom_event":
        raise ValueError("custom_event 暂不支持")
    elif scene == "system":
        data_names = [
            f"{bk_tenant_id}_{bk_biz_id}_sys_base",
            f"base_{bk_biz_id}_system_proc_port",
            f"base_{bk_biz_id}_system_proc_perf",
        ]
        data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, data_name__in=data_names)
        for data_source in data_sources:
            result.append(
                _get_data_source_status(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, data_source=data_source)
            )
    elif scene == "kubernetes":
        cluster = BCSClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, cluster_id=bcs_cluster_id
        ).first()
        if not cluster:
            raise ValueError(f"集群不存在: {bcs_cluster_id}")
        data_sources = DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_data_id__in=[cluster.K8sMetricDataID, cluster.CustomMetricDataID]
        )
        for data_source in data_sources:
            result.append(
                _get_data_source_status(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, data_source=data_source)
            )
    else:
        raise ValueError(f"不支持的场景: {scene}")

    return result
