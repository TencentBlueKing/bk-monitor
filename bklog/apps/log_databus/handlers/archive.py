"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from django.db.transaction import atomic
from django.forms import model_to_dict
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.api import TransferApi
from apps.log_databus.constants import (
    RESTORE_INDEX_SET_PREFIX,
    ArchiveExpireTime,
    ArchiveInstanceType,
)
from apps.log_databus.exceptions import (
    ArchiveIndexSetInfoNotFound,
    ArchiveIndexSetStatusError,
    ArchiveNotFound,
    CollectorActiveException,
    CollectorConfigNotExistException,
    RestoreExpired,
    RestoreNotFound,
)
from apps.log_databus.models import ArchiveConfig, CollectorConfig, RestoreConfig
from apps.log_search.constants import (
    DEFAULT_TIME_FIELD,
    InnerTag,
    TimeFieldTypeEnum,
    TimeFieldUnitEnum,
)
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import LogIndexSetData, Scenario
from apps.utils.db import array_group, array_hash
from apps.utils.function import ignored
from apps.utils.local import get_local_param, get_request_username
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import (
    format_user_time_zone,
    format_user_time_zone_humanize,
)
from bkm_space.utils import bk_biz_id_to_space_uid


class ArchiveHandler:
    def __init__(self, archive_config_id=None):
        self.archive = None
        if archive_config_id is not None:
            try:
                self.archive: ArchiveConfig = ArchiveConfig.objects.get(archive_config_id=archive_config_id)
            except ArchiveConfig.DoesNotExist:
                raise ArchiveNotFound

    @classmethod
    def to_user_time_format(cls, time):
        return format_user_time_zone(time, get_local_param("time_zone"))

    @classmethod
    def list(cls, archives):
        """
        list
        @param archives:
        @return:
        """
        archive_group = array_group(archives, "archive_config_id", True)
        archive_config_ids = list(archive_group.keys())
        archive_objs_all = ArchiveConfig.objects.filter(archive_config_id__in=archive_config_ids)
        table_ids = list()
        index_set_ids = list()
        for _obj in archive_objs_all:
            if _obj.instance_type != ArchiveInstanceType.INDEX_SET.value:
                table_ids.append(_obj.table_id)
            else:
                index_set_ids.append(_obj.instance_id)
        log_index_set_data_objs = LogIndexSetData.objects.filter(index_set_id__in=index_set_ids)
        index_set_table_ids = [_obj.result_table_id for _obj in log_index_set_data_objs]

        table_ids.extend(index_set_table_ids)
        archive_detail = array_group(TransferApi.list_result_table_snapshot({"table_ids": table_ids}), "table_id", True)
        index_set_table_id_mapping = dict()
        for _obj in log_index_set_data_objs:
            if _obj.index_set_id not in index_set_table_id_mapping:
                index_set_table_id_mapping[_obj.index_set_id] = list()
            index_set_table_id_mapping[_obj.index_set_id].append(_obj.result_table_id)
        for archive in archive_objs_all:
            if archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
                archive_group[archive.archive_config_id]["instance_name"] = archive.instance_name
                archive_group[archive.archive_config_id]["_index_set_id"] = archive.instance_id
                table_ids = index_set_table_id_mapping.get(archive.instance_id, [])
                if not table_ids:
                    for field in ["doc_count", "store_size", "index_count"]:
                        archive_group[archive.archive_config_id][field] = 0
                for table_id in table_ids:
                    for field in ["doc_count", "store_size", "index_count"]:
                        if field not in archive_group.get(archive.archive_config_id, {}):
                            archive_group[archive.archive_config_id][field] = 0
                        _num = int(archive_detail.get(table_id, {}).get(field, 0))
                        archive_group[archive.archive_config_id][field] += _num
            else:
                archive_group[archive.archive_config_id]["instance_name"] = archive.instance_name
                archive_group[archive.archive_config_id]["_collector_config_id"] = archive.collector_config_id
                for field in ["doc_count", "store_size", "index_count"]:
                    _num = int(archive_detail.get(archive.table_id, {}).get(field, 0))
                    archive_group[archive.archive_config_id][field] = _num
        return archives

    def retrieve(self, page, pagesize):
        """
        retrieve
        @param page:
        @param pagesize:
        @return:
        """
        if self.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
            table_ids = list(
                LogIndexSetData.objects.filter(index_set_id=self.archive.instance_id).values_list(
                    "result_table_id", flat=True
                )
            )
        else:
            table_ids = [self.archive.table_id]
        snapshot_info = TransferApi.list_result_table_snapshot_indices({"table_ids": table_ids})
        archive = model_to_dict(self.archive)
        indices = []
        for snapshot in snapshot_info:
            for _snapshot in snapshot:
                expired_time = (
                    ArchiveExpireTime.PERMANENT
                    if self.archive.snapshot_days == 0
                    else format_user_time_zone_humanize(_snapshot.get("expired_time"), get_local_param("time_zone"))
                )
                indices.extend(
                    [
                        {
                            **indice,
                            "start_time": self.to_user_time_format(indice.get("start_time")),
                            "end_time": self.to_user_time_format(indice.get("end_time")),
                            "expired_time": expired_time,
                            "state": _snapshot.get("state"),
                        }
                        for indice in _snapshot.get("indices", [])
                    ]
                )
        archive["indices"] = indices[page * pagesize : (page + 1) * pagesize]
        return archive

    @atomic
    def create_or_update(self, params):
        """
        create_or_update
        @param params:
        @return:
        """
        if self.archive:
            self.archive.snapshot_days = params.get("snapshot_days")
            self.archive.save()
            if self.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
                # 索引集归档需要查询当前索引集所关联的所有table_id
                index_set_data_objs = LogIndexSetData.objects.filter(index_set_id=self.archive.instance_id)
                if not index_set_data_objs:
                    raise ArchiveIndexSetInfoNotFound
                table_ids = list()
                for _obj in index_set_data_objs:
                    if _obj.apply_status != LogIndexSetData.Status.NORMAL:
                        raise ArchiveIndexSetStatusError
                    table_ids.append(_obj.result_table_id)

                multi_execute_func = MultiExecuteFunc()
                for table_id in table_ids:
                    multi_params = {"table_id": table_id, "snapshot_days": self.archive.snapshot_days}
                    multi_execute_func.append(
                        result_key=f"modify_result_table_snapshot_{table_id}",
                        func=TransferApi.modify_result_table_snapshot,
                        params=multi_params,
                    )

                multi_execute_func.run()

            else:
                meta_update_params = {"table_id": self.archive.table_id, "snapshot_days": self.archive.snapshot_days}
                TransferApi.modify_result_table_snapshot(meta_update_params)
            return model_to_dict(self.archive)
        # 只有采集项类型需要确认结果表状态
        if params["instance_type"] == ArchiveInstanceType.COLLECTOR_CONFIG.value:
            try:
                collector: CollectorConfig = CollectorConfig.objects.get(collector_config_id=params["instance_id"])
            except CollectorConfig.DoesNotExist:
                raise CollectorConfigNotExistException
            if not collector.is_active:
                raise CollectorActiveException

        if params["instance_type"] == ArchiveInstanceType.INDEX_SET.value:
            index_set_data_objs = LogIndexSetData.objects.filter(index_set_id=int(params["instance_id"]))
            if not index_set_data_objs:
                raise ArchiveIndexSetInfoNotFound
            table_ids = list()
            for _obj in index_set_data_objs:
                if _obj.apply_status != LogIndexSetData.Status.NORMAL:
                    raise ArchiveIndexSetStatusError
                table_ids.append(_obj.result_table_id)
            create_obj = ArchiveConfig.objects.create(**params)

            multi_execute_func = MultiExecuteFunc()
            for table_id in table_ids:
                multi_params = {
                    "table_id": table_id,
                    "target_snapshot_repository_name": create_obj.target_snapshot_repository_name,
                    "snapshot_days": create_obj.snapshot_days,
                }
                multi_execute_func.append(
                    result_key=f"create_result_table_snapshot_{table_id}",
                    func=TransferApi.create_result_table_snapshot,
                    params=multi_params,
                )

            multi_execute_func.run()
        else:
            create_obj = ArchiveConfig.objects.create(**params)
            meta_create_params = {
                "table_id": create_obj.table_id,
                "target_snapshot_repository_name": create_obj.target_snapshot_repository_name,
                "snapshot_days": create_obj.snapshot_days,
            }
            TransferApi.create_result_table_snapshot(meta_create_params)
        return model_to_dict(create_obj)

    @atomic
    def delete(self):
        self.archive.delete()
        if self.archive.instance_type != ArchiveInstanceType.INDEX_SET.value:
            TransferApi.delete_result_table_snapshot({"table_id": self.archive.table_id})
        else:
            table_ids = list(
                LogIndexSetData.objects.filter(index_set_id=self.archive.instance_id).values_list(
                    "result_table_id", flat=True
                )
            )
            multi_execute_func = MultiExecuteFunc()
            for table_id in table_ids:
                params = {"table_id": table_id}
                multi_execute_func.append(
                    result_key=f"delete_result_table_snapshot_{table_id}",
                    func=TransferApi.delete_result_table_snapshot,
                    params=params,
                )

            multi_execute_func.run()

    @atomic
    def restore(self, bk_biz_id, index_set_name, start_time, end_time, expired_time, notice_user):
        """
        restore
        @param bk_biz_id:
        @param index_set_name:
        @param start_time:
        @param end_time:
        @param expired_time:
        @param notice_user:
        @return:
        """
        index_set = self._create_index_set(index_set_name)
        result_errors = list()
        if self.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
            table_ids = list(
                LogIndexSetData.objects.filter(index_set_id=self.archive.instance_id).values_list(
                    "result_table_id", flat=True
                )
            )
            multi_execute_func = MultiExecuteFunc()
            for table_id in table_ids:
                params = {
                    "table_id": table_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "expired_time": expired_time,
                }
                multi_execute_func.append(
                    result_key=f"restore_{table_id}",
                    func=TransferApi.restore_result_table_snapshot,
                    params=params,
                )

            multi_result = multi_execute_func.run(return_exception=True)
            # 构建批量创建参数列表
            bulk_create_params = list()
            for table_id in table_ids:
                meta_restore_result = multi_result.get(f"restore_{table_id}", {})
                if isinstance(meta_restore_result, Exception):
                    result_errors.append({"table_id": table_id, "reason": str(meta_restore_result)})
                    continue
                params = {
                    "bk_biz_id": bk_biz_id,
                    "archive_config_id": self.archive.archive_config_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "expired_time": expired_time,
                    "index_set_name": index_set_name,
                    "notice_user": ",".join(notice_user),
                    "index_set_id": index_set.index_set_id,
                    "meta_restore_id": meta_restore_result.get("restore_id"),
                    "total_store_size": meta_restore_result.get("total_store_size"),
                    "total_doc_count": meta_restore_result.get("total_doc_count"),
                    "created_at": timezone.now(),
                    "created_by": get_request_username(),
                }
                bulk_create_params.append(RestoreConfig(**params))
            if bulk_create_params:
                RestoreConfig.objects.bulk_create(bulk_create_params)
                objs = RestoreConfig.objects.filter(
                    archive_config_id=self.archive.archive_config_id, index_set_name=index_set_name
                )
                restore_config_info = [model_to_dict(obj) for obj in objs]
            else:
                restore_config_info = list()
        else:
            create_restore_config = RestoreConfig.objects.create(
                **{
                    "bk_biz_id": bk_biz_id,
                    "archive_config_id": self.archive.archive_config_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "expired_time": expired_time,
                    "index_set_name": index_set_name,
                    "notice_user": ",".join(notice_user),
                }
            )

            meta_params = {
                "table_id": self.archive.table_id,
                "start_time": start_time,
                "end_time": end_time,
                "expired_time": expired_time,
            }
            meta_restore_result = TransferApi.restore_result_table_snapshot(meta_params)

            create_restore_config.index_set_id = index_set.index_set_id
            create_restore_config.meta_restore_id = meta_restore_result["restore_id"]
            create_restore_config.total_store_size = meta_restore_result["total_store_size"]
            create_restore_config.total_doc_count = meta_restore_result["total_doc_count"]
            create_restore_config.save()
            restore_config_info = [model_to_dict(create_restore_config)]

        res = {
            "index_set_id": index_set.index_set_id,
            "index_set_name": index_set.index_set_name,
            "restore_config_info": restore_config_info,
            "errors": result_errors,
        }

        return res

    def _create_index_set(self, index_set_name):
        index_set_name = _("[回溯]") + index_set_name
        if self.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
            table_ids = list(
                LogIndexSetData.objects.filter(index_set_id=self.archive.instance_id).values_list(
                    "result_table_id", flat=True
                )
            )
            indexes = [
                {
                    "bk_biz_id": self.archive.bk_biz_id,
                    "result_table_id": f"{RESTORE_INDEX_SET_PREFIX}*{table_id.replace('.', '_')}_*",
                    "result_table_name": self.archive.instance_name,
                    "time_field": DEFAULT_TIME_FIELD,
                }
                for table_id in table_ids
            ]
            # 索引集下所包含的物理索引一定存在一个集群 所以取第一个result_table_id去获取集群信息
            cluster_infos = TransferApi.get_result_table_storage(
                {"result_table_list": table_ids[0], "storage_type": "elasticsearch"}
            )
            cluster_info = cluster_infos.get(table_ids[0])
        else:
            indexes = [
                {
                    "bk_biz_id": self.archive.bk_biz_id,
                    "result_table_id": f"{RESTORE_INDEX_SET_PREFIX}*{self.archive.table_id.replace('.', '_')}_*",
                    "result_table_name": self.archive.instance_name,
                    "time_field": DEFAULT_TIME_FIELD,
                }
            ]

            cluster_infos = TransferApi.get_result_table_storage(
                {"result_table_list": self.archive.table_id, "storage_type": "elasticsearch"}
            )
            cluster_info = cluster_infos.get(self.archive.table_id)
        storage_cluster_id = cluster_info["cluster_config"]["cluster_id"]
        index_set = IndexSetHandler.create(
            index_set_name=index_set_name,
            space_uid=bk_biz_id_to_space_uid(self.archive.bk_biz_id),
            storage_cluster_id=storage_cluster_id,
            scenario_id=Scenario.ES,
            view_roles=[],
            indexes=indexes,
            category_id=self.archive.instance.category_id,
            collector_config_id=self.archive.collector_config_id,
            time_field=DEFAULT_TIME_FIELD,
            time_field_type=TimeFieldTypeEnum.DATE.value,
            time_field_unit=TimeFieldUnitEnum.MILLISECOND.value,
        )
        index_set.set_tag(index_set.index_set_id, InnerTag.RESTORING.value)
        return index_set

    @classmethod
    def list_archive(cls, bk_biz_id):
        """
        list_archive
        @param bk_biz_id:
        @return:
        """
        return [
            {
                "archive_config_id": archive.archive_config_id,
                "instance_name": archive.instance_name,
                "instance_id": archive.instance_id,
                "_collector_config_id": archive.collector_config_id,
            }
            for archive in ArchiveConfig.objects.filter(bk_biz_id=bk_biz_id)
        ]

    @classmethod
    def list_restore(cls, restore_list):
        """
        list_restore
        @param restore_list:
        @return:
        """
        ret = []
        instances = restore_list.serializer.instance
        for instance in instances:
            # archive config maybe delete so not show restore
            with ignored(ArchiveConfig.DoesNotExist):
                ret.append(
                    {
                        "restore_config_id": instance.restore_config_id,
                        "index_set_name": instance.index_set_name,
                        "index_set_id": instance.index_set_id,
                        "start_time": cls.to_user_time_format(instance.start_time),
                        "end_time": cls.to_user_time_format(instance.end_time),
                        "expired_time": cls.to_user_time_format(instance.expired_time),
                        "total_store_size": instance.total_store_size,
                        "instance_id": instance.archive.instance_id,
                        "instance_name": instance.archive.instance_name,
                        "instance_type": instance.archive.instance_type,
                        "_collector_config_id": instance.archive.collector_config_id,
                        "archive_config_id": instance.archive.archive_config_id,
                        "notice_user": instance.notice_user.split(","),
                        "is_expired": instance.is_expired(),
                    }
                )
        return ret

    @classmethod
    @atomic
    def update_restore(cls, restore_config_id, expired_time):
        """
        update_restore
        @param restore_config_id:
        @param expired_time:
        @return:
        """
        try:
            restore: RestoreConfig = RestoreConfig.objects.get(restore_config_id=restore_config_id)
        except RestoreConfig.DoesNotExist:
            raise RestoreNotFound
        if restore.is_expired():
            raise RestoreExpired

        # 归档任务是索引集的场景下 会存在多个归档回溯
        result_errors = list()
        if restore.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
            restore_objs = RestoreConfig.objects.filter(index_set_id=restore.index_set_id)
            restore_objs.update(expired_time=expired_time)
            meta_restore_ids = list(restore_objs.values_list("meta_restore_ids", flat=True))
            multi_execute_func = MultiExecuteFunc()
            for meta_restore_id in meta_restore_ids:
                params = {"restore_id": meta_restore_id, "expired_time": expired_time}
                multi_execute_func.append(
                    result_key=f"modify_restore_result_table_snapshot_{meta_restore_id}",
                    func=TransferApi.modify_restore_result_table_snapshot,
                    params=params,
                )
            multi_execute_result = multi_execute_func.run(return_exception=True)
            for meta_restore_id in meta_restore_ids:
                multi_result = multi_execute_result.get(f"modify_restore_result_table_snapshot_{meta_restore_id}", {})
                if isinstance(multi_result, Exception):
                    result_errors.append({"meta_restore_id": meta_restore_id, "reason": str(multi_result)})

            restore_config_info = [model_to_dict(obj) for obj in restore_objs]
        else:
            restore.expired_time = expired_time
            restore.save()
            TransferApi.modify_restore_result_table_snapshot(
                {"restore_id": restore.meta_restore_id, "expired_time": expired_time}
            )

            restore_config_info = [model_to_dict(restore)]

        return {"restore_config_info": restore_config_info, "errors": result_errors}

    @classmethod
    @atomic
    def delete_restore(cls, restore_config_id):
        """
        delete_restore
        @param restore_config_id:
        @return:
        """
        try:
            restore: RestoreConfig = RestoreConfig.objects.get(restore_config_id=restore_config_id)
        except RestoreConfig.DoesNotExist:
            raise RestoreNotFound
        index_set_handler = IndexSetHandler(restore.index_set_id)
        index_set_handler.stop()
        # 归档任务是索引集的场景下 会存在多个归档回溯
        if restore.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
            restore_objs = RestoreConfig.objects.filter(index_set_id=restore.index_set_id)
            meta_restore_ids = list(restore_objs.values_list("meta_restore_id", flat=True))
            restore_objs.delete()
            multi_execute_func = MultiExecuteFunc()
            for meta_restore_id in meta_restore_ids:
                params = {"restore_id": meta_restore_id}
                multi_execute_func.append(
                    result_key=f"delete_restore_result_table_snapshot_{meta_restore_id}",
                    func=TransferApi.delete_restore_result_table_snapshot,
                    params=params,
                )
            multi_execute_func.run()
        else:
            restore.delete()
            TransferApi.delete_restore_result_table_snapshot({"restore_id": restore.meta_restore_id})

    def archive_state(self):
        if self.archive.instance_type == ArchiveInstanceType.INDEX_SET.value:
            table_ids = list(
                LogIndexSetData.objects.filter(index_set_id=self.archive.instance_id).values_list(
                    "result_table_id", flat=True
                )
            )
        else:
            table_ids = [self.archive.table_id]
        return TransferApi.get_result_table_snapshot_state({"table_ids": table_ids})

    @staticmethod
    def batch_get_restore_state(restore_config_ids: list):
        """
        batch_get_restore_state
        @param restore_config_ids:
        @return:
        """
        restores = RestoreConfig.objects.filter(restore_config_id__in=restore_config_ids).values(
            "meta_restore_id", "restore_config_id"
        )
        meta_restore_ids = [restore["meta_restore_id"] for restore in restores]
        restore_hash = array_hash(restores, "meta_restore_id", "restore_config_id")
        meta_restore_states = TransferApi.get_restore_result_table_snapshot_state({"restore_ids": meta_restore_ids})
        for meta_restore_state in meta_restore_states:
            meta_restore_state["restore_config_id"] = restore_hash[meta_restore_state["restore_id"]]
        return meta_restore_states
