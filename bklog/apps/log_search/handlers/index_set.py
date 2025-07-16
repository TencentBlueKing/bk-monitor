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

import json
import re
from collections import defaultdict

import arrow
import pytz
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.api import BkLogApi, TransferApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.feature_toggle.handlers.toggle import feature_switch
from apps.iam import Permission, ResourceEnum
from apps.log_databus.constants import STORAGE_CLUSTER_TYPE
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import CollectorConfig
from apps.log_desensitize.constants import (
    MODEL_TO_DICT_EXCLUDE_FIELD,
    DesensitizeRuleStateEnum,
)
from apps.log_desensitize.models import (
    DesensitizeConfig,
    DesensitizeFieldConfig,
    DesensitizeRule,
)
from apps.log_esquery.utils.es_route import EsRoute
from apps.log_search.constants import (
    BKDATA_INDEX_RE,
    COMMON_LOG_INDEX_RE,
    DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
    DEFAULT_TIME_FIELD,
    EsHealthStatus,
    GlobalCategoriesEnum,
    IndexSetType,
    InnerTag,
    SearchScopeEnum,
    TimeFieldTypeEnum,
    TimeFieldUnitEnum,
)
from apps.log_search.exceptions import (
    DesensitizeConfigCreateOrUpdateException,
    DesensitizeConfigDoseNotExistException,
    DesensitizeRuleException,
    IndexCrossClusterException,
    IndexListDataException,
    IndexSetDoseNotExistException,
    IndexSetFieldsConfigAlreadyExistException,
    IndexSetFieldsConfigNotExistException,
    IndexSetInnerTagOperatorException,
    IndexSetSourceException,
    IndexSetTagNameExistException,
    IndexSetTagNotExistException,
    IndexTraceNotAcceptException,
    ResultTableIdDuplicateException,
    ScenarioNotSupportedException,
    SearchUnKnowTimeField,
    UnauthorizedResultTableException,
    BaseSearchIndexSetException,
    DataIDNotExistException,
)
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.models import (
    IndexSetCustomConfig,
    IndexSetFieldsConfig,
    IndexSetTag,
    IndexSetUserFavorite,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    Space,
    StorageClusterRecord,
    UserIndexSetCustomConfig,
    UserIndexSetFieldsConfig,
    UserIndexSetSearchHistory,
)
from apps.log_search.tasks.mapping import sync_single_index_set_mapping_snapshot
from apps.log_search.tasks.sync_index_set_archive import sync_index_set_archive
from apps.log_search.utils import fetch_request_username
from apps.log_trace.handlers.proto.proto import Proto
from apps.models import model_to_dict
from apps.utils import APIModel
from apps.utils.bk_data_auth import BkDataAuthHandler
from apps.utils.db import array_hash
from apps.utils.local import (
    get_local_param,
    get_request_app_code,
    get_request_external_username,
    get_request_username,
)
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import space_uid_to_bk_biz_id


class IndexSetHandler(APIModel):
    def __init__(self, index_set_id=None):
        super().__init__()
        self.index_set_id = index_set_id

    @staticmethod
    def get_index_set_for_storage(storage_cluster_id):
        return LogIndexSet.objects.filter(storage_cluster_id=storage_cluster_id)

    def config(self, config_id: int, index_set_ids: list = None, index_set_type: str = IndexSetType.SINGLE.value):
        """修改用户当前索引集的配置"""
        username = get_request_username()
        params = {"username": username, "source_app_code": get_request_app_code(), "defaults": {"config_id": config_id}}
        if index_set_type == IndexSetType.UNION.value:
            index_set_ids_hash = UserIndexSetFieldsConfig.get_index_set_ids_hash(index_set_ids)
            params.update(
                {
                    "index_set_ids": index_set_ids,
                    "index_set_type": IndexSetType.UNION.value,
                    "index_set_ids_hash": index_set_ids_hash,
                }
            )
        else:
            params.update({"index_set_id": self.index_set_id})

        UserIndexSetFieldsConfig.objects.update_or_create(**params)

        if index_set_type == IndexSetType.UNION.value:
            return

        # add user_operation_record
        try:
            log_index_set_obj = LogIndexSet.objects.get(index_set_id=self.index_set_id)
            operation_record = {
                "username": username,
                "biz_id": 0,
                "space_uid": log_index_set_obj.space_uid,
                "record_type": UserOperationTypeEnum.SEARCH,
                "record_sub_type": log_index_set_obj.scenario_id,
                "record_object_id": self.index_set_id,
                "action": UserOperationActionEnum.CONFIG,
                "params": {
                    "index_set_id": self.index_set_id,
                },
            }
        except LogIndexSet.DoesNotExist:
            logger.exception(f"LogIndexSet --> {self.index_set_id} does not exist")
        else:
            user_operation_record.delay(operation_record)

    @classmethod
    def get_all_related_space_uids(cls, space_uid):
        """
        获取当前空间所关联的所有空间ID列表，包括自身
        """
        space_uids = [space_uid]
        space = SpaceApi.get_space_detail(space_uid=space_uid)
        if space and space.space_type_id == SpaceTypeEnum.BKCC.value:
            # 如果查询的是业务空间，则将其关联的其他类型空间的索引集也一并查询出来
            related_space_list = space.extend.get("resources") or []
            space_uids.extend(
                [
                    SpaceApi.gen_space_uid(
                        space_type=relate_space["resource_type"], space_id=relate_space["resource_id"]
                    )
                    for relate_space in related_space_list
                ]
            )
        return space_uids

    @classmethod
    def get_user_index_set(cls, space_uid, is_group=False, scenarios=None):
        space_uids = cls.get_all_related_space_uids(space_uid)
        index_sets = LogIndexSet.get_index_set(scenarios=scenarios, space_uids=space_uids)
        # 补充采集场景
        collector_config_ids = [
            index_set["collector_config_id"] for index_set in index_sets if index_set["collector_config_id"]
        ]
        collector_scenario_map = array_hash(
            data=CollectorConfig.objects.filter(collector_config_id__in=collector_config_ids).values(
                "collector_config_id", "collector_scenario_id"
            ),
            key="collector_config_id",
            value="collector_scenario_id",
        )
        for index_set in index_sets:
            index_set["collector_scenario_id"] = collector_scenario_map.get(index_set["collector_config_id"])
        # 不分组，直接返回
        if not is_group:
            return index_sets

        remove_ids = set()
        log_index_sets = []
        other_index_sets = []
        for index_set in index_sets:
            if not index_set["collector_config_id"] and index_set["scenario_id"] == Scenario.LOG:
                log_index_sets.append(index_set)
            else:
                other_index_sets.append(index_set)

        # 先构建一个字典，建立 result_table_id 到 other_index_sets 的映射关系
        rt_id_to_index_mapping = {}
        for index in other_index_sets:
            if index["collector_config_id"] and index["scenario_id"] == Scenario.LOG:
                rt_id = index["indices"][0]["result_table_id"]
                rt_id_to_index_mapping.setdefault(rt_id, []).append(index)

        for log_index_set in log_index_sets:
            result_table_id_list = [idx["result_table_id"] for idx in log_index_set["indices"]]
            for rt_id in result_table_id_list:
                if rt_id in rt_id_to_index_mapping:
                    for index in rt_id_to_index_mapping[rt_id]:
                        remove_ids.add(index["index_set_id"])
                        log_index_set.setdefault("children", []).append(index)

        index_sets = [index_set for index_set in index_sets if index_set["index_set_id"] not in remove_ids]
        return index_sets

    @classmethod
    def post_list(cls, index_sets):
        """
        补充存储集数据分类、数据源、集群名称字段、标签信息、es集群端口号 、es集群域名
        :param index_sets:
        :return:
        """

        # 获取集群列表，集群ID和集群名称的对应关系
        cluster_map = {}

        # 如果有启动日志采集接入，则获取集群列表信息
        if feature_switch("scenario_log") and settings.RUN_VER != "tencent":
            cluster_map = IndexSetHandler.get_cluster_map()
        scenario_choices = dict(Scenario.CHOICES)

        tag_ids_mapping = dict()
        tag_ids_all = set()

        multi_execute_func = MultiExecuteFunc()
        for _index in index_sets:
            # 标签处理
            if _index["tag_ids"]:
                tag_ids_mapping[int(_index["index_set_id"])] = _index["tag_ids"]
                tag_ids_all = tag_ids_all.union(set(_index["tag_ids"]))

            _index["category_name"] = GlobalCategoriesEnum.get_display(_index["category_id"])
            _index["scenario_name"] = scenario_choices.get(_index["scenario_id"])
            _index["storage_cluster_name"] = ",".join(
                {
                    storage_name
                    for storage_name in cluster_map.get(_index["storage_cluster_id"], {})
                    .get("cluster_name", "")
                    .split(",")
                }
            )

            normal_idx = [idx for idx in _index["indexes"] if idx["apply_status"] == LogIndexSetData.Status.NORMAL]

            if _index["scenario_id"] == Scenario.BKDATA:
                multi_execute_func.append(
                    _index["index_set_id"],
                    BkLogApi.cluster,
                    {
                        "scenario_id": Scenario.BKDATA,
                        "indices": ",".join([index.get("result_table_id") for index in _index.get("indexes", [])]),
                    },
                )

            if len(normal_idx) == len(_index["indexes"]):
                _index["apply_status"] = LogIndexSet.Status.NORMAL
                _index["apply_status_name"] = _("正常")
            else:
                _index["apply_status"] = LogIndexSet.Status.PENDING
                _index["apply_status_name"] = _("审批中")

            # 补充业务ID信息
            _index["bk_biz_id"] = space_uid_to_bk_biz_id(_index["space_uid"])

            if not _index["time_field"]:
                time_field = None
                if _index["indexes"]:
                    time_field = _index["indexes"][0].get("time_field")
                if _index["scenario_id"] in [Scenario.BKDATA, Scenario.LOG] and not time_field:
                    time_field = DEFAULT_TIME_FIELD
                _index["time_field_type"] = TimeFieldTypeEnum.DATE.value
                _index["time_field_unit"] = TimeFieldUnitEnum.MILLISECOND.value
                _index["time_field"] = time_field
        result = multi_execute_func.run()

        # 获取标签信息
        index_set_tag_objs = IndexSetTag.objects.filter(tag_id__in=tag_ids_all)
        index_set_tag_mapping = {
            obj.tag_id: {
                "name": InnerTag.get_choice_label(obj.name),
                "color": obj.color,
                "tag_id": obj.tag_id,
            }
            for obj in index_set_tag_objs
        }

        for _index in index_sets:
            if _index["scenario_id"] == Scenario.BKDATA:
                _index["storage_cluster_id"] = result.get(_index["index_set_id"], {}).get("storage_cluster_id")
                _index["storage_cluster_name"] = ",".join(
                    {
                        storage_name
                        for storage_name in result.get(_index["index_set_id"], {})
                        .get("storage_cluster_name", "")
                        .split(",")
                    }
                )
                # 补充集群的port和domain信息
                _index["storage_cluster_port"] = result.get(_index["index_set_id"], {}).get("storage_cluster_port", "")
                _index["storage_cluster_domain_name"] = result.get(_index["index_set_id"], {}).get(
                    "storage_cluster_domain_name", ""
                )
            else:
                storage_cluster_id = _index["storage_cluster_id"]
                _index["storage_cluster_port"] = cluster_map.get(storage_cluster_id, {}).get("cluster_port", "")
                _index["storage_cluster_domain_name"] = cluster_map.get(storage_cluster_id, {}).get(
                    "cluster_domain_name", ""
                )

            # 补充标签信息
            _index.pop("tag_ids")
            tag_ids = tag_ids_mapping.get(int(_index["index_set_id"]), [])
            if not tag_ids:
                _index["tags"] = list()
                continue

            _index["tags"] = [
                index_set_tag_mapping.get(int(tag_id)) for tag_id in tag_ids if index_set_tag_mapping.get(int(tag_id))
            ]

        return index_sets

    @staticmethod
    def get_cluster_map():
        """
        集群ID和集群名称映射、集群port、集群domain映射关系
        :return:
        """
        cluster_data = TransferApi.get_cluster_info()
        cluster_map = {}
        for cluster_obj in cluster_data:
            cluster_config = cluster_obj["cluster_config"]
            cluster_map.update(
                {
                    cluster_config["cluster_id"]: {
                        "cluster_name": cluster_config["cluster_name"],
                        "cluster_domain_name": cluster_config["domain_name"],
                        "cluster_port": cluster_config["port"],
                    }
                }
            )
        return cluster_map

    @classmethod
    @transaction.atomic()
    def create(
        cls,
        index_set_name,
        space_uid,
        scenario_id,
        view_roles,
        indexes,
        storage_cluster_id=None,
        category_id=None,
        collector_config_id=None,
        is_trace_log=False,
        time_field=None,
        time_field_type=None,
        time_field_unit=None,
        bk_app_code=None,
        username="",
        bcs_project_id="",
        is_editable=True,
        target_fields=None,
        sort_fields=None,
    ):
        # 创建索引
        index_set_handler = cls.get_index_set_handler(scenario_id)
        view_roles = []
        if not bk_app_code:
            bk_app_code = get_request_app_code()
        index_set = index_set_handler(
            index_set_name,
            space_uid,
            storage_cluster_id,
            view_roles,
            indexes=indexes,
            category_id=category_id,
            collector_config_id=collector_config_id,
            is_trace_log=is_trace_log,
            time_field=time_field,
            time_field_type=time_field_type,
            time_field_unit=time_field_unit,
            bk_app_code=bk_app_code,
            username=username,
            bcs_project_id=bcs_project_id,
            is_editable=is_editable,
            target_fields=target_fields,
            sort_fields=sort_fields,
        ).create_index_set()

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": 0,
            "space_uid": space_uid,
            "record_type": UserOperationTypeEnum.INDEX_SET,
            "record_sub_type": scenario_id,
            "record_object_id": index_set.index_set_id,
            "action": UserOperationActionEnum.CREATE,
            "params": {
                "index_set_name": index_set_name,
                "space_uid": space_uid,
                "storage_cluster_id": storage_cluster_id,
                "scenario_id": scenario_id,
                "view_roles": view_roles,
                "indexes": indexes,
                "category_id": category_id,
                "collector_config_id": collector_config_id,
                "is_trace_log": is_trace_log,
                "time_field": time_field,
                "time_field_type": time_field_type,
                "time_field_unit": time_field_unit,
                "bk_app_code": bk_app_code,
                "target_fields": target_fields,
                "sort_fields": sort_fields,
            },
        }
        user_operation_record.delay(operation_record)

        return index_set

    def update(
        self,
        index_set_name,
        view_roles,
        indexes,
        category_id=None,
        is_trace_log=False,
        storage_cluster_id=None,
        time_field=None,
        time_field_type=None,
        time_field_unit=None,
        bk_app_code=None,
        username="",
        target_fields=None,
        sort_fields=None,
    ):
        index_set_handler = self.get_index_set_handler(self.scenario_id)
        view_roles = []
        index_set = index_set_handler(
            index_set_name,
            self.data.space_uid,
            storage_cluster_id,
            view_roles,
            indexes=indexes,
            category_id=category_id,
            is_trace_log=is_trace_log,
            time_field=time_field,
            time_field_type=time_field_type,
            time_field_unit=time_field_unit,
            bk_app_code=bk_app_code,
            username=username,
            target_fields=target_fields,
            sort_fields=sort_fields,
        ).update_index_set(self.data)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "space_uid": self.data.space_uid,
            "record_type": UserOperationTypeEnum.INDEX_SET,
            "record_sub_type": self.data.scenario_id,
            "record_object_id": self.data.index_set_id,
            "action": UserOperationActionEnum.UPDATE,
            "params": {
                "index_set_name": index_set_name,
                "view_roles": view_roles,
                "indexes": indexes,
                "category_id": category_id,
                "is_trace_log": is_trace_log,
                "storage_cluster_id": storage_cluster_id,
                "time_field": time_field,
                "time_field_type": time_field_type,
                "time_field_unit": time_field_unit,
                "bk_app_code": bk_app_code,
                "target_fields": target_fields,
                "sort_fields": sort_fields,
            },
        }
        user_operation_record.delay(operation_record)

        return index_set

    def delete(self, index_set_name=None):
        if index_set_name:
            index_set = LogIndexSet.objects.get(index_set_id=self.index_set_id)
            index_set.index_set_name = index_set_name
            index_set.save()

        index_set_handler = self.get_index_set_handler(self.scenario_id)
        index_set_handler(
            self.data.index_set_name,
            self.data.space_uid,
            self.data.storage_cluster_id,
            self.data.view_roles,
            action="delete",
        ).delete_index_set(self.data)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "space_uid": self.data.space_uid,
            "record_type": UserOperationTypeEnum.INDEX_SET,
            "record_sub_type": self.data.scenario_id,
            "record_object_id": self.data.index_set_id,
            "action": UserOperationActionEnum.DESTROY,
            "params": "",
        }
        user_operation_record.delay(operation_record)

        return

    def stop(self):
        """
        暂停索引集
        """
        index_set = LogIndexSet.objects.get(index_set_id=self.index_set_id)
        index_set.is_active = False
        index_set.save()

    def start(self):
        """
        启动索引集
        """
        index_set = LogIndexSet.objects.get(index_set_id=self.index_set_id)
        index_set.is_active = True
        index_set.save()

    def add_index(
        self,
        bk_biz_id,
        time_filed,
        result_table_id,
        scenario_id,
        storage_cluster_id,
        result_table_name=None,
        time_field_type=None,
        time_field_unit=None,
    ):
        """
        添加索引到索引集内
        """
        # 判断索引集是否已加入此索引
        logger.info(f"[index_set_data][{self.index_set_id}]add_index => {result_table_id}")
        if LogIndexSetData.objects.filter(
            bk_biz_id=bk_biz_id or None, result_table_id=result_table_id, index_set_id=self.index_set_id
        ):
            raise ResultTableIdDuplicateException(
                ResultTableIdDuplicateException.MESSAGE.format(result_table_id=result_table_id)
            )

        # 创建索引集详情
        LogIndexSetDataHandler(
            self.data,
            bk_biz_id,
            time_filed,
            result_table_id,
            storage_cluster_id=storage_cluster_id,
            scenario_id=scenario_id,
            time_field_type=time_field_type,
            time_field_unit=time_field_unit,
            result_table_name=result_table_name,
            bk_username=get_request_username(),
        ).add_index()
        return True

    def delete_index(self, bk_biz_id, time_filed, result_table_id):
        """
        删除索引集
        """
        LogIndexSetDataHandler(
            self.data, bk_biz_id, time_filed, result_table_id, storage_cluster_id=self.storage_cluster_id
        ).delete_index()

    def bizs(self):
        if self.data.scenario_id in [Scenario.ES]:
            return []

        # 返回业务列表
        space_uids = (
            LogIndexSetData.objects.filter(index_set_id=self.index_set_id)
            .exclude(bk_biz_id=None)
            .values_list("space_uid", flat=True)
        )

        if not space_uids:
            return []

        return [
            {"bk_biz_id": space.bk_biz_id, "bk_biz_name": space.space_name}
            for space in Space.objects.filter(space_uid__in=space_uids)
        ]

    def indices(self):
        index_set_obj: LogIndexSet = self._get_data()
        index_set_data = index_set_obj.get_indexes(has_applied=True)
        scenario_id = index_set_obj.scenario_id
        storage_cluster_id = index_set_obj.storage_cluster_id
        index_list: list = [x.get("result_table_id") for x in index_set_data]
        if scenario_id == Scenario.ES:
            multi_execute_func = MultiExecuteFunc()
            for index in index_list:

                def get_indices(i):
                    return EsRoute(
                        scenario_id=scenario_id, storage_cluster_id=storage_cluster_id, indices=i
                    ).cat_indices()

                multi_execute_func.append(index, get_indices, index)
            result = multi_execute_func.run()
            return self._indices_result(result, index_list)
        ret = defaultdict(list)
        indices = EsRoute(
            scenario_id=scenario_id, storage_cluster_id=storage_cluster_id, indices=",".join(index_list)
        ).cat_indices(need_filter=False)
        indices = StorageHandler.sort_indices(indices)
        index_list.sort(key=lambda s: len(s), reverse=True)
        for index_es_info in indices:
            index_es_name: str = index_es_info.get("index")
            for index_name in index_list:
                if self._match_rt_for_index(index_es_name, index_name.replace(".", "_"), scenario_id):
                    ret[index_name].append(index_es_info)
                    break
        return self._indices_result(ret, index_list)

    @staticmethod
    def get_storage_usage_info(bk_biz_id, index_set_ids):
        """
        查询索引集存储的日用量和总用量
        """
        from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler

        multi_execute_func = MultiExecuteFunc(max_workers=10)
        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=index_set_ids)
        for index_set_obj in index_set_objs:
            try:
                index_set_id = index_set_obj.index_set_id
                multi_execute_func.append(
                    result_key=f"indices_info_{index_set_id}",
                    func=IndexSetHandler(index_set_id).indices,
                )

                # 获取24小时的日志条数
                current_time = arrow.now()
                params = {
                    "bk_biz_id": bk_biz_id,
                    "index_set_ids": [index_set_id],
                    "start_time": int(current_time.shift(days=-1).timestamp()),
                    "end_time": int(current_time.timestamp()),
                }
                multi_execute_func.append(
                    result_key=f"daily_count_{index_set_id}", func=UnifyQueryFieldHandler(params).get_total_count
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.exception("query storage usage info error, index_set_id->%s, reason: %s", index_set_id, e)

        indices_info_dict = {}
        daily_usage_dict = {}
        multi_result = multi_execute_func.run()
        for key, result in multi_result.items():
            field_name, _index_set_id = key.rsplit("_", maxsplit=1)
            if field_name == "indices_info":
                try:
                    # 总条数
                    total_count = sum(int(idx["stat"]["docs.count"]) for idx in result["list"])
                    # 总用量
                    total_usage = sum(int(idx["stat"]["store.size"]) for idx in result["list"])
                except ValueError:
                    total_count = total_usage = 0
                indices_info_dict.update({_index_set_id: {"total_count": total_count, "total_usage": total_usage}})
            else:
                daily_usage_dict.update({_index_set_id: result})
        result_data = []
        # 返回索引集,日用量和总用量
        for _index_set_id, item in indices_info_dict.items():
            total_count = item["total_count"]
            total_usage = item["total_usage"]
            daily_count = daily_usage_dict.get(_index_set_id, 0)
            # 计算日用量
            daily_usage = int(daily_count * (total_usage / total_count)) if total_count != 0 else 0
            result_data.append(
                {
                    "index_set_id": _index_set_id,
                    "daily_count": daily_count,
                    "total_count": total_count,
                    "daily_usage": daily_usage,
                    "total_usage": total_usage,
                }
            )
        return result_data

    def _match_rt_for_index(self, index_es_name: str, index_name: str, scenario_id: str) -> bool:
        index_re = re.compile(COMMON_LOG_INDEX_RE.format(index_name))
        if scenario_id == Scenario.BKDATA:
            index_re = re.compile(BKDATA_INDEX_RE.format(index_name))
        if index_re.match(index_es_name):
            return True
        return False

    def _indices_result(self, indices_for_index: dict, index_list: list):
        result = []
        for index in index_list:
            if index in indices_for_index:
                indices_info = indices_for_index[index]
                result.append(
                    {
                        "result_table_id": index,
                        "stat": {
                            "health": self._get_health(indices_info),
                            "pri": self._get_sum("pri", indices_info),
                            "rep": self._get_sum("rep", indices_info),
                            "docs.count": self._get_sum("docs.count", indices_info),
                            "docs.deleted": self._get_sum("docs.deleted", indices_info),
                            "store.size": self._get_sum("store.size", indices_info),
                            "pri.store.size": self._get_sum("store.size", indices_info),
                        },
                        "details": indices_info,
                    }
                )
                continue
            result.append(
                {
                    "result_table_id": index,
                    "stat": {
                        "health": "--",
                        "pri": "--",
                        "rep": "--",
                        "docs.count": "--",
                        "docs.deleted": "--",
                        "store.size": 0,
                        "pri.store.size": 0,
                    },
                    "details": "--",
                }
            )
        return {"total": len(index_list), "list": result}

    def mark_favorite(self):
        index_set_obj: LogIndexSet = self._get_data()
        index_set_obj.mark_favorite(fetch_request_username())

    def cancel_favorite(self):
        index_set_obj: LogIndexSet = self._get_data()
        index_set_obj.cancel_favorite(fetch_request_username())

    @transaction.atomic()
    def update_or_create_desensitize_config(self, params: dict):
        """
        创建或更新脱敏配置
        """

        try:
            obj, created = DesensitizeConfig.objects.update_or_create(
                index_set_id=self.index_set_id, defaults={"text_fields": params["text_fields"]}
            )

            # 兼容以脱敏配置直接入库
            # 创建&更新脱敏字段配置信息 先删除在创建
            if not created:
                DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_id, rule_id=0).delete()

            if not created:
                # 更新操作 查询出当前业务下和全局的脱敏规则 包含已删除的
                rule_objs = DesensitizeRule.origin_objects.filter(
                    Q(space_uid=self.data.space_uid) | Q(is_public=True)
                ).all()
            else:
                # 创建操作 查询出当前业务下和全局的脱敏规则 不包含已删除的
                rule_objs = DesensitizeRule.objects.filter(Q(space_uid=self.data.space_uid) | Q(is_public=True)).all()

            rules_mapping = {rule_obj.id: model_to_dict(rule_obj) for rule_obj in rule_objs}

            # 构建配置直接入库批量创建参数列表
            bulk_create_list = list()
            field_names = list()
            for field_config in params["field_configs"]:
                field_name = field_config.get("field_name")
                sort_index = 0
                rule_ids = list()
                if field_name not in field_names:
                    field_names.append(field_name)
                for rule in field_config.get("rules"):
                    rule_id = rule.get("rule_id")
                    rule_state = rule.get("state")
                    model_params = {
                        "operator": "",
                        "params": "",
                        "match_pattern": "",
                    }
                    if rule_id:
                        # 根据规则状态执行不同的操作
                        if rule_state in [DesensitizeRuleStateEnum.ADD.value, DesensitizeRuleStateEnum.UPDATE.value]:
                            if rule_id not in rules_mapping:
                                raise DesensitizeRuleException(
                                    DesensitizeRuleException.MESSAGE.format(field_name=field_name, rule_id=rule_id)
                                )
                            # 读最新的配置入库
                            rule_info = rules_mapping[rule_id]
                            model_params["operator"] = rule_info["operator"]
                            model_params["params"] = rule_info["params"]
                            model_params["match_pattern"] = rule_info["match_pattern"]
                            model_params["sort_index"] = sort_index
                            DesensitizeFieldConfig.objects.update_or_create(
                                index_set_id=self.index_set_id,
                                field_name=field_name,
                                rule_id=rule_id,
                                defaults=model_params,
                            )
                        elif rule_state == DesensitizeRuleStateEnum.DELETE.value:
                            continue
                        else:
                            # 只更新优先级
                            DesensitizeFieldConfig.objects.filter(
                                index_set_id=self.index_set_id, field_name=field_name, rule_id=rule_id
                            ).update(sort_index=sort_index)
                        rule_ids.append(rule_id)

                    else:
                        bulk_create_params = {
                            "index_set_id": self.index_set_id,
                            "field_name": field_name,
                            "rule_id": 0,
                            "match_pattern": rule.get("match_pattern"),
                            "operator": rule.get("operator"),
                            "params": rule.get("params"),
                            "sort_index": sort_index,
                        }
                        bulk_create_list.append(DesensitizeFieldConfig(**bulk_create_params))

                    sort_index += 1
                if rule_ids and not created:
                    # 处理删除的字段配置 删除字段绑定库里存在但是更新时不存在的规则ID
                    DesensitizeFieldConfig.objects.filter(
                        index_set_id=self.index_set_id, field_name=field_name
                    ).exclude(rule_id__in=rule_ids).delete()
            if field_names and not created:
                # 处理删除的字段配置 删除库里存在但是更新时不存在的字段配置
                DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_id).exclude(
                    field_name__in=field_names
                ).delete()
            if bulk_create_list:
                DesensitizeFieldConfig.objects.bulk_create(bulk_create_list)
        except Exception as e:
            raise DesensitizeConfigCreateOrUpdateException(DesensitizeConfigCreateOrUpdateException.MESSAGE.format(e=e))

        return params

    def desensitize_config_retrieve(self, raise_exception=True):
        """
        脱敏配置详情
        """
        try:
            desensitize_obj = DesensitizeConfig.objects.get(index_set_id=self.index_set_id)
            desensitize_field_config_objs = DesensitizeFieldConfig.objects.filter(
                index_set_id=self.index_set_id
            ).order_by("sort_index")
        except DesensitizeConfig.DoesNotExist:
            if raise_exception:
                raise DesensitizeConfigDoseNotExistException()
            else:
                return {}

        rule_ids = set(desensitize_field_config_objs.values_list("rule_id", flat=True))
        desensitize_rule_objs = DesensitizeRule.origin_objects.filter(id__in=rule_ids)
        desensitize_rule_info = {_obj.id: model_to_dict(_obj) for _obj in desensitize_rule_objs}

        # 构建返回数据
        ret = model_to_dict(desensitize_obj)
        ret["field_configs"] = list()

        # 构建字段绑定的 rules {"field_name": [{rule_id: 1}]}
        field_info_mapping = dict()
        for _obj in desensitize_field_config_objs:
            field_name = _obj.field_name
            if field_name not in field_info_mapping:
                field_info_mapping[field_name] = list()
            _rule = model_to_dict(_obj, exclude=MODEL_TO_DICT_EXCLUDE_FIELD)

            rule_id = _rule["rule_id"]
            if rule_id:
                # 添加规则变更标识
                if int(rule_id) in desensitize_rule_info:
                    _rule["rule_name"] = desensitize_rule_info[rule_id]["rule_name"]
                    _rule["match_fields"] = desensitize_rule_info[rule_id]["match_fields"]

                if int(rule_id) not in desensitize_rule_info or desensitize_rule_info[rule_id]["is_deleted"]:
                    state = DesensitizeRuleStateEnum.DELETE.value
                    new_rule = {}
                elif (
                    _rule["operator"] != desensitize_rule_info[rule_id]["operator"]
                    or _rule["match_pattern"] != desensitize_rule_info[rule_id]["match_pattern"]
                    or sorted(_rule["params"].items()) != sorted(desensitize_rule_info[rule_id]["params"].items())
                ):
                    state = DesensitizeRuleStateEnum.UPDATE.value
                    new_rule = {
                        "rule_name": desensitize_rule_info[rule_id]["rule_name"],
                        "operator": desensitize_rule_info[rule_id]["operator"],
                        "params": desensitize_rule_info[rule_id]["params"],
                        "match_pattern": desensitize_rule_info[rule_id]["match_pattern"],
                        "match_fields": desensitize_rule_info[rule_id]["match_fields"],
                    }
                else:
                    state = DesensitizeRuleStateEnum.NORMAL.value
                    new_rule = {}
            else:
                state = DesensitizeRuleStateEnum.NORMAL.value
                new_rule = {}

            _rule["state"] = state
            _rule["new_rule"] = new_rule

            field_info_mapping[field_name].append(_rule)

        for _field_name, _rules in field_info_mapping.items():
            ret["field_configs"].append(
                {
                    "field_name": _field_name,
                    "rules": sorted(_rules, key=lambda x: x["sort_index"]),
                }
            )

        return ret

    @transaction.atomic()
    def desensitize_config_delete(self):
        """
        脱敏配置删除
        """
        DesensitizeConfig.objects.filter(index_set_id=self.index_set_id).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_id).delete()

    def add_tag(self, tag_id: int):
        """
        索引集添加标签
        """
        # 校验标签是否存在
        if not IndexSetTag.objects.filter(tag_id=tag_id).exists():
            raise IndexSetTagNotExistException(IndexSetTagNotExistException.MESSAGE.format(tag_id=tag_id))

        # 校验是否为内置标签
        if tag_id in self._get_inner_tag_ids():
            raise IndexSetInnerTagOperatorException()

        index_set_obj = self._get_data()

        tag_ids = list(index_set_obj.tag_ids)

        if str(tag_id) not in tag_ids:
            tag_ids.append(str(tag_id))

            index_set_obj.tag_ids = tag_ids

            index_set_obj.save()

        return

    def delete_tag(self, tag_id: int):
        """
        索引集删除标签
        """
        # 校验是否为内置标签
        if tag_id in self._get_inner_tag_ids():
            raise IndexSetInnerTagOperatorException()

        index_set_obj = self._get_data()

        tag_ids = list(index_set_obj.tag_ids)

        if tag_ids and str(tag_id) in tag_ids:
            tag_ids.remove(str(tag_id))
            index_set_obj.tag_ids = tag_ids
            index_set_obj.save()

        return

    @staticmethod
    def create_tag(params: dict):
        """
        创建标签
        """
        # 名称校验
        if (
            params["name"] in list(InnerTag.get_dict_choices().values())
            or IndexSetTag.objects.filter(name=params["name"]).exists()
        ):
            raise IndexSetTagNameExistException(IndexSetTagNameExistException.MESSAGE.format(name=params["name"]))

        obj = IndexSetTag.objects.create(name=params["name"], color=params["color"])

        return model_to_dict(obj)

    @staticmethod
    def tag_list():
        """
        标签列表
        """
        objs = IndexSetTag.objects.all()

        ret = list()

        inner_tag_names = list(InnerTag.get_dict_choices().keys())
        for obj in objs:
            _data = model_to_dict(obj)
            if _data["name"] in inner_tag_names:
                _data["is_built_in"] = True
            else:
                _data["is_built_in"] = False
            _data["name"] = InnerTag.get_choice_label(obj.name)
            ret.append(_data)

        return ret

    @staticmethod
    def _get_inner_tag_ids():
        """
        获取内置标签ID列表
        """
        inner_tag_names = list(InnerTag.get_dict_choices().keys())
        inner_tag_ids = list(IndexSetTag.objects.filter(name__in=inner_tag_names).values_list("tag_id", flat=True))
        return inner_tag_ids

    @staticmethod
    def get_desensitize_config_state(index_set_ids: list):
        """
        获取索引集脱敏状态
        """
        if not index_set_ids:
            return {}
        index_set_exist_ids = set(
            DesensitizeFieldConfig.objects.filter(index_set_id__in=index_set_ids).values_list("index_set_id", flat=True)
        )

        ret = dict()

        for _index_set_id in set(index_set_ids):
            if _index_set_id in index_set_exist_ids:
                ret[_index_set_id] = {"is_desensitize": True}
            else:
                ret[_index_set_id] = {"is_desensitize": False}

        return ret

    @staticmethod
    def _get_health(src: list):
        has_red_health_list = [item.get("health", "") == EsHealthStatus.RED.value for item in src]
        has_yellow_health_list = [item.get("health", "") == EsHealthStatus.YELLOW.value for item in src]
        if any(has_red_health_list):
            return EsHealthStatus.RED.value
        if any(has_yellow_health_list):
            return EsHealthStatus.YELLOW.value
        return EsHealthStatus.GREEN.value

    @staticmethod
    def _get_sum(key: str, src: list) -> int:
        return sum([int(item.get(key, 0)) for item in src])

    def _get_data(self):
        try:
            obj = LogIndexSet.objects.get(index_set_id=self.index_set_id)
        except LogIndexSet.DoesNotExist:
            raise IndexSetDoseNotExistException()
        return obj

    @property
    def scenario_id(self):
        return self.data.scenario_id

    @property
    def storage_cluster_id(self):
        return self.data.storage_cluster_id

    @property
    def source_object(self):
        if not self.storage_cluster_id:
            return None
        cluster_info = StorageHandler(cluster_id=self.storage_cluster_id).get_cluster_info_by_id()
        return {
            "scenario_id": self.scenario_id,
            "domain_name": cluster_info.get("cluster_config").get("domain_name"),
            "cluster_id": cluster_info.get("cluster_config").get("cluster_id"),
            "cluster_name": cluster_info.get("cluster_config").get("cluster_name"),
            "port": cluster_info.get("cluster_config").get("port"),
            "username": cluster_info.get("auth_info").get("username"),
            "password": cluster_info.get("auth_info").get("password"),
        }

    @classmethod
    def get_index_set_handler(cls, scenario_id):
        try:
            return {
                Scenario.BKDATA: BkDataIndexSetHandler,
                Scenario.ES: EsIndexSetHandler,
                Scenario.LOG: LogIndexSetHandler,
            }[scenario_id]
        except KeyError:
            raise ScenarioNotSupportedException(ScenarioNotSupportedException.MESSAGE.format(scenario_id=scenario_id))

    @classmethod
    def get_storage_by_table_list(cls, indexes):
        """
        采集接入场景：通过所选的索引列表校验集群是否一致，且返回集群信息
        :param indexes:
        :return:
        """
        table_list = []
        for _index in indexes:
            if not _index.get("result_table_id"):
                raise IndexCrossClusterException()
            table_list.append(_index.get("result_table_id"))
        if not table_list:
            raise IndexListDataException()

        # 调用接口查询结果表集群信息
        table_str = ",".join(table_list)
        storage_info = TransferApi.get_result_table_storage(
            {"result_table_list": table_str, "storage_type": STORAGE_CLUSTER_TYPE}
        )

        # 校验所有结果表查询出的集群是否一致
        cluster_id = ""
        for _table in table_list:
            table_cluster_id = storage_info.get(_table, {}).get("cluster_config", {}).get("cluster_id")
            if not cluster_id:
                cluster_id = table_cluster_id
            if not table_cluster_id or table_cluster_id != cluster_id:
                cluster_id = None

        return cluster_id

    @classmethod
    def replace(
        cls,
        index_set_name,
        scenario_id,
        view_roles,
        indexes,
        bk_app_code,
        space_uid=None,
        storage_cluster_id=None,
        category_id=None,
        collector_config_id=None,
        is_trace_log=False,
        time_field=None,
        time_field_type=None,
        time_field_unit=None,
        target_fields=None,
        sort_fields=None,
    ):
        # 检查索引集是否存在
        index_set_obj = LogIndexSet.objects.filter(index_set_name=index_set_name).first()
        if index_set_obj and index_set_obj.source_app_code != bk_app_code:
            raise IndexSetSourceException()

        index_set_handler = cls.get_index_set_handler(scenario_id)
        view_roles = []

        # 更新索引集
        if index_set_obj:
            index_set = index_set_handler(
                index_set_name,
                space_uid,
                storage_cluster_id,
                view_roles,
                indexes=indexes,
                category_id=category_id,
                is_trace_log=is_trace_log,
                time_field=time_field,
                time_field_type=time_field_type,
                time_field_unit=time_field_unit,
                bk_app_code=bk_app_code,
                target_fields=target_fields,
                sort_fields=sort_fields,
            ).update_index_set(index_set_obj)

            # add user_operation_record
            operation_record = {
                "username": get_request_username(),
                "space_uid": space_uid,
                "record_type": UserOperationTypeEnum.INDEX_SET,
                "record_sub_type": scenario_id,
                "record_object_id": index_set_obj.index_set_id,
                "action": UserOperationActionEnum.REPLACE_UPDATE,
                "params": {
                    "index_set_name": index_set_name,
                    "space_uid": space_uid,
                    "view_roles": view_roles,
                    "indexes": indexes,
                    "category_id": category_id,
                    "is_trace_log": is_trace_log,
                    "storage_cluster_id": storage_cluster_id,
                    "time_field": time_field,
                    "time_field_type": time_field_type,
                    "time_field_unit": time_field_unit,
                    "bk_app_code": bk_app_code,
                    "scenario_id": scenario_id,
                    "target_fields": target_fields,
                    "sort_fields": sort_fields,
                },
            }
            user_operation_record.delay(operation_record)

            return index_set

        # 创建索引集
        if scenario_id == Scenario.BKDATA:
            storage_cluster_id = None
        elif scenario_id == Scenario.ES:
            pass
        else:
            storage_cluster_id = cls.get_storage_by_table_list(indexes)
        index_set = index_set_handler(
            index_set_name,
            space_uid,
            storage_cluster_id,
            view_roles,
            indexes,
            category_id,
            collector_config_id,
            is_trace_log=is_trace_log,
            time_field=time_field,
            time_field_type=time_field_type,
            time_field_unit=time_field_unit,
            bk_app_code=bk_app_code,
        ).create_index_set()

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "space_uid": space_uid,
            "record_type": UserOperationTypeEnum.INDEX_SET,
            "record_sub_type": scenario_id,
            "record_object_id": index_set.index_set_id,
            "action": UserOperationActionEnum.REPLACE_CREATE,
            "params": {
                "index_set_name": index_set_name,
                "space_uid": space_uid,
                "view_roles": view_roles,
                "indexes": indexes,
                "category_id": category_id,
                "collector_config_id": collector_config_id,
                "is_trace_log": is_trace_log,
                "storage_cluster_id": storage_cluster_id,
                "time_field": time_field,
                "time_field_type": time_field_type,
                "time_field_unit": time_field_unit,
                "bk_app_code": bk_app_code,
                "scenario_id": scenario_id,
            },
        }
        user_operation_record.delay(operation_record)

        return index_set

    @staticmethod
    def fetch_user_search_index_set(params):
        """
        根据创建者、空间唯一标识、时间范围、限制条数获取某用户最近查询的索引集
        """
        username = params["username"]
        space_uid = params.get("space_uid")
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        limit = params["limit"]
        if not start_time:
            history_obj = UserIndexSetSearchHistory.objects.filter(
                is_deleted=False, search_type="default", created_by=username
            ).order_by("-created_at")
        else:
            tz_info = pytz.timezone(get_local_param("time_zone", settings.TIME_ZONE))
            start_time = arrow.get(start_time).to(tz=tz_info).datetime
            end_time = arrow.get(end_time).to(tz=tz_info).datetime
            history_obj = UserIndexSetSearchHistory.objects.filter(
                is_deleted=False, search_type="default", created_at__range=[start_time, end_time], created_by=username
            ).order_by("-created_at")
        history_data = list(history_obj.values("index_set_id", "created_at", "params", "duration"))
        index_set_ids = list(history_obj.values_list("index_set_id", flat=True))
        detail_data = list(
            LogIndexSet.objects.filter(index_set_id__in=index_set_ids, is_active=True).values(
                "index_set_id", "index_set_name", "space_uid"
            )
        )
        return_data = []
        for history in history_data:
            for detail in detail_data:
                if detail["index_set_id"] == history["index_set_id"]:
                    if space_uid and space_uid != detail["space_uid"]:
                        continue
                    search_data = {
                        "index_set_id": history["index_set_id"],
                        "created_at": history["created_at"],
                        "params": history["params"],
                        "duration": history["duration"],
                        "index_set_name": detail["index_set_name"],
                        "space_uid": detail["space_uid"],
                    }
                    return_data.append(search_data)
        return_data = return_data[: int(limit)]
        return return_data

    @staticmethod
    def fetch_user_favorite_index_set(params):
        """
        根据创建者、空间唯一标识、限制条数获取某用户收藏的索引集
        """
        username = params["username"]
        space_uid = params.get("space_uid")
        limit = params.get("limit")
        index_set_ids = list(IndexSetUserFavorite.fetch_user_favorite_index_set(username=username))
        index_set_obj = LogIndexSet.objects.filter(index_set_id__in=index_set_ids, is_active=True)
        if space_uid:
            index_set_obj = index_set_obj.filter(space_uid=space_uid)
        index_set_data = list(index_set_obj.values("index_set_id", "index_set_name", "created_at", "space_uid"))
        if limit:
            index_set_data = index_set_data[: int(limit)]
        return index_set_data

    @staticmethod
    def get_space_info(index_set_id):
        """
        根据索引集ID获取空间信息
        """
        index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if not index_set_obj:
            raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))
        space = SpaceApi.get_space_detail(space_uid=index_set_obj.space_uid)

        return {
            "id": space.id,
            "space_type_id": space.space_type_id,
            "space_id": space.space_id,
            "space_name": space.space_name,
            "space_uid": space.space_uid,
            "space_code": space.space_code,
            "bk_biz_id": space.bk_biz_id,
            "time_zone": space.extend.get("time_zone") or "Asia/Shanghai",
            "bk_tenant_id": space.bk_tenant_id,
        }

    @classmethod
    def query_by_bk_data_id(cls, bk_data_id):
        collector_config = CollectorConfig.objects.filter(bk_data_id=bk_data_id).first()
        if not collector_config:
            raise DataIDNotExistException(DataIDNotExistException.MESSAGE.format(bk_data_id=bk_data_id))
        index_set_obj = LogIndexSet.objects.filter(index_set_id=collector_config.index_set_id).first()
        if not index_set_obj:
            raise BaseSearchIndexSetException(
                BaseSearchIndexSetException.MESSAGE.format(index_set_id=collector_config.index_set_id)
            )
        return {
            "index_set_id": index_set_obj.index_set_id,
            "index_set_name": index_set_obj.index_set_name,
            "space_uid": index_set_obj.space_uid,
            "collector_config_id": collector_config.collector_config_id,
            "collector_config_name": collector_config.collector_config_name,
        }


class BaseIndexSetHandler:
    scenario_id = None

    def __init__(
        self,
        index_set_name,
        space_uid,
        storage_cluster_id,
        view_roles,
        indexes=None,
        category_id=None,
        collector_config_id=None,
        is_trace_log=None,
        time_field=None,
        time_field_type=None,
        time_field_unit=None,
        action=None,
        bk_app_code=None,
        username="",
        bcs_project_id=0,
        is_editable=True,
        target_fields=None,
        sort_fields=None,
    ):
        super().__init__()

        self.index_set_name = index_set_name
        self.space_uid = space_uid
        self.storage_cluster_id = storage_cluster_id
        self.view_roles = view_roles

        self.is_trace_log = is_trace_log

        if not indexes:
            indexes = []
        self.indexes = indexes
        self.bkdata_project_id = None
        self.index_set_obj = None
        self.collector_config_id = collector_config_id
        self.category_id = category_id
        self.bk_app_code = bk_app_code
        self.username = username
        self.bcs_project_id = bcs_project_id
        self.is_editable = is_editable

        # time_field
        self.time_field, self.time_field_type, self.time_field_unit = self.init_time_field(
            self.scenario_id,
            time_field,
            time_field_type,
            time_field_unit,
            action,
        )

        # 上下文、实时日志定位字段 排序字段
        self.target_fields = target_fields if target_fields else []
        self.sort_fields = sort_fields if sort_fields else []
        self.target_fields_raw = target_fields
        self.sort_fields_raw = sort_fields

    @staticmethod
    def init_time_field(scenario_id, time_field, time_field_type, time_field_unit, action=None):
        if scenario_id == Scenario.BKDATA:
            time_field = DEFAULT_TIME_FIELD
            time_field_type = TimeFieldTypeEnum.DATE.value
            time_field_unit = TimeFieldUnitEnum.MILLISECOND.value
        elif scenario_id == Scenario.LOG:
            time_field = DEFAULT_TIME_FIELD
            time_field_type = TimeFieldTypeEnum.DATE.value
            time_field_unit = TimeFieldUnitEnum.MILLISECOND.value
        elif scenario_id == Scenario.ES and action != "delete":
            if not time_field:
                raise SearchUnKnowTimeField()
            if time_field_type in [TimeFieldTypeEnum.LONG.value]:
                if not time_field_unit:
                    raise SearchUnKnowTimeField()
        return time_field, time_field_type, time_field_unit

    def create_index_set(self):
        """
        创建索引集
        """
        self.pre_create()
        logger.info(f"[create_index_set]pre_create index_set_name=>{self.index_set_name}")

        index_set = self.create()
        logger.info(f"[create_index_set]create index_set_name=>{self.index_set_name}")

        self.post_create(index_set)
        logger.info(f"[create_index_set]post_create index_set_name=>{self.index_set_name}")
        return index_set

    def update_index_set(self, index_set_obj):
        """
        更新索引集
        :param index_set_obj: 索引集对象
        """
        self.index_set_obj = index_set_obj

        self.pre_update()
        logger.info(f"[update_index_set]pre_create index_set_name=>{self.index_set_name}")

        index_set = self.update()
        logger.info(f"[update_index_set]create index_set_name=>{self.index_set_name}")

        self.post_update(index_set)
        logger.info(f"[update_index_set]post_create index_set_name=>{self.index_set_name}")
        return index_set

    def delete_index_set(self, index_set_obj):
        """
        删除索引集
        :param index_set_obj: 索引集对象
        """
        self.index_set_obj = index_set_obj

        self.pre_delete()
        self.delete()
        self.post_delete(index_set=index_set_obj)

    def pre_create(self):
        """
        创建前检查
        1.检查trace结构是否符合
        :return:
        """
        if self.is_trace_log:
            self.is_trace_log_pre_check()

    def create(self):
        # 创建索引集
        self.index_set_obj = LogIndexSet.objects.create(
            index_set_name=self.index_set_name,
            space_uid=self.space_uid,
            scenario_id=self.scenario_id,
            view_roles=self.view_roles,
            bkdata_project_id=self.bkdata_project_id,
            collector_config_id=self.collector_config_id,
            storage_cluster_id=self.storage_cluster_id,
            category_id=self.category_id,
            is_trace_log=self.is_trace_log,
            time_field=self.time_field,
            time_field_type=self.time_field_type,
            time_field_unit=self.time_field_unit,
            source_app_code=self.bk_app_code,
            bcs_project_id=self.bcs_project_id,
            is_editable=self.is_editable,
            target_fields=self.target_fields,
            sort_fields=self.sort_fields,
        )
        logger.info(
            f"[create_index_set][{self.index_set_obj.index_set_id}]index_set_name => {self.index_set_name}, indexes => {len(self.indexes)}"
        )

        # 创建索引集的同时添加索引
        for index in self.indexes:
            _, time_field_type, time_field_unit = self.init_time_field(
                index["scenario_id"],
                index.get("time_field"),
                index.get("time_field_type"),
                index.get("time_field_unit"),
            )
            IndexSetHandler(index_set_id=self.index_set_obj.index_set_id).add_index(
                bk_biz_id=index["bk_biz_id"],
                time_filed=index.get("time_field"),
                result_table_id=index["result_table_id"],
                scenario_id=index["scenario_id"],
                storage_cluster_id=index["storage_cluster_id"],
                time_field_type=time_field_type,
                time_field_unit=time_field_unit,
            )

        # 更新字段快照
        sync_single_index_set_mapping_snapshot.delay(self.index_set_obj.index_set_id)
        return self.index_set_obj

    @staticmethod
    def get_rt_id(index_set_id, collector_config_id, indexes, clustered_rt=None):
        if clustered_rt:
            return f"bklog_index_set_{str(index_set_id)}_clustered.__default__"
        if collector_config_id:
            return ",".join([index["result_table_id"] for index in indexes])
        return f"bklog_index_set_{str(index_set_id)}.__default__"

    @staticmethod
    def get_data_label(scenario_id, index_set_id, clustered_rt=None):
        if clustered_rt:
            return f"{scenario_id}_index_set_{str(index_set_id)}_clustered"
        return f"{scenario_id}_index_set_{str(index_set_id)}"

    def post_create(self, index_set):
        # 新建授权
        Permission(username=self.username).grant_creator_action(
            resource=ResourceEnum.INDICES.create_simple_instance(
                index_set.index_set_id, attribute={"name": index_set.index_set_name}
            ),
            creator=index_set.created_by,
        )
        # 创建结果表路由信息
        try:
            request_params = {
                "cluster_id": index_set.storage_cluster_id,
                "index_set": ",".join([index["result_table_id"] for index in self.indexes]).replace(".", "_"),
                "data_label": f"bklog_index_set_{index_set.index_set_id}",
                "space_id": index_set.space_uid.split("__")[-1],
                "space_type": index_set.space_uid.split("__")[0],
                "need_create_index": True if index_set.collector_config_id else False,
                "options": [
                    {
                        "name": "time_field",
                        "value_type": "dict",
                        "value": json.dumps(
                            {
                                "name": index_set.time_field,
                                "type": index_set.time_field_type,
                                "unit": index_set.time_field_unit
                                if index_set.time_field_type != TimeFieldTypeEnum.DATE.value
                                else TimeFieldUnitEnum.MILLISECOND.value,
                            }
                        ),
                    },
                    {
                        "name": "need_add_time",
                        "value_type": "bool",
                        "value": json.dumps(index_set.scenario_id != Scenario.ES),
                    },
                ],
            }
            multi_execute_func = MultiExecuteFunc()
            objs = LogIndexSetData.objects.filter(index_set_id=index_set.index_set_id)
            for obj in objs:
                request_params.update(
                    {
                        "table_id": f"bklog_index_set_{index_set.index_set_id}_{obj.result_table_id.replace('.', '_')}.__default__",
                        "source_type": obj.scenario_id,
                        "storage_cluster_id": obj.storage_cluster_id,
                    }
                )
                multi_execute_func.append(
                    result_key=obj.result_table_id,
                    func=TransferApi.create_or_update_log_router,
                    params=request_params,
                )
            multi_execute_func.run()
        except Exception as e:
            logger.exception("create or update index set(%s) es router failed：%s", index_set.index_set_id, e)
        return True

    def pre_update(self):
        if self.is_trace_log:
            self.is_trace_log_pre_check()

    def update(self):
        if self.category_id:
            self.index_set_obj.category_id = self.category_id

        if self.index_set_obj.storage_cluster_id == self.storage_cluster_id:
            old_storage_cluster_id = None
        else:
            old_storage_cluster_id = self.index_set_obj.storage_cluster_id

        self.index_set_obj.index_set_name = self.index_set_name
        self.index_set_obj.view_roles = self.view_roles
        self.index_set_obj.storage_cluster_id = self.storage_cluster_id
        self.index_set_obj.is_trace_log = self.is_trace_log

        # 更新 is_active字段
        self.index_set_obj.is_active = True

        # 时间字段更新
        self.index_set_obj.time_field = self.time_field
        self.index_set_obj.time_field_type = self.time_field_type
        self.index_set_obj.time_field_unit = self.time_field_unit

        # 上下文、实时日志 定位字段 排序字段更新
        if self.target_fields_raw is not None:
            self.index_set_obj.target_fields = self.target_fields_raw
        if self.sort_fields_raw is not None:
            self.index_set_obj.sort_fields = self.sort_fields_raw

        self.index_set_obj.save()

        if old_storage_cluster_id:
            # 保存旧的存储集群记录
            StorageClusterRecord.objects.create(
                index_set_id=self.index_set_obj.index_set_id, storage_cluster_id=old_storage_cluster_id
            )

        # 需移除的索引
        to_delete_indexes = [
            index
            for index in self.index_set_obj.indexes
            if index["result_table_id"] not in [index["result_table_id"] for index in self.indexes]
        ]

        for index in to_delete_indexes:
            IndexSetHandler(index_set_id=self.index_set_obj.index_set_id).delete_index(
                index["bk_biz_id"], index.get("time_field"), index["result_table_id"]
            )

        # 需新增的索引
        to_append_indexes = [
            index
            for index in self.indexes
            if index["result_table_id"] not in [index["result_table_id"] for index in self.index_set_obj.indexes]
        ]
        for index in to_append_indexes:
            _, time_field_type, time_field_unit = self.init_time_field(
                index["scenario_id"],
                index.get("time_field"),
                index.get("time_field_type"),
                index.get("time_field_unit"),
            )
            IndexSetHandler(index_set_id=self.index_set_obj.index_set_id).add_index(
                index["bk_biz_id"],
                index.get("time_field"),
                index["result_table_id"],
                index["scenario_id"],
                index["storage_cluster_id"],
                time_field_type=time_field_type,
                time_field_unit=time_field_unit,
            )

        # 更新字段快照
        sync_single_index_set_mapping_snapshot.delay(self.index_set_obj.index_set_id)

        # 更新索引集归档配置
        sync_index_set_archive.delay(self.index_set_obj.index_set_id)

        return self.index_set_obj

    def post_update(self, index_set):
        self.post_create(index_set)
        return index_set

    def pre_delete(self):
        pass

    def delete(self):
        self.index_set_obj.delete()
        StorageClusterRecord.objects.filter(index_set_id=self.index_set_obj.index_set_id).delete()

    def post_delete(self, index_set):
        # @TODO 调用auth模块删除权限
        pass

    def is_trace_log_pre_check(self):
        if self.is_trace_log:
            rt_list = [index.get("result_table_id", "") for index in self.indexes]
            mapping_list: list = BkLogApi.mapping(
                {
                    "indices": ",".join(rt_list),
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "bkdata_authentication_method": "user",
                }
            )
            property_dict: dict = MappingHandlers.find_property_dict(mapping_list)
            field_list: list = MappingHandlers.get_all_index_fields_by_mapping(property_dict)
            trace_proto_type = Proto.judge_trace_type(field_list)
            if trace_proto_type is not None:
                return True
            raise IndexTraceNotAcceptException()
        return False


class BkDataIndexSetHandler(BaseIndexSetHandler):
    scenario_id = Scenario.BKDATA

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 是否需要跳转到数据平台进行授权
        self.need_authorize = False

    def pre_create(self):
        super().pre_create()
        self.check_rt_authorization_for_user()
        self.auto_authorize_rt()

    def pre_update(self):
        super().pre_update()
        self.check_rt_authorization_for_user()
        self.auto_authorize_rt()

    def auto_authorize_rt(self):
        """
        自动授权
        """
        BkDataAuthHandler.authorize_result_table_to_token(
            result_tables=[index["result_table_id"] for index in self.indexes]
        )

    def check_rt_authorization_for_user(self):
        """
        判断用户是否拥有所有RT的管理权限
        """
        unauthorized_result_tables = BkDataAuthHandler(username=self.username).filter_unauthorized_rt_by_user(
            result_tables=[index["result_table_id"] for index in self.indexes]
        )
        if unauthorized_result_tables:
            raise UnauthorizedResultTableException(
                UnauthorizedResultTableException.MESSAGE.format(result_tables=",".join(unauthorized_result_tables))
            )

    def check_rt_authorization_for_token(self, index_set):
        result_tables = [index["result_table_id"] for index in self.indexes]
        unauthorized_result_tables = BkDataAuthHandler().filter_unauthorized_rt_by_token(result_tables=result_tables)

        LogIndexSetData.objects.filter(index_set_id=index_set.index_set_id).exclude(
            apply_status=LogIndexSetData.Status.ABNORMAL
        ).update(apply_status=LogIndexSetData.Status.NORMAL)

        if unauthorized_result_tables:
            # 如果存在没有权限的RT，要把状态设置为审批中
            LogIndexSetData.objects.filter(
                index_set_id=index_set.index_set_id,
                result_table_id__in=unauthorized_result_tables,
            ).update(apply_status=LogIndexSetData.Status.PENDING)

    def post_create(self, index_set):
        super().post_create(index_set)
        self.check_rt_authorization_for_token(index_set)


class EsIndexSetHandler(BaseIndexSetHandler):
    scenario_id = Scenario.ES


class LogIndexSetHandler(BaseIndexSetHandler):
    scenario_id = Scenario.LOG


class LogIndexSetDataHandler:
    def __init__(
        self,
        index_set_data,
        bk_biz_id,
        time_filed,
        result_table_id,
        result_table_name=None,
        storage_cluster_id=None,
        scenario_id=None,
        time_field_type=None,
        time_field_unit=None,
        apply_status=LogIndexSetData.Status.NORMAL,
        bk_username=None,
    ):
        self.index_set_data = index_set_data
        self.bk_biz_id = bk_biz_id
        self.time_field = time_filed
        self.result_table_id = result_table_id
        self.result_table_name = result_table_name
        self.storage_cluster_id = storage_cluster_id
        self.scenario_id = scenario_id
        self.time_field_type = time_field_type
        self.time_field_unit = time_field_unit
        self.apply_status = apply_status
        self.bk_username = get_request_username() or bk_username

    def add_index(self):
        """
        往索引集添加索引
        """
        obj, created = LogIndexSetData.objects.get_or_create(  # pylint: disable=unused-variable
            defaults={
                "time_field": self.time_field,
                "result_table_name": self.result_table_name,
                "apply_status": self.apply_status,
                "scenario_id": self.scenario_id,
                "storage_cluster_id": self.storage_cluster_id,
                "time_field_type": self.time_field_type,
                "time_field_unit": self.time_field_unit,
            },
            index_set_id=self.index_set_data.index_set_id,
            bk_biz_id=self.bk_biz_id or None,
            result_table_id=self.result_table_id,
            is_deleted=False,
        )
        return obj

    def delete_index(self):
        """
        删除索引
        """
        LogIndexSetData.objects.filter(
            index_set_id=self.index_set_data.index_set_id,
            result_table_id=self.result_table_id,
            bk_biz_id=self.bk_biz_id,
        ).delete()


class IndexSetFieldsConfigHandler:
    """索引集配置字段(展示字段以及排序字段)"""

    data: IndexSetFieldsConfig | None = None

    def __init__(
        self,
        config_id: int = None,
        index_set_id: int = None,
        scope: str = SearchScopeEnum.DEFAULT.value,
        index_set_ids: list = None,
        index_set_type: str = IndexSetType.SINGLE.value,
    ):
        self.config_id = config_id
        self.index_set_id = index_set_id
        self.scope = scope
        self.source_app_code = get_request_app_code()
        self.index_set_ids = index_set_ids
        self.index_set_type = index_set_type
        if config_id:
            try:
                self.data = IndexSetFieldsConfig.objects.get(pk=config_id)
            except IndexSetFieldsConfig.DoesNotExist:
                raise IndexSetFieldsConfigNotExistException()
        self.index_set_ids_hash = IndexSetFieldsConfig.get_index_set_ids_hash(self.index_set_ids)

    def retrieve(self) -> dict:
        if not self.data:
            raise IndexSetFieldsConfigNotExistException()
        return model_to_dict(self.data)

    def list(self, scope: str = SearchScopeEnum.DEFAULT.value) -> list:
        query_params = {"scope": scope, "source_app_code": self.source_app_code, "index_set_type": self.index_set_type}
        if self.index_set_type == IndexSetType.UNION.value:
            query_params.update({"index_set_ids_hash": self.index_set_ids_hash})
        else:
            query_params.update({"index_set_id": self.index_set_id})
        objs = IndexSetFieldsConfig.objects.filter(**query_params).all()
        config_list = [model_to_dict(obj) for obj in objs]
        config_list.sort(key=lambda c: c["name"] == DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME, reverse=True)
        return config_list

    def create_or_update(self, name: str, display_fields: list, sort_list: list):
        username = get_request_external_username() or get_request_username()
        # 校验配置需要修改名称时, 名称是否可用
        if self.data and self.data.name != name or not self.data:
            if self.index_set_type == IndexSetType.UNION.value:
                if IndexSetFieldsConfig.objects.filter(
                    name=name, index_set_ids_hash=self.index_set_ids_hash, source_app_code=self.source_app_code
                ).exists():
                    raise IndexSetFieldsConfigAlreadyExistException()
            else:
                if IndexSetFieldsConfig.objects.filter(
                    name=name, index_set_id=self.index_set_id, source_app_code=self.source_app_code
                ).exists():
                    raise IndexSetFieldsConfigAlreadyExistException()

        if self.data:
            # 更新配置, 只允许更新name, display_fields, sort_list
            if self.data.name != DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME:
                self.data.name = name
            self.data.display_fields = display_fields
            self.data.sort_list = sort_list
            self.data.save()
        else:
            # 创建配置
            params = {
                "name": name,
                "display_fields": display_fields,
                "sort_list": sort_list,
                "scope": self.scope,
                "source_app_code": self.source_app_code,
            }
            if self.index_set_type == IndexSetType.UNION.value:
                params.update(
                    {
                        "index_set_ids": self.index_set_ids,
                        "index_set_ids_hash": self.index_set_ids_hash,
                        "index_set_type": IndexSetType.UNION.value,
                    }
                )
            else:
                params.update({"index_set_id": self.index_set_id, "index_set_type": IndexSetType.SINGLE.value})
            self.data = IndexSetFieldsConfig.objects.create(**params)
            self.data.created_by = username
            self.data.save()

        if self.index_set_type == IndexSetType.UNION.value:
            return model_to_dict(self.data)
        # add user_operation_record
        try:
            log_index_set_obj = LogIndexSet.objects.get(index_set_id=self.index_set_id)
            operation_record = {
                "username": username,
                "biz_id": 0,
                "space_uid": log_index_set_obj.space_uid,
                "record_type": UserOperationTypeEnum.INDEX_SET_CONFIG,
                "record_sub_type": log_index_set_obj.scenario_id,
                "record_object_id": self.index_set_id,
                "action": UserOperationActionEnum.UPDATE if self.data else UserOperationActionEnum.CREATE,
                "params": {
                    "index_set_id": self.index_set_id,
                    "display_fields": display_fields,
                    "sort_list": sort_list,
                    "source_app_code": self.source_app_code,
                },
            }
        except LogIndexSet.DoesNotExist:
            logger.exception(f"LogIndexSet --> {self.index_set_id} does not exist")
        else:
            user_operation_record.delay(operation_record)

        return model_to_dict(self.data)

    def delete(self):
        IndexSetFieldsConfig.delete_config(self.config_id)


class UserIndexSetConfigHandler:
    def __init__(
        self,
        index_set_id: int = None,
        index_set_ids: list[int] = None,
        index_set_type: str = IndexSetType.SINGLE.value,
    ):
        self.index_set_id = index_set_id
        self.index_set_ids = index_set_ids
        self.index_set_type = index_set_type
        # 对列表进行排序
        if self.index_set_ids:
            self.index_set_ids.sort()

    def update_or_create(self, index_set_config: dict):
        """
        更新或创建用户索引集自定义配置
        :param index_set_config: 索引集配置
        """
        if self.index_set_type == IndexSetType.SINGLE.value:
            model_params = {"index_set_id": self.index_set_id}
            index_set_id = self.index_set_id
        elif self.index_set_type == IndexSetType.UNION.value:
            model_params = {"index_set_ids": self.index_set_ids}
            index_set_id = self.index_set_ids

        index_set_hash = UserIndexSetCustomConfig.get_index_set_hash(index_set_id)
        model_params.update({"index_set_config": index_set_config})

        obj, _ = UserIndexSetCustomConfig.objects.update_or_create(
            username=get_request_username(),
            index_set_hash=index_set_hash,
            defaults=model_params,
        )
        return model_to_dict(obj)

    def get_index_set_config(self):
        """
        获取用户索引集配置
        """
        if self.index_set_type == IndexSetType.SINGLE.value:
            index_set_id = self.index_set_id
        elif self.index_set_type == IndexSetType.UNION.value:
            index_set_id = self.index_set_ids

        index_set_hash = UserIndexSetCustomConfig.get_index_set_hash(index_set_id)
        obj = UserIndexSetCustomConfig.objects.filter(
            index_set_hash=index_set_hash,
            username=get_request_username(),
        ).first()
        return obj.index_set_config if obj else {}


class IndexSetCustomConfigHandler:
    def __init__(
        self,
        index_set_id: int = None,
        index_set_ids: list[int] = None,
        index_set_type: str = IndexSetType.SINGLE.value,
    ):
        self.index_set_id = index_set_id
        self.index_set_ids = index_set_ids
        self.index_set_type = index_set_type
        # 对列表进行排序
        if self.index_set_ids:
            self.index_set_ids.sort()
        self.index_set_hash = self.get_index_set_hash()

    def update_or_create(self, index_set_config: dict):
        """
        更新或创建索引集自定义配置
        :param index_set_config: 索引集自定义配置
        """
        if self.index_set_type == IndexSetType.SINGLE.value:
            model_params = {"index_set_id": self.index_set_id}
        elif self.index_set_type == IndexSetType.UNION.value:
            model_params = {"index_set_ids": self.index_set_ids}
        model_params.update({"index_set_config": index_set_config})

        obj, _ = IndexSetCustomConfig.objects.update_or_create(
            index_set_hash=self.index_set_hash,
            defaults=model_params,
        )
        return model_to_dict(obj)

    def get_index_set_hash(self):
        """
        获取索引集hash值
        """
        if self.index_set_type == IndexSetType.SINGLE.value:
            return IndexSetCustomConfig.get_index_set_hash(self.index_set_id)
        elif self.index_set_type == IndexSetType.UNION.value:
            return IndexSetCustomConfig.get_index_set_hash(self.index_set_ids)

    def get_index_set_config(self):
        """
        获取索引集自定义配置
        """
        obj = IndexSetCustomConfig.objects.filter(
            index_set_hash=self.index_set_hash,
        ).first()
        return obj.index_set_config if obj else {}
