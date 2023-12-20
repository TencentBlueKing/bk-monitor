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
import json
import logging
from typing import Dict, List, Optional, Set

from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now as tz_now

from metadata import models
from metadata.models.space import utils
from metadata.models.space.constants import (
    BKCI_1001_TABLE_ID_PREFIX,
    BKCI_SYSTEM_TABLE_ID_PREFIX,
    DATA_LABEL_TO_RESULT_TABLE_CHANNEL,
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    DBM_1001_TABLE_ID_PREFIX,
    RESULT_TABLE_DETAIL_CHANNEL,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_CHANNEL,
    SPACE_TO_RESULT_TABLE_KEY,
    BCSClusterTypes,
    EtlConfigs,
    MeasurementType,
    SpaceTypes,
)
from metadata.models.space.ds_rt import (
    get_cluster_data_ids,
    get_measurement_type_by_table_id,
    get_platform_data_ids,
    get_result_tables_by_data_ids,
    get_space_table_id_data_id,
    get_table_id_cluster_id,
    get_table_info_for_influxdb_and_vm,
)
from metadata.utils.db import filter_model_by_in_page, filter_query_set_by_in_page
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class SpaceTableIDRedis:
    """空间路由结果表数据推送 redis 相关功能"""

    def push_space_table_ids(self, space_type: str, space_id: str, is_publish: Optional[bool] = False):
        """推送空间及对应的结果表和过滤条件"""
        logger.info("start to push space table_id data, space_type: %s, space_id: %s", space_type, space_id)
        # NOTE: 为防止 space_id 传递非字符串，转换一次
        space_id = str(space_id)
        # 过滤空间关联的数据源信息
        if space_type == SpaceTypes.BKCC.value:
            self._push_bkcc_space_table_ids(space_type, space_id)
        elif space_type == SpaceTypes.BKCI.value:
            # 开启容器服务，则需要处理集群+业务+构建机+其它(在当前空间下创建的插件、自定义上报等)
            self._push_bkci_space_table_ids(space_type, space_id)
        elif space_type == SpaceTypes.BKSAAS.value:
            self._push_bksaas_space_table_ids(space_type, space_id)

        # 如果指定要更新，则通知
        if is_publish:
            RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, [f"{space_type}__{space_id}"])
        logger.info("push space table_id data successfully, space_type: %s, space_id: %s", space_type, space_id)

    def push_data_label_table_ids(
        self,
        data_label_list: Optional[List] = None,
        table_id_list: Optional[List] = None,
        is_publish: Optional[bool] = False,
    ):
        """推送 data_label 及对应的结果表"""
        logger.info(
            "start to push data_label table_id data, data_label_list: %s, table_id_list: %s",
            json.dumps(data_label_list),
            json.dumps(table_id_list),
        )
        table_ids = self._refine_table_ids(table_id_list)
        # 过滤掉结果表数据标签为空或者为 None 的记录
        data_labels = (
            models.ResultTable.objects.filter(table_id__in=table_ids)
            .exclude(Q(data_label="") | Q(data_label=None))
            .values_list("data_label", flat=True)
        )
        if data_label_list:
            data_labels = data_labels.filter(data_label__in=data_label_list)
        # 再通过 data_label 过滤到结果表
        rt_dl_qs = filter_model_by_in_page(
            model=models.ResultTable,
            field_op="data_label__in",
            filter_data=list(data_labels),
            value_func="values",
            value_field_list=["table_id", "data_label"],
        )
        # 组装数据
        rt_dl_map = {}
        for data in rt_dl_qs:
            rt_dl_map.setdefault(data["data_label"], []).append(data["table_id"])

        if rt_dl_map:
            redis_values = {data_label: json.dumps(table_ids) for data_label, table_ids in rt_dl_map.items()}
            RedisTools.hmset_to_redis(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_values)

            if is_publish:
                RedisTools.publish(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, list(rt_dl_map.keys()))
        logger.info("push redis data_label_to_result_table")

    def push_table_id_detail(self, table_id_list: Optional[List] = None, is_publish: Optional[bool] = False):
        """推送结果表的详细信息"""
        logger.info("start to push table_id detail data, table_id_list: %s", json.dumps(table_id_list))
        table_id_detail = get_table_info_for_influxdb_and_vm(table_id_list)
        if not table_id_detail:
            logger.info("table_id_list: %s not found table from influxdb or vm", json.dumps(table_id_list))
            return

        table_ids = set(table_id_detail.keys())
        # 获取结果表类型
        _rt_filter_data = filter_model_by_in_page(
            model=models.ResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "schema_type", "data_label"],
        )

        _table_id_dict = {rt["table_id"]: rt for rt in _rt_filter_data}
        _table_list = list(_table_id_dict.values())
        # 写入 influxdb 的结果表，不会太多，直接获取结果表和数据源的关系
        _ds_rt_filter_data = filter_model_by_in_page(
            model=models.DataSourceResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "bk_data_id"],
        )
        table_id_data_id = {drt["table_id"]: drt["bk_data_id"] for drt in _ds_rt_filter_data}
        # 获取结果表对应的类型
        measurement_type_dict = get_measurement_type_by_table_id(table_ids, _table_list, table_id_data_id)
        table_id_cluster_id = get_table_id_cluster_id(table_ids)
        # 再追加上结果表的指标数据、集群 ID、类型
        table_id_fields = self._compose_table_id_fields(set(table_id_detail.keys()))
        _table_id_detail = {}
        for table_id, detail in table_id_detail.items():
            detail["fields"] = table_id_fields.get(table_id) or []
            detail["measurement_type"] = measurement_type_dict.get(table_id) or ""
            detail["bcs_cluster_id"] = table_id_cluster_id.get(table_id) or ""
            detail["data_label"] = _table_id_dict.get(table_id, {}).get("data_label") or ""
            detail["bk_data_id"] = table_id_data_id.get(table_id, 0)
            _table_id_detail[table_id] = json.dumps(detail)

        # 推送数据
        if _table_id_detail:
            RedisTools.hmset_to_redis(RESULT_TABLE_DETAIL_KEY, _table_id_detail)
            if is_publish:
                RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(_table_id_detail.keys()))
        logger.info("push redis result_table_detail")

    def _push_bkcc_space_table_ids(
        self,
        space_type: str,
        space_id: str,
        from_authorization: Optional[bool] = None,
    ):
        """推送 bkcc 类型空间数据"""
        logger.info("start to push bkcc space table_id, space_type: %s, space_id: %s", space_type, space_id)
        _values = self._compose_data(space_type, space_id, from_authorization=from_authorization)
        # 推送数据
        if _values:
            redis_values = {f"{space_type}__{space_id}": json.dumps(_values)}
            RedisTools.hmset_to_redis(SPACE_TO_RESULT_TABLE_KEY, redis_values)
        logger.info(
            "push redis space_to_result_table, space_type: %s, space_id: %s",
            space_type,
            space_id,
        )

    def _push_bkci_space_table_ids(
        self,
        space_type: str,
        space_id: str,
    ):
        """推送 bcs 类型空间下的关联业务的数据"""
        logger.info("start to push biz of bcs space table_id, space_type: %s, space_id: %s", space_type, space_id)
        _values = self._compose_bcs_space_biz_table_ids(space_type, space_id)
        _values.update(self._compose_bcs_space_cluster_table_ids(space_type, space_id))
        _values.update(self._compose_bkci_level_table_ids(space_type, space_id))
        _values.update(self._compose_bkci_other_table_ids(space_type, space_id))
        # 追加跨空间类型的数据源授权
        _values.update(self._compose_bkci_cross_table_ids(space_type, space_id))
        # 推送数据
        if _values:
            redis_values = {f"{space_type}__{space_id}": json.dumps(_values)}
            RedisTools.hmset_to_redis(SPACE_TO_RESULT_TABLE_KEY, redis_values)
        logger.info(
            "push redis space_to_result_table, space_type: %s, space_id:%s",
            space_type,
            space_id,
        )

    def _push_bksaas_space_table_ids(
        self,
        space_type: str,
        space_id: str,
        table_id_list: Optional[List] = None,
    ):
        """推送 bksaas 类型空间下的数据"""
        logger.info("start to push bksaas space table_id, space_type: %s, space_id: %s", space_type, space_id)
        _values = self._compose_bksaas_space_cluster_table_ids(space_type, space_id, table_id_list)
        # 获取蓝鲸应用使用的集群数据
        _values.update(self._compose_bksaas_other_table_ids(space_type, space_id, table_id_list))
        if _values:
            redis_values = {f"{space_type}__{space_id}": json.dumps(_values)}
            RedisTools.hmset_to_redis(SPACE_TO_RESULT_TABLE_KEY, redis_values)
        logger.info(
            "push redis space_to_result_table, space_type: %s, space_id: %s",
            space_type,
            space_id,
        )

    def _compose_bcs_space_biz_table_ids(self, space_type: str, space_id: str) -> Dict:
        """推送 bcs 类型关联业务的数据，现阶段仅包含主机信息"""
        logger.info("start to push cluster of bcs space table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 首先获取关联业务的数据
        resource_type = SpaceTypes.BKCC.value
        obj = models.SpaceResource.objects.filter(
            space_type_id=space_type, space_id=space_id, resource_type=resource_type
        ).first()
        if not obj:
            logger.error("space: %s__%s, resource_type: %s not found", space_type, space_id, resource_type)
            return {}
        # 获取空间关联的业务，注意这里业务 ID 为字符串类型
        tids = models.ResultTable.objects.filter(table_id__startswith=BKCI_SYSTEM_TABLE_ID_PREFIX).values_list(
            "table_id", flat=True
        )
        return {tid: {"filters": [{"bk_biz_id": str(obj.resource_id)}]} for tid in tids}

    def _compose_bcs_space_cluster_table_ids(
        self,
        space_type: str,
        space_id: str,
    ) -> Dict:
        """推送 bcs 类型空间下的集群数据"""
        logger.info("start to push cluster of bcs space table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 获取空间的集群数据
        resource_type = SpaceTypes.BCS.value
        # 优先进行判断项目相关联的容器资源，减少等待
        sr_objs = models.SpaceResource.objects.filter(
            space_type_id=space_type, space_id=space_id, resource_type=resource_type, resource_id=space_id
        )
        default_values = {}
        str_obj = sr_objs.first()
        if not str_obj:
            logger.error("space: %s__%s, resource_type: %s not found", space_type, space_id, resource_type)
            return default_values
        res_list = str_obj.dimension_values
        # 如果关键维度数据为空，同样返回默认
        if not res_list:
            return default_values
        # 获取集群的数据, 格式: {cluster_id: {"bcs_cluster_id": xxx, "namespace": xxx}}
        cluster_info = {}
        for res in res_list:
            if res["cluster_type"] == BCSClusterTypes.SHARED.value and res["namespace"]:
                cluster_info[res["cluster_id"]] = [
                    {"bcs_cluster_id": res["cluster_id"], "namespace": ns} for ns in res["namespace"]
                ]
            elif res["cluster_type"] == BCSClusterTypes.SINGLE.value:
                cluster_info[res["cluster_id"]] = [{"bcs_cluster_id": res["cluster_id"], "namespace": None}]
        cluster_id_list = list(cluster_info.keys())
        # 获取集群下对应的数据源
        data_id_cluster_id = get_cluster_data_ids(cluster_id_list)
        if not data_id_cluster_id:
            logger.error("space: %s__%s not found cluster", space_type, space_id)
            return default_values
        # 获取结果表及数据源
        table_id_data_id = get_result_tables_by_data_ids(list(data_id_cluster_id.keys()))
        # 组装 filter
        _values = {}
        for tid, data_id in table_id_data_id.items():
            cluster_id = data_id_cluster_id.get(data_id)
            if not cluster_id:
                continue
            # 获取对应的集群及命名空间信息
            _values[tid] = {"filters": cluster_info.get(cluster_id) or []}

        return _values

    def _compose_bkci_level_table_ids(self, space_type: str, space_id: str) -> Dict:
        """组装 bkci 全局下的结果表"""
        logger.info("start to push bkci level table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 过滤空间级的数据源
        data_ids = get_platform_data_ids(space_type=space_type)
        # 一个空间下 data_id 不会太多
        table_is_list = list(
            models.DataSourceResultTable.objects.filter(bk_data_id__in=data_ids.keys()).values_list(
                "table_id", flat=True
            )
        )
        _values = {}
        if not table_is_list:
            return _values
        # 过滤仅写入influxdb和vm的数据
        table_ids = self._refine_table_ids(table_is_list)
        # 组装数据
        for tid in table_ids:
            _values[tid] = {"filters": [{"projectId": space_id}]}

        return _values

    def _compose_bkci_other_table_ids(self, space_type: str, space_id: str) -> Dict:
        logger.info("start to push bkci space other table_id, space_type: %s, space_id: %s", space_type, space_id)
        exclude_data_id_list = utils.cached_cluster_data_id_list()
        table_id_data_id = get_space_table_id_data_id(
            space_type,
            space_id,
            exclude_data_id_list=exclude_data_id_list,
            include_platform_data_id=False,
            from_authorization=False,
        )
        _values = {}
        if not table_id_data_id:
            logger.error("space_type: %s, space_id:%s not found table_id and data_id", space_type, space_id)
            return _values

        table_ids = self._refine_table_ids(list(table_id_data_id.keys()))
        # 组装数据
        for tid in table_ids:
            # NOTE: 现阶段针对1001下 `system.` 或者 `dbm_system.` 开头的结果表不允许被覆盖
            if tid.startswith("system.") or tid.startswith("dbm_system."):
                continue
            _values[tid] = {"filters": []}

        return _values

    def _compose_bkci_cross_table_ids(self, space_type: str, space_id: str) -> Dict:
        """组装跨空间类型的结果表数据"""
        logger.info(
            "start to push bkci space cross space_type table_id, space_type: %s, space_id: %s", space_type, space_id
        )
        tids = models.ResultTable.objects.filter(table_id__startswith=BKCI_1001_TABLE_ID_PREFIX).values_list(
            "table_id", flat=True
        )
        return {tid: {"filters": [{"projectId": space_id}]} for tid in tids}

    def _compose_bksaas_space_cluster_table_ids(
        self,
        space_type: str,
        space_id: str,
        table_id_list: Optional[List] = None,
    ):
        logger.info(
            "start to push cluster of bksaas space table_id, space_type: %s, space_id: %s", space_type, space_id
        )
        # 获取空间的集群数据
        resource_type = SpaceTypes.BKSAAS.value
        # 优先进行判断项目相关联的容器资源，减少等待
        sr_objs = models.SpaceResource.objects.filter(
            space_type_id=space_type, space_id=space_id, resource_type=resource_type, resource_id=space_id
        )
        default_values = {}
        str_obj = sr_objs.first()
        if not str_obj:
            logger.error("space: %s__%s, resource_type: %s not found", space_type, space_id, resource_type)
            return default_values
        res_list = str_obj.dimension_values
        # 如果关键维度数据为空，同样返回默认
        if not res_list:
            return default_values
        # 获取集群的数据, 格式: {cluster_id: {"bcs_cluster_id": xxx, "namespace": xxx}}
        cluster_info = {}
        for res in res_list:
            if res["cluster_type"] == BCSClusterTypes.SHARED.value and res["namespace"]:
                cluster_info[res["cluster_id"]] = [
                    {"bcs_cluster_id": res["cluster_id"], "namespace": ns} for ns in res["namespace"]
                ]
            elif res["cluster_type"] == BCSClusterTypes.SINGLE.value:
                cluster_info[res["cluster_id"]] = [{"bcs_cluster_id": res["cluster_id"], "namespace": None}]
        cluster_id_list = list(cluster_info.keys())
        # 获取集群下对应的数据源
        data_id_cluster_id = get_cluster_data_ids(cluster_id_list, table_id_list)
        if not data_id_cluster_id:
            logger.error("space: %s__%s not found cluster", space_type, space_id)
            return default_values
        # 获取结果表及数据源
        table_id_data_id = get_result_tables_by_data_ids(list(data_id_cluster_id.keys()), table_id_list)
        # 组装 filter
        _values = {}
        for tid, data_id in table_id_data_id.items():
            cluster_id = data_id_cluster_id.get(data_id)
            if not cluster_id:
                continue
            # 获取对应的集群及命名空间信息
            _values[tid] = {"filters": cluster_info.get(cluster_id) or []}

        return _values

    def _compose_bksaas_other_table_ids(self, space_type: str, space_id: str, table_id_list: Optional[List] = None):
        """组装蓝鲸应用非集群数据
        TODO: 暂时不考虑全局的数据源信息
        """
        logger.info("start to push bksaas space other table_id, space_type: %s, space_id: %s", space_type, space_id)
        exclude_data_id_list = utils.cached_cluster_data_id_list()
        # 过滤到对应的结果表
        table_id_data_id = get_space_table_id_data_id(
            space_type,
            space_id,
            table_id_list=table_id_list,
            exclude_data_id_list=exclude_data_id_list,
            include_platform_data_id=False,
        )

        default_values = {}
        if not table_id_data_id:
            logger.error("space_type: %s, space_id:%s not found table_id and data_id", space_type, space_id)
            return default_values
        # 提取仅包含写入 influxdb 和 vm 的结果表
        table_ids = self._refine_table_ids(list(table_id_data_id.keys()))
        # 组装数据
        _values = {}
        # 针对非集群的数据，不限制过滤条件
        for tid in table_ids:
            _values[tid] = {"filters": []}

        return _values

    def _compose_data(
        self,
        space_type: str,
        space_id: str,
        table_id_list: Optional[List] = None,
        include_platform_data_id: Optional[bool] = True,
        from_authorization: Optional[bool] = None,
        default_filters: Optional[List] = None,
    ) -> Dict:
        # 过滤到对应的结果表
        table_id_data_id = get_space_table_id_data_id(
            space_type,
            space_id,
            table_id_list=table_id_list,
            include_platform_data_id=include_platform_data_id,
            from_authorization=from_authorization,
        )
        _values = {}
        # 如果为空，返回默认值
        if not table_id_data_id:
            logger.error("space_type: %s, space_id:%s not found table_id and data_id", space_type, space_id)
            return _values

        # 提取仅包含写入 influxdb 和 vm 的结果表
        table_ids = self._refine_table_ids(list(table_id_data_id.keys()))
        # 再一次过滤，过滤到有链路的结果表，并且写入 influxdb 或 vm 的数据
        table_id_data_id = {tid: table_id_data_id.get(tid) for tid in table_ids}

        data_id_list = list(table_id_data_id.values())
        _filter_data = filter_model_by_in_page(
            model=models.DataSource,
            field_op="bk_data_id__in",
            filter_data=data_id_list,
            value_func="values",
            value_field_list=["bk_data_id", "etl_config", "space_uid", "is_platform_data_id"],
        )
        # 获取datasource的信息，避免后续每次都去查询db
        data_id_detail = {
            data["bk_data_id"]: {
                "etl_config": data["etl_config"],
                "space_uid": data["space_uid"],
                "is_platform_data_id": data["is_platform_data_id"],
            }
            for data in _filter_data
        }

        # 判断是否添加过滤条件
        _table_list = filter_model_by_in_page(
            model=models.ResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "schema_type", "data_label"],
        )
        # 获取结果表对应的类型
        measurement_type_dict = get_measurement_type_by_table_id(table_ids, _table_list, table_id_data_id)
        # 获取空间所属的数据源 ID
        _space_data_ids = models.SpaceDataSource.objects.filter(
            space_type_id=space_type, space_id=space_id, from_authorization=False
        ).values_list("bk_data_id", flat=True)
        for tid in table_ids:
            # NOTE: 特殊逻辑，忽略跨空间类型的 bkci 的结果表; 如果有其它，再提取为常量
            if tid.startswith(BKCI_1001_TABLE_ID_PREFIX):
                continue

            # NOTE: 特殊逻辑，针对 `dbm_system` 开头的结果表，设置过滤条件为空
            if tid.startswith(DBM_1001_TABLE_ID_PREFIX):
                # 如果不允许访问，则需要跳过
                if f"{space_type}__{space_id}" not in settings.ACCESS_DBM_RT_SPACE_UID:
                    continue
                _values[tid] = {"filters": []}
                continue

            measurement_type = measurement_type_dict.get(tid)
            # 如果查询不到类型，则忽略
            if not measurement_type:
                logger.error("table_id: %s not find measurement type", tid)
                continue
            data_id = table_id_data_id.get(tid)
            # 如果没有对应的结果表，则忽略
            if not data_id:
                logger.error("table_id: %s not found data_id", tid)
                continue
            _data_id_detail = data_id_detail.get(data_id)
            is_exist_space = data_id in _space_data_ids
            # 拼装过滤条件, 如果有指定，则按照指定数据设置过滤条件
            if default_filters:
                _values[tid] = {"filters": default_filters}
            else:
                filters = []
                if self._is_need_filter_for_bkcc(
                    measurement_type, space_type, space_id, _data_id_detail, is_exist_space
                ):
                    filters = [{"bk_biz_id": space_id}]
                _values[tid] = {"filters": filters}

        return _values

    def _is_need_filter_for_bkcc(
        self,
        measurement_type: str,
        space_type: str,
        space_id: str,
        data_id_detail: Optional[Dict] = None,
        is_exist_space: Optional[bool] = True,
    ) -> bool:
        """针对业务类型空间判断是否需要添加过滤条件"""
        if not data_id_detail:
            return True

        # NOTE: 为防止查询范围放大，先功能开关控制，针对归属到具体空间的数据源，不需要添加过滤条件
        if not settings.IS_RESTRICT_DS_BELONG_SPACE and (data_id_detail["space_uid"] == f"{space_type}__{space_id}"):
            return False

        # 如果不是自定义时序，则不需要关注类似的情况，必须增加过滤条件
        if (
            measurement_type
            not in [
                MeasurementType.BK_SPLIT.value,
                MeasurementType.BK_STANDARD_V2_TIME_SERIES.value,
                MeasurementType.BK_EXPORTER.value,
            ]
            and data_id_detail["etl_config"] != EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value
        ):
            return True

        # 对自定义插件的处理，兼容黑白名单对类型的更改
        # 黑名单时，会更改为单指标单表
        if measurement_type == MeasurementType.BK_EXPORTER.value or (
            data_id_detail["etl_config"] == EtlConfigs.BK_EXPORTER.value
            and measurement_type == MeasurementType.BK_SPLIT.value
        ):
            # 如果space_id与data_id所属空间UID相同，则不需要过滤
            if data_id_detail["space_uid"] == f"{space_type}__{space_id}":
                return False
            else:
                return True

        is_platform_data_id = data_id_detail["is_platform_data_id"]
        # 可以执行到以下代码，必然是自定义时序的数据源
        # 1. 非公共的(全空间或指定空间类型)自定义时序，查询时，不需要任何查询条件
        if not is_platform_data_id:
            return False

        # 2. 公共自定义时序，如果存在在当前space，不需要添加过滤条件
        if is_exist_space:
            return False

        # 3. 此时，必然是自定义时序，且是公共的平台数据源，同时非该当前空间下，ß需要添加过滤条件
        return True

    def _refine_table_ids(self, table_id_list: Optional[List] = None) -> Set:
        """提取写入到influxdb或vm的结果表数据"""
        # 过滤写入 influxdb 的结果表
        influxdb_table_ids = models.InfluxDBStorage.objects.values_list("table_id", flat=True)
        if table_id_list:
            influxdb_table_ids = filter_query_set_by_in_page(
                query_set=influxdb_table_ids,
                field_op="table_id__in",
                filter_data=table_id_list,
            )
        # 过滤写入 vm 的结果表
        vm_table_ids = models.AccessVMRecord.objects.values_list("result_table_id", flat=True)
        if table_id_list:
            vm_table_ids = filter_query_set_by_in_page(
                query_set=vm_table_ids,
                field_op="result_table_id__in",
                filter_data=table_id_list,
            )

        table_ids = set(influxdb_table_ids).union(set(vm_table_ids))

        return table_ids

    def _filter_ts_info(self, table_ids: Set) -> Dict:
        """根据结果表获取对应的时序数据"""
        if not table_ids:
            return {}
        _filter_data = filter_model_by_in_page(
            model=models.TimeSeriesGroup,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "time_series_group_id"],
        )
        if not _filter_data:
            return {}

        table_id_ts_group_id = {data["table_id"]: data["time_series_group_id"] for data in _filter_data}
        # NOTE: 针对自定义时序，过滤掉历史废弃的指标，时间在`TIME_SERIES_METRIC_EXPIRED_SECONDS`的为有效数据
        # 其它类型直接获取所有指标和维度
        begin_time = tz_now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        _filter_group_id_list = list(table_id_ts_group_id.values())
        ts_group_fields = filter_model_by_in_page(
            model=models.TimeSeriesMetric,
            field_op="group_id__in",
            filter_data=_filter_group_id_list,
            value_func="values",
            value_field_list=["field_name", "group_id"],
            other_filter={"last_modify_time__gte": begin_time},
        )

        group_id_field_map = {}
        for data in ts_group_fields:
            group_id_field_map.setdefault(data["group_id"], set()).add(data["field_name"])

        return {"table_id_ts_group_id": table_id_ts_group_id, "group_id_field_map": group_id_field_map}

    def _compose_table_id_fields(self, table_ids: Optional[Set] = None) -> Dict:
        """组装结果表对应的指标数据"""
        # 过滤到对应的结果表
        table_id_fields_qs = models.ResultTableField.objects.filter(
            tag=models.ResultTableField.FIELD_TAG_METRIC, table_id__in=table_ids
        ).values("table_id", "field_name")
        table_id_fields = {}
        for data in table_id_fields_qs:
            table_id_fields.setdefault(data["table_id"], []).append(data["field_name"])
        # 根据 option 过滤是否有开启黑名单，如果开启黑名单，则指标会有过期时间
        white_tables = set(
            models.ResultTableOption.objects.filter(
                table_id__in=table_ids,
                name=models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST,
                value="false",
            ).values_list("table_id", flat=True)
        )
        logger.info("white table_id list: %s", json.dumps(white_tables))

        # 剩余的结果表，需要判断是否时序的，然后根据过期时间过滤数据
        table_id_set = table_ids - white_tables
        ts_info = self._filter_ts_info(table_id_set)
        table_id_ts_group_id = ts_info.get("table_id_ts_group_id") or {}
        group_id_field_map = ts_info.get("group_id_field_map") or {}
        # 组装结果表对应的指标数据
        # _exist_table_id_list 用来标识结果表已经存在
        table_id_metrics, _exist_table_id_list = {}, []
        # 如果指标为空，也需要记录结果表
        for table_id, group_id in table_id_ts_group_id.items():
            table_id_metrics[table_id] = group_id_field_map.get(group_id) or []
            _exist_table_id_list.append(table_id)
        # 处理非时序结果表指标
        table_id_metrics.update(
            {
                table_id: table_id_fields[table_id]
                for table_id in table_id_fields
                if table_id not in _exist_table_id_list
            }
        )

        return table_id_metrics
