# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import itertools
import logging
from typing import Optional

from curator import utils
from django.db import models
from django.db.models import Count, Sum
from django.db.transaction import atomic, on_commit
from django.forms import model_to_dict
from django.utils import timezone
from django.utils.translation import ugettext as _

from bkmonitor.utils.time_tools import biz2utc_str
from metadata import config
from metadata.utils.db import array_group
from metadata.utils.es_tools import (
    get_client,
    get_cluster_disk_size,
    get_value_if_not_none,
)

logger = logging.getLogger("metadata")


class EsSnapshot(models.Model):
    """
    ES快照
    """

    ES_RUNNING_STATUS = "running"
    # 当停用后，不允许新增，也不允许过期删除
    ES_STOPPED_STATUS = "stopped"
    # 0 表示永久
    PERMANENT_PRESERVATION = 0

    table_id = models.CharField("结果表id", max_length=128, primary_key=True)
    # 快照所在的快照仓库
    target_snapshot_repository_name = models.CharField("快照仓库名称", max_length=128, default="")

    # 快照存储天数
    snapshot_days = models.IntegerField("快照天数", default=0)

    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    status = models.CharField("快照状态", blank=True, null=True, default="running", max_length=16)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_snapshot(cls, table_id, target_snapshot_repository_name, snapshot_days, operator):
        from metadata.models import ESStorage

        es_storage = ESStorage.objects.filter(table_id=table_id).first()
        if not es_storage:
            raise ValueError(_("结果表不存在"))

        if not EsSnapshotRepository.objects.filter(
            repository_name=target_snapshot_repository_name, cluster_id=es_storage.storage_cluster_id, is_deleted=False
        ).exists():
            raise ValueError(_("快照仓库不存在或已经被删除"))

        if cls.objects.filter(table_id=table_id).exists():
            raise ValueError(_("结果表快照存在"))

        return cls.objects.create(
            table_id=table_id,
            target_snapshot_repository_name=target_snapshot_repository_name,
            snapshot_days=snapshot_days,
            creator=operator,
            last_modify_user=operator,
            status=cls.ES_RUNNING_STATUS,
        )

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_snapshot(cls, table_id, snapshot_days, operator, status: Optional[str] = None):
        try:
            obj = cls.objects.get(table_id=table_id)
        except cls.DoesNotExist:
            return
        obj.snapshot_days = snapshot_days
        obj.last_modify_user = operator
        updated_fields = ["snapshot_days", "last_modify_user"]
        # 如果状态不为空，则进行状态的更新
        if status is not None:
            obj.status = status
            updated_fields.append("status")
        obj.save(update_fields=updated_fields)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_snapshot(cls, table_id, is_sync: Optional[bool] = False):
        """
        当快照产生当比较多当会产生很多的es调用 比较重 移到后台去执行实际的快照清理
        """
        from metadata.task.tasks import delete_es_result_table_snapshot

        try:
            snapshot = cls.objects.get(table_id=table_id)
        except cls.DoesNotExist:
            logger.exception("ES SnapShot does not exists, table_id(%s)", table_id)
            raise ValueError(_("快照仓库不存在或已经被删除"))

        if is_sync:
            logger.info("table_id %s sync to delete snapshot %s", table_id, snapshot.target_snapshot_repository_name)
            delete_es_result_table_snapshot(table_id, snapshot.target_snapshot_repository_name)
        else:
            logger.info("table_id %s async to delete snapshot %s", table_id, snapshot.target_snapshot_repository_name)
            delete_es_result_table_snapshot.delay(table_id, snapshot.target_snapshot_repository_name)
        snapshot.delete()

    @classmethod
    def batch_get_state(cls, table_ids: list):
        from metadata.models import ESStorage

        es_storages = ESStorage.objects.filter(table_id__in=table_ids)
        result = []

        for es_storage in es_storages:
            snapshots = []
            try:
                snapshots = es_storage.es_client.snapshot.get(
                    es_storage.snapshot_obj.target_snapshot_repository_name, es_storage.search_snapshot
                ).get("snapshots", [])
            except Exception as e:  # noqa
                logger.exception(
                    "batch get es snapshots error, target_snapshot_repository_name({}), search_snapshot({})".format(
                        es_storage.snapshot_obj.target_snapshot_repository_name, es_storage.search_snapshot
                    )
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

    def is_permanent(self):
        return self.snapshot_days == self.PERMANENT_PRESERVATION

    def to_self_json(self):
        return {
            "table_id": self.table_id,
            "snapshot_days": self.snapshot_days,
            "target_snapshot_repository_name": self.target_snapshot_repository_name,
            "creator": self.creator,
            "create_time": self.create_time.timestamp(),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.timestamp(),
        }

    def to_json(self):
        from metadata.models import ESStorage

        all_snapshots = []
        es_storage = ESStorage.objects.get(table_id=self.table_id)
        try:
            all_snapshots = es_storage.es_client.snapshot.get(
                self.target_snapshot_repository_name, es_storage.search_snapshot
            ).get("snapshots", [])
        except Exception as e:  # noqa
            logger.exception(
                "get es snapshots error, target_snapshot_repository_name({}), search_snapshot({})".format(
                    self.target_snapshot_repository_name, es_storage.search_snapshot
                )
            )

        return [
            {
                "snapshot_name": snapshot.get("snapshot"),
                "state": snapshot.get("state"),
                "table_id": self.table_id,
                "expired_time": es_storage.expired_date_timestamp(snapshot.get("snapshot")),
                "indices": EsSnapshotIndice.batch_to_json(self.table_id, snapshot.get("snapshot")),
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

    class Meta:
        verbose_name = "ES仓库记录表"
        verbose_name_plural = "ES仓库记录表"

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_repository(cls, cluster_id, snapshot_repository_name, es_config, alias, operator):
        from metadata.models import ClusterInfo

        cluster: ClusterInfo = ClusterInfo.objects.filter(cluster_id=cluster_id).first()
        if not cluster:
            raise ValueError(_("集群不存在"))
        if cluster.cluster_type != cluster.TYPE_ES:
            raise ValueError(_("集群不是es集群"))
        if cls.objects.filter(repository_name=snapshot_repository_name).exists():
            raise ValueError(_("仓库名称已经存在"))

        es_client = get_client(cluster)
        new_rep = cls.objects.create(
            cluster_id=cluster_id,
            repository_name=snapshot_repository_name,
            alias=alias,
            creator=operator,
            last_modify_user=operator,
        )
        try:
            es_client.snapshot.create_repository(snapshot_repository_name, es_config)
        except Exception as e:  # noqa
            logger.exception("create repository(%s) error, err=>(%s)", snapshot_repository_name, e)
            raise ValueError(_("创建集群仓库({})失败 err({})").format(snapshot_repository_name, e))
        return new_rep

    @classmethod
    def modify_repository(cls, cluster_id, snapshot_repository_name, alias, operator):
        cls.objects.filter(cluster_id=cluster_id, repository_name=snapshot_repository_name).update(
            alias=alias, last_modify_user=operator
        )

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_repository(cls, cluster_id, snapshot_repository_name, operator):
        if EsSnapshotIndice.objects.filter(cluster_id=cluster_id, repository_name=snapshot_repository_name).exists():
            raise ValueError(_("集群还存在快照无法删除"))
        cls.objects.filter(cluster_id=cluster_id, repository_name=snapshot_repository_name).update(
            is_deleted=True, last_modify_user=operator
        )
        get_client(cluster_id).snapshot.delete_repository(snapshot_repository_name)

    @classmethod
    def verify_repository(cls, cluster_id, snapshot_repository_name):
        if not cls.objects.filter(
            cluster_id=cluster_id, repository_name=snapshot_repository_name, is_deleted=False
        ).exists():
            raise ValueError(_("仓库不存在"))
        return get_client(cluster_id).snapshot.verify_repository(snapshot_repository_name)

    def to_json(self):
        result = {
            "repository_name": self.repository_name,
            "cluster_id": self.cluster_id,
            "alias": self.alias,
            "creator": self.creator,
            "create_time": self.create_time.timestamp(),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.timestamp(),
        }
        try:
            result.update(
                get_client(self.cluster_id).snapshot.get_repository(self.repository_name).get(self.repository_name, {})
            )
        except Exception as e:  # noqa
            logger.exception("get repository(%s) cluster_id(%s) error", self.repository_name, self.cluster_id)

        return result


class EsSnapshotIndice(models.Model):
    table_id = models.CharField("结果表id", max_length=128)
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
    def batch_to_json(cls, table_id, snapshot_name):
        batch_obj = cls.objects.filter(table_id=table_id, snapshot_name=snapshot_name)
        return [obj.to_json() for obj in batch_obj]

    @classmethod
    def all_doc_count_and_store_size(cls, table_ids):
        agg_result = (
            cls.objects.filter(table_id__in=table_ids)
            .values("table_id")
            .annotate(doc_count=Sum("doc_count"), store_size=Sum("store_size"), index_count=Count("table_id"))
        )
        return array_group(agg_result, "table_id", True)

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
            "is_stored": EsSnapshotRestore.is_restored_index(self.index_name, now),
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

    class Meta:
        verbose_name = "ES回溯任务表"
        verbose_name_plural = "ES回溯任务表"

    @classmethod
    def build_restore_index_name(cls, index_name):
        return f"{cls.RESTORE_INDEX_PREFIX}{index_name}"

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_restore(cls, table_id, start_time, end_time, expired_time, operator, is_sync: Optional[bool] = False):
        from metadata.models import ESStorage

        es_storage = ESStorage.objects.filter(table_id=table_id).first()
        if not es_storage:
            raise ValueError(_("结果表不存在"))
        if not es_storage.have_snapshot_conf:
            raise ValueError(_("结果表不存在快照配置"))

        # NOTE: 这里需要转换为 utc 时间，因为，过滤时，会进行时间的转换
        start_time_with_tz = biz2utc_str(start_time, _format="%Y-%m-%dT%H:%M:%SZ")
        end_time_with_tz = biz2utc_str(end_time, _format="%Y-%m-%dT%H:%M:%SZ")
        expired_time = biz2utc_str(expired_time)

        # 筛选与目标时间区间产生交集的物理索引
        snapshot_indices = EsSnapshotIndice.objects.filter(
            start_time__lt=end_time_with_tz, end_time__gte=start_time_with_tz, table_id=table_id
        )
        if not snapshot_indices.exists():
            raise ValueError(_("该时间区间内没有快照数据"))
        now = datetime.datetime.utcnow()
        indices = [snapshot_indice.index_name for snapshot_indice in snapshot_indices]
        total_doc_count = sum([snapshot_indice.doc_count for snapshot_indice in snapshot_indices])

        total_store_size = sum([snapshot_indice.store_size for snapshot_indice in snapshot_indices])
        cluster_total_size = get_cluster_disk_size(es_storage.es_client, kind="total")
        cluster_used_size = get_cluster_disk_size(es_storage.es_client, kind="used")
        if cluster_used_size + total_store_size > cluster_total_size * cls.NOT_OVER_ES_CLUSTER_SIZE_PERCENT:
            raise ValueError(_("回溯的索引大小加集群已经使用的容量已经超过了集群总容量的{}").format(cls.NOT_OVER_ES_CLUSTER_SIZE_PERCENT))

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
        )

        # 需要过滤出已经回溯了的索引 来进行创建回溯
        snapshot_indices = [
            snapshot_indice
            for snapshot_indice in snapshot_indices
            if not cls.is_restored_index(snapshot_indice.index_name, now, restore.restore_id)
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
            restore_result_table_snapshot(indices_group_by_snapshot, restore.restore_id)
        else:
            logger.info("restore id %s async to create restore %s", restore.restore_id, indices_group_by_snapshot)
            on_commit(lambda: restore_result_table_snapshot.delay(indices_group_by_snapshot, restore.restore_id))
        return {
            "restore_id": restore.restore_id,
            "total_store_size": restore.total_store_size,
            "total_doc_count": restore.total_doc_count,
        }

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_restore(cls, restore_id, expired_time, operator):
        try:
            restore = cls.objects.get(restore_id=restore_id)
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
    def delete_restore(cls, restore_id, operator, is_sync: Optional[bool] = False):
        try:
            restore = cls.objects.get(restore_id=restore_id)
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
    def clean_expired_restore(cls):
        now = datetime.datetime.utcnow()
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
    def batch_get_state(cls, restore_ids: list):
        restores = cls.objects.filter(restore_id__in=restore_ids)
        return [
            {
                "table_id": restore.table_id,
                "restore_id": restore.restore_id,
                "total_doc_count": restore.total_doc_count,
                "complete_doc_count": restore.get_complete_doc_count(),
                "duration": restore.duration,
            }
            for restore in restores
        ]

    @classmethod
    def is_restored_index(cls, index, now, restore_id=None):
        """
        判断索引是否已经被回溯
        """
        queryset = cls.objects.exclude(is_deleted=True).exclude(expired_delete=True)
        if restore_id:
            queryset = queryset.exclude(restore_id=restore_id)
        return queryset.filter(indices__icontains=index, expired_time__gt=now).exists()

    def create_es_restore(self, indices_group_by_snapshot):
        for snapshot, snapshot_indices in indices_group_by_snapshot.items():
            try:
                indices = [indice.get("index_name") for indice in snapshot_indices]
                repository_name = snapshot_indices[0]["repository_name"]
                cluster_id = EsSnapshotRepository.objects.get(repository_name=repository_name).cluster_id
                es_client = get_client(cluster_id)

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
        indices = [indice for indice in indices if not self.is_restored_index(indice, now, self.restore_id)]

        from metadata.models import ESStorage

        es_storage = ESStorage.objects.get(table_id=self.table_id)
        es_client = get_client(es_storage.storage_cluster_id)

        # es index 删除是通过url带参数 防止索引太多超过url长度限制 所以进行多批删除
        indices_chunks = utils.chunk_index_list([self.build_restore_index_name(indice) for indice in indices])
        logger.info("restore -> [%s] need delete indices [%s]", self.restore_id, ",".join(indices))
        for indices_chunk in indices_chunks:
            try:
                es_client.indices.delete(utils.to_csv(indices_chunk))
            except Exception as e:
                logger.error(
                    "restore -> [%s] delete indices [%s] failed -> %s", self.restore_id, ",".join(indices_chunk), e
                )
                continue
            logger.info("restore -> [%s] has delete indices [%s]", self.restore_id, ",".join(indices_chunk))

        logger.info("restore -> [%s] has clean complete maybe expired or delete", self.restore_id)

    def get_complete_doc_count(self):
        # avoid es count api return data inconsistency
        if self.complete_doc_count >= self.total_doc_count:
            return self.total_doc_count

        from metadata.models import ESStorage

        es_storage = ESStorage.objects.get(table_id=self.table_id)
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
        }
