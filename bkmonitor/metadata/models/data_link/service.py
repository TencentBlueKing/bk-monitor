"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.conf import settings
from django.db.transaction import atomic
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api
from metadata import config
from metadata.models.data_link import DataIdConfig, utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus

logger = logging.getLogger("metadata")


@atomic(config.DATABASE_CONNECTION_NAME)
def apply_data_id_v2(
    bk_tenant_id: str,
    data_name: str,
    bk_biz_id: int,
    namespace: str = settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
    is_base: bool = False,
    event_type: str = "metric",
    prefer_kafka_cluster_name: str | None = None,
) -> bool:
    """
    下发 data_id 资源，并记录对应的资源及配置
    @param bk_tenant_id: 租户ID
    @param data_name: 数据源名称
    @param namespace: 资源命名空间
    @param bk_biz_id: 业务ID
    @param is_base: 是否是基础数据源
    @param event_type: 数据类型
    """
    logger.info("apply_data_id_v2:apply data_id for data_name: %s,event_type: %s", data_name, event_type)

    if is_base:  # 如果是基础数据源（1000,1001）,那么沿用固定格式的data_name，会以此name作为bkbase申请时的唯一键
        bkbase_data_name = data_name
    else:  # 用户自定义数据源，需要进行二次处理，主要为避免超过meta长度限制和特殊字符
        bkbase_data_name = utils.compose_bkdata_data_id_name(data_name)

    logger.info("apply_data_id_v2:bkbase_data_name: %s", bkbase_data_name)

    data_id_config_ins, _ = DataIdConfig.objects.get_or_create(
        name=bkbase_data_name, namespace=namespace, bk_biz_id=bk_biz_id, bk_tenant_id=bk_tenant_id
    )
    data_id_config = data_id_config_ins.compose_config(
        event_type=event_type,
        prefer_kafka_cluster_name=prefer_kafka_cluster_name,
    )

    api.bkdata.apply_data_link(config=[data_id_config], bk_tenant_id=bk_tenant_id)
    logger.info("apply_data_id_v2:apply data_id for data_name: %s success", data_name)
    return True


def get_data_id_v2(
    data_name: str,
    bk_biz_id: int,
    namespace: str | None = settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
    is_base: bool = False,
    with_detail: bool = False,
) -> dict:
    """
    获取数据源对应的 data_id
    """
    logger.info("get_data_id: data_name->[%s]", data_name)
    if is_base:  # 如果是基础数据源（1000,1001）,那么沿用固定格式的data_name，会以此name作为bkbase申请时的唯一键
        data_id_name = data_name
    else:  # 用户自定义数据源，需要进行二次处理，主要为避免超过meta长度限制和特殊字符
        data_id_name = utils.compose_bkdata_data_id_name(data_name)

    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)

    data_id_config = api.bkdata.get_data_link(
        kind=DataLinkKind.get_choice_value(DataLinkKind.DATAID.value),
        namespace=namespace,
        name=data_id_name,
        bk_tenant_id=bk_tenant_id,
    )
    data_id_config_ins = DataIdConfig.objects.get(name=data_id_name, namespace=namespace, bk_tenant_id=bk_tenant_id)
    logger.info("get_data_id: request bkbase data_id_config->[%s]", data_id_config)
    # 解析数据获取到数据源ID
    phase = data_id_config.get("status", {}).get("phase")
    # 如果状态不是处于正常的终态，则返回 None
    if phase == DataLinkResourceStatus.OK.value:
        data_id = int(data_id_config.get("metadata", {}).get("annotations", {}).get("dataId", 0))
        data_id_config_ins.status = phase
        data_id_config_ins.save()
        logger.info("get_data_id: request data_name -> [%s] now is ok", data_name)
        if with_detail:
            return {"status": phase, "data_id": data_id, "data_id_config": data_id_config}
        return {"status": phase, "data_id": data_id}

    data_id_config_ins.status = phase
    data_id_config_ins.save()
    logger.info("get_data_id: request data_name -> [%s] ,phase->[%s]", data_name, phase)
    if with_detail:
        return {"status": phase, "data_id": None, "data_id_config": data_id_config}
    return {"status": phase, "data_id": None}


def get_data_link_component_config(
    bk_tenant_id: str,
    kind: str,
    component_name: str,
    namespace: str | None = settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
):
    """
    获取数据链路组件状态
    @param kind: 数据链路组件类型
    @param component_name: 数据链路组件名称
    @param namespace: 数据链路命名空间
    @return: 状态
    """
    logger.info(
        "get_data_link_component_config: try to get component config,kind->[%s],name->[%s],namespace->[%s]",
        kind,
        component_name,
        namespace,
    )
    try:
        bkbase_kind = DataLinkKind.get_choice_value(kind)
        if not bkbase_kind:
            logger.info("get_data_link_component_config: kind is not valid,kind->[%s]", kind)
        component_config = api.bkdata.get_data_link(
            bk_tenant_id=bk_tenant_id, kind=bkbase_kind, namespace=namespace, name=component_name
        )
        return component_config
    except Exception as e:
        logger.error(
            "get_data_link_component_config: get component config failed,kind->[%s],name->[%s],namespace->[%s],"
            "error->[%s]",
            kind,
            component_name,
            namespace,
            e,
        )
        return None


def get_data_link_component_status(
    bk_tenant_id: str,
    kind: str,
    component_name: str,
    namespace: str = settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
):
    """
    获取数据链路组件状态
    @param kind: 数据链路组件类型
    @param component_name: 数据链路组件名称
    @param namespace: 数据链路命名空间
    @return: 状态
    """
    logger.info(
        "get_data_link_component_status: try to get component status,kind->[%s],name->[%s],namespace->[%s]",
        kind,
        component_name,
        namespace,
    )
    try:
        bkbase_kind = DataLinkKind.get_choice_value(kind)
        if not bkbase_kind:
            logger.info("get_data_link_component_status: kind is not valid,kind->[%s]", kind)
        component_config = get_bkbase_component_status_with_retry(
            bk_tenant_id=bk_tenant_id, kind=bkbase_kind, namespace=namespace, name=component_name
        )
        phase = component_config.get("status", {}).get("phase")
        return phase
    except RetryError as e:
        logger.error(
            "get_data_link_component_status: get component status failed,kind->[%s],name->[%s],namespace->["
            "%s],error->[%s]",
            kind,
            component_name,
            namespace,
            e.__cause__,
        )
        return DataLinkResourceStatus.FAILED.value
    except Exception as e:
        logger.error(
            "get_data_link_component_status: get component status failed,kind->[%s],name->[%s],namespace->[%s],"
            "error->[%s]",
            kind,
            component_name,
            namespace,
            e,
        )
        return DataLinkResourceStatus.FAILED.value


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_bkbase_component_status_with_retry(
    bk_tenant_id: str,
    kind: str,
    namespace: str,
    name: str,
):
    """
    获取bkbase组件状态，具备重试机制
    """
    try:
        return api.bkdata.get_data_link(bk_tenant_id=bk_tenant_id, kind=kind, namespace=namespace, name=name)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "get_bkbase_component_status_with_retry: get component status failed,kind->[%s],name->[%s],error->[%s]",
            kind,
            name,
            e,
        )
        raise e
