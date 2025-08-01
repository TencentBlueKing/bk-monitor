"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
from datetime import datetime

from django.conf import settings
from django.db.models import Q
from django.db.transaction import atomic

from alarm_backends.core.lock.service_lock import share_lock
from api.cmdb.define import Business
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.prometheus import metrics
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE, BULK_UPDATE_BATCH_SIZE
from metadata.models.space import Space, SpaceDataSource, SpaceResource
from metadata.models.space.constants import (
    SKIP_DATA_ID_LIST_FOR_BKCC,
    SPACE_TO_RESULT_TABLE_CHANNEL,
    SYSTEM_USERNAME,
    BCSClusterTypes,
    SpaceStatus,
    SpaceTypes,
)
from metadata.models.space.space_data_source import (
    get_biz_data_id,
    get_real_zero_biz_data_id,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.utils import (
    cached_cluster_k8s_data_id,
    create_bcs_spaces,
    create_bkcc_space_data_source,
    create_bkcc_spaces,
    get_metadata_cluster_list,
    get_project_clusters,
    get_shared_cluster_namespaces,
    get_valid_bcs_projects,
)
from metadata.models.vm.constants import (
    QUERY_VM_SPACE_UID_CHANNEL_KEY,
    QUERY_VM_SPACE_UID_LIST_KEY,
)
from metadata.task.utils import bulk_handle
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


@share_lock(identify="metadata__sync_bkcc_space")
def sync_bkcc_space(allow_deleted=False):
    """同步 bkcc 的业务，自动创建对应的空间

    TODO: 是否由服务方调用接口创建或者服务方可以被 watch
    NOTE: 空间创建后，不需要单独推送
    """
    logger.info("start sync bkcc space task")
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkcc_space", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()

    # 先同步已归档业务
    sync_archived_bkcc_space()

    bkcc_type_id = SpaceTypes.BKCC.value
    biz_list: list[Business] = []
    for tenant in api.bk_login.list_tenant():
        temp: list[Business] = api.cmdb.get_business(bk_tenant_id=tenant["id"])
        for b in temp:
            setattr(b, "bk_tenant_id", tenant["id"])
        biz_list.extend(temp)

    # NOTE: 为防止出现接口变动的情况，导致误删操作；如果为空，则忽略数据处理
    if not biz_list:
        logger.info("query cmdb api resp is null")
        return

    biz_id_name_dict = {str(b.bk_biz_id): (b.bk_biz_name, b.bk_tenant_id) for b in biz_list}
    # 过滤已经创建空间的业务
    space_id_list = Space.objects.filter(space_type_id=bkcc_type_id).values_list("space_id", flat=True)
    diff = set(biz_id_name_dict.keys()) - set(space_id_list)
    diff_delete = set(space_id_list) - set(biz_id_name_dict.keys())
    # 如果业务没有查询，则直接返回；否则, 创建对应的空间信息
    if not (diff or diff_delete):
        logger.info("bkcc space not need add or delete!")
        return

    # 针对删除的业务
    # 当业务在 cmdb 删除业务，并且允许删除为 True 时，才进行删除；避免因为接口返回不正确，误删除的场景
    if diff_delete and allow_deleted:
        # 删除和数据源的关联
        SpaceDataSource.objects.filter(space_type_id=bkcc_type_id, space_id__in=diff_delete).delete()
        # NOTE 标识关联空间不可用，这里主要是针对 bcs 资源
        space_resources = SpaceResource.objects.filter(resource_type=bkcc_type_id, resource_id__in=diff_delete)
        # 对应的 BKCI(BCS) 空间，也标识为不可用
        Space.objects.filter(
            space_type_id=SpaceTypes.BKCI.value, space_id__in=[i.space_id for i in space_resources]
        ).update(is_bcs_valid=False)
        # 删除关联资源
        space_resources.delete()
        # 删除对应的 BKCC 空间
        Space.objects.filter(space_type_id=bkcc_type_id, space_id__in=diff_delete).delete()
        logger.info("delete space_type_id: [%s], space_id: [%s]", bkcc_type_id, ",".join(diff_delete))

    if diff:
        # 针对添加的业务
        diff_biz_list = [
            {
                "bk_biz_id": biz_id,
                "bk_biz_name": biz_id_name_dict[biz_id][0],
                "bk_tenant_id": biz_id_name_dict[biz_id][1],
            }
            for biz_id in diff
        ]

        # 创建空间
        try:
            create_bkcc_spaces(diff_biz_list)
        except Exception:
            logger.exception("create bkcc biz space error")
            return
        # 追加业务空间到 vm 查询的白名单中, 并通知到 unifyquery
        RedisTools.sadd(QUERY_VM_SPACE_UID_LIST_KEY, [f"bkcc__{biz_id}" for biz_id in diff])
        RedisTools.publish(QUERY_VM_SPACE_UID_CHANNEL_KEY, [json.dumps({"time": time.time()})])

        logger.info("create bkcc space successfully, space: %s", json.dumps(diff_biz_list))

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkcc_space", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_bkcc_space", process_target=None).observe(cost_time)
    metrics.report_all()
    logger.info("sync bkcc space task cost time: %s", cost_time)


def sync_archived_bkcc_space():
    """同步 bkcc 被归档的业务，停用对应的空间"""
    logger.info("start sync archived bkcc space task")
    bkcc_type_id = SpaceTypes.BKCC.value
    # 获取已归档的业务
    archived_biz_list: list[Business] = []
    for tenant in api.bk_login.list_tenant():
        archived_biz_list.extend(api.cmdb.get_business(bk_tenant_id=tenant["id"], is_archived=True))
    archived_biz_id_list = [str(b.bk_biz_id) for b in archived_biz_list]
    # 归档的业务，变更空间名称为 {当前名称}(已归档_20240619)
    name_suffix = f"(已归档_{datetime.now().strftime('%Y%m%d')})"
    # 获取当前启用且需要同步归档的业务空间
    need_archive_space = Space.objects.filter(
        space_type_id=bkcc_type_id, status=SpaceStatus.NORMAL.value, space_id__in=archived_biz_id_list
    )
    if not need_archive_space:
        return
    need_archive_biz_id_list = []
    for obj in need_archive_space:
        need_archive_biz_id_list.append(obj.space_id)
        obj.space_name = f"{obj.space_name}{name_suffix}"
        obj.status = SpaceStatus.DISABLED.value
    Space.objects.bulk_update(need_archive_space, ["space_name", "status"], batch_size=BULK_UPDATE_BATCH_SIZE)
    # NOTE 标识关联空间不可用，这里主要是针对 bcs 资源
    space_resources = SpaceResource.objects.filter(resource_type=bkcc_type_id, resource_id__in=need_archive_biz_id_list)
    # 对应的 BKCI(BCS) 空间，也标识为不可用
    Space.objects.filter(
        space_type_id=SpaceTypes.BKCI.value, space_id__in=[i.space_id for i in space_resources]
    ).update(is_bcs_valid=False)

    logger.info("update archived space_type_id: [%s], space_id: [%s]", bkcc_type_id, ",".join(need_archive_biz_id_list))


@share_lock(identify="metadata__refresh_bkcc_space_name")
def refresh_bkcc_space_name():
    """刷新 bkcc 类型空间名称

    NOTE: 名称变动，不需要同步到存储介质(redis|consul)，所以单独任务处理
    """
    logger.info("start sync bkcc space name task")
    bkcc_type_id = SpaceTypes.BKCC.value
    biz_list: list[Business] = []
    for tenant in api.bk_login.list_tenant():
        biz_list.extend(api.cmdb.get_business(bk_tenant_id=tenant["id"]))
    biz_id_name_dict: dict[str, str] = {str(b.bk_biz_id): b.bk_biz_name for b in biz_list}
    space_id_name_map: dict[str, str] = {
        space.space_id: space.space_name for space in Space.objects.filter(space_type_id=bkcc_type_id)
    }
    # 比对名称是否有变动，如果变动，则进行更新
    diff = dict(set(biz_id_name_dict.items()) - set(space_id_name_map.items()))
    # 过滤数据，然后进行更新
    for obj in Space.objects.filter(space_id__in=diff.keys()):
        space_name = diff.get(obj.space_id)
        if not space_name:
            logger.warning("space_name of space_id: %s is null", obj.space_id)
            continue
        obj.space_name = space_name
        obj.save(update_fields=["space_name"])

    logger.info("refresh bkcc space name successfully")


@share_lock(identify="metadata__sync_data_source")
def sync_bkcc_space_data_source():
    """同步bkcc数据源和空间的关系及数据源的所属类型"""
    logger.info("start sync bkcc space data source task")
    start_time = time.time()
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkcc_space_data_source", status=TASK_STARTED, process_target=None
    ).inc()

    def _refine(data_id_dict, space_id, bk_data_id) -> bool:
        """移除已经存在的数据源关联"""
        is_exist = False
        space_data_id_list = list(set(data_id_dict.get(int(space_id), [])))
        if space_data_id_list and bk_data_id in space_data_id_list:
            space_data_id_list.remove(bk_data_id)
            is_exist = True
        data_id_dict[int(space_id)] = space_data_id_list
        return is_exist

    biz_data_id_dict = get_biz_data_id()
    # 针对 0 业务按照规则转换为所属业务
    # NOTE: 因为 0 业务的数据源不一定是 bkcc 类型，需要忽略掉更新
    real_biz_data_id_dict, zero_data_id_list = get_real_zero_biz_data_id()
    models.DataSource.objects.filter(bk_data_id__in=zero_data_id_list).exclude(
        Q(bk_data_id__in=SKIP_DATA_ID_LIST_FOR_BKCC)
        | Q(space_uid__startswith=SpaceTypes.BKCI.value)
        | Q(space_uid__startswith=SpaceTypes.BKSAAS.value)
    ).update(is_platform_data_id=True, space_type_id=SpaceTypes.BKCC.value)
    logger.info(
        "update is_platform_data_id: %s, belong space type: %s of data id: %s",
        True,
        SpaceTypes.BKCC.value,
        json.dumps(zero_data_id_list),
    )

    # 过滤掉已经存在的data id
    exist_sd = models.SpaceDataSource.objects.filter(space_type_id=SpaceTypes.BKCC.value).values(
        "space_id", "bk_data_id"
    )
    for sd in exist_sd:
        is_exist = _refine(biz_data_id_dict, sd["space_id"], sd["bk_data_id"])
        if not is_exist:
            _refine(real_biz_data_id_dict, sd["space_id"], sd["bk_data_id"])

    # 创建空间和数据源的关联
    create_bkcc_space_data_source(biz_data_id_dict)
    create_bkcc_space_data_source(real_biz_data_id_dict)

    biz_id_list = list(biz_data_id_dict.keys())
    biz_id_list.extend(real_biz_data_id_dict.keys())

    # 组装数据，推送 redis 功能
    space_id_list = [str(biz_id) for biz_id in biz_id_list if str(biz_id) != "0"]
    push_and_publish_space_router(space_type=SpaceTypes.BKCC.value, space_id_list=space_id_list)
    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkcc_space_data_source", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="sync_bkcc_space_data_source", process_target=None
    ).observe(cost_time)
    metrics.report_all()
    logger.info("push bkcc type space to redis successfully, space: %s,cost: %s", json.dumps(space_id_list), cost_time)


@share_lock(identify="metadata__sync_bcs_space")
def sync_bcs_space():
    """同步 BCS 项目空间数据

    TODO: 当仅有项目还没有集群时，关联的资源为空，应该在增加一个关联资源变动检测的任务
    """
    logger.info("start sync bcs space task")
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bcs_space", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()

    bcs_type_id = SpaceTypes.BKCI.value
    projects = []
    for tenant in api.bk_login.list_tenant():
        projects.extend(get_valid_bcs_projects(bk_tenant_id=tenant["id"]))
    project_id_dict = {p["project_code"]: p for p in projects}

    space_qs = Space.objects.filter(space_type_id=bcs_type_id)
    # 获取所有已有空间的ID列表
    space_id_list = space_qs.values_list("space_id", flat=True)
    space_objs = {space.space_id: space for space in space_qs}

    redis_space_id_list = []
    # 判断需要更新的项目
    for project_code, project_info in project_id_dict.items():
        if not project_info["project_id"]:
            logger.warning(
                "[sync_bcs_space] bcs project_id is empty, project_code: %s, project_name: %s",
                project_code,
                project_info["name"],
            )
        if project_code in space_objs:
            current_space = space_objs[project_code]
            new_space_code = project_info["project_id"]
            # 修复条件判断：当space_code不一致或space_name不一致时更新
            if current_space.space_code != new_space_code or current_space.space_name != project_info["name"]:
                logger.info(
                    "[sync_bcs_space] detected space inconsistency, space_id: %s, current_code: '%s', new_code: '%s', current_name: '%s', new_name: '%s'",
                    project_code,
                    current_space.space_code,
                    new_space_code,
                    current_space.space_name,
                    project_info["name"],
                )
                # 更新已有项目的space_code和名称
                Space.objects.filter(space_type_id=bcs_type_id, space_id=project_code).update(
                    space_code=new_space_code,
                    space_name=project_info["name"],
                    is_bcs_valid=True,
                )
                logger.info(
                    "[sync_bcs_space] updated bcs project, space_id: %s, code: '%s'→'%s', name: '%s'→'%s'",
                    project_code,
                    current_space.space_code,
                    new_space_code,
                    current_space.space_name,
                    project_info["name"],
                )
                redis_space_id_list.append(f"{bcs_type_id}__{project_code}")

    # 判断需要新增的项目（在项目字典中存在但不在已有空间列表中）
    diff = set(project_id_dict.keys()) - set(space_id_list)

    # 如果没有需要更新或新增的项目，直接返回
    if not diff:
        logger.info("[sync_bcs_space] bcs space not need add!")
        return

    diff_project_list = []
    # 准备新增项目列表
    for project_code in diff:
        diff_project_list.append(project_id_dict[project_code])
        redis_space_id_list.append(f"{bcs_type_id}__{project_code}")

    # 批量创建新增项目空间
    try:
        create_bcs_spaces(diff_project_list)
    except Exception:
        logger.exception("[sync_bcs_space] create bcs project space error")

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bcs_space", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_bcs_space", process_target=None).observe(cost_time)
    metrics.report_all()
    logger.info(
        "[sync_bcs_space] create bcs space successfully, space: %s,cost: %s", json.dumps(diff_project_list), cost_time
    )


@share_lock(identify="metadata_refresh_bcs_project_biz")
def refresh_bcs_project_biz():
    """检测 bcs 项目绑定的业务的变化"""
    logger.info("start check and update the binded biz of bcs project task")
    # 检测所有 bcs 项目
    projects = []
    for tenant in api.bk_login.list_tenant():
        projects.extend(get_valid_bcs_projects(bk_tenant_id=tenant["id"]))
    project_id_dict = {p["project_code"]: p["bk_biz_id"] for p in projects}
    # 1. 判断项目空间是否存在，如果不存在直接跳过
    # 2. 如果项目空间存在，则判断绑定的业务是否相等
    # 3. 如果相等，则忽略
    # 4. 如果不相等，则更新绑定的业务资源
    # 5. 推送到redis，并发布项目变动
    space_id_resource_dict = {
        sr.space_id: sr
        for sr in SpaceResource.objects.filter(space_type_id=SpaceTypes.BKCI.value, resource_type=SpaceTypes.BKCC.value)
    }
    # 记录变动的
    changed_space_for_redis, space_id_list, add_resource_list = [], [], []

    for s in Space.objects.filter(space_type_id=SpaceTypes.BKCI.value):
        # 没有开启容器服务的直接跳过
        if not s.space_code:
            continue
        space_id = s.space_id
        if space_id not in project_id_dict:
            continue

        biz_id = project_id_dict[space_id]

        # NOTE: 防止出现，删掉一部分数据场景的问题
        res = space_id_resource_dict.get(space_id)
        if not res:
            add_resource_list.append(
                SpaceResource(
                    bk_tenant_id=s.bk_tenant_id,
                    space_type_id=SpaceTypes.BKCI.value,
                    space_id=space_id,
                    resource_type=SpaceTypes.BKCC.value,
                    resource_id=biz_id,
                    creator=SYSTEM_USERNAME,
                    updater=SYSTEM_USERNAME,
                    dimension_values=[{"bk_biz_id": biz_id}],
                )
            )
            space_id_list.append(space_id)
            continue

        if res.resource_id == biz_id:
            continue

        res.resource_id = biz_id
        res.dimension_values = [{"bk_biz_id": biz_id}]
        res.save()
        changed_space_for_redis.append(s.space_uid)
        space_id_list.append(space_id)

    if add_resource_list:
        SpaceResource.objects.bulk_create(add_resource_list)
        logger.info("create bcs space resource successfully, space: %s", json.dumps(space_id_list))


def get_cluster_data_id(space_id, cluster_id_list, space_data_id_map):
    filter_data_id_list = models.BCSClusterInfo.objects.filter(cluster_id__in=cluster_id_list).values(
        "K8sMetricDataID", "CustomMetricDataID", "K8sEventDataID"
    )
    for data_id in filter_data_id_list:
        space_data_id_map.setdefault(space_id, []).extend(
            [data_id["K8sMetricDataID"], data_id["CustomMetricDataID"], data_id["K8sEventDataID"]]
        )
    logger.info("cluster data id info: %s", json.dumps(space_data_id_map))


def bulk_create_records(space_type, space_data_id_map, space_id_list, from_authorization):
    """批量创建记录

    NOTE: 当共享集群项目时，返回的数据中，共享集群即使这个项目下的专用集群，也是这个项目的共享集群
          因此，分开创建，避免相同的数据写入
    """
    if not space_data_id_map:
        return
    add_space_data_id_list = []
    for space_id, data_ids in space_data_id_map.items():
        data_id_list = models.SpaceDataSource.objects.filter(
            space_type_id=space_type, space_id=space_id, bk_data_id__in=set(data_ids)
        ).values_list("bk_data_id", flat=True)
        diff = set(data_ids) - set(data_id_list)
        for i in diff:
            add_space_data_id_list.append(
                SpaceDataSource(
                    space_type_id=space_type,
                    space_id=space_id,
                    bk_data_id=i,
                    creator=SYSTEM_USERNAME,
                    updater=SYSTEM_USERNAME,
                    from_authorization=from_authorization,
                )
            )
        if diff:
            space_id_list.append(space_id)
    # 批量创建，创建失败，可以不影响其它
    try:
        models.SpaceDataSource.objects.bulk_create(add_space_data_id_list, BULK_CREATE_BATCH_SIZE)
    except Exception:
        logger.exception("batch create SpaceDataSource records failed")


@share_lock(identify="metadata__refresh_cluster_resource")
def refresh_cluster_resource():
    """检测集群资源的变化

    当绑定资源的集群信息变动时，刷新绑定的集群资源
    """
    logger.info("start sync bcs space cluster resource task")
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_cluster_resource", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()
    # 拉取现阶段绑定的资源，注意资源类型仅为 bcs
    space_type = SpaceTypes.BKCI.value
    resource_type = SpaceTypes.BCS.value
    space_res_dict = {
        sr["resource_id"]: sr["dimension_values"]
        for sr in SpaceResource.objects.get_resource_by_resource_type(space_type, resource_type)
    }
    # code 映射 id，仅过滤到有集群的项目
    space_id_code_map = {
        s["space_id"]: (s["space_code"], s["bk_tenant_id"])
        for s in Space.objects.filter(space_type_id=space_type, is_bcs_valid=True).values(
            "space_id", "space_code", "bk_tenant_id"
        )
        if s["space_code"]
    }
    # 根据项目查询项目下资源的变化
    changed_space_list, space_id_list, add_resource_list = [], [], []
    space_data_id_map, shared_space_data_id_map = {}, {}
    # 获取存储在metadata中的集群数据
    metadata_clusters = get_metadata_cluster_list()

    for s_id, (s_code, bk_tenant_id) in space_id_code_map.items():
        clusters = get_project_clusters(bk_tenant_id=bk_tenant_id, project_id=s_code)
        if not clusters:
            continue
        dimension_values = []
        project_cluster, shared_cluster, shared_cluster_ns = set(), set(), {}
        used_cluster_list = set()
        for c in clusters:
            cluster_id = c["cluster_id"]
            # 防止共享集群所在项目返回相同集群的场景
            if cluster_id not in metadata_clusters or cluster_id in used_cluster_list:
                continue
            used_cluster_list.add(cluster_id)
            if c["is_shared"]:
                ns_list = [
                    ns["namespace"]
                    for ns in get_shared_cluster_namespaces(
                        bk_tenant_id=bk_tenant_id, cluster_id=cluster_id, project_code=s_id
                    )
                    if cluster_id == ns["cluster_id"]
                ]
                dimension_values.append({"cluster_id": cluster_id, "namespace": ns_list, "cluster_type": "shared"})
                shared_cluster_ns[cluster_id] = set(ns_list)
                shared_cluster.add(cluster_id)
            else:
                dimension_values.append({"cluster_id": cluster_id, "namespace": None, "cluster_type": "single"})
                project_cluster.add(cluster_id)
        # 过滤集群对应的 data id
        get_cluster_data_id(s_id, project_cluster, space_data_id_map)
        logger.info("cluster data id info: %s", json.dumps(space_data_id_map))
        if shared_cluster:
            get_cluster_data_id(s_id, shared_cluster, shared_space_data_id_map)
            logger.info("cluster data id info: %s", json.dumps(shared_space_data_id_map))

        sr = space_res_dict.get(s_id)
        if sr is None:
            add_resource_list.append(
                SpaceResource(
                    space_type_id=SpaceTypes.BKCI.value,
                    space_id=s_id,
                    resource_type=SpaceTypes.BCS.value,
                    resource_id=s_id,
                    creator=SYSTEM_USERNAME,
                    updater=SYSTEM_USERNAME,
                    dimension_values=dimension_values,
                )
            )
            space_id_list.append(s_id)
            continue
        # 获取现存的，判断是否有变化
        exist_project_cluster, exist_shared_cluster_ns = set(), {}
        for srd in sr:
            cluster_id = srd["cluster_id"]
            if srd["namespace"]:
                exist_shared_cluster_ns[cluster_id] = set(srd["namespace"])
            else:
                exist_project_cluster.add(cluster_id)
        # 对比差异
        if project_cluster != exist_project_cluster or shared_cluster_ns != exist_shared_cluster_ns:
            changed_space_list.append(f"{space_type}__{s_id}")
            SpaceResource.objects.filter(
                space_type_id=space_type, space_id=s_id, resource_type=resource_type, resource_id=s_id
            ).update(dimension_values=dimension_values)
            space_id_list.append(s_id)
    # 创建资源
    if add_resource_list:
        SpaceResource.objects.bulk_create(add_resource_list)
        logger.info("create bcs space resource successfully, space: %s", json.dumps(space_id_list))

    # 根据空间 data id，判断是否已经添加
    # 创建专用集群下的数据源 ID 记录
    # 因为共享集群在所属项目下会返回两次，因此，需要先创建属于专用集群的数据源关联
    bulk_create_records(space_type, space_data_id_map, space_id_list, False)
    # 创建共享集群下的数据源 ID 记录
    bulk_create_records(space_type, shared_space_data_id_map, space_id_list, True)

    logger.info("bulk create space data_id record")

    if space_id_list:
        # 推送 redis 功能, 包含空间到结果表，数据标签到结果表，结果表详情
        push_and_publish_space_router(space_type=SpaceTypes.BKCI.value, space_id_list=space_id_list)

        logger.info("push updated bcs space resource to redis successfully, space: %s", json.dumps(space_id_list))

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_cluster_resource", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="refresh_cluster_resource", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("sync bcs space cluster resource task cost time: %s", cost_time)


@share_lock(identify="metadata_refresh_bkci_project")
def refresh_bkci_space_name():
    """刷新 bkci 空间名称"""
    projects = []
    for tenant in api.bk_login.list_tenant():
        projects.extend(get_valid_bcs_projects(bk_tenant_id=tenant["id"]))
    # 如果查询项目为空，则直接返回
    if not projects:
        return
    project_code_name_map = {project["project_code"]: project["name"] for project in projects}
    # 过滤 bkci 项目
    space_qs = Space.objects.filter(space_type_id=SpaceTypes.BKCI.value)
    # 比对名称是否一样，如果不一样，则进行更新
    for space in space_qs:
        project_name = project_code_name_map.get(space.space_id)
        if project_name is None:
            logger.error(
                "space not found from bkci api, space_id: %s, space_name: %s", space.space_id, space.space_name
            )
            continue
        # 获取更新前的名称
        old_name = space.space_name
        if project_name == old_name:
            continue
        # 更新记录
        space.space_name = project_name
        space.save(update_fields=["space_name"])
        logger.info(
            "space_id: %s updated space_name, old_name: %s, new_name: %s", space.space_id, old_name, project_name
        )

    logger.info("refresh only bkci space successfully")


def push_and_publish_space_router(
    space_type: str | None = None,
    space_id: str | None = None,
    space_id_list: list[str] | None = None,
    is_publish: bool | None = True,
    bk_tenant_id: str | None = DEFAULT_TENANT_ID,
):
    """推送数据和通知"""
    from metadata.models.space.constants import SPACE_TO_RESULT_TABLE_CHANNEL
    from metadata.models.space.ds_rt import get_space_table_id_data_id
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    # 过滤数据
    spaces = models.Space.objects.values("space_type_id", "space_id", "bk_tenant_id")
    if space_type:
        spaces = spaces.filter(space_type_id=space_type)
    if space_id:
        spaces = spaces.filter(space_id=space_id)
    if bk_tenant_id:
        logger.info("push and publish space router with bk_tenant_id->[%s]", bk_tenant_id)
        spaces = spaces.filter(bk_tenant_id=bk_tenant_id)
    # 这里不应该会有太多空间 ID 的输入
    if space_id_list:
        spaces = spaces.filter(space_id__in=space_id_list)

    # 拼装数据
    space_list = [
        {"space_type": space["space_type_id"], "space_id": space["space_id"], "bk_tenant_id": space["bk_tenant_id"]}
        for space in spaces
    ]

    # 批量处理 -- SPACE_TO_RESULT_TABLE 路由
    bulk_handle(
        lambda batch_spaces: SpaceTableIDRedis().push_multi_space_table_ids(batch_spaces, is_publish=False),
        list(spaces),
    )

    # 通知到使用方
    if is_publish:
        space_uid_list = []
        for space in spaces:
            if settings.ENABLE_MULTI_TENANT_MODE:
                space_uid_list.append(f"{space['bk_tenant_id']}|{space['space_type_id']}__{space['space_id']}")
            else:
                space_uid_list.append(f"{space['space_type_id']}__{space['space_id']}")
        RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, space_uid_list)

    # 仅存在空间 id 时，可以直接按照结果表进行处理
    # 非多租户环境: 所有table_id的路由一并推送
    # 多租户环境: 按空间逐个推送路由,因为table_id不再唯一

    if settings.ENABLE_MULTI_TENANT_MODE:  # 若开启多租户模式，则以空间粒度推送路由
        for space in space_list:
            tid_ds = get_space_table_id_data_id(space["space_type"], space["space_id"])
            space_tid_list = list(tid_ds.keys())
            space_client = SpaceTableIDRedis()
            space_client.push_table_id_detail(
                table_id_list=space_tid_list,
                is_publish=is_publish,
                include_es_table_ids=True,
                bk_tenant_id=space["bk_tenant_id"],
            )
            space_client.push_data_label_table_ids(
                table_id_list=space_tid_list,
                is_publish=is_publish,
                bk_tenant_id=space["bk_tenant_id"],
            )
    else:
        table_id_list = []
        if space_id:
            for space in space_list:
                tid_ds = get_space_table_id_data_id(space["space_type"], space["space_id"])
                table_id_list.extend(tid_ds.keys())

        space_client = SpaceTableIDRedis()
        space_client.push_data_label_table_ids(table_id_list=table_id_list, is_publish=is_publish)
        space_client.push_table_id_detail(table_id_list=table_id_list, is_publish=is_publish, include_es_table_ids=True)


@atomic(config.DATABASE_CONNECTION_NAME)
def delete_and_create_paas_space_data_id(
    space_type: str,
    space_id: str,
    need_delete_data_ids: set,
    need_add_data_ids: set,
):
    if need_delete_data_ids:
        models.SpaceDataSource.objects.filter(
            space_type_id=space_type, space_id=space_id, bk_data_id__in=need_delete_data_ids
        ).delete()
    bulk_create_records = []
    for data_id in need_add_data_ids:
        bulk_create_records.append(
            models.SpaceDataSource(
                space_type_id=space_type, space_id=space_id, bk_data_id=data_id, from_authorization=True
            )
        )

    # 批量创建
    models.SpaceDataSource.objects.bulk_create(bulk_create_records, batch_size=BULK_CREATE_BATCH_SIZE)


def authorize_paas_space_cluster_data_source(space_cluster: dict):
    """重新针对使用的集群内置指标数据源授权

    NOTE: 仅针对集群的进行授权处理
    """
    space_type = SpaceTypes.BKSAAS.value
    # 变更授权的集群内置指标 ID
    # 过滤和已经授权的交集，然后删除，再批量创建
    space_data_ids = list(
        models.SpaceDataSource.objects.filter(space_type_id=space_type).values("space_id", "bk_data_id")
    )
    space_data_id_map = {}
    for space_data_id in space_data_ids:
        space_data_id_map.setdefault(space_data_id["space_id"], set()).add(space_data_id["bk_data_id"])
    paas_data_id_list = settings.BKPAAS_AUTHORIZED_DATA_ID_LIST
    # 进行数据匹配
    for space_id, data_ids in space_data_id_map.items():
        # 匹配到需要增加的数据源
        need_create_data_ids = set(paas_data_id_list) - set(data_ids)
        try:
            # 如果数据源不存在，则根据差异创建记录
            if need_create_data_ids:
                # 因为可能还会增加，更改为批量创建
                objs = [
                    models.SpaceDataSource(
                        space_type_id=space_type, space_id=space_id, bk_data_id=data_id, from_authorization=True
                    )
                    for data_id in need_create_data_ids
                ]
                models.SpaceDataSource.objects.bulk_create(objs, batch_size=BULK_CREATE_BATCH_SIZE)
        except Exception as e:
            logger.error(
                """authorize paas data_ids failed, space_type: %s, space_id: %s, data_ids: %s, error: %s""",
                space_type,
                space_id,
                json.dumps(paas_data_id_list),
                e,
            )

        clusters = space_cluster.get(space_id)
        if not clusters:
            logger.error("not found cluster by space: %s", f"{space_type}__{space_id}")
            continue

        # 获取空间使用的集群 data_id, 然后删除
        # 获取集群内置指标
        cluster_data_id_list = cached_cluster_k8s_data_id()
        need_delete_data_ids = data_ids & set(cluster_data_id_list.keys())
        # 获取最新使用的集群的 data_id
        need_add_data_ids = {cluster_data_id_list[c] for c in clusters if c in cluster_data_id_list}
        # 如果要删除的和要添加的一样，则不需要处理
        if need_add_data_ids == need_delete_data_ids:
            continue

        logger.info(
            """delete and create space data_ids,
            space_type: %s, space_id: %s, need_delete_data_ids: %s, need_add_data_ids: %s""",
            space_type,
            space_id,
            json.dumps(need_delete_data_ids),
            json.dumps(need_add_data_ids),
        )
        try:
            delete_and_create_paas_space_data_id(space_type, space_id, need_delete_data_ids, need_add_data_ids)
        except Exception as e:
            logger.error(
                """delete and create space data_ids failed, space_type: %s, space_id: %s,
                need_delete_data_ids: %s, need_add_data_ids: %s, error: %s""",
                space_type,
                space_id,
                json.dumps(need_delete_data_ids),
                json.dumps(need_add_data_ids),
                e,
            )


def create_and_update_paas_space_resource(space_cluster_namespaces: dict):
    """创建或更新空间绑定的资源"""
    space_type = SpaceTypes.BKSAAS.value
    # 针对资源的集群进行处理
    objs = models.SpaceResource.objects.filter(space_type_id=space_type, space_id__in=space_cluster_namespaces.keys())

    # 进行关联资源的更新
    exist_space_set = set()
    for obj in objs:
        exist_space_set.add(obj.space_id)
        obj.dimension_values = space_cluster_namespaces.get(obj.space_id, [])
    try:
        models.SpaceResource.objects.bulk_update(objs, ["dimension_values"], batch_size=BULK_UPDATE_BATCH_SIZE)
    except Exception as e:
        logger.error("bulk update space resource error, space: %s, error: %s", json.dumps(exist_space_set), e)

    # 如果不存在，则进行创建
    need_add_space = set(space_cluster_namespaces.keys()) - exist_space_set
    add_records = []
    for space in need_add_space:
        add_records.append(
            models.SpaceResource(
                space_type_id=space_type,
                space_id=space,
                resource_type=space_type,
                resource_id=space,
                dimension_values=space_cluster_namespaces.get(space, []),
            )
        )
    try:
        models.SpaceResource.objects.bulk_create(add_records, batch_size=BULK_CREATE_BATCH_SIZE)
    except Exception as e:
        logger.error("bulk add space resource error, space: %s, error: %s", json.dumps(need_add_space), e)


@share_lock(identify="metadata_refresh_bksaas_space_resource")
def refresh_bksaas_space_resouce():
    """刷新蓝鲸应用空间绑定的资源"""
    logger.info("start to refresh bksaas space resource")

    # 设置每次处理的数据量
    MAX_PAGE_NUM = 30
    space_type = SpaceTypes.BKSAAS.value

    # 获取bksaas的空间
    spaces = list(models.Space.objects.filter(space_type_id=space_type))
    space_id_list = [{"app_code": space.space_id} for space in spaces]

    # 批量获取蓝鲸应用使用的集群资源
    space_id_count = len(space_id_list)
    # 分组
    space_with_page_list = [space_id_list[i : i + MAX_PAGE_NUM] for i in range(0, space_id_count, MAX_PAGE_NUM)]

    # 然后根据分组进行请求
    space_cluster_namespaces, space_cluster = {}, {}
    for space_dicts in space_with_page_list:
        cluster_ns = api.bk_paas.get_app_cluster_namespace.bulk_request(space_dicts)
        # 组装数据
        for space_dict, val in zip(space_dicts, cluster_ns):
            # 转换格式 {"cluster_id": xxx, "namespace": ["xxx", "xxx"]}
            _cn = {}
            for v in val:
                _cn.setdefault(v["bcs_cluster_id"], []).append(v["namespace"])
            # 获取空间使用的集群数据
            space_cluster_namespaces[space_dict["app_code"]] = [
                {
                    "cluster_id": c,
                    "namespace": n,
                    "cluster_type": BCSClusterTypes.SHARED.value,
                }
                for c, n in _cn.items()
            ]
            space_cluster[space_dict["app_code"]] = {v["bcs_cluster_id"] for v in val}

    # 创建或更新空间绑定的资源
    create_and_update_paas_space_resource(space_cluster_namespaces)
    # 重新授权
    authorize_paas_space_cluster_data_source(space_cluster)

    # 批量进行推送数据
    # NOTE: 此时集群或者公共插件相关的信息已经存在了，不需要再进行指标或 data_label 的映射
    space_client = SpaceTableIDRedis()
    bulk_handle(lambda space_list: space_client.push_multi_space_table_ids(space_list), spaces)

    # 通知到使用方
    push_redis_keys = []
    for space in spaces:
        if settings.ENABLE_MULTI_TENANT_MODE:
            push_redis_keys.append(f"{space.bk_tenant_id}|{space.space_type_id}__{space.space_id}")
        else:
            push_redis_keys.append(f"{space.space_type_id}__{space.space_id}")
    RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, push_redis_keys)

    logger.info("refresh bksaas space resource successfully")
