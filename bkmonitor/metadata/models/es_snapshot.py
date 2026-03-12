"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import itertools
import logging
from collections import defaultdict
from typing import Any

import elasticsearch
import elasticsearch5
import elasticsearch6
from curator import utils
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Count, Sum, Q
from django.db.transaction import atomic, on_commit
from django.forms import model_to_dict
from django.utils import timezone
from django.utils.translation import gettext as _

from bkmonitor.utils.time_tools import biz2utc_str
from constants.common import DEFAULT_TENANT_ID
from metadata import config
from metadata.utils.db import array_group
from metadata.utils.es_tools import (
    get_client,
    get_cluster_disk_size,
    get_value_if_not_none,
)

logger = logging.getLogger("metadata")


class EsSearchCodes:
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    FAIL = "fail"


class EsSnapshot(models.Model):
    """
    ES快照
    """

    ES_RUNNING_STATUS = "running"
    # 当停用后，不允许新增，也不允许过期删除
    ES_STOPPED_STATUS = "stopped"
    # 0 表示永久
    PERMANENT_PRESERVATION = 0

    id = models.AutoField(primary_key=True)
    table_id = models.CharField("结果表id", max_length=128)
    # 快照所在的快照仓库
    target_snapshot_repository_name = models.CharField("快照仓库名称", max_length=128, default="")

    # 快照存储天数
    snapshot_days = models.IntegerField("快照天数", default=0)

    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    status = models.CharField("快照状态", blank=True, null=True, default="running", max_length=16)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    class Meta:
        unique_together = ("table_id", "target_snapshot_repository_name")

    @classmethod
    def _lock_snapshot_scope(cls, table_ids: list, bk_tenant_id: str):
        """锁定快照记录"""
        # 去重并排序，避免死锁
        unique_table_ids = sorted(list(set(table_ids)))

        # 1. 一次性锁定所有相关快照记录（按顺序避免死锁）
        locked_snapshots = cls.objects.select_for_update().filter(
            table_id__in=unique_table_ids,
            bk_tenant_id=bk_tenant_id
        ).order_by("id")

        # 返回锁定的记录数（可选）
        return list(locked_snapshots)

    @classmethod
    def _lock_and_validate_create_snapshot(
        cls,
        table_ids: list,
        bk_tenant_id: str,
        target_snapshot_repository_name: str,
        status: str | None = None
    ):
        """带锁的校验方法"""
        from metadata.models import ESStorage

        if not table_ids:
            raise ValueError("table_ids is empty")

        # 立即获取锁（执行查询）
        snapshot_list = cls._lock_snapshot_scope(table_ids, bk_tenant_id)

        # 2. 将快照记录按 table_id 分组
        snapshots_by_table = {}
        for snapshot in snapshot_list:
            if snapshot.table_id not in snapshots_by_table:
                snapshots_by_table[snapshot.table_id] = []
            snapshots_by_table[snapshot.table_id].append(snapshot)

        # 3. 其他校验（这些表通常不会被并发修改，所以不用锁定）
        es_storages = ESStorage.objects.select_for_update().filter(
            table_id__in=table_ids,
            bk_tenant_id=bk_tenant_id,
        ).order_by("id")

        exist_table_ids = es_storages.values_list("table_id", flat=True)
        if set(table_ids) != set(exist_table_ids):
            raise ValueError(_("结果表不存在"))

        storage_cluster_ids = es_storages.values_list("storage_cluster_id", flat=True)
        if len(set(storage_cluster_ids)) != 1:
            raise ValueError(_("结果表ids所在ES存储集群不一致"))

        cluster_id = storage_cluster_ids[0]

        if not EsSnapshotRepository.objects.filter(
            repository_name=target_snapshot_repository_name,
            cluster_id=cluster_id,
            is_deleted=False,
            bk_tenant_id=bk_tenant_id,
        ).exists():
            raise ValueError(_("快照仓库不存在或已经被删除"))

        # 4. 在锁的保护下检查业务规则
        # 检查是否已存在相同仓库的配置
        running_tables = []
        for table_id in table_ids:
            if table_id not in snapshots_by_table:
                continue
            has_same_repo = any(
                s.target_snapshot_repository_name == target_snapshot_repository_name
                for s in snapshots_by_table[table_id]
            )
            if has_same_repo:
                raise ValueError(_("目标es集群快照仓库结果表快照已存在: %s") % table_id)
                
            if status != cls.ES_RUNNING_STATUS:
                continue
            has_running = any(
                s.status == cls.ES_RUNNING_STATUS
                for s in snapshots_by_table[table_id]
            )
            if has_running:
                running_tables.append(table_id)

        if running_tables:
            raise ValueError(_("已存在启用中结果表快照: %s") % ", ".join(running_tables))

        return snapshots_by_table

    @classmethod
    def validated_snapshot(cls, table_id, bk_tenant_id, target_snapshot_repository_name: str | None = None):
        """返回校验后的快照配置"""
        # 变更为可切换归档仓库后，可能存在多份归档配置, 需通过table_id和快照仓库名称确定修改的快照配置
        # 同时兼容一个table_id只能有一个快照配置的版本
        query = Q(table_id=table_id, bk_tenant_id=bk_tenant_id)
        if target_snapshot_repository_name:
            query &= Q(target_snapshot_repository_name=target_snapshot_repository_name)

        objs = cls.objects.filter(query)
        if objs.count() > 1 and not target_snapshot_repository_name:
            raise ValueError(_("结果表快照配置存在多个，快照仓库名称不能为空"))

        return objs.first()
    
    @classmethod
    def validated_multi_snapshots(
        cls, table_ids: list, bk_tenant_id, target_snapshot_repository_name: str | None = None
    ):
        """返回校验后的多份快照配置"""
        query = Q(table_id__in=table_ids, bk_tenant_id=bk_tenant_id)
        if target_snapshot_repository_name:
            query &= Q(target_snapshot_repository_name=target_snapshot_repository_name)

        objs = cls.objects.filter(query)

        duplicate_table_ids = objs.values('table_id').annotate(count=Count('table_id')).filter(count__gt=1)
        if duplicate_table_ids.exists() and not target_snapshot_repository_name:
            raise ValueError(_("部分结果表快照配置存在多个，快照仓库名称不能为空"))

        return objs

    @classmethod
    def has_running_snapshot(cls, table_id, bk_tenant_id, exclude_id: int | None = None):
        """是否有正在运行的快照任务"""
        qs = cls.objects.filter(table_id=table_id, status=cls.ES_RUNNING_STATUS, bk_tenant_id=bk_tenant_id)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_snapshot(
        cls,
        table_id,
        target_snapshot_repository_name,
        snapshot_days,
        operator,
        status: str | None = None,
        bk_tenant_id=DEFAULT_TENANT_ID
    ):
        status = status or cls.ES_RUNNING_STATUS
        # 使用带锁的校验
        cls._lock_and_validate_create_snapshot(
            [table_id], bk_tenant_id, target_snapshot_repository_name, status
        )

        return cls.objects.create(
            table_id=table_id,
            target_snapshot_repository_name=target_snapshot_repository_name,
            snapshot_days=snapshot_days,
            creator=operator,
            last_modify_user=operator,
            status=status,
            bk_tenant_id=bk_tenant_id,
        )
    
    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def bulk_create_snapshot(
        cls,
        table_ids,
        target_snapshot_repository_name,
        snapshot_days, operator,
        status: str | None = None,
        bk_tenant_id=DEFAULT_TENANT_ID
    ):
        """批量创建ES快照配置

        :param table_ids: 需要修改快照配置的结果表 ID 列表。
        :param target_snapshot_repository_name: 目标快照仓库名称
        :param snapshot_days: 快照保留天数。
        :param operator: 本次修改的操作者用户名。
        :param status: 快照配置目标状态，为 ``None`` 时默认为running状态。
        :param bk_tenant_id: 租户 ID，默认为默认租户。
        :return: 实际创建的记录条数。
        """
        status = status or cls.ES_RUNNING_STATUS
        unique_table_ids = list(set(table_ids))
        # 使用带锁的校验
        cls._lock_and_validate_create_snapshot(
            unique_table_ids, bk_tenant_id, target_snapshot_repository_name, status
        )

        # 批量创建新记录（排除已存在相同仓库配置的 table_id）
        snapshots_to_create = []
        for table_id in unique_table_ids:
            snapshots_to_create.append(cls(
                table_id=table_id,
                target_snapshot_repository_name=target_snapshot_repository_name,
                snapshot_days=snapshot_days,
                creator=operator,
                last_modify_user=operator,
                status=status,
                bk_tenant_id=bk_tenant_id,
            ))

        if snapshots_to_create:
            cls.objects.bulk_create(snapshots_to_create)

        return len(snapshots_to_create)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_snapshot(
        cls,
        table_id,
        snapshot_days,
        operator,
        status: str | None = None,
        target_snapshot_repository_name: str | None = None,
        bk_tenant_id=DEFAULT_TENANT_ID
    ):
        cls._lock_snapshot_scope([table_id], bk_tenant_id)
        obj = cls.validated_snapshot(table_id, bk_tenant_id, target_snapshot_repository_name)
        if not obj:
            return
        obj.snapshot_days = snapshot_days
        obj.last_modify_user = operator
        updated_fields = ["snapshot_days", "last_modify_user"]
        if (
            status == cls.ES_RUNNING_STATUS and
            obj.status != cls.ES_RUNNING_STATUS and
            cls.has_running_snapshot(obj.table_id, obj.bk_tenant_id, exclude_id=obj.id)
        ):
            raise ValueError(_("已存在启用中结果表快照"))
        
        # 如果状态不为空，则进行状态的更新
        if status is not None:
            obj.status = status
            updated_fields.append("status")
            
        obj.save(update_fields=updated_fields)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def bulk_modify_snapshot(
        cls,
        table_ids,
        snapshot_days,
        operator,
        status: str | None = None,
        target_snapshot_repository_name: str | None = None,
        bk_tenant_id=DEFAULT_TENANT_ID
    ):
        """批量修改ES快照配置
        
        :param table_ids: 需要修改快照配置的结果表 ID 列表。
        :param snapshot_days: 快照保留天数。
        :param operator: 本次修改的操作者用户名。
        :param status: 快照配置目标状态，为 ``None`` 时不修改状态。
        :param target_snapshot_repository_name: 目标快照仓库名称，用于校验已有配置。
        :param bk_tenant_id: 租户 ID，默认为默认租户。
        :return: 实际更新的记录条数。
        """
        unique_table_ids = list(set(table_ids))
        # 1. 锁定相关记录
        cls._lock_snapshot_scope(unique_table_ids, bk_tenant_id)
        # 2. 获取要更新的对象
        objs = cls.validated_multi_snapshots(unique_table_ids, bk_tenant_id, target_snapshot_repository_name)    
        if not objs.exists():
            return 0
        
        # 3. 检查 running 状态冲突
        if status == cls.ES_RUNNING_STATUS:
            # 注意：这里查询的也是被锁定的范围
            other_running = cls.objects.filter(
                table_id__in=unique_table_ids,
                bk_tenant_id=bk_tenant_id,
                status=cls.ES_RUNNING_STATUS
            ).exclude(id__in=objs.values_list('id', flat=True)).exists()

            if other_running:
                raise ValueError(_("已存在启用中结果表快照"))

        # 4. 执行更新
        update_fields = {
            'snapshot_days': snapshot_days,
            'last_modify_user': operator,
        }
        if status is not None:
            update_fields['status'] = status

        updated_count = objs.update(**update_fields)

        return updated_count

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_snapshot(
        cls,
        table_id,
        is_sync: bool | None = False,
        target_snapshot_repository_name: str | None = None,
        bk_tenant_id=DEFAULT_TENANT_ID
    ):
        """
        当快照产生当比较多当会产生很多的es调用 比较重 移到后台去执行实际的快照清理
        """
        from metadata.task.tasks import delete_es_result_table_snapshot

        snapshot = cls.validated_snapshot(
            table_id, bk_tenant_id, target_snapshot_repository_name=target_snapshot_repository_name
        )
        if not snapshot:
            logger.error("ES SnapShot does not exists, table_id(%s)", table_id)
            raise ValueError(_("快照配置不存在或已经被删除"))

        if is_sync:
            logger.info("table_id %s sync to delete snapshot %s", table_id, snapshot.target_snapshot_repository_name)
            delete_es_result_table_snapshot(
                table_id=table_id,
                target_snapshot_repository_name=snapshot.target_snapshot_repository_name,
                bk_tenant_id=bk_tenant_id,
            )
        else:
            logger.info("table_id %s async to delete snapshot %s", table_id, snapshot.target_snapshot_repository_name)
            delete_es_result_table_snapshot.delay(
                table_id=table_id,
                target_snapshot_repository_name=snapshot.target_snapshot_repository_name,
                bk_tenant_id=bk_tenant_id,
            )
        snapshot.delete()

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def retry_snapshot(
        cls,
        table_id,
        is_sync: bool | None = False,
        target_snapshot_repository_name: str | None = None,
        bk_tenant_id=DEFAULT_TENANT_ID
    ):
        from metadata.task.tasks import retry_es_result_table_snapshot

        snapshot = cls.validated_snapshot(
            table_id, bk_tenant_id, target_snapshot_repository_name=target_snapshot_repository_name
        )
        if not snapshot:
            logger.error("ES SnapShot does not exists, table_id(%s)", table_id)
            raise ValueError(_("快照配置不存在或已经被删除"))

        if snapshot.status != cls.ES_RUNNING_STATUS:
            raise ValueError(_("快照配置未启用"))

        if is_sync:
            logger.info("table_id %s sync to retry snapshot %s", table_id, snapshot.target_snapshot_repository_name)
            retry_es_result_table_snapshot(
                table_id=table_id,
                target_snapshot_repository_name=snapshot.target_snapshot_repository_name,
                bk_tenant_id=bk_tenant_id,
            )
        else:
            logger.info("table_id %s async to retry snapshot %s", table_id, snapshot.target_snapshot_repository_name)
            retry_es_result_table_snapshot.delay(
                table_id=table_id,
                target_snapshot_repository_name=snapshot.target_snapshot_repository_name,
                bk_tenant_id=bk_tenant_id,
            )

    @classmethod
    def batch_get_state(cls, bk_tenant_id: str, table_ids: list):
        from metadata.models import ESStorage

        es_storages = ESStorage.objects.filter(table_id__in=table_ids, bk_tenant_id=bk_tenant_id)
        result = []

        for es_storage in es_storages:
            snapshots = []
            try:
                snapshots = es_storage.es_client.snapshot.get(
                    es_storage.snapshot_obj.target_snapshot_repository_name, es_storage.search_snapshot
                ).get("snapshots", [])
            except ObjectDoesNotExist:
                # 关联的快照配置不存在时跳过当前存储，避免中断批量查询
                logger.debug(
                    "skip es_storage %s when batch getting snapshots: snapshot config does not exist",
                    es_storage.table_id,
                )
            except Exception as e:  # noqa
                logger.exception(
                    f"batch get es snapshots error, target_snapshot_repository_name({es_storage.snapshot_obj.target_snapshot_repository_name}), search_snapshot({es_storage.search_snapshot})"
                )

            for snapshot in snapshots:
                result.append(
                    {
                        "table_id": es_storage.table_id,
                        "snapshot_name": snapshot.get("snapshot"),
                        "state": snapshot.get("state"),
                        "duration": snapshot.get("duration_in_millis"),
                    }
                )
        return result

    @classmethod
    def batch_get_recent_state(cls, bk_tenant_id: str, table_ids: list):
        """批量获取最近一次的状态"""
        from metadata.models import ESStorage

        es_storages = ESStorage.objects.filter(table_id__in=table_ids, bk_tenant_id=bk_tenant_id)
        result = []

        for es_storage in es_storages:
            snapshots = []
            failures = []
            search_code = EsSearchCodes.SUCCESS
            try:
                snapshots = es_storage.es_client.snapshot.get(
                    es_storage.snapshot_obj.target_snapshot_repository_name, es_storage.search_snapshot
                ).get("snapshots", [])
            except (elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
                search_code = EsSearchCodes.NOT_FOUND
            except ObjectDoesNotExist as e:
                search_code = EsSearchCodes.FAIL
                failures.append(str(e))
            except Exception as e:  # noqa
                logger.exception(
                    f"batch get es snapshots error, target_snapshot_repository_name({es_storage.snapshot_obj.target_snapshot_repository_name}), search_snapshot({es_storage.search_snapshot})"
                )
                search_code = EsSearchCodes.FAIL
                failures.append(str(e))

            max_datetime, max_snapshot = es_storage.get_max_snapshot(snapshots)
            result.append(
                {
                    "table_id": es_storage.table_id,
                    "snapshot_name": max_snapshot.get("snapshot"),
                    "state": max_snapshot.get("state"),
                    "duration": max_snapshot.get("duration_in_millis"),
                    "failures": max_snapshot.get("failures") or failures,
                    "code": search_code,
                }
            )

        return result

    def is_permanent(self):
        return self.snapshot_days == self.PERMANENT_PRESERVATION

    def to_self_json(self):
        return {
            "table_id": self.table_id,
            "snapshot_days": self.snapshot_days,
            "target_snapshot_repository_name": self.target_snapshot_repository_name,
            "status": self.status,
            "creator": self.creator,
            "create_time": self.create_time.timestamp(),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.timestamp(),
            "bk_tenant_id": self.bk_tenant_id,
        }

    def to_json(self):
        from metadata.models import ESStorage

        all_snapshots: list[dict[str, Any]] = []
        es_storage = ESStorage.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
        try:
            all_snapshots = es_storage.es_client.snapshot.get(
                self.target_snapshot_repository_name, es_storage.search_snapshot
            ).get("snapshots", [])
        except Exception as e:  # noqa
            logger.exception(
                f"get es snapshots error, target_snapshot_repository_name({self.target_snapshot_repository_name}), search_snapshot({es_storage.search_snapshot})"
            )

        return [
            {
                "snapshot_name": snapshot.get("snapshot", ""),
                "state": snapshot.get("state"),
                "table_id": self.table_id,
                "expired_time": es_storage.expired_date_timestamp(snapshot.get("snapshot", ""), self.snapshot_days),
                "indices": EsSnapshotIndice.batch_to_json(
                    bk_tenant_id=self.bk_tenant_id,
                    table_id=self.table_id,
                    snapshot_name=snapshot.get("snapshot", ""),
                    repository_name=self.target_snapshot_repository_name,
                ),
            }
            for snapshot in all_snapshots
        ]


class EsSnapshotRepository(models.Model):
    repository_name = models.CharField("仓库名称", max_length=128, primary_key=True)
    cluster_id = models.IntegerField("集群id")
    alias = models.CharField("仓库别名", max_length=128)
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    is_deleted = models.BooleanField("仓库表是否已经禁用", default=False)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    class Meta:
        verbose_name = "ES仓库记录表"
        verbose_name_plural = "ES仓库记录表"

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_repository(
        cls, bk_tenant_id: str, cluster_id: int, snapshot_repository_name, es_config, alias, operator
    ):
        from metadata.models import ClusterInfo

        cluster: ClusterInfo | None = ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_id=cluster_id
        ).first()
        if not cluster:
            raise ValueError(_("集群不存在"))
        if cluster.cluster_type != cluster.TYPE_ES:
            raise ValueError(_("集群不是es集群"))
        if cls.objects.filter(repository_name=snapshot_repository_name).exists():
            raise ValueError(_("仓库名称已经存在"))

        es_client = get_client(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
        new_rep = cls.objects.create(
            cluster_id=cluster_id,
            repository_name=snapshot_repository_name,
            alias=alias,
            creator=operator,
            last_modify_user=operator,
            bk_tenant_id=bk_tenant_id,
        )
        try:
            es_client.snapshot.create_repository(snapshot_repository_name, es_config)
        except Exception as e:  # noqa
            logger.exception("create repository(%s) error, err=>(%s)", snapshot_repository_name, e)
            raise ValueError(_("创建集群仓库({})失败 err({})").format(snapshot_repository_name, e))
        return new_rep

    @classmethod
    def modify_repository(cls, cluster_id, snapshot_repository_name, alias, operator, bk_tenant_id=DEFAULT_TENANT_ID):
        cls.objects.filter(cluster_id=cluster_id, repository_name=snapshot_repository_name).update(
            alias=alias, last_modify_user=operator, bk_tenant_id=bk_tenant_id
        )

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_repository(cls, cluster_id, snapshot_repository_name, operator, bk_tenant_id=DEFAULT_TENANT_ID):
        if EsSnapshotIndice.objects.filter(
            cluster_id=cluster_id, repository_name=snapshot_repository_name, bk_tenant_id=bk_tenant_id
        ).exists():
            raise ValueError(_("集群还存在快照无法删除"))
        cls.objects.filter(
            cluster_id=cluster_id, repository_name=snapshot_repository_name, bk_tenant_id=bk_tenant_id
        ).update(is_deleted=True, last_modify_user=operator)
        get_client(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id).snapshot.delete_repository(
            snapshot_repository_name
        )

    @classmethod
    def verify_repository(cls, cluster_id, snapshot_repository_name, bk_tenant_id=DEFAULT_TENANT_ID):
        if not cls.objects.filter(
            cluster_id=cluster_id, repository_name=snapshot_repository_name, is_deleted=False, bk_tenant_id=bk_tenant_id
        ).exists():
            raise ValueError(_("仓库不存在"))
        return get_client(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id).snapshot.verify_repository(
            snapshot_repository_name
        )

    def to_json(self):
        result = {
            "repository_name": self.repository_name,
            "cluster_id": self.cluster_id,
            "alias": self.alias,
            "creator": self.creator,
            "create_time": self.create_time.timestamp(),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.timestamp(),
            "bk_tenant_id": self.bk_tenant_id,
        }
        try:
            result.update(
                get_client(bk_tenant_id=self.bk_tenant_id, cluster_id=self.cluster_id)
                .snapshot.get_repository(self.repository_name)
                .get(self.repository_name, {})
            )
        except Exception as e:  # noqa
            logger.exception("get repository(%s) cluster_id(%s) error", self.repository_name, self.cluster_id)

        return result


class EsSnapshotIndice(models.Model):
    table_id = models.CharField("结果表id", max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    snapshot_name = models.CharField("快照名称", max_length=150)

    cluster_id = models.IntegerField("集群id")
    repository_name = models.CharField("所在仓库名称", max_length=128)
    index_name = models.CharField("物理索引名称", max_length=150)
    doc_count = models.BigIntegerField("文档数量")
    store_size = models.BigIntegerField("索引大小")

    start_time = models.DateTimeField("索引开始时间")
    end_time = models.DateTimeField("索引结束时间")

    class Meta:
        verbose_name = "快照物理索引记录"
        verbose_name_plural = "快照物理索引记录"

    @classmethod
    def batch_to_json(cls, bk_tenant_id: str, table_id: str, snapshot_name: str, repository_name: str | None = None):
        query = Q(table_id=table_id, snapshot_name=snapshot_name, bk_tenant_id=bk_tenant_id)
        if repository_name:
            query &= Q(repository_name=repository_name)
        batch_obj = cls.objects.filter(query)
        return [obj.to_json() for obj in batch_obj]

    @classmethod
    def all_doc_count_and_store_size(cls, bk_tenant_id: str, table_ids: list[str], repository_names: list[str]):
        query = Q(table_id__in=table_ids, bk_tenant_id=bk_tenant_id)
        if repository_names:
            query &= Q(repository_name__in=repository_names)

        agg_result = (
            cls.objects.filter(query)
            .values("table_id", "repository_name")
            .annotate(doc_count=Sum("doc_count"), store_size=Sum("store_size"), index_count=Count("table_id"))
        )
        agg_result = [
            {**item, "table_id_repository_name": (item["table_id"], item["repository_name"])}
            for item in agg_result
        ]
        return array_group(agg_result, "table_id_repository_name", True)

    def to_json(self):
        now = datetime.datetime.utcnow()
        return {
            "table_id": self.table_id,
            "cluster_id": self.cluster_id,
            "repository_name": self.repository_name,
            "snapshot_name": self.snapshot_name,
            "index_name": self.index_name,
            "start_time": self.start_time.timestamp(),
            "end_time": self.end_time.timestamp(),
            "doc_count": self.doc_count,
            "store_size": self.store_size,
            "is_stored": EsSnapshotRestore.is_restored_index(
                index=self.index_name, now=now, bk_tenant_id=self.bk_tenant_id
            ),
            "bk_tenant_id": self.bk_tenant_id,
        }


class EsSnapshotRestore(models.Model):
    RESTORE_INDEX_PREFIX = "restore_"
    # 回溯后的索引加原本集群容量不能超过集群容量的80%
    NOT_OVER_ES_CLUSTER_SIZE_PERCENT = 0.8

    restore_id = models.AutoField("仓库id", primary_key=True)
    table_id = models.CharField("结果表id", max_length=128)

    start_time = models.DateTimeField("开始时间")
    end_time = models.DateTimeField("结束时间")

    expired_time = models.DateTimeField("到期时间")
    expired_delete = models.BooleanField("是否到期删除", default=False)

    indices = models.TextField("索引文档列表")
    complete_doc_count = models.BigIntegerField("回溯已经回溯完成的文档数量", default=0)

    total_doc_count = models.BigIntegerField("回溯总的文档大小")
    total_store_size = models.BigIntegerField("回溯索引的存储大小")

    duration = models.IntegerField("回溯持续时间", default=-1)

    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    is_deleted = models.BooleanField("仓库表是否已经禁用", default=False)

    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    # 需根据所属仓库名称确定回溯属于哪个快照配置
    repository_name = models.CharField("所属仓库名称", blank=True, null=True, default="", max_length=128)

    class Meta:
        verbose_name = "ES回溯任务表"
        verbose_name_plural = "ES回溯任务表"

    @classmethod
    def build_restore_index_name(cls, index_name):
        return f"{cls.RESTORE_INDEX_PREFIX}{index_name}"

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_restore(
        cls,
        bk_tenant_id: str,
        table_id,
        start_time,
        end_time,
        expired_time,
        operator,
        is_sync: bool | None = False,
        repository_name: str | None = None,
    ):
        from metadata.models import ESStorage

        es_storage = ESStorage.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
        if not es_storage:
            raise ValueError(_("结果表不存在"))
        
        snapshot = EsSnapshot.validated_snapshot(
            table_id, bk_tenant_id, target_snapshot_repository_name=repository_name
        )
        if not snapshot:
            raise ValueError(_("结果表不存在快照配置"))

        # NOTE: 这里需要转换为 utc 时间，因为，过滤时，会进行时间的转换
        start_time_with_tz = biz2utc_str(start_time, _format="%Y-%m-%dT%H:%M:%SZ")
        end_time_with_tz = biz2utc_str(end_time, _format="%Y-%m-%dT%H:%M:%SZ")
        expired_time = biz2utc_str(expired_time)

        query = Q(
            start_time__lt=end_time_with_tz,
            end_time__gte=start_time_with_tz,
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            repository_name=snapshot.target_snapshot_repository_name
        )

        # 筛选与目标时间区间产生交集的物理索引
        snapshot_indices = EsSnapshotIndice.objects.filter(query)
        
        if not snapshot_indices.exists():
            raise ValueError(_("该时间区间内没有快照数据"))
        now = datetime.datetime.utcnow()
        indices = [snapshot_indice.index_name for snapshot_indice in snapshot_indices]
        total_doc_count = sum([snapshot_indice.doc_count for snapshot_indice in snapshot_indices])

        total_store_size = sum([snapshot_indice.store_size for snapshot_indice in snapshot_indices])
        cluster_total_size = get_cluster_disk_size(es_storage.es_client, kind="total")
        cluster_used_size = get_cluster_disk_size(es_storage.es_client, kind="used")
        if cluster_used_size + total_store_size > cluster_total_size * cls.NOT_OVER_ES_CLUSTER_SIZE_PERCENT:
            raise ValueError(
                _("回溯的索引大小加集群已经使用的容量已经超过了集群总容量的{}").format(
                    cls.NOT_OVER_ES_CLUSTER_SIZE_PERCENT
                )
            )

        restore = cls.objects.create(
            table_id=table_id,
            start_time=start_time,
            end_time=end_time,
            expired_time=expired_time,
            total_doc_count=total_doc_count,
            total_store_size=total_store_size,
            indices=",".join(indices),
            creator=operator,
            last_modify_user=operator,
            bk_tenant_id=bk_tenant_id,
            repository_name=snapshot.target_snapshot_repository_name,
        )

        # 需要过滤出已经回溯了的索引 来进行创建回溯
        snapshot_indices = [
            snapshot_indice
            for snapshot_indice in snapshot_indices
            if not cls.is_restored_index(
                index=snapshot_indice.index_name, now=now, restore_id=restore.restore_id, bk_tenant_id=bk_tenant_id
            )
        ]
        # 如果都已经回溯过了 就不再执行创建回溯操作，直接返回数据
        if not snapshot_indices:
            return {
                "restore_id": restore.restore_id,
                "total_store_size": restore.total_store_size,
                "total_doc_count": restore.total_doc_count,
            }
        # 异步任务执行创建操作 需要多次调用es请求
        indices_group_by_snapshot = array_group(
            [model_to_dict(snapshot_indice) for snapshot_indice in snapshot_indices], "snapshot_name"
        )
        from metadata.task.tasks import restore_result_table_snapshot

        # 根据参数进行同步或者异步操作的处理
        if is_sync:
            logger.info("restore id %s sync to create restore %s", restore.restore_id, indices_group_by_snapshot)
            # 通过ID方式指定，无需再次使用租户ID过滤
            restore_result_table_snapshot(indices_group_by_snapshot, restore.restore_id)
        else:
            logger.info("restore id %s async to create restore %s", restore.restore_id, indices_group_by_snapshot)
            on_commit(
                lambda: restore_result_table_snapshot.delay(indices_group_by_snapshot, restore.restore_id),
                using=config.DATABASE_CONNECTION_NAME,
            )
        return {
            "restore_id": restore.restore_id,
            "total_store_size": restore.total_store_size,
            "total_doc_count": restore.total_doc_count,
        }

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_restore(cls, bk_tenant_id: str, restore_id, expired_time, operator):
        try:
            restore = cls.objects.get(restore_id=restore_id, bk_tenant_id=bk_tenant_id)
        except cls.DoesNotExist:
            raise ValueError(_("结果表回溯不存在"))
        if restore.is_deleted:
            raise ValueError(_("回溯已经删除"))
        if restore.is_expired():
            raise ValueError(_("回溯已经过期"))

        restore.expired_time = biz2utc_str(expired_time)
        restore.last_modify_user = operator
        restore.save()

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_restore(cls, bk_tenant_id: str, restore_id, operator, is_sync: bool | None = False):
        try:
            restore = cls.objects.get(restore_id=restore_id, bk_tenant_id=bk_tenant_id)
        except cls.DoesNotExist:
            raise ValueError(_("回溯不存在"))
        if restore.is_deleted:
            raise ValueError(_("回溯已经删除"))

        from metadata.task.tasks import delete_restore_indices

        # 异步删除回溯索引
        if is_sync:
            logger.info("sync to delete restore, restore id: %s", restore.restore_id)
            delete_restore_indices(restore.restore_id)
        else:
            logger.info("async to delete restore, restore id: %s", restore.restore_id)
            delete_restore_indices.delay(restore.restore_id)

        restore.is_deleted = True
        restore.last_modify_user = operator
        restore.save()

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def retry_restore(
        cls,
        bk_tenant_id: str,
        restore_id,
        operator,
        indices: list = None,
        is_sync: bool | None = False,
        is_force: bool | None = False,
    ):
        try:
            restore = cls.objects.get(restore_id=restore_id, bk_tenant_id=bk_tenant_id)
        except cls.DoesNotExist:
            raise ValueError(_("回溯不存在"))
        if restore.is_deleted:
            raise ValueError(_("回溯已经删除"))
        if restore.is_expired():
            raise ValueError(_("回溯已经过期"))

        from metadata.models import ESStorage

        es_storage = ESStorage.objects.filter(table_id=restore.table_id, bk_tenant_id=restore.bk_tenant_id).first()
        if not es_storage:
            raise ValueError(_("结果表不存在"))

        snapshot = EsSnapshot.validated_snapshot(
            restore.table_id, restore.bk_tenant_id, target_snapshot_repository_name=restore.repository_name
        )
        if not snapshot:
            raise ValueError(_("结果表不存在快照配置"))

        restore_indices = restore.indices.split(",")
        indices = indices or []
        # 判断索引是否属于该回溯任务
        if not set(indices).issubset(set(restore_indices)):
            raise ValueError(_("索引不属于该回溯"))

        each_complete_doc_count = restore.get_each_complete_doc_count(filter_indices=indices)
        retry_snapshot_indices = []
        pre_delete_indices = []
        completed_indices = []
        incomplete_indices = []

        for restore_index, complete_info in each_complete_doc_count.items():
            snapshot_index = complete_info.get("snapshot_index")
            # 快照已不存在，无法重试
            if not snapshot_index:
                raise ValueError(_("部分索引的快照已不存在，无法重试"))

            is_restored = complete_info.get("is_restored")
            # 快照已经完成，无需重试
            if is_restored and snapshot_index.doc_count == complete_info.get("complete_doc_count"):
                completed_indices.append(model_to_dict(snapshot_index))
                continue
            # 已经回溯的，需先删除
            if is_restored:
                # 非强制模式，跳过重试回溯中的索引
                incomplete_indices.append(
                    {**model_to_dict(snapshot_index), "complete_doc_count": complete_info.get("complete_doc_count", 0)}
                )
                if not is_force:
                    continue
                pre_delete_indices.append(restore_index)
            retry_snapshot_indices.append(snapshot_index)

        retry_details = {
            "completed": completed_indices,
            "incomplete": incomplete_indices,
            "pre_delete": pre_delete_indices,
            "retry": [model_to_dict(snapshot_index) for snapshot_index in retry_snapshot_indices],
        }
        if not retry_snapshot_indices:
            return {
                "restore_id": restore.restore_id,
                "retry_store_size": 0,
                "retry_doc_count": 0,
                "retry_details": retry_details,
            }

        # 存在回溯中的索引
        if pre_delete_indices:
            es_client = get_client(bk_tenant_id=restore.bk_tenant_id, cluster_id=es_storage.storage_cluster_id)
            # es index 删除是通过url带参数 防止索引太多超过url长度限制 所以进行多批删除
            indices_chunks = utils.chunk_index_list(pre_delete_indices)
            for indices_chunk in indices_chunks:
                try:
                    # 静默跳过不存在的索引，因indices每次操作可能是不幂等的，含有实际已删除的索引时将一直异常
                    es_client.indices.delete(utils.to_csv(indices_chunk), ignore_unavailable=True)
                except Exception as e:
                    logger.error(
                        "retry restore -> [%s] delete indices [%s] failed -> %s",
                        restore.restore_id,
                        ",".join(indices_chunk),
                        e,
                    )
                    raise ValueError(_("回溯索引删除失败"))
                logger.info(
                    "retry restore -> [%s] has delete indices [%s]", restore.restore_id, ",".join(indices_chunk)
                )

        retry_store_size = sum([snapshot_index.store_size for snapshot_index in retry_snapshot_indices])
        cluster_total_size = get_cluster_disk_size(es_storage.es_client, kind="total")
        cluster_used_size = get_cluster_disk_size(es_storage.es_client, kind="used")
        if cluster_used_size + retry_store_size > cluster_total_size * cls.NOT_OVER_ES_CLUSTER_SIZE_PERCENT:
            raise ValueError(
                _("重试回溯的索引大小加集群已经使用的容量已经超过了集群总容量的{}").format(
                    cls.NOT_OVER_ES_CLUSTER_SIZE_PERCENT
                )
            )

        # 异步任务执行创建操作 需要多次调用es请求
        indices_group_by_snapshot = array_group(
            [model_to_dict(snapshot_index) for snapshot_index in retry_snapshot_indices], "snapshot_name"
        )
        from metadata.task.tasks import restore_result_table_snapshot

        # 根据参数进行同步或者异步操作的处理
        if is_sync:
            logger.info("restore id %s sync to retry restore %s", restore.restore_id, indices_group_by_snapshot)
            restore_result_table_snapshot(indices_group_by_snapshot, restore.restore_id)
        else:
            logger.info("restore id %s async to retry restore %s", restore.restore_id, indices_group_by_snapshot)
            on_commit(
                lambda: restore_result_table_snapshot.delay(indices_group_by_snapshot, restore.restore_id),
                using=config.DATABASE_CONNECTION_NAME,
            )

        restore.last_modify_user = operator
        restore.save()

        return {
            "restore_id": restore.restore_id,
            "retry_store_size": retry_store_size,
            "retry_doc_count": sum([snapshot_index.doc_count for snapshot_index in retry_snapshot_indices]),
            "retry_details": retry_details,
        }

    @classmethod
    def clean_expired_restore(cls):
        # 跟判断回溯是否过期保持一致
        now = timezone.now()
        expired_restores = (
            cls.objects.exclude(expired_delete=True).exclude(is_deleted=True).filter(expired_time__lt=now)
        )

        for expired_restore in expired_restores:
            try:
                with atomic(config.DATABASE_CONNECTION_NAME):
                    expired_restore.expired_delete = True
                    expired_restore.save()
                    expired_restore.delete_restore_indices()
            except Exception as e:
                logger.error("clean expired restore -> [%s] failed -> [%s]", expired_restore.restore_id, e)
                continue

            logger.info("restore ->[%s] has expired, has be clean", expired_restore.restore_id)

    @classmethod
    def batch_get_state(cls, bk_tenant_id: str, restore_ids: list):
        restores = cls.objects.filter(restore_id__in=restore_ids, bk_tenant_id=bk_tenant_id)
        return [
            {
                "table_id": restore.table_id,
                "restore_id": restore.restore_id,
                "total_doc_count": restore.total_doc_count,
                "complete_doc_count": restore.get_complete_doc_count(),
                "duration": restore.duration,
                "bk_tenant_id": restore.bk_tenant_id,
            }
            for restore in restores
        ]

    @classmethod
    def batch_get_indices(cls, bk_tenant_id: str, restore_ids: list):
        # 过滤掉已删除和过期的回溯
        restores = cls.objects.filter(
            restore_id__in=restore_ids,
            is_deleted=False,
            expired_delete=False,
            bk_tenant_id=bk_tenant_id,
        )
        rt_restore_mappings = defaultdict(list)
        es_storage_query = Q()
        for _restore in restores:
            rt_restore_mappings[(_restore.table_id, _restore.bk_tenant_id)].append(_restore)
            es_storage_query |= Q(table_id=_restore.table_id, bk_tenant_id=_restore.bk_tenant_id)

        from metadata.models import ESStorage

        es_storages = ESStorage.objects.filter(es_storage_query)
        storage_rt_mappings = defaultdict(list)
        for _storage in es_storages:
            storage_rt_mappings[(_storage.storage_cluster_id, _storage.bk_tenant_id)].extend(
                rt_restore_mappings.get((_storage.table_id, _storage.bk_tenant_id), [])
            )

        data = []
        # 根据集群查询回溯索引
        for (storage_cluster_id, bk_tenant_id), restores in storage_rt_mappings.items():
            es_client = get_client(bk_tenant_id=bk_tenant_id, cluster_id=storage_cluster_id)
            if not restores:
                continue
            try:
                es_indices = es_client.cat.indices(f"{cls.RESTORE_INDEX_PREFIX}*", format="json")
            except Exception as e:
                logger.error("restore get complete doc count cat indices error as [%s]", e)
                raise ValueError(_("获取elasticsearch回溯索引失败"))
            for restore in restores:
                restore_indices = restore.get_each_complete_doc_count(cat_indices=es_indices)
                indices_details = []
                for restore_index, complete_info in restore_indices.items():
                    snapshot_index = complete_info.pop("snapshot_index", None)
                    indices_details.append(
                        {**complete_info, **(model_to_dict(snapshot_index) if snapshot_index else {})}
                    )
                data.append(
                    {
                        **model_to_dict(restore),
                        "indices_details": indices_details,
                    }
                )

        data.sort(key=lambda x: x["restore_id"], reverse=True)
        return data

    @classmethod
    def is_restored_index(cls, index, now, restore_id=None, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        判断索引是否已经被回溯
        """
        queryset = cls.objects.exclude(is_deleted=True).exclude(expired_delete=True)
        if restore_id:
            queryset = queryset.exclude(restore_id=restore_id)
        return queryset.filter(indices__icontains=index, expired_time__gt=now, bk_tenant_id=bk_tenant_id).exists()

    def create_es_restore(self, indices_group_by_snapshot):
        for snapshot, snapshot_indices in indices_group_by_snapshot.items():
            try:
                indices = [indice.get("index_name") for indice in snapshot_indices]
                repository_name = snapshot_indices[0]["repository_name"]
                cluster_id = EsSnapshotRepository.objects.get(
                    repository_name=repository_name, bk_tenant_id=self.bk_tenant_id
                ).cluster_id
                es_client = get_client(bk_tenant_id=self.bk_tenant_id, cluster_id=cluster_id)
                es_client.snapshot.restore(
                    repository_name,
                    snapshot,
                    {
                        "indices": ",".join(indices),
                        "include_global_state": False,
                        "index_settings": {
                            # 回溯的索引不需要有副本
                            "index.number_of_replicas": 0
                        },
                        "rename_pattern": "(.+)",
                        "rename_replacement": f"{self.RESTORE_INDEX_PREFIX}$1",
                    },
                )
                logger.info("table_id->[%s] create snapshot restore indices->[%s]", self.table_id, ",".join(indices))
            except Exception as e:
                logger.error("table_id -> [%s] create snapshot restore failed => %s", self.table_id, e)

    def delete_restore_indices(self):
        indices = self.indices.split(",")
        now = datetime.datetime.utcnow()
        indices = [
            indice
            for indice in indices
            if not self.is_restored_index(
                index=indice, now=now, restore_id=self.restore_id, bk_tenant_id=self.bk_tenant_id
            )
        ]

        from metadata.models import ESStorage

        es_storage = ESStorage.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
        es_client = get_client(bk_tenant_id=self.bk_tenant_id, cluster_id=es_storage.storage_cluster_id)

        # es index 删除是通过url带参数 防止索引太多超过url长度限制 所以进行多批删除
        indices_chunks = (
            utils.chunk_index_list([self.build_restore_index_name(indice) for indice in indices]) if indices else []
        )
        logger.info("restore -> [%s] need delete indices [%s]", self.restore_id, ",".join(indices))
        for indices_chunk in indices_chunks:
            try:
                # 静默跳过不存在的索引，因indices每次操作可能是不幂等的，含有实际已删除的索引时将一直异常
                es_client.indices.delete(utils.to_csv(indices_chunk), ignore_unavailable=True)
            except Exception as e:
                logger.error(
                    "restore -> [%s] delete indices [%s] failed -> %s", self.restore_id, ",".join(indices_chunk), e
                )
                raise ValueError(_("回溯索引删除失败"))
            logger.info("restore -> [%s] has delete indices [%s]", self.restore_id, ",".join(indices_chunk))

        logger.info("restore -> [%s] has clean complete maybe expired or delete", self.restore_id)

    def get_complete_doc_count(self):
        # avoid es count api return data inconsistency
        if self.complete_doc_count >= self.total_doc_count:
            return self.total_doc_count

        from metadata.models import ESStorage

        es_storage = ESStorage.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
        try:
            es_indices = es_storage.get_client().cat.indices(f"{self.RESTORE_INDEX_PREFIX}*", format="json")
        except Exception as e:
            logger.error("restore get complete doc count cat indices error as [%s]", e)
            return self.complete_doc_count

        indices = self.indices.split(",")
        complete_doc_count = 0
        for es_indice, indice in itertools.product(es_indices, indices):
            if es_indice["index"] == self.build_restore_index_name(indice):
                complete_doc_count = complete_doc_count + int(get_value_if_not_none(es_indice["docs.count"], 0))

        if self.total_doc_count <= complete_doc_count:
            self.duration = int((timezone.now() - self.create_time).total_seconds())
            logger.info("restore -> [%s] restore complete duration -> [%s]s", self.restore_id, self.duration)
        self.complete_doc_count = complete_doc_count
        self.save()
        return self.complete_doc_count

    def get_each_complete_doc_count(self, filter_indices: list = None, cat_indices: list = None):
        """获取每个回溯索引的完成量"""
        indices = filter_indices or self.indices.split(",")
        snapshot_indices = EsSnapshotIndice.objects.filter(
            start_time__lte=self.end_time,
            end_time__gte=self.start_time,
            table_id=self.table_id,
            index_name__in=indices,
            bk_tenant_id=self.bk_tenant_id,
            repository_name=self.repository_name,
        )

        is_completed = self.complete_doc_count >= self.total_doc_count

        restore_indices_mapping = {
            self.build_restore_index_name(snapshot_index.index_name): {
                "index_name": snapshot_index.index_name,
                "snapshot_index": snapshot_index,
                "is_restored": True if is_completed else False,
                "complete_doc_count": snapshot_index.doc_count if is_completed else 0,
            }
            for snapshot_index in snapshot_indices
        }

        if is_completed:
            return restore_indices_mapping

        # 如果未查询索引，需查询索引
        if not cat_indices:
            from metadata.models import ESStorage

            es_storage = ESStorage.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
            try:
                cat_indices = es_storage.get_client().cat.indices(f"{self.RESTORE_INDEX_PREFIX}*", format="json")
            except Exception as e:
                logger.error("restore get complete doc count cat indices error as [%s]", e)
                raise ValueError(_("获取elasticsearch回溯索引失败"))

        for es_index in cat_indices:
            if es_index["index"] in restore_indices_mapping:
                restore_indices_mapping[es_index["index"]].update(
                    {
                        "is_restored": True,
                        "complete_doc_count": int(get_value_if_not_none(es_index["docs.count"], 0)),
                    }
                )
        return restore_indices_mapping

    def is_expired(self) -> bool:
        return timezone.now() > self.expired_time

    def to_json(self):
        return {
            "restore_id": self.restore_id,
            "table_id": self.table_id,
            "is_expired": self.is_expired(),
            "start_time": self.start_time.timestamp(),
            "end_time": self.end_time.timestamp(),
            "expired_time": self.expired_time.timestamp(),
            "indices": self.indices,
            "complete_doc_count": self.complete_doc_count,
            "total_doc_count": self.total_doc_count,
            "total_store_size": self.total_store_size,
            "creator": self.creator,
            "create_time": self.create_time.timestamp(),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.timestamp(),
            "bk_tenant_id": self.bk_tenant_id,
        }
