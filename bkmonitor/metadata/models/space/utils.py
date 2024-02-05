# -*- coding: utf-8 -*-
import json
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.translation import ugettext as _

from core.drf_resource import api
from core.errors.bkmonitor.space import SpaceNotFound
from metadata import config
from metadata.models import (
    DataSource,
    DataSourceResultTable,
    ResultTable,
    ResultTableField,
    TimeSeriesGroup,
)
from metadata.models.bcs import BCSClusterInfo
from metadata.models.constants import BULK_CREATE_BATCH_SIZE

from .constants import (
    BKCI_AUTHORIZED_DATA_ID_LIST,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    SPACE_DATASOURCE_ETL_LIST,
    SYSTEM_USERNAME,
    BCSClusterTypes,
    SpaceStatus,
    SpaceTypes,
)
from .space import Space, SpaceDataSource, SpaceResource, SpaceType

logger = logging.getLogger("metadata")


def list_spaces(
    space_type_id: Optional[str] = None,
    space_id: Optional[str] = None,
    space_name: Optional[str] = None,
    id: Optional[int] = None,
    is_exact: Optional[bool] = False,
    is_detail: Optional[bool] = False,
    page: Optional[int] = DEFAULT_PAGE,
    page_size: Optional[int] = DEFAULT_PAGE_SIZE,
    exclude_platform_space: Optional[bool] = True,
    include_resource_id: Optional[bool] = False,
) -> Dict:
    """查询空间实例信息

    :param space_type_id: 空间类型ID
    :param space_id: 空间ID
    :param space_name: 空间中文名称
    :param id: 空间自增 ID
    :param is_exact: 是否精确查询
    :param is_detail: 是否需要更详细信息, 如果为True，则返回所有数据
    :param page: 分页
    :param page_size: 每页的数量
    :param exclude_platform_space: 过滤掉平台级的空间
    :param include_resource_id: 包含资源 id
    :return: 空间列表信息
    """
    # 获取空间类型 ID 和 空间类型名称
    space_type_id_name = {obj["type_id"]: obj["type_name"] for obj in SpaceType.objects.values("type_id", "type_name")}
    space_info = Space.objects.list_all_spaces(
        space_type_id,
        space_id,
        space_name,
        id,
        is_exact,
        page,
        page_size,
        exclude_platform_space,
        space_type_id_name,
    )
    # 如果不需要详情，也不需要资源 id 时，直接忽略
    if not (is_detail or include_resource_id):
        return space_info

    # 包含资源 id 优先级高于查询详情, 如果需要资源 id, 则直接返回
    spaces = [(space["space_type_id"], space["space_id"]) for space in space_info["list"]]
    if include_resource_id:
        # 组装空间列表，分组过滤关联的资源 ID，避免单次过滤时，where 条件太多，导致慢查询
        space_resource = _filter_space_resource_by_page(spaces)
        for space in space_info["list"]:
            key = (space["space_type_id"], space["space_id"])
            space["resources"] = space_resource.get(key, [])
        return space_info

    # 追加空间关联的资源信息
    # 用于后续资源的匹配，组装数据格式: {(空间类型ID, 空间ID): 空间信息}
    space_type_ids, space_ids = [], []
    for s in space_info["list"]:
        space_type_ids.append(s["space_type_id"])
        space_ids.append(s["space_id"])
    # 获取 data id
    space_data_source = SpaceDataSource.objects.filter(space_type_id__in=space_type_ids, space_id__in=space_ids).values(
        "space_type_id", "space_id", "bk_data_id", "from_authorization"
    )
    # 转换为数据格式: {(空间类型ID, 空间ID): [{"bk_dta_id": "", "from_authorization": False}]}
    # 添加平台级的 data id
    platform_data_id = get_platform_data_id_list()
    space_data_source_dict = {}
    for sd in space_data_source:
        key = (sd["space_type_id"], sd["space_id"])
        val = {"bk_data_id": sd["bk_data_id"], "from_authorization": sd["from_authorization"]}
        if key in space_data_source_dict:
            space_data_source_dict[key].append(val)
        else:
            _data_id_list = [val]
            _data_id_list.extend(platform_data_id)
            # 添加空间级 data id
            _data_id_list.extend(get_space_data_id_list(sd["space_type_id"]))
            space_data_source_dict[key] = _data_id_list
    # 获取资源
    space_resource = SpaceResource.objects.filter(space_type_id__in=space_type_ids, space_id__in=space_ids).values(
        "space_type_id", "space_id", "resource_type", "resource_id"
    )
    # 转换数据格式: {(空间类型ID, 空间ID): [{"resource_type": "", "resource_id": ""}]}
    space_resource_dict = {}
    for sr in space_resource:
        key = (sr["space_type_id"], sr["space_id"])
        val = {"resource_type": sr["resource_type"], "resource_id": sr["resource_id"]}
        if key in space_resource_dict:
            space_resource_dict[key].append(val)
        else:
            space_resource_dict[key] = [val]
    # 组装数据
    for s in space_info["list"]:
        key = (s["space_type_id"], s["space_id"])
        s["data_sources"] = space_data_source_dict.get(key, [])
        s["resources"] = space_resource_dict.get(key, [])
    # 返回带有更详细信息的空间列表
    return space_info


def _filter_space_resource_by_page(spaces: List) -> Dict:
    """过滤关联空间资源
    :param spaces: 空间列表
    :return: 过滤到的空间资源数据
    """
    default_ret_data = {}
    if not spaces:
        return default_ret_data
    # NOTE: 这里不要设置太大
    page_size = 500
    chunk_list = [spaces[i : i + page_size] for i in range(0, len(spaces), page_size)]

    # 空间关联的资源数据
    space_resource_data = []
    for chunk in chunk_list:
        # 组装过滤数据
        filter_q = Q()
        for space in chunk:
            filter_q |= Q(space_type_id=space[0], space_id=space[1])
        space_resource_data.extend(
            list(
                SpaceResource.objects.filter(filter_q).values(
                    "space_type_id", "space_id", "resource_type", "resource_id"
                )
            )
        )

    # 组装空间和资源的映射
    space_resource_dict = {}
    for space_resource in space_resource_data:
        space_resource_dict.setdefault((space_resource["space_type_id"], space_resource["space_id"]), []).append(
            {"resource_type": space_resource["resource_type"], "resource_id": space_resource["resource_id"]}
        )

    return space_resource_dict


def get_space_detail(
    space_type_id: Optional[str] = None, space_id: Optional[str] = None, id: Optional[int] = None
) -> Dict:
    """查询空间的详情， 包含基本属性及关联的资源信息

    :param space_type_id: 空间类型 ID
    :param space_id: 空间 ID
    :param id: 空间自增 ID
    :return: 返回空间详情
    """
    try:
        if id:
            space_obj = Space.objects.get(id=id)
        else:
            space_obj = Space.objects.get(space_type_id=space_type_id, space_id=space_id)
    except Space.DoesNotExist:
        logger.error("space type id: %s, space: %s not found", space_type_id, space_id)
        raise SpaceNotFound(space_type_id=space_type_id, space_id=space_id)
    # 判断 BCS 是否可用
    space_resource = SpaceResource.objects.filter(space_type_id=space_obj.space_type_id, space_id=space_obj.space_id)
    if space_obj.is_bcs_valid:
        space_resource = space_resource.exclude(resource_type=SpaceTypes.BCS.value)
    # 然后关联的资源信息
    resources = list(space_resource.values("resource_type", "resource_id"))
    # 相关的 data id
    data_sources = list(
        SpaceDataSource.objects.filter(space_type_id=space_obj.space_type_id, space_id=space_obj.space_id).values(
            "bk_data_id", "from_authorization"
        )
    )

    # 组合返回数据
    detail = space_obj.to_dict()
    # 关联的资源和数据源信息
    detail["resources"] = resources
    detail["data_sources"] = data_sources

    return detail


def get_dimension_values(space_type_id: str, space_id: str, resource_type: Optional[str] = None) -> List:
    """获取资源的维度数据"""
    space_resources = SpaceResource.objects.filter(space_type_id=space_type_id, space_id=space_id)
    if resource_type:
        space_resources = space_resources.filter(resource_type=resource_type)
    dimension_list = []
    for r in space_resources:
        dimension_list.extend(r.dimension_values)
    return dimension_list


@atomic(config.DATABASE_CONNECTION_NAME)
def create_space(
    creator: str,
    space_id: str,
    space_type_id: str,
    space_name: str,
    resources: Optional[List] = None,
    space_code: Optional[str] = "",
) -> Dict:
    """创建空间

    如果需要关联资源，则创建关联资源信息

    :param creator: 创建者
    :param space_id: 空间 ID
    :param space_type_id: 空间类型 ID
    :param space_name: 空间中文名称
    :param resources: 绑定的资源信息，如[{"resource_type": "xxx", "resource_id": "xxx"}]
    :param space_code: 空间 Code，用于标识 BCS 的项目 ID
    :return: 空间的详情
    """
    # 创建空间实例
    params = {
        "creator": creator,
        "space_type_id": space_type_id,
        "space_id": space_id,
        "space_code": space_code,
        "space_name": space_name,
        "status": SpaceStatus.NORMAL.value,
    }
    # NOTE: 针对空间 code 不为空时，认为开启容器服务功能
    if space_code:
        params["is_bcs_valid"] = True

    space_obj = Space.objects.create(**params)

    # NOTE: 针对 bkci 类型 需要授权一下空间访问 1001(唯一一个跨空间类型查询的场景)
    try:
        if space_type_id == SpaceTypes.BKCI.value:
            # 正常创建空间前不会存在，直接创建
            authorize_data_id_list(space_type_id, space_id, BKCI_AUTHORIZED_DATA_ID_LIST)
    except Exception as e:
        logger.error(
            "authorize space datasource error, space_type: %s, space_id: %s, data_ids: %s, error: %s",
            space_type_id,
            space_id,
            json.dumps(BKCI_AUTHORIZED_DATA_ID_LIST),
            e,
        )

    # 针对 bksaas 授权使用的集群及 PaaS 特定的数据源
    try:
        if space_type_id == SpaceTypes.BKSAAS.value:
            authorize_data_id_list(space_type_id, space_id, settings.BKPAAS_AUTHORIZED_DATA_ID_LIST)
            create_bksaas_space_resource(space_type_id, space_id, creator)
    except Exception as e:
        logger.error(
            "create space datasource error, space_type: %s, space_id: %s, error: %s",
            space_type_id,
            space_id,
            e,
        )
    # 关联资源
    # 考虑到关联类型不会太多，直接展开处理
    resources = resources or []
    for r in resources:
        res = SpaceResource.objects.filter(
            resource_type=r["resource_type"],
            resource_id=r["resource_id"],
        ).first()
        # 解析到dimension fields
        dimension_fields = SpaceType.objects.get(type_id=r["resource_type"]).dimension_fields
        # 如果绑定的资源不存在，则设置为空；然后如果有设置关键维度，默认取第一个维度并设置为资源ID
        dimension_values = res.dimension_values if res else []
        if dimension_fields:
            dimension_values = [{dimension_fields[0]: r["resource_id"]}]
        # TODO:如果查询不到，则需要通过具体的系统去查询相应的资源
        # 先默认到 `资源 ID`
        SpaceResource.objects.create(
            creator=creator,
            space_type_id=space_type_id,
            space_id=space_id,
            resource_type=r["resource_type"],
            resource_id=r["resource_id"],
            dimension_values=dimension_values,
        )

        logger.info(
            "create space resource successfully, "
            "space_type_id: %s, space: %s, resource_type_id: %s, resource: %s, dimension: %s",
            space_type_id,
            space_id,
            r["resource_type"],
            r["resource_id"],
            json.dumps(dimension_values),
        )

    return space_obj.to_dict()


def bulk_create_space_data_source(
    space_type: str, space_id: str, data_id_list: List, from_authorization: Optional[bool] = True
):
    """批量创建空间和数据源关系"""
    bulk_create_records = []
    for data_id in data_id_list:
        bulk_create_records.append(
            SpaceDataSource(
                space_type_id=space_type, space_id=space_id, bk_data_id=data_id, from_authorization=from_authorization
            )
        )
    # 批量创建
    SpaceDataSource.objects.bulk_create(bulk_create_records, batch_size=BULK_CREATE_BATCH_SIZE)


def authorize_data_id_list(space_type: str, space_id: str, data_id_list: List):
    """针对指定类型授权特定的数据源"""
    logger.info(
        "start to authorize data id, space_type: %s, space_id: %s, data_id_list: %s",
        space_type,
        space_id,
        json.dumps(data_id_list),
    )
    if not data_id_list:
        return
    used_data_ids = SpaceDataSource.objects.filter(
        space_type_id=space_type, space_id=space_id, bk_data_id__in=data_id_list
    ).values_list("bk_data_id", flat=True)
    need_created_data_ids = set(data_id_list) - set(used_data_ids)
    try:
        bulk_create_space_data_source(space_type, space_id, list(need_created_data_ids), from_authorization=True)
    except Exception as e:
        logger.error(
            "bulk create space datasource failed, data_id_list: %s, error: %s", json.dumps(need_created_data_ids), e
        )
        return

    logger.info("authorize data id successfully, data_id_list: %s", json.dumps(data_id_list))


@atomic(config.DATABASE_CONNECTION_NAME)
def create_bksaas_space_resource(space_type: str, space_id: str, creator: str):
    """创建蓝鲸应用类型关联的空间资源"""
    logger.info("create and authorize bksaas space resource, space_type: %s, space_id: %s", space_type, space_id)
    # 通过蓝鲸应用的空间 ID 获取使用的集群信息
    cluster_namespaces = api.bk_paas.get_app_cluster_namespace(app_code=space_id)
    if not cluster_namespaces:
        return

    # 组装数据
    _cluster_ns = {}
    for cn in cluster_namespaces:
        _cluster_ns.setdefault(cn["bcs_cluster_id"], []).append(cn["namespace"])

    # 提取集群，然后获取集群的内置指标数据
    dimension_values = []
    for cluster_id, ns_list in _cluster_ns.items():
        dimension_values.append(
            {
                "cluster_id": cluster_id,
                "namespace": ns_list,
                "cluster_type": BCSClusterTypes.SHARED.value,
            }
        )
    # 组装绑定的资源数据
    try:
        SpaceResource.objects.create(
            creator=creator,
            space_type_id=space_type,
            space_id=space_id,
            resource_type=space_type,
            resource_id=space_id,
            dimension_values=dimension_values,
        )
    except Exception as e:
        logger.error(
            "create space resource failed, space_type: %s, space_id: %s, dimension_values: %s  error: %s",
            space_type,
            space_id,
            json.dumps(dimension_values),
            e,
        )
        raise

    clusters = set(_cluster_ns.keys())
    # 获取集群的内置指标进行授权
    ks8_metric_data_ids = list(
        BCSClusterInfo.objects.filter(cluster_id__in=clusters).values_list("K8sMetricDataID", flat=True)
    )
    # 然后进行批量授权
    try:
        bulk_create_space_data_source(space_type, space_id, ks8_metric_data_ids, from_authorization=True)
    except Exception as e:
        logger.error(
            "bulk create space datasource of k8s metric failed, data_id_list: %s, error: %s",
            json.dumps(ks8_metric_data_ids),
            e,
        )
        raise


@atomic(config.DATABASE_CONNECTION_NAME)
def update_space(
    updater: str, space_type_id: str, space_id: str, space_name: str, space_code: str, resources: List
) -> Dict:
    """更新空间信息

    :param updater: 更新者
    :param space_type_id: 空间类型 ID
    :param space_id: 空间 ID
    :param space_name: 空间中文名称
    :param space_code: 空间 Code，用于标识 BCS 的项目 ID
    :param resources: 绑定的资源信息，如[{"resource_type": "xxx", "resource_id": "xxx"}]
    :return: 空间的详细信息
    """
    space_obj = Space.objects.get(space_type_id=space_type_id, space_id=space_id)
    # 更新名称
    if space_name:
        space_obj.space_name = space_name
        space_obj.save(update_fields=["space_name"])
    # 更新空间编码
    if space_code:
        space_obj.space_code = space_code
        # 如果有设置空间编码，则标识开启容器服务
        space_obj.is_bcs_valid = True
        space_obj.save(update_fields=["space_code", "is_bcs_valid"])

    # 如果有关联资源，则更新关联的资源
    for r in resources:
        res = SpaceResource.objects.filter(resource_type=r["resource_type"], resource_id=r["resource_id"]).first()
        # 解析到dimension fields
        dimension_fields = SpaceType.objects.get(type_id=r["resource_type"]).dimension_fields
        # 如果绑定的资源不存在，则设置为空；然后如果有设置关键维度，默认取第一个维度并设置为资源ID
        dimension_values = res.dimension_values if res else []
        if dimension_fields:
            dimension_values = [{dimension_fields[0]: r["resource_id"]}]
        # 更新需要绑定的资源
        SpaceResource.objects.update_or_create(
            space_type_id=r["resource_type"],
            space_id=space_id,
            resource_type=r["resource_type"],
            resource_id=r["resource_id"],
            defaults={
                "updater": updater,
                "dimension_values": dimension_values,
            },
        )
        logger.info(
            "update or create space resource successfully, "
            "space_type_id: %s, space: %s, resource_type_id: %s, resource: %s, dimension: %s",
            r["resource_type"],
            space_id,
            r["resource_type"],
            r["resource_id"],
            json.dumps(dimension_values),
        )

    return space_obj.to_dict()


@atomic(config.DATABASE_CONNECTION_NAME)
def merge_space(src_space_type_id: str, src_space_id: str, dst_space_type_id, dst_space_id: str):
    """合并空间

    注意: 需要讨论下，如下处理是否合适

    :param src_space_type_id: 源空间类型 ID
    :param src_space_id: 源空间 ID，要合并的空间
    :param dst_space_id: 目的空间类型 ID
    :param dst_space_id: 目的空间 ID，合并到的空间
    :return:
    """
    # 校验绑定的资源可以合并
    src_space_resources = SpaceResource.objects.filter(space_type_id=src_space_type_id, space_id=src_space_id).values(
        "resource_type", "resource_id", "dimension_values"
    )
    dst_space_resources = SpaceResource.objects.filter(space_type_id=dst_space_type_id, space_id=dst_space_id).values(
        "resource_type", "resource_id", "dimension_values"
    )
    # 如果出现资源类型一样，但是资源ID不一样，则抛出异常
    src_space_resource_ids = {sr["resource_type"]: sr for sr in src_space_resources}
    dst_space_resource_ids = {sr["resource_type"]: sr for sr in dst_space_resources}
    # 处理资源
    diff_resource_ids = []
    added_resource_ids = []
    for resource_type, sr in src_space_resource_ids.items():
        if (
            resource_type in dst_space_resource_ids
            and sr["resource_id"] != dst_space_resource_ids[resource_type]["resource_id"]
        ):
            diff_resource_ids.append(sr)
            continue
        if resource_type not in dst_space_resource_ids:
            added_resource_ids.append(sr)
    if diff_resource_ids:
        raise ValueError(_("绑定的资源类型下的资源不一致，不能合并"))

    # 1. 查询源空间
    src_space_obj = Space.objects.get(space_type_id=src_space_type_id, space_id=src_space_id)
    # 2. 查询空间下关联的 data id
    src_space_data_ids = SpaceDataSource.objects.filter(
        space_type_id=src_space_type_id, space_id=src_space_id, from_authorization=False
    ).values_list("bk_data_id", flat=True)
    dst_space_data_ids = SpaceDataSource.objects.filter(
        space_type_id=dst_space_type_id, space_id=dst_space_id, from_authorization=False
    ).values_list("bk_data_id", flat=True)

    # 3. 更新 data id 授权范围, 去除相同的 data id
    added_space_data_source = []
    for d in set(src_space_data_ids) - set(dst_space_data_ids):
        added_space_data_source.append(
            SpaceDataSource(
                space_type_id=dst_space_type_id, space_id=dst_space_id, bk_data_id=d.bk_data_id, from_authorization=True
            )
        )
    if added_space_data_source:
        SpaceDataSource.objects.bulk_create(added_space_data_source)
    # 4. 合并资源，去除相同的资源
    add_space_resources = [
        SpaceResource(space_type_id=dst_space_type_id, space_id=dst_space_id, **sr) for sr in added_resource_ids
    ]
    SpaceResource.objects.bulk_update(add_space_resources)
    # 禁用源空间
    src_space_obj.status = SpaceStatus.DISABLED.value
    src_space_obj.save(update_fields=["status"])


def disable_space(spaces: List[Dict]):
    """禁用空间

    现阶段只是设置状态为disabled
    :param spaces: 空间信息，如[{"space_type_id": "bcs", "space_id": "testproject"}]
    """
    filter_q = Q()
    for s in spaces:
        filter_q |= Q(space_type_id=s["space_type_id"], space_id=s["space_id"])
    # 更新状态
    filtered_spaces = Space.objects.filter(filter_q)
    filtered_spaces.update(status=SpaceStatus.DISABLED.value)

    return [s.to_dict() for s in filtered_spaces]


def get_platform_data_id_list() -> List:
    """获取平台级 data id"""
    return list(
        DataSource.objects.filter(is_platform_data_id=True, space_type_id=SpaceTypes.ALL.value).values_list(
            "bk_data_id", flat=True
        )
    )


def get_space_data_id_list(space_type_id: str) -> List:
    """获取空间级 data id

    也就是允许相同空间类型下的空间访问
    """
    return list(
        DataSource.objects.filter(is_platform_data_id=True, space_type_id=space_type_id).values_list(
            "bk_data_id", flat=True
        )
    )


def get_platform_result_table_id_list() -> List:
    """获取平台级及空间级的结果表 ID"""
    data_id_list = get_platform_data_id_list()
    return list(DataSourceResultTable.objects.filter(bk_data_id__in=data_id_list).values_list("table_id", flat=True))


def get_result_table_data_id_dict(data_id_list: Optional[List] = None, table_id: Optional[str] = None) -> Dict:
    """通过 data id 获取结果表映射"""
    qs = DataSourceResultTable.objects.all()
    if data_id_list:
        qs = DataSourceResultTable.objects.filter(bk_data_id__in=data_id_list)
    if table_id:
        qs = qs.filter(table_id=table_id)
    return {d["table_id"]: d["bk_data_id"] for d in qs.values("table_id", "bk_data_id")}


def get_platform_result_table_list() -> List:
    """获取平台级的结果表信息"""
    result_table_id_list = get_platform_result_table_id_list()
    return ResultTable.objects.filter(table_id__in=result_table_id_list).values("table_id", "schema_type", "data_label")


def get_result_table_list(filter_platform: Optional[bool] = False, table_id_list: Optional[List] = None) -> List:
    """过滤结果表数据"""
    if filter_platform:
        return get_platform_result_table_list()
    return ResultTable.objects.filter(table_id__in=table_id_list).values("table_id", "schema_type", "data_label")


def get_platform_result_table_field_list(tag: str = "metric") -> List:
    """获取平台级的结果表指标属性信息"""
    result_table_id_list = get_platform_result_table_id_list()
    return ResultTableField.objects.filter(table_id__in=result_table_id_list, tag=tag).values("table_id", "field_name")


def get_data_id_list_by_biz_id(bk_biz_id: int) -> List:
    """获取业务下的 data id

    仅为归属业务下的 data id
    """
    # 过滤到结果表和业务列表
    rt_filter = ResultTable.objects.filter(is_deleted=False)
    table_id_list = rt_filter.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True)
    # 过滤对应的 data id
    return DataSourceResultTable.objects.filter(table_id__in=table_id_list).values_list("bk_data_id", flat=True)


def get_metadata_project_dict(project_id: Optional[str] = None, desire_all_data: Optional[bool] = False) -> Dict:
    """获取 metadata 中存储的项目数据"""
    project_cluster = BCSClusterInfo.objects.filter(status="running")
    data = []
    if desire_all_data:
        data = list(project_cluster.values("project_id", "cluster_id"))
    elif project_id:
        data = list(project_cluster.filter(project_id=project_id).values("project_id", "bk_biz_id", "cluster_id"))
    # 拼装数据，格式为 {project_id: set([cluster_id1, cluster_id2])}
    project_cluster = {}
    for d in data:
        p_id, c_id = d["project_id"], d["cluster_id"]
        if p_id in project_cluster:
            project_cluster[p_id].add(c_id)
        else:
            project_cluster[p_id] = {c_id}

    return project_cluster


def get_data_id_by_cluster(cluster_id: Optional[str] = None, desire_all_data: Optional[bool] = False) -> Dict:
    """通过集群获取数据源"""
    # 获取相应的记录
    bcs_cluster = BCSClusterInfo.objects.filter(status="running")
    # 组装数据
    cluster_data_id_dict = {}
    data = []
    if cluster_id:
        bcs_cluster = bcs_cluster.filter(cluster_id=cluster_id)
    elif not desire_all_data:
        # 其它情况时，返回为空
        logger.error("query data id by cluster_id error, cluster_id is null")
        return cluster_data_id_dict
    # 添加集群默认的
    # NOTE: 暂时不需要 event 相关的路由
    for c in bcs_cluster:
        data.append({"cluster_id": c.cluster_id, "bk_data_id": c.K8sMetricDataID})
        data.append({"cluster_id": c.cluster_id, "bk_data_id": c.CustomMetricDataID})

    # 组装格式为: {cluster_id: set([data_id1, data_id2])}
    for d in data:
        cluster_id = d["cluster_id"]
        bk_data_id = d["bk_data_id"]
        if cluster_id in cluster_data_id_dict:
            cluster_data_id_dict[cluster_id].add(bk_data_id)
        else:
            cluster_data_id_dict[cluster_id] = {bk_data_id}

    return cluster_data_id_dict


def get_shared_cluster_namespaces(cluster_id: str, project_code: str) -> List:
    """获取共享集群的命名空间信息"""
    # 通过 project manager api 项目使用获取共享集群的命名空间
    try:
        return api.bcs.fetch_shared_cluster_namespaces(cluster_id=cluster_id, project_code=project_code)
    except Exception as e:
        logging.error("request shared cluster namespace error, err: %s", e)
        return []


def get_project_clusters(project_id: str) -> List:
    """获取项目下的集群列表"""
    try:
        return api.bcs_cluster_manager.get_project_clusters(project_id=project_id)
    except Exception as e:
        logger.error("request project cluster list error, err: %s", e)
        return []


def get_space_shared_namespaces(space_id: str):
    """获取共享命名空间信息"""
    shared_clusters = api.bcs_cluster_manager.get_shared_clusters()
    shared_cluster_namespaces = []
    for cluster in shared_clusters:
        shared_cluster_namespaces.extend(
            get_shared_cluster_namespaces(cluster_id=cluster["cluster_id"], project_code=space_id)
        )

    cluster_namespace_dict = {}
    for d in shared_cluster_namespaces:
        cluster_id, ns = d["cluster_id"], d["namespace"]
        if cluster_id in cluster_namespace_dict:
            cluster_namespace_dict[cluster_id].append(ns)
        else:
            cluster_namespace_dict[cluster_id] = [ns]

    return cluster_namespace_dict


@atomic(config.DATABASE_CONNECTION_NAME)
def create_bkcc_spaces(biz_list: List) -> bool:
    """创建业务对应的空间信息

    NOTE: 业务类型，不需要关联资源

    :param biz_list: 需要创建的业务列表，需要包含业务ID、业务中文名称
    :return: 返回 True 或异常
    """
    space_data = []
    for biz in biz_list:
        space_data.append(
            Space(
                creator=SYSTEM_USERNAME,
                updater=SYSTEM_USERNAME,
                space_type_id=SpaceTypes.BKCC.value,
                space_id=str(biz["bk_biz_id"]),
                space_name=biz["bk_biz_name"],
            )
        )

    Space.objects.bulk_create(space_data)
    logger.info("bulk create bkcc space successfully, space: %s", json.dumps(biz_list))

    return True


@atomic(config.DATABASE_CONNECTION_NAME)
def create_bkcc_space_data_source(biz_data_id_dict: Dict):
    """批量创建空间和数据源的关系"""
    space_data_source, data_id_list = [], []
    # 添加归属空间的 data id 关联
    for biz_id, data_ids in biz_data_id_dict.items():
        # 忽略 0 业务的数据源，不创建
        if biz_id == 0 or not data_ids:
            continue
        data_id_list.extend(data_ids)
        for id in set(data_ids):
            space_data_source.append(
                SpaceDataSource(
                    creator=SYSTEM_USERNAME,
                    updater=SYSTEM_USERNAME,
                    space_type_id=SpaceTypes.BKCC.value,
                    space_id=str(biz_id),
                    bk_data_id=id,
                )
            )

    SpaceDataSource.objects.bulk_create(space_data_source)
    # 设置数据源类型为 bkcc
    set_data_source_space_type(data_id_list, SpaceTypes.BKCC.value)


def add_cluster_data_id_list(space_type_id: str, space_id: str, cluster_data_id_list: List, is_shared: bool) -> List:
    """添加集群下的data id

    针对共享集群时，data id为授权项目访问
    """
    item = {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "space_type_id": space_type_id,
        "space_id": space_id,
        "from_authorization": True,
    }
    data = []
    if is_shared:
        for data_id in cluster_data_id_list:
            item["bk_data_id"] = int(data_id)
            data.append(SpaceDataSource(**item))
    else:
        for data_id in cluster_data_id_list:
            item["bk_data_id"] = int(data_id)
            item["from_authorization"] = False
            data.append(SpaceDataSource(**item))
    return data


def compose_bcs_space_data_source(
    space_type_id: str,
    space_id: str,
    data_id_list: List,
    project_cluster_data_id_list: List,
    shared_cluster_data_id_list: List,
) -> List:
    """处理重复的数据"""
    exist_data_id_list = []
    _data_id_set = set(project_cluster_data_id_list)
    _data_id_set = _data_id_set.union(shared_cluster_data_id_list)
    # 排除集群中使用的 data id，然后组装数据
    data = []
    item = {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "space_type_id": space_type_id,
        "space_id": space_id,
        "from_authorization": True,
    }
    filter_data_id_list = DataSource.objects.filter(
        etl_config__in=SPACE_DATASOURCE_ETL_LIST, bk_data_id__in=_data_id_set
    ).values_list("bk_data_id", flat=True)
    for data_id in set(data_id_list) - _data_id_set:
        if data_id not in filter_data_id_list:
            continue
        item["bk_data_id"] = int(data_id)
        data.append(SpaceDataSource(**item))
    for data_id in project_cluster_data_id_list:
        if data_id not in filter_data_id_list:
            continue
        if data_id in exist_data_id_list:
            continue
        exist_data_id_list.append(data_id)
        item["bk_data_id"] = int(data_id)
        item["from_authorization"] = False
        data.append(SpaceDataSource(**item))
    for data_id in shared_cluster_data_id_list:
        if data_id not in filter_data_id_list:
            continue
        if data_id in exist_data_id_list:
            continue
        exist_data_id_list.append(data_id)
        item["bk_data_id"] = int(data_id)
        item["from_authorization"] = False
        data.append(SpaceDataSource(**item))

    return data


def create_bcs_spaces(project_list: List) -> bool:
    """创建容器对应的空间信息，需要检查业务下的 ID 及关联资源(业务和集群及命名空间)

    :param project_list: 项目相关信息，包含项目 ID、项目名称、项目 Code
    :return: 返回 True 或异常
    """
    space_data, space_data_id_list, space_resource_list = [], [], []
    for p in project_list:
        space_data.append(
            Space(
                creator=SYSTEM_USERNAME,
                updater=SYSTEM_USERNAME,
                space_type_id=SpaceTypes.BKCI.value,
                space_id=p["project_code"],
                space_code=p["project_id"],
                space_name=p["name"],
                is_bcs_valid=True,
            )
        )
        # 获取业务下的 data id, 然后授权给项目使用
        data_id_list = list(
            SpaceDataSource.objects.filter(
                space_type_id=SpaceTypes.BKCC.value,
                space_id=str(p["bk_biz_id"]),
                from_authorization=False,
            ).values_list("bk_data_id", flat=True)
        )
        # 添加 bkcc 空间级 data id
        data_id_list.extend(get_space_data_id_list(SpaceTypes.BKCC.value))
        # 组装空间和 data id 的关系数据，同步过来的是业务下的 data id，相当于授权给容器项目使用
        shared_cluster_data_id_list, project_cluster_data_id_list = [], []
        # 组装空间对应的资源
        # 查询项目下集群，防止出现查询所有集群超时问题
        cluster_list = api.bcs_cluster_manager.get_project_clusters(project_id=p["project_id"])
        # 添加项目关联的业务资源
        space_resource_list.append(
            SpaceResource(
                creator=SYSTEM_USERNAME,
                updater=SYSTEM_USERNAME,
                space_type_id=SpaceTypes.BKCI.value,
                space_id=p["project_code"],
                resource_type=SpaceTypes.BKCC.value,
                resource_id=p["bk_biz_id"],
                dimension_values=[{"bk_biz_id": p["bk_biz_id"]}],
            )
        )
        # 获取存储在metadata中的集群数据
        metadata_clusters = get_metadata_cluster_list()
        # 关联项目下的集群, 针对共享集群，需要获取对应的空间信息
        project_cluster_ns_list = []
        for c in cluster_list:
            if c["cluster_id"] not in metadata_clusters:
                continue
            cluster_data_id_dict = get_data_id_by_cluster(c["cluster_id"])
            cluster_data_id_list = []
            if cluster_data_id_dict:
                cluster_data_id_list = list(cluster_data_id_dict.get(c["cluster_id"]) or [])
            if c["is_shared"]:
                shared_cluster_data_id_list.extend(cluster_data_id_list)
                ns_list = [
                    ns["namespace"]
                    for ns in get_shared_cluster_namespaces(cluster_id=c["cluster_id"], project_code=p["project_code"])
                ]
                project_cluster_ns_list.append(
                    {"cluster_id": c["cluster_id"], "namespace": ns_list, "cluster_type": "shared"}
                )
            else:
                project_cluster_data_id_list.extend(cluster_data_id_list)
                project_cluster_ns_list.append(
                    {"cluster_id": c["cluster_id"], "namespace": None, "cluster_type": "single"}
                )
        space_data_id_list.extend(
            compose_bcs_space_data_source(
                SpaceTypes.BKCI.value,
                p["project_code"],
                data_id_list,
                project_cluster_data_id_list,
                shared_cluster_data_id_list,
            )
        )
        space_resource_list.append(
            SpaceResource(
                creator=SYSTEM_USERNAME,
                updater=SYSTEM_USERNAME,
                space_type_id=SpaceTypes.BKCI.value,
                space_id=p["project_code"],
                resource_type=SpaceTypes.BCS.value,
                resource_id=p["project_code"],
                dimension_values=project_cluster_ns_list,
            )
        )
    # 创建资源
    with atomic(config.DATABASE_CONNECTION_NAME):
        # 创建空间
        Space.objects.bulk_create(space_data)
        logger.info("bulk create bcs space successfully, space: %s", json.dumps(project_list))
        # 创建空间和data id的关系
        SpaceDataSource.objects.bulk_create(space_data_id_list)
        logger.info(
            "bulk create bcs space data source successfully, space_data_id: %s",
            json.dumps([(s.space_type_id, s.space_id, s.bk_data_id) for s in space_data_id_list]),
        )
        # 创建关联的资源
        SpaceResource.objects.bulk_create(space_resource_list)

    return True


def get_metadata_cluster_list() -> List:
    return list(BCSClusterInfo.objects.filter(status="running").values_list("cluster_id", flat=True))


def get_valid_bcs_projects() -> List:
    """获取可用的 BKCI(BCS) 项目空间"""
    projects = api.bcs_cc.batch_get_projects()
    # 排除业务ID为 0 的记录，或者绑定的 BKCC 业务 ID 不存在的信息
    bk_biz_id_list = [b.bk_biz_id for b in api.cmdb.get_business()]
    # 返回有效的项目记录
    valid_project_list = []
    for p in projects:
        if p["bk_biz_id"] == "0" or int(p["bk_biz_id"]) not in bk_biz_id_list:
            continue
        valid_project_list.append(p)

    return valid_project_list


def get_space_by_table_id(table_id: str) -> Dict[str, Any]:
    """通过结果表获取空间信息

    @param table_id: 结果表
    @return: 返回空间信息，包含空间类型，空间ID，是否所有空间
    """
    try:
        bk_biz_id = ResultTable.objects.get(table_id=table_id).bk_biz_id
    except ResultTable.DoesNotExist:
        raise ValueError(f"table_id:[{table_id}] not found")

    # 查询关联的data id
    try:
        bk_data_id = DataSourceResultTable.objects.get(table_id=table_id).bk_data_id
    except DataSourceResultTable.DoesNotExist:
        raise ValueError(f"table_id:[{table_id}] not found data source")
    ds = DataSource.objects.get(bk_data_id=bk_data_id)

    # 查询数据源是否为平台级并且为`0`业务
    if int(bk_biz_id) == 0 and ds.is_platform_data_id:
        return {"space_type_id": None, "space_id": None, "is_all_space": True}

    # 查询数据源关联的空间
    try:
        sds = SpaceDataSource.objects.get(bk_data_id=bk_data_id, from_authorization=False)
    except SpaceDataSource.DoesNotExist:
        raise ValueError(f"table_id:[{table_id}] not found space info")

    # 返回空间信息
    return {"space_type_id": sds.space_type_id, "space_id": sds.space_id, "is_all_space": False}


def set_data_source_space_type(data_id_list: List, space_type_id: str):
    """设置数据源的所属的空间类型"""
    DataSource.objects.filter(bk_data_id__in=data_id_list).update(space_type_id=space_type_id)

    logger.info("set data id: %s belong to space type: %s", json.dumps(data_id_list), space_type_id)


def cached_ts_metric_data_id_list() -> List:
    """从缓存中读取 ts metric 对应的 data id

    NOTE: 设置超时时间为一小时
    """
    key = "cached_ts_metric_data_id_list"
    if key in cache:
        return cache.get(key)
    # 不存在，则缓存
    data_id_list = list(TimeSeriesGroup.objects.values_list("bk_data_id", flat=True))
    cache.set(key, data_id_list, 60 * 60)
    return data_id_list


def cached_cluster_data_id_list() -> List:
    """从缓存中读取集群对应的 data id

    NOTE: 设置超时时间为一小时
    """
    key = "cached_cluster_data_id_list"
    if key in cache:
        return cache.get(key)
    # 不存在，则缓存
    cluster_data_ids = BCSClusterInfo.objects.values("K8sMetricDataID", "CustomMetricDataID")
    cluster_data_id_list = []
    for data_id in cluster_data_ids:
        cluster_data_id_list.append(data_id["K8sMetricDataID"])
        cluster_data_id_list.append(data_id["CustomMetricDataID"])
    cache.set(key, cluster_data_id_list, 60 * 60)
    return cluster_data_id_list


def get_bkci_projects() -> List:
    """获取 bkci 的项目信息"""
    try:
        # 查询项目信息
        return api.bcs_cc.batch_get_projects(filter_k8s_kind=False)
    except Exception as e:
        logger.error("query project error, %s", e)
        return []


def cached_cluster_k8s_data_id() -> List:
    """从缓存中读取集群内置的数据源 ID

    NOTE: 因为集群变动没有那么频繁，可以设置超时时间为1小时
    """
    key = "cached_cluster_k8s_data_id"
    if key in cache:
        return cache.get(key)
    # 不存在，则缓存
    cluster_data_ids = BCSClusterInfo.objects.values("cluster_id", "K8sMetricDataID")
    cluster_data_id = {cluster_info["cluster_id"]: cluster_info["K8sMetricDataID"] for cluster_info in cluster_data_ids}
    cache.set(key, cluster_data_id, 1 * 60 * 60)
    return cluster_data_id
