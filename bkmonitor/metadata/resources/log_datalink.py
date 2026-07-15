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
from typing import Any

from django.db.transaction import atomic
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.api import SpaceApi
from bkm_space.define import Space, SpaceTypeEnum
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.user import get_request_username
from core.drf_resource import Resource
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE, BULK_UPDATE_BATCH_SIZE
from metadata.service.space_redis import SpaceTableIDRedis, push_and_publish_es_aliases

logger = logging.getLogger(__name__)


class ParamsSerializer(serializers.Serializer):
    """参数序列化器"""

    class RtOption(serializers.Serializer):
        name = serializers.CharField(required=True, label="名称")
        value = serializers.CharField(required=True, label="值")
        value_type = serializers.CharField(required=False, label="值类型", default="dict")
        creator = serializers.CharField(required=False, label="创建者", default="system")

    bk_tenant_id = TenantIdField(label="租户ID")
    options = serializers.ListField(required=False, child=RtOption(), default=list)


def _create_or_update_options(bk_tenant_id: str, table_id: str, options: list[dict]) -> None:
    """创建或者更新结果表 option。"""

    exist_objs = {
        obj.name: obj for obj in models.ResultTableOption.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
    }
    need_update_objs, need_add_objs = [], []
    update_fields = set()

    for option in options:
        exist_obj = exist_objs.get(option["name"])
        need_update = False
        if exist_obj:
            if option["value"] != exist_obj.value:
                exist_obj.value = option["value"]
                update_fields.add("value")
                need_update = True
            if option["value_type"] != exist_obj.value_type:
                exist_obj.value_type = option["value_type"]
                update_fields.add("value_type")
                need_update = True
            if need_update:
                need_update_objs.append(exist_obj)
        else:
            need_add_objs.append(models.ResultTableOption(bk_tenant_id=bk_tenant_id, table_id=table_id, **dict(option)))

    if need_add_objs:
        models.ResultTableOption.objects.bulk_create(need_add_objs, batch_size=BULK_CREATE_BATCH_SIZE)
    if need_update_objs:
        models.ResultTableOption.objects.bulk_update(
            need_update_objs, list(update_fields), batch_size=BULK_UPDATE_BATCH_SIZE
        )


def _select_route_origin_table_id(
    *,
    table_id: str,
    target_origin_table_id: str | None,
    retained_origin_table_id: str | None,
    requested_origin_table_id: str | None,
) -> str | None:
    """从目标和保留 Storage 中选择虚拟表唯一关联的实体表。"""

    if requested_origin_table_id:
        if (
            retained_origin_table_id
            and retained_origin_table_id != table_id
            and retained_origin_table_id != requested_origin_table_id
        ):
            raise ValidationError(
                f"Route table {table_id} already points to another origin table: {[retained_origin_table_id]}"
            )
        return requested_origin_table_id

    unique_origins = {
        origin_table_id
        for origin_table_id in (target_origin_table_id, retained_origin_table_id)
        if origin_table_id and origin_table_id != table_id
    }
    if len(unique_origins) > 1:
        raise ValidationError(f"Route table {table_id} has inconsistent origin tables: {sorted(unique_origins)}")
    return next(iter(unique_origins), target_origin_table_id)


def _resolve_es_route_origin_table_id(
    *, bk_tenant_id: str, table_id: str, requested_origin_table_id: str | None
) -> str | None:
    """解析切换到 ES 时使用的实体表。"""

    es_origin_table_id = (
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
        .values_list("origin_table_id", flat=True)
        .first()
    )
    doris_origin_table_id = (
        models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
        .values_list("origin_table_id", flat=True)
        .first()
    )
    return _select_route_origin_table_id(
        table_id=table_id,
        target_origin_table_id=es_origin_table_id,
        retained_origin_table_id=doris_origin_table_id,
        requested_origin_table_id=requested_origin_table_id,
    )


def _resolve_doris_route_origin_table_id(
    *, bk_tenant_id: str, table_id: str, requested_origin_table_id: str | None
) -> str | None:
    """解析切换到 Doris 时使用的实体表。"""

    doris_origin_table_id = (
        models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
        .values_list("origin_table_id", flat=True)
        .first()
    )
    es_origin_table_id = (
        models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
        .values_list("origin_table_id", flat=True)
        .first()
    )
    return _select_route_origin_table_id(
        table_id=table_id,
        target_origin_table_id=doris_origin_table_id,
        retained_origin_table_id=es_origin_table_id,
        requested_origin_table_id=requested_origin_table_id,
    )


def _validate_virtual_route_origin(result_table: models.ResultTable, origin_table_id: str | None) -> str:
    """确保虚拟结果表关联了另一张实体结果表。"""

    if not origin_table_id or origin_table_id == result_table.table_id:
        raise ValidationError(f"Virtual route table {result_table.table_id} must reference an origin result table")
    return origin_table_id


def _validate_origin_result_table(*, bk_tenant_id: str, origin_table_id: str, expected_storage_type: str) -> None:
    """确认关联实体表当前使用目标存储类型。"""

    try:
        origin_result_table = models.ResultTable.objects.select_for_update().get(
            bk_tenant_id=bk_tenant_id,
            table_id=origin_table_id,
        )
    except models.ResultTable.DoesNotExist as error:
        raise ValidationError(f"Origin result table not found: {origin_table_id}") from error

    if origin_result_table.default_storage != expected_storage_type:
        raise ValidationError(
            f"Origin result table {origin_table_id} does not use storage type {expected_storage_type}"
        )


def _validate_origin_cluster(
    *,
    bk_tenant_id: str,
    origin_table_id: str,
    storage_type: str,
    cluster_id: int,
    requested_cluster_id: int | None,
) -> int:
    """校验实体 Storage 集群与请求、集群配置及 current 记录一致。"""

    if requested_cluster_id is not None and requested_cluster_id != cluster_id:
        raise ValidationError(
            f"Route cluster {requested_cluster_id} does not match origin storage cluster {cluster_id}"
        )

    if not models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id, cluster_id=cluster_id, cluster_type=storage_type
    ).exists():
        raise ValidationError(
            f"Origin storage cluster is invalid: cluster_id={cluster_id}, storage_type={storage_type}"
        )

    current_cluster_ids = list(
        models.StorageClusterRecord.objects.select_for_update()
        .filter(
            bk_tenant_id=bk_tenant_id,
            table_id=origin_table_id,
            is_current=True,
            is_deleted=False,
        )
        .values_list("cluster_id", flat=True)
    )
    if current_cluster_ids != [cluster_id]:
        raise ValidationError(
            f"Origin result table {origin_table_id} current storage record {current_cluster_ids} "
            f"does not match {storage_type} storage cluster {cluster_id}"
        )
    return cluster_id


def _resolve_es_origin_cluster_id(*, bk_tenant_id: str, origin_table_id: str, requested_cluster_id: int | None) -> int:
    """从关联实体表的 ESStorage 解析集群。"""

    _validate_origin_result_table(
        bk_tenant_id=bk_tenant_id,
        origin_table_id=origin_table_id,
        expected_storage_type=models.ClusterInfo.TYPE_ES,
    )
    try:
        origin_storage = models.ESStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=origin_table_id)
    except models.ESStorage.DoesNotExist as error:
        raise ValidationError(
            f"Origin storage not found: {origin_table_id}, storage_type={models.ClusterInfo.TYPE_ES}"
        ) from error
    return _validate_origin_cluster(
        bk_tenant_id=bk_tenant_id,
        origin_table_id=origin_table_id,
        storage_type=models.ClusterInfo.TYPE_ES,
        cluster_id=origin_storage.storage_cluster_id,
        requested_cluster_id=requested_cluster_id,
    )


def _resolve_doris_origin_cluster_id(
    *, bk_tenant_id: str, origin_table_id: str, requested_cluster_id: int | None
) -> int:
    """从关联实体表的 DorisStorage 解析集群。"""

    _validate_origin_result_table(
        bk_tenant_id=bk_tenant_id,
        origin_table_id=origin_table_id,
        expected_storage_type=models.ClusterInfo.TYPE_DORIS,
    )
    try:
        origin_storage = models.DorisStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=origin_table_id)
    except models.DorisStorage.DoesNotExist as error:
        raise ValidationError(
            f"Origin storage not found: {origin_table_id}, storage_type={models.ClusterInfo.TYPE_DORIS}"
        ) from error
    return _validate_origin_cluster(
        bk_tenant_id=bk_tenant_id,
        origin_table_id=origin_table_id,
        storage_type=models.ClusterInfo.TYPE_DORIS,
        cluster_id=origin_storage.storage_cluster_id,
        requested_cluster_id=requested_cluster_id,
    )


def _save_changed_fields(storage, update_values: dict[str, Any]) -> None:
    """只保存发生变化的 Storage 字段。"""

    update_fields: list[str] = []
    for field_name, value in update_values.items():
        if getattr(storage, field_name) != value:
            setattr(storage, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        storage.save(update_fields=update_fields)


def _sync_es_route_storage(
    *,
    bk_tenant_id: str,
    result_table: models.ResultTable,
    requested_origin_table_id: str | None,
    requested_cluster_id: int | None,
    index_set: str | None,
    source_type: str | None,
) -> None:
    """同步 ES 虚拟路由 Storage，并将虚拟表切换为 ES。

    ``index_set`` 和 ``source_type`` 为 ``None`` 表示请求未提供，更新时保留原值；空字符串表示显式清空。
    """

    result_table = models.ResultTable.objects.select_for_update().get(pk=result_table.pk)
    resolved_origin_table_id = _resolve_es_route_origin_table_id(
        bk_tenant_id=bk_tenant_id,
        table_id=result_table.table_id,
        requested_origin_table_id=requested_origin_table_id,
    )
    resolved_origin_table_id = _validate_virtual_route_origin(result_table, resolved_origin_table_id)
    resolved_cluster_id = _resolve_es_origin_cluster_id(
        bk_tenant_id=bk_tenant_id,
        origin_table_id=resolved_origin_table_id,
        requested_cluster_id=requested_cluster_id,
    )
    storage = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=result_table.table_id).first()
    if storage is None:
        models.ESStorage.create_table(
            bk_tenant_id=bk_tenant_id,
            table_id=result_table.table_id,
            cluster_id=resolved_cluster_id,
            is_sync_db=False,
            enable_create_index=False,
            source_type=source_type if source_type is not None else "",
            index_set=index_set if index_set is not None else "",
            need_create_index=False,
            origin_table_id=resolved_origin_table_id,
            create_storage_cluster_record=False,
        )
    else:
        update_values = {
            "origin_table_id": resolved_origin_table_id,
            "storage_cluster_id": resolved_cluster_id,
            "need_create_index": False,
        }
        if index_set is not None:
            update_values["index_set"] = index_set
        if source_type is not None:
            update_values["source_type"] = source_type
        _save_changed_fields(storage, update_values)

    if result_table.default_storage != models.ClusterInfo.TYPE_ES:
        result_table.default_storage = models.ClusterInfo.TYPE_ES
        result_table.save(update_fields=["default_storage"])


def _sync_doris_route_storage(
    *,
    bk_tenant_id: str,
    result_table: models.ResultTable,
    requested_origin_table_id: str | None,
    requested_cluster_id: int | None,
    index_set: str | None,
    source_type: str | None,
    bkbase_table_id: str | None,
) -> None:
    """同步 Doris 虚拟路由 Storage，并将虚拟表切换为 Doris。

    可选路由字段为 ``None`` 表示请求未提供，更新时保留原值；空字符串表示显式清空。
    """

    result_table = models.ResultTable.objects.select_for_update().get(pk=result_table.pk)
    resolved_origin_table_id = _resolve_doris_route_origin_table_id(
        bk_tenant_id=bk_tenant_id,
        table_id=result_table.table_id,
        requested_origin_table_id=requested_origin_table_id,
    )
    resolved_origin_table_id = _validate_virtual_route_origin(result_table, resolved_origin_table_id)
    resolved_cluster_id = _resolve_doris_origin_cluster_id(
        bk_tenant_id=bk_tenant_id,
        origin_table_id=resolved_origin_table_id,
        requested_cluster_id=requested_cluster_id,
    )
    storage = models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=result_table.table_id).first()
    if storage is None:
        models.DorisStorage.create_table(
            bk_tenant_id=bk_tenant_id,
            table_id=result_table.table_id,
            is_sync_db=False,
            source_type=source_type if source_type is not None else "",
            bkbase_table_id=bkbase_table_id,
            origin_table_id=resolved_origin_table_id,
            index_set=index_set,
            storage_cluster_id=resolved_cluster_id,
            create_storage_cluster_record=False,
        )
    else:
        update_values = {
            "origin_table_id": resolved_origin_table_id,
            "storage_cluster_id": resolved_cluster_id,
        }
        if index_set is not None:
            update_values["index_set"] = index_set
        if source_type is not None:
            update_values["source_type"] = source_type
        if bkbase_table_id is not None:
            update_values["bkbase_table_id"] = bkbase_table_id
        _save_changed_fields(storage, update_values)

    if result_table.default_storage != models.ClusterInfo.TYPE_DORIS:
        result_table.default_storage = models.ClusterInfo.TYPE_DORIS
        result_table.save(update_fields=["default_storage"])


def _create_es_router(
    *,
    bk_tenant_id: str,
    space: models.Space,
    table_id: str,
    options: list[dict[str, Any]],
    data_label: str = "",
    requested_cluster_id: int | None = None,
    index_set: str | None = None,
    source_type: str | None = None,
    requested_origin_table_id: str | None = None,
) -> None:
    """创建 ES 虚拟路由表。

    :param str bk_tenant_id: 虚拟表所属租户 ID。
    :param models.Space space: 虚拟表所属空间，用于取得业务 ID 并发布空间路由。
    :param str table_id: 要创建的虚拟结果表 ID。
    :param list[dict[str, Any]] options: 需要创建的 ResultTableOption 配置；每项包含 ``name``、``value``、
        ``value_type`` 和 ``creator``。
    :param str data_label: 虚拟表的数据标签，空字符串表示不配置标签。
    :param int | None requested_cluster_id: 请求指定的 ES 集群 ID，仅用于和实体 ESStorage 做一致性校验；
        None 表示不约束请求值，最终集群仍取实体 ESStorage。
    :param str | None index_set: 虚拟 ESStorage 的索引集规则；None 在创建时按空字符串保存。
    :param str | None source_type: 虚拟 ESStorage 的数据源类型；None 在创建时按空字符串保存。
    :param str | None requested_origin_table_id: 请求指定的关联实体结果表 ID；无已有 Storage 可继承时必须提供。
    """

    result_table = models.ResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_ES,
        creator="system",
        bk_biz_id=space.get_bk_biz_id(),
        data_label=data_label,
    )
    if options:
        _create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=options)
    _sync_es_route_storage(
        bk_tenant_id=bk_tenant_id,
        result_table=result_table,
        requested_origin_table_id=requested_origin_table_id,
        requested_cluster_id=requested_cluster_id,
        index_set=index_set,
        source_type=source_type,
    )

    logger.info("create_es_router: try to push route for table_id->[%s]", table_id)
    SpaceTableIDRedis().push_space_table_ids(
        space_type=space.space_type_id,
        space_id=space.space_id,
        is_publish=True,
    )
    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=[table_id], is_publish=True)

    if data_label:
        logger.info(
            "create_es_router: try to push data label route for table_id->[%s], data_label->[%s]",
            table_id,
            data_label,
        )
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=[data_label], bk_tenant_id=bk_tenant_id, is_publish=True
        )


def _create_doris_router(
    *,
    bk_tenant_id: str,
    space: models.Space,
    table_id: str,
    options: list[dict[str, Any]],
    data_label: str = "",
    requested_cluster_id: int | None = None,
    index_set: str | None = None,
    source_type: str | None = None,
    requested_origin_table_id: str | None = None,
    bkbase_table_id: str | None = None,
) -> None:
    """创建 Doris 虚拟路由表。

    :param str bk_tenant_id: 虚拟表所属租户 ID。
    :param models.Space space: 虚拟表所属空间，用于取得业务 ID 并发布空间路由。
    :param str table_id: 要创建的虚拟结果表 ID。
    :param list[dict[str, Any]] options: 需要创建的 ResultTableOption 配置；每项包含 ``name``、``value``、
        ``value_type`` 和 ``creator``。
    :param str data_label: 虚拟表的数据标签，空字符串表示不配置标签。
    :param int | None requested_cluster_id: 请求指定的 Doris 集群 ID，仅用于和实体 DorisStorage 做一致性校验；
        None 表示不约束请求值，最终集群仍取实体 DorisStorage。
    :param str | None index_set: 虚拟 DorisStorage 的索引集规则；None 在创建时保持为空。
    :param str | None source_type: 虚拟 DorisStorage 的数据源类型；None 在创建时按空字符串保存。
    :param str | None requested_origin_table_id: 请求指定的关联实体结果表 ID；无已有 Storage 可继承时必须提供。
    :param str | None bkbase_table_id: 虚拟 DorisStorage 关联的计算平台结果表 ID；None 表示不配置。
    """

    logger.info(
        "create_doris_router: try to create doris router,table_id->[%s],bkbase_table_id->[%s],bk_biz_id->[%s]",
        table_id,
        bkbase_table_id,
        space.get_bk_biz_id(),
    )

    result_table = models.ResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_DORIS,
        creator="system",
        bk_biz_id=space.get_bk_biz_id(),
        data_label=data_label,
    )
    if options:
        _create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=options)
    _sync_doris_route_storage(
        bk_tenant_id=bk_tenant_id,
        result_table=result_table,
        requested_origin_table_id=requested_origin_table_id,
        requested_cluster_id=requested_cluster_id,
        index_set=index_set,
        source_type=source_type,
        bkbase_table_id=bkbase_table_id,
    )

    logger.info("create_doris_router: create doris datalink related records successfully,now try to push router")
    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=[table_id], is_publish=True)
    SpaceTableIDRedis().push_space_table_ids(
        space_type=space.space_type_id,
        space_id=space.space_id,
        is_publish=True,
    )
    if data_label:
        logger.info(
            "create_doris_router: try to push data label router for table_id->[%s],data_label->[%s]",
            table_id,
            data_label,
        )
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=[data_label], bk_tenant_id=bk_tenant_id, is_publish=True
        )

    logger.info("create_doris_router: push doris datalink router success")


def _update_es_router(
    *,
    bk_tenant_id: str,
    table_id: str,
    options: list[dict[str, Any]],
    data_label: str = "",
    requested_cluster_id: int | None = None,
    index_set: str | None = None,
    source_type: str | None = None,
    requested_origin_table_id: str | None = None,
) -> None:
    """更新 ES 虚拟路由表。

    :param str bk_tenant_id: 虚拟表所属租户 ID。
    :param str table_id: 要更新的虚拟结果表 ID。
    :param list[dict[str, Any]] options: 需要创建或更新的 ResultTableOption 配置；每项包含 ``name``、``value``、
        ``value_type`` 和 ``creator``。
    :param str data_label: 新的数据标签；空字符串表示不修改现有标签。
    :param int | None requested_cluster_id: 请求指定的 ES 集群 ID，仅用于和实体 ESStorage 做一致性校验。
    :param str | None index_set: 新的索引集规则；None 表示不修改，空字符串表示清空。
    :param str | None source_type: 新的数据源类型；None 表示不修改，空字符串表示清空。
    :param str | None requested_origin_table_id: 请求指定的关联实体结果表 ID；None 表示沿已有 Storage 继承。
    """

    need_refresh_data_label = False
    try:
        result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    except models.ResultTable.DoesNotExist as error:
        raise ValidationError("Result table not found") from error

    old_data_label = result_table.data_label
    if data_label and data_label != old_data_label:
        result_table.data_label = data_label
        result_table.save(update_fields=["data_label"])
        need_refresh_data_label = True

    _sync_es_route_storage(
        bk_tenant_id=bk_tenant_id,
        result_table=result_table,
        requested_origin_table_id=requested_origin_table_id,
        requested_cluster_id=requested_cluster_id,
        index_set=index_set,
        source_type=source_type,
    )

    if options:
        _create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=options)

    if need_refresh_data_label:
        logger.info(
            "update_es_router: try to push data label router for table_id->[%s], data_label->[%s]",
            table_id,
            data_label,
        )
        push_data_labels = [data_label]
        if old_data_label:
            push_data_labels.append(old_data_label)
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=push_data_labels, bk_tenant_id=bk_tenant_id, is_publish=True
        )
        push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=data_label)
        if old_data_label:
            push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=old_data_label)

    logger.info("update_es_router: try to push es detail router for table_id->[%s]", table_id)
    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=[table_id], is_publish=True)


def _update_doris_router(
    *,
    bk_tenant_id: str,
    table_id: str,
    options: list[dict[str, Any]],
    data_label: str = "",
    requested_cluster_id: int | None = None,
    index_set: str | None = None,
    source_type: str | None = None,
    requested_origin_table_id: str | None = None,
    bkbase_table_id: str | None = None,
) -> None:
    """更新 Doris 虚拟路由表。

    :param str bk_tenant_id: 虚拟表所属租户 ID。
    :param str table_id: 要更新的虚拟结果表 ID。
    :param list[dict[str, Any]] options: 需要创建或更新的 ResultTableOption 配置；每项包含 ``name``、``value``、
        ``value_type`` 和 ``creator``。
    :param str data_label: 新的数据标签；空字符串表示不修改现有标签。
    :param int | None requested_cluster_id: 请求指定的 Doris 集群 ID，仅用于和实体 DorisStorage 做一致性校验。
    :param str | None index_set: 新的索引集规则；None 表示不修改，空字符串表示清空。
    :param str | None source_type: 新的数据源类型；None 表示不修改，空字符串表示清空。
    :param str | None requested_origin_table_id: 请求指定的关联实体结果表 ID；None 表示沿已有 Storage 继承。
    :param str | None bkbase_table_id: 新的计算平台结果表 ID；None 表示不修改。
    """

    logger.info("update_doris_router: try to update doris router for table_id->[%s]", table_id)

    need_refresh_data_label = False
    result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    old_data_label = result_table.data_label

    if data_label and data_label != old_data_label:
        result_table.data_label = data_label
        result_table.save(update_fields=["data_label"])
        need_refresh_data_label = True

    _sync_doris_route_storage(
        bk_tenant_id=bk_tenant_id,
        result_table=result_table,
        requested_origin_table_id=requested_origin_table_id,
        requested_cluster_id=requested_cluster_id,
        index_set=index_set,
        source_type=source_type,
        bkbase_table_id=bkbase_table_id,
    )

    if options:
        _create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=options)

    logger.info(
        "update_doris_router:update doris router for table_id->[%s] successfully,now try to push router", table_id
    )
    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=[table_id], is_publish=True)

    if need_refresh_data_label:
        logger.info(
            "update_doris_router: try to push data label router for table_id->[%s], data_label->[%s]",
            table_id,
            data_label,
        )
        push_data_labels = [data_label]
        if old_data_label:
            push_data_labels.append(old_data_label)
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=push_data_labels, bk_tenant_id=bk_tenant_id, is_publish=True
        )

    logger.info("update_doris_router:push doris router for table_id->[%s] successfully", table_id)


class CreateOrUpdateLogRouter(Resource):
    """更新或者创建log路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
        bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
        storage_type = serializers.ChoiceField(
            required=False,
            choices=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
            label="存储类型",
            default=models.ClusterInfo.TYPE_ES,
        )
        origin_table_id = serializers.CharField(required=False, label="原始结果表ID")

        class QueryAliasSettingSerializer(serializers.Serializer):
            field_name = serializers.CharField(required=True, label="字段名", help_text="需要设置查询别名的字段名")
            query_alias = serializers.CharField(required=True, label="查询别名", help_text="字段的查询别名")

        query_alias_settings = QueryAliasSettingSerializer(
            required=False, label="查询别名设置", default=None, many=True
        )

    def perform_request(self, validated_request_data: dict) -> None:
        space = models.Space.objects.get(
            space_type_id=validated_request_data["space_type"],
            space_id=validated_request_data["space_id"],
            bk_tenant_id=get_request_tenant_id(),
        )
        bk_tenant_id: str = space.bk_tenant_id

        # 根据结果表判断是创建或更新
        table_id: str = validated_request_data["table_id"]
        result_table = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        storage_type = validated_request_data["storage_type"]
        options = validated_request_data["options"]
        data_label = validated_request_data.get("data_label", "")
        requested_cluster_id = validated_request_data.get("cluster_id")
        index_set = validated_request_data.get("index_set")
        source_type = validated_request_data.get("source_type")
        requested_origin_table_id = validated_request_data.get("origin_table_id")
        bkbase_table_id = validated_request_data.get("bkbase_table_id")

        logger.info(
            "CreateOrUpdateLogRouter: try to create or update log router for table id->[%s],with storage_type->[%s]",
            table_id,
            storage_type,
        )

        # 查询别名与虚拟路由 Storage/default_storage 使用同一个 metadata DB 事务。
        with atomic(config.DATABASE_CONNECTION_NAME):
            if validated_request_data.get("query_alias_settings") is not None:
                operator = get_request_username() or "system"
                models.ESFieldQueryAliasOption.manage_query_alias_settings(
                    table_id=table_id,
                    query_alias_settings=validated_request_data["query_alias_settings"],
                    operator=operator,
                    bk_tenant_id=bk_tenant_id,
                )

            if result_table is None:
                if storage_type == models.ClusterInfo.TYPE_ES:
                    _create_es_router(
                        bk_tenant_id=bk_tenant_id,
                        space=space,
                        table_id=table_id,
                        options=options,
                        data_label=data_label,
                        requested_cluster_id=requested_cluster_id,
                        index_set=index_set,
                        source_type=source_type,
                        requested_origin_table_id=requested_origin_table_id,
                    )
                else:
                    _create_doris_router(
                        bk_tenant_id=bk_tenant_id,
                        space=space,
                        table_id=table_id,
                        options=options,
                        data_label=data_label,
                        requested_cluster_id=requested_cluster_id,
                        index_set=index_set,
                        source_type=source_type,
                        requested_origin_table_id=requested_origin_table_id,
                        bkbase_table_id=bkbase_table_id,
                    )
            elif storage_type == models.ClusterInfo.TYPE_ES:
                _update_es_router(
                    bk_tenant_id=bk_tenant_id,
                    table_id=table_id,
                    options=options,
                    data_label=data_label,
                    requested_cluster_id=requested_cluster_id,
                    index_set=index_set,
                    source_type=source_type,
                    requested_origin_table_id=requested_origin_table_id,
                )
            else:
                _update_doris_router(
                    bk_tenant_id=bk_tenant_id,
                    table_id=table_id,
                    options=options,
                    data_label=data_label,
                    requested_cluster_id=requested_cluster_id,
                    index_set=index_set,
                    source_type=source_type,
                    requested_origin_table_id=requested_origin_table_id,
                    bkbase_table_id=bkbase_table_id,
                )


class BulkCreateOrUpdateLogRouter(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        space_type = serializers.CharField(label="空间类型")
        space_id = serializers.CharField(label="空间ID")
        data_label = serializers.CharField(allow_blank=True, label="数据标签")

        class TableInfoSerializer(ParamsSerializer):
            table_id = serializers.CharField(required=True, label="结果表ID")
            cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
            index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
            source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
            bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
            origin_table_id = serializers.CharField(required=False, label="原始结果表ID")
            storage_type = serializers.ChoiceField(
                required=False,
                choices=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
                label="存储类型",
                default=models.ClusterInfo.TYPE_ES,
            )
            is_enable = serializers.BooleanField(required=False, label="是否启用")

            class QueryAliasSettingSerializer(serializers.Serializer):
                field_name = serializers.CharField(required=True, label="字段名", help_text="需要设置查询别名的字段名")
                query_alias = serializers.CharField(required=True, label="查询别名", help_text="字段的查询别名")

            query_alias_settings = QueryAliasSettingSerializer(
                required=False, label="查询别名设置", default=None, many=True
            )

        table_info = serializers.ListField(child=TableInfoSerializer(), label="结果表信息列表", min_length=1)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        space_type = validated_request_data["space_type"]
        space_id = validated_request_data["space_id"]
        data_label = validated_request_data.get("data_label", "")
        table_info_list = validated_request_data["table_info"]

        space = models.Space.objects.get(space_type_id=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        logger.info(
            "CreateOrUpdateLogDataLink: processing %d table(s) for space [%s:%s] with data_label [%s]",
            len(table_info_list),
            space_type,
            space_id,
            data_label,
        )

        # 批量处理所有表信息
        processed_table_ids = []
        with atomic(config.DATABASE_CONNECTION_NAME):
            table_mapping = {
                table.table_id: table
                for table in models.ResultTable.objects.filter(
                    bk_tenant_id=bk_tenant_id, table_id__in=[info["table_id"] for info in table_info_list]
                )
            }

            for table_info in table_info_list:
                table_id = table_info["table_id"]
                storage_type = table_info.get("storage_type", models.ClusterInfo.TYPE_ES)
                options = table_info["options"]
                is_enable = table_info.get("is_enable")
                requested_origin_table_id = table_info.get("origin_table_id")
                requested_cluster_id = table_info.get("cluster_id")
                index_set = table_info.get("index_set")
                source_type = table_info.get("source_type")
                bkbase_table_id = table_info.get("bkbase_table_id")

                try:
                    # 检查结果表是否存在
                    result_table = table_mapping.get(table_id)
                    if result_table:
                        # 更新现有表
                        self._update_existing_table(
                            bk_tenant_id=bk_tenant_id,
                            result_table=result_table,
                            data_label=data_label,
                            is_enable=is_enable,
                            options=options,
                        )
                    else:
                        # 创建新表
                        result_table = self._create_new_table(
                            bk_tenant_id=bk_tenant_id,
                            space=space,
                            table_id=table_id,
                            data_label=data_label,
                            storage_type=storage_type,
                            is_enable=True if is_enable is None else is_enable,
                            options=options,
                        )
                        if result_table is None:
                            logger.info(
                                "CreateOrUpdateLogDataLink: skip disabled new route table [%s]",
                                table_id,
                            )
                            continue

                    if storage_type == models.ClusterInfo.TYPE_ES:
                        _sync_es_route_storage(
                            bk_tenant_id=bk_tenant_id,
                            result_table=result_table,
                            requested_origin_table_id=requested_origin_table_id,
                            requested_cluster_id=requested_cluster_id,
                            index_set=index_set,
                            source_type=source_type,
                        )
                    else:
                        _sync_doris_route_storage(
                            bk_tenant_id=bk_tenant_id,
                            result_table=result_table,
                            requested_origin_table_id=requested_origin_table_id,
                            requested_cluster_id=requested_cluster_id,
                            index_set=index_set,
                            source_type=source_type,
                            bkbase_table_id=bkbase_table_id,
                        )

                    # 处理查询别名设置
                    if table_info.get("query_alias_settings") is not None:
                        operator = get_request_username() or "system"
                        models.ESFieldQueryAliasOption.manage_query_alias_settings(
                            table_id=table_id,
                            query_alias_settings=table_info["query_alias_settings"],
                            operator=operator,
                            bk_tenant_id=bk_tenant_id,
                        )

                    processed_table_ids.append(table_id)
                    logger.info("CreateOrUpdateLogDataLink: processed table_id [%s]", table_id)
                except Exception as e:
                    logger.error(
                        "CreateOrUpdateLogDataLink: failed to process table_id [%s], error: %s",
                        table_id,
                        str(e),
                    )
                    raise e

        # 清理data_label下多余的配置
        if data_label:
            self._cleanup_excess_data_label_config(bk_tenant_id, data_label, processed_table_ids)

        self._push_space_routes(space_type, space_id)
        self._push_table_routes(bk_tenant_id, processed_table_ids)
        if data_label and processed_table_ids:
            self._push_data_label_route(bk_tenant_id, data_label)

        logger.info(
            "CreateOrUpdateLogDataLink: successfully processed all %d table(s) for space [%s:%s]",
            len(table_info_list),
            space_type,
            space_id,
        )

    def _update_existing_table(
        self,
        *,
        bk_tenant_id: str,
        result_table: models.ResultTable,
        data_label: str,
        is_enable: bool | None,
        options: list[dict[str, Any]],
    ) -> None:
        """更新现有结果表"""
        # 更新结果表data_label
        if data_label and data_label != result_table.data_label:
            result_table.data_label = data_label
            result_table.save(update_fields=["data_label"])

        # 更新结果表是否启用
        if is_enable is not None and is_enable != result_table.is_enable:
            result_table.is_enable = is_enable
            result_table.save(update_fields=["is_enable"])

        # 更新options
        if options:
            _create_or_update_options(
                bk_tenant_id=bk_tenant_id,
                table_id=result_table.table_id,
                options=options,
            )

    def _create_new_table(
        self,
        *,
        bk_tenant_id: str,
        space: models.Space,
        table_id: str,
        data_label: str,
        storage_type: str,
        is_enable: bool,
        options: list[dict[str, Any]],
    ) -> models.ResultTable | None:
        """创建新的结果表"""
        # 如果结果表不启用，则不创建
        if is_enable is False:
            return None

        # 创建结果表
        result_table = models.ResultTable.objects.create(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            table_name_zh=table_id,
            is_custom_table=True,
            default_storage=storage_type,
            creator="system",
            bk_biz_id=space.get_bk_biz_id(),
            data_label=data_label,
        )

        # 创建结果表options
        if options:
            _create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=options)

        return result_table

    def _push_space_routes(self, space_type: str, space_id: str) -> None:
        """推送当前空间及关联业务空间路由。"""

        logger.info("CreateOrUpdateLogDataLink: pushing routes for space [%s:%s]", space_type, space_id)
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)

        if space_type != "bkcc":
            related_space: Space = SpaceApi.get_related_space(f"{space_type}__{space_id}", SpaceTypeEnum.BKCC.value)
            if related_space:
                SpaceTableIDRedis().push_space_table_ids(
                    space_type=related_space.space_type_id, space_id=related_space.space_id, is_publish=True
                )

    def _push_table_routes(self, bk_tenant_id: str, table_ids: list[str]) -> None:
        """推送当前默认存储对应的结果表详情路由。"""

        if not table_ids:
            return
        logger.info("CreateOrUpdateLogDataLink: pushing routes for %d tables", len(table_ids))
        SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=table_ids, is_publish=True)

    def _push_data_label_route(self, bk_tenant_id: str, data_label: str) -> None:
        """推送 data_label 路由并保持现有别名通知行为。"""

        logger.info("CreateOrUpdateLogDataLink: pushing data_label route for [%s]", data_label)
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=[data_label], bk_tenant_id=bk_tenant_id, is_publish=True
        )
        push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=data_label)

    def _cleanup_excess_data_label_config(self, bk_tenant_id: str, data_label: str, processed_table_ids: list):
        """清理data_label下多余的配置"""
        logger.info("CreateOrUpdateLogDataLink: cleaning up excess configurations for data_label [%s]", data_label)

        # 查找该data_label下的所有结果表
        existing_tables = models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, data_label=data_label
        ).values_list("table_id", flat=True)

        # 找出需要清理的table_ids（存在于数据库中但不在当前处理列表中的）
        excess_table_ids = set(existing_tables) - set(processed_table_ids)

        if excess_table_ids:
            logger.info(
                "CreateOrUpdateLogDataLink: found %d excess tables to clean up: %s",
                len(excess_table_ids),
                list(excess_table_ids),
            )

            # 清理多余的结果表data_label
            models.ResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id, table_id__in=excess_table_ids, data_label=data_label
            ).update(data_label="")

            logger.info("CreateOrUpdateLogDataLink: cleaned up %d excess table configurations", len(excess_table_ids))
        else:
            logger.info("CreateOrUpdateLogDataLink: no excess configurations found for data_label [%s]", data_label)


class CleanLogRouter(Resource):
    """清理日志路由数据"""

    class RequestSerializer(ParamsSerializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        data_label = serializers.CharField(label="数据标签")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        data_label = validated_request_data["data_label"]

        # 将data_label关联的所有结果表都设为不启用
        models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, data_label=data_label).update(is_enable=False)
