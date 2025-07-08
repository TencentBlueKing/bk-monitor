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
import json
import logging

from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now as tz_now

from constants.common import DEFAULT_TENANT_ID
from metadata import models
from metadata.models.constants import DEFAULT_MEASUREMENT
from metadata.models.space import utils
from metadata.models.space.constants import (
    ALL_SPACE_TYPE_TABLE_ID_LIST,
    BKCI_1001_TABLE_ID_PREFIX,
    BKCI_SYSTEM_TABLE_ID_PREFIX,
    DATA_LABEL_TO_RESULT_TABLE_CHANNEL,
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    DBM_1001_TABLE_ID_PREFIX,
    P4_1001_TABLE_ID_PREFIX,
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
from metadata.models.space.utils import (
    get_biz_ids_by_space_ids,
    get_related_spaces,
    reformat_table_id,
    update_filters_with_alias,
)
from metadata.utils.db import filter_model_by_in_page, filter_query_set_by_in_page
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class SpaceTableIDRedis:
    """
    空间路由结果表数据推送 redis 相关功能
    多租户环境下,不允许跨租户推送路由,即每次操作的目标数据,必须是同一租户下的,不能跨租户
    """

    def push_space_table_ids(self, space_type: str, space_id: str, is_publish: bool | None = False):
        """
        推送空间及对应的结果表和过滤条件
        多租户环境下,需要统一在table_id后拼接租户ID
        """
        logger.info("start to push space table_id data, space_type: %s, space_id: %s", space_type, space_id)
        # NOTE: 为防止 space_id 传递非字符串，转换一次
        space_id = str(space_id)

        space = models.Space.objects.get(space_type_id=space_type, space_id=space_id)
        bk_tenant_id = space.bk_tenant_id

        # 过滤空间关联的数据源信息
        if space_type == SpaceTypes.BKCC.value:
            redis_values = self._compose_bkcc_space_table_ids(space)
        elif space_type == SpaceTypes.BKCI.value:
            # 开启容器服务，则需要处理集群+业务+构建机+其它(在当前空间下创建的插件、自定义上报等)
            redis_values = self._compose_bkci_space_table_ids(space)
        elif space_type == SpaceTypes.BKSAAS.value:
            redis_values = self._compose_bksaas_space_table_ids(space)
        else:
            logger.error("not found space_type: %s, space_id: %s", space_type, space_id)
            raise ValueError("not found space type")

        # 二段式校验&补充
        values_to_redis = {}
        for key, value in redis_values.items():
            key = reformat_table_id(key)
            if settings.ENABLE_MULTI_TENANT_MODE:
                # 若开启多租户模式,需要增加租户ID后缀
                key = f"{key}|{bk_tenant_id}"
            values_to_redis[key] = value

        # 组装redis key
        if settings.ENABLE_MULTI_TENANT_MODE:
            space_redis_key = f"{space_type}__{space_id}|{bk_tenant_id}"
        else:
            space_redis_key = f"{space_type}__{space_id}"

        # 推送数据
        if values_to_redis:
            RedisTools.hmset_to_redis(SPACE_TO_RESULT_TABLE_KEY, {space_redis_key: json.dumps(values_to_redis)})

        logger.info(
            "push redis space_to_result_table, space_type: %s, space_id: %s",
            space_type,
            space_id,
        )

        # 通知使用方
        if is_publish:
            RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, [space_redis_key])
        logger.info("push space table_id data successfully, space_type: %s, space_id: %s", space_type, space_id)

    def push_multi_space_table_ids(self, spaces: list[models.Space], is_publish: bool | None = False) -> None:
        """
        批量推送空间数据
        """
        # 推送数据
        for space in spaces:
            self.push_space_table_ids(space.space_type_id, space.space_id, is_publish=False)

        # 通知使用方
        if is_publish:
            push_redis_keys = []
            for space in spaces:
                if settings.ENABLE_MULTI_TENANT_MODE:
                    push_redis_keys.append(f"{space.space_type_id}__{space.space_id}|{space.bk_tenant_id}")
                else:
                    push_redis_keys.append(f"{space.space_type_id}__{space.space_id}")
            RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, push_redis_keys)

    def push_data_label_table_ids(
        self,
        data_label_list: list | None = None,
        table_id_list: list | None = None,
        is_publish: bool | None = False,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ):
        """推送 data_label 及对应的结果表"""
        logger.info(
            "start to push data_label table_id data, data_label_list: %s, table_id_list: %s, is_publish: %s,"
            "bk_tenant_id: %s",
            json.dumps(data_label_list),
            json.dumps(table_id_list),
            is_publish,
            bk_tenant_id,
        )
        data_labels = self._refine_available_data_label(
            table_id_list=table_id_list, data_label_list=data_label_list, bk_tenant_id=bk_tenant_id
        )

        # 如果data_labels为空，则直接返回
        if not data_labels:
            return logger.info("push redis data_label_to_result_table")

        # 组装data_label查询条件
        data_label_query = Q(data_label__contains=data_labels[0])
        for data_label in data_labels[1:]:
            data_label_query |= Q(data_label__contains=data_label)

        # 通过data_label查询结果表
        rt_dl_qs = models.ResultTable.objects.filter(
            data_label_query,
            is_deleted=False,
            is_enable=True,
            bk_tenant_id=bk_tenant_id,
        ).values("table_id", "data_label")

        # 组装数据
        rt_dl_map = {}
        for data in rt_dl_qs:
            # data_label可能存在逗号分割，需要拆分
            # 部分data_label可能不在data_labels中，需要过滤
            for data_label in data["data_label"].split(","):
                if not data_label or data_label not in data_labels:
                    continue
                rt_dl_map.setdefault(data_label, []).append(data["table_id"])

        # 若开启多租户模式,则data_label和table_id都需要在前面拼接bk_tenant_id
        if settings.ENABLE_MULTI_TENANT_MODE:
            rt_dl_map = {
                f"{data_label}|{bk_tenant_id}": [f"{table_id}|{bk_tenant_id}" for table_id in table_ids]
                for data_label, table_ids in rt_dl_map.items()
            }

        redis_values = {}
        if rt_dl_map:
            redis_values = {
                data_label: json.dumps([reformat_table_id(table_id) for table_id in table_ids])
                for data_label, table_ids in rt_dl_map.items()
            }

        if redis_values:
            RedisTools.hmset_to_redis(DATA_LABEL_TO_RESULT_TABLE_KEY, redis_values)
            if is_publish:
                RedisTools.publish(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, list(rt_dl_map.keys()))

        logger.info("push redis data_label_to_result_table")

    def push_es_table_id_detail(
        self,
        table_id_list: list | None = None,
        is_publish: bool | None = True,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ):
        """
        推送ES结果表的详情信息至RESULT_TABLE_DETAIL路由
        @param table_id_list: 结果表列表
        @param is_publish: 是否执行推送
        @param bk_tenant_id: 租户ID
        """
        logger.info(
            "push_es_table_id_detail： start to push table_id detail data, table_id_list: %sis_publish->[%s],"
            "bk_tenant_id->[%s]",
            json.dumps(table_id_list),
            is_publish,
            bk_tenant_id,
        )
        _table_id_detail: dict[str, dict] = {}
        try:
            _table_id_detail.update(
                self._compose_es_table_id_detail(table_id_list=table_id_list, bk_tenant_id=bk_tenant_id)
            )

            if _table_id_detail:
                logger.info(
                    "push_es_table_id_detail: table_id_list->[%s] got detail->[%s],try to set to key->[%s]",
                    table_id_list,
                    json.dumps(_table_id_detail),
                    RESULT_TABLE_DETAIL_KEY,
                )
                updated_table_id_detail: dict[str, dict] = {}
                for key, value in _table_id_detail.items():
                    parts = key.split(".")  # 通过 "." 分割 key
                    if len(parts) == 1:
                        logger.info(
                            "push_es_table_id_detail: key(table_id)->[%s] is missing '.', adding '.__default__'", key
                        )
                        # 如果分割结果长度为 1，补充 ".__default__"
                        new_key = f"{key}.__default__"
                        updated_table_id_detail[new_key] = value
                    elif len(parts) == 2:
                        # 如果分割结果长度为 2，保持原样
                        updated_table_id_detail[key] = value
                    else:
                        # 如果分割结果长度超过 2，打印错误日志
                        logger.error(
                            "push_es_table_id_detail: key(table_id)->[%s] is invalid, contains too many dots", key
                        )

                # 更新 _table_id_detail
                _table_id_detail = updated_table_id_detail

                # 若开启多租户模式,则在table_id前拼接bk_tenant_id
                if settings.ENABLE_MULTI_TENANT_MODE:
                    logger.info(
                        "push_es_table_id_detail: enable multi tenant mode,will append bk_tenant_id->[%s]",
                        bk_tenant_id,
                    )
                    for key in list(_table_id_detail.keys()):
                        table_detail = _table_id_detail.pop(key)
                        if table_detail.get("data_label"):
                            table_detail["data_label"] = ",".join(
                                [f"{dl}|{bk_tenant_id}" for dl in table_detail["data_label"].split(",") if dl]
                            )
                        _table_id_detail[f"{key}|{bk_tenant_id}"] = table_detail

                RedisTools.hmset_to_redis(
                    RESULT_TABLE_DETAIL_KEY, {key: json.dumps(value) for key, value in _table_id_detail.items()}
                )
                if is_publish:
                    logger.info(
                        "push_es_table_id_detail: table_id_list->[%s] got detail->[%s],try to push into channel->[%s]",
                        table_id_list,
                        json.dumps(_table_id_detail),
                        RESULT_TABLE_DETAIL_CHANNEL,
                    )
                    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(_table_id_detail.keys()))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "push_es_table_id_detail: failed to push es_table_detail for table_id_list->[%s],error->[%s]",
                table_id_list,
                e,
            )
            return
        logger.info("push_es_table_id_detail: push es_table_detail for table_id_list->[%s] successfully", table_id_list)

    def _compose_doris_table_id_detail(
        self, bk_tenant_id: str, table_id_list: list[str] | None = None
    ) -> dict[str, dict]:
        """组装doris结果表的详情"""
        logger.info(
            "_compose_doris_table_id_detail:start to compose doris table_id detail data,table_id_list->[%s]",
            table_id_list,
        )
        if table_id_list:
            doris_records = models.DorisStorage.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id)
            data_label_map = models.ResultTable.objects.filter(
                table_id__in=table_id_list, bk_tenant_id=bk_tenant_id
            ).values("table_id", "data_label")
        else:
            doris_records = models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id)
            tids = list(doris_records.values_list("table_id", flat=True))
            data_label_map = models.ResultTable.objects.filter(table_id__in=tids, bk_tenant_id=bk_tenant_id).values(
                "table_id", "data_label"
            )

        data_label_map_dict = {item["table_id"]: item["data_label"] for item in data_label_map}

        data: dict[str, dict] = {}
        for record in doris_records:
            db = record.bkbase_table_id
            table_id = record.table_id
            data_label = data_label_map_dict.get(table_id, "")

            data[table_id] = {
                "db": db,
                "measurement": models.ClusterInfo.TYPE_DORIS,
                "storage_type": "bk_sql",
                "data_label": data_label,
            }
        return data

    def push_doris_table_id_detail(
        self, bk_tenant_id: str, table_id_list: list | None = None, is_publish: bool | None = True
    ):
        """
        推送Doris结果表详情路由
        @param bk_tenant_id: 租户ID
        @param table_id_list: 结果表列表
        @param is_publish: 是否执行推送
        """
        logger.info(
            "push_doris_table_id_detail: try to push doris_table_id_detail for table_id_list->[%s]", table_id_list
        )

        _table_id_detail = {}
        try:
            _table_id_detail.update(self._compose_doris_table_id_detail(bk_tenant_id, table_id_list))

            if _table_id_detail:
                logger.info(
                    "push_doris_table_id_detail: table_id_list->[%s], got table_id_detail->[%s]",
                    table_id_list,
                    json.dumps(_table_id_detail),
                )
                updated_table_id_detail = {}
                for key, value in _table_id_detail.items():
                    parts = key.split(".")  # 通过 "." 分割 key
                    if len(parts) == 1:
                        logger.info(
                            "push_doris_table_id_detail: key(table_id)->[%s] is missing '.', adding '.__default__'", key
                        )
                        # 如果分割结果长度为 1，补充 ".__default__"
                        new_key = f"{key}.__default__"
                        updated_table_id_detail[new_key] = value
                    elif len(parts) == 2:
                        # 如果分割结果长度为 2，保持原样
                        updated_table_id_detail[key] = value
                    else:
                        # 如果分割结果长度超过 2，打印错误日志
                        logger.error(
                            "push_doris_table_id_detail: key(table_id)->[%s] is invalid, contains too many dots", key
                        )

                # 更新 _table_id_detail
                _table_id_detail = updated_table_id_detail

                # 若开启多租户模式,则在table_id前拼接bk_tenant_id
                if settings.ENABLE_MULTI_TENANT_MODE:
                    logger.info(
                        "push_es_table_id_detail: enable multi tenant mode,will append bk_tenant_id->[%s]",
                        bk_tenant_id,
                    )
                    for key in list(_table_id_detail.keys()):
                        _table_id_detail[f"{key}|{bk_tenant_id}"] = _table_id_detail.pop(key)
                        if _table_id_detail[f"{key}|{bk_tenant_id}"].get("data_label"):
                            _table_id_detail[f"{key}|{bk_tenant_id}"]["data_label"] = ",".join(
                                [
                                    f"{dl}|{bk_tenant_id}"
                                    for dl in _table_id_detail[f"{key}|{bk_tenant_id}"]["data_label"].split(",")
                                    if dl
                                ]
                            )

                RedisTools.hmset_to_redis(
                    RESULT_TABLE_DETAIL_KEY, {key: json.dumps(value) for key, value in _table_id_detail.items()}
                )
                if is_publish:
                    logger.info(
                        "push_doris_table_id_detail: table_id_list->[%s] got detail->[%s],try to push into channel->["
                        "%s]",
                        table_id_list,
                        json.dumps(_table_id_detail),
                        RESULT_TABLE_DETAIL_CHANNEL,
                    )
                    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(_table_id_detail.keys()))

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "push_doris_table_id_detail: failed to push doris_table_detail for table_id_list->[%s],error->[%s]",
                table_id_list,
                e,
            )
            return
        logger.info(
            "push_doris_table_id_detail: push doris_table_detail for table_id_list->[%s] successfully", table_id_list
        )

    def _compose_bkbase_table_id_detail(
        self, bk_tenant_id: str, table_id_list: list[str] | None = None
    ) -> dict[str, dict]:
        """
        组装计算平台结果表详情
        """
        logger.info(
            "_compose_bkbase_table_id_detail: start to compose bkbase table id detail,table_id_list->[%s] ",
            table_id_list,
        )
        bkbase_rt_records = models.ResultTable.objects.filter(default_storage=models.ClusterInfo.TYPE_BKDATA)
        if table_id_list:
            bkbase_rt_records = bkbase_rt_records.filter(table_id__in=table_id_list)

        data = {}
        table_id_list = list(bkbase_rt_records.values_list("table_id", flat=True))
        all_fields = self._compose_table_id_fields(bk_tenant_id=bk_tenant_id, table_ids=set(table_id_list))
        for record in bkbase_rt_records:
            # table_id: 2_bkbase_test_metric.__default__ 在计算平台实际的物理表为 2_bkbase_test_metric
            db = record.table_id.split(".")[0]  # 计算平台实际的物理表名为二段式的第一部分
            fields = all_fields.get(record.table_id) or []
            data[record.table_id] = {
                "db": db,
                "measurement": "",  # 现阶段不关注存储类型
                "storage_type": "bk_sql",
                "data_label": record.data_label,
                "fields": fields,
            }

        return data

    def push_bkbase_table_id_detail(
        self, bk_tenant_id: str, table_id_list: list | None = None, is_publish: bool | None = True
    ):
        """
        推送BkBase结果表详情路由
        @param bk_tenant_id: 租户ID
        @param table_id_list: 结果表列表
        @param is_publish: 是否执行推送
        """
        logger.info(
            "push_bkbase_table_id_detail: try to push bkbase_table_id_detail for table_id_list->[%s]", table_id_list
        )

        _table_id_detail: dict[str, dict] = {}
        try:
            _table_id_detail.update(
                self._compose_bkbase_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=table_id_list)
            )

            if _table_id_detail:
                logger.info(
                    "push_bkbase_table_id_detail: table_id_list->[%s], got table_id_detail->[%s]",
                    table_id_list,
                    json.dumps(_table_id_detail),
                )
                updated_table_id_detail: dict[str, dict] = {}
                for key, value in _table_id_detail.items():
                    parts = key.split(".")  # 通过 "." 分割 key
                    if len(parts) == 1:
                        logger.info(
                            "push_bkbase_table_id_detail: key(table_id)->[%s] is missing '.', adding '.__default__'",
                            key,
                        )
                        # 如果分割结果长度为 1，补充 ".__default__"
                        new_key = f"{key}.__default__"
                        updated_table_id_detail[new_key] = value
                    elif len(parts) == 2:
                        # 如果分割结果长度为 2，保持原样
                        updated_table_id_detail[key] = value
                    else:
                        # 如果分割结果长度超过 2，打印错误日志
                        logger.error(
                            "push_doris_table_id_detail: key(table_id)->[%s] is invalid, contains too many dots", key
                        )

                # 更新 _table_id_detail
                _table_id_detail = updated_table_id_detail

                # 若开启多租户模式,则在table_id前拼接bk_tenant_id
                if settings.ENABLE_MULTI_TENANT_MODE:
                    logger.info(
                        "push_bkbase_table_id_detail: enable multi tenant mode,will append bk_tenant_id->[%s]",
                        bk_tenant_id,
                    )
                    for key in list(_table_id_detail.keys()):
                        _table_id_detail[f"{key}|{bk_tenant_id}"] = _table_id_detail.pop(key)
                        if _table_id_detail[f"{key}|{bk_tenant_id}"].get("data_label"):
                            _table_id_detail[f"{key}|{bk_tenant_id}"]["data_label"] = ",".join(
                                [
                                    f"{dl}|{bk_tenant_id}"
                                    for dl in _table_id_detail[f"{key}|{bk_tenant_id}"]["data_label"].split(",")
                                    if dl
                                ]
                            )

                RedisTools.hmset_to_redis(
                    RESULT_TABLE_DETAIL_KEY, {key: json.dumps(value) for key, value in _table_id_detail.items()}
                )
                if is_publish:
                    logger.info(
                        "push_bkbase_table_id_detail: table_id_list->[%s] got detail->[%s],try to push into channel->["
                        "%s]",
                        table_id_list,
                        json.dumps(_table_id_detail),
                        RESULT_TABLE_DETAIL_CHANNEL,
                    )
                    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(_table_id_detail.keys()))

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "push_bkbase_table_id_detail: failed to push bkbase_table_detail for table_id_list->[%s],error->[%s]",
                table_id_list,
                e,
            )
            return
        logger.info(
            "push_bkbase_table_id_detail: push bkbase_table_detail for table_id_list->[%s] successfully", table_id_list
        )

    def push_table_id_detail(
        self,
        table_id_list: list | None = None,
        is_publish: bool | None = False,
        include_es_table_ids: bool | None = False,
        bk_tenant_id: str = DEFAULT_TENANT_ID,
    ):
        """推送结果表的详细信息"""
        logger.info(
            "push_table_id_detail： start to push table_id detail data, table_id_list: %s,is_publish->[%s],"
            "include_es_table_ids->[%s]",
            json.dumps(table_id_list),
            is_publish,
            include_es_table_ids,
        )
        # TODO：待AccessVMRecord全量迁移至BkBaseResultTable后，实施改造，使用新版组装方式

        table_id_detail = get_table_info_for_influxdb_and_vm(table_id_list=table_id_list, bk_tenant_id=bk_tenant_id)

        if not table_id_detail and not include_es_table_ids:  # 当指标结果表详情路由为空且不包含ES结果表的话,提前返回
            logger.info(
                "push_table_id_detail: table_id_list: %s not found table from influxdb or vm", json.dumps(table_id_list)
            )
            return

        table_ids = set(table_id_detail.keys())

        other_filter = None
        if settings.ENABLE_MULTI_TENANT_MODE:
            other_filter = {
                "bk_tenant_id": bk_tenant_id,
            }

        # 获取结果表类型
        _rt_filter_data = filter_model_by_in_page(
            model=models.ResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "schema_type", "data_label"],
            other_filter=other_filter,
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
            other_filter=other_filter,
        )

        table_id_data_id = {drt["table_id"]: drt["bk_data_id"] for drt in _ds_rt_filter_data}

        # 获取结果表对应的类型
        measurement_type_dict = get_measurement_type_by_table_id(
            table_ids, _table_list, table_id_data_id, bk_tenant_id=bk_tenant_id
        )

        table_id_cluster_id = get_table_id_cluster_id(table_id_list=table_ids, bk_tenant_id=bk_tenant_id)
        # 再追加上结果表的指标数据、集群 ID、类型
        table_id_fields = self._compose_table_id_fields(
            table_ids=set(table_id_detail.keys()), bk_tenant_id=bk_tenant_id
        )
        _table_id_detail: dict[str, dict] = {}
        for table_id, detail in table_id_detail.items():
            detail["fields"] = table_id_fields.get(table_id) or []
            detail["measurement_type"] = measurement_type_dict.get(table_id) or ""
            detail["bcs_cluster_id"] = table_id_cluster_id.get(table_id) or ""
            detail["data_label"] = _table_id_dict.get(table_id, {}).get("data_label") or ""
            detail["bk_data_id"] = table_id_data_id.get(table_id, 0)
            _table_id_detail[table_id] = detail

        # 追加预计算结果表详情
        # TODO: BkBase 多租户
        _table_id_detail.update(self._compose_record_rule_table_id_detail())

        # 追加 es 结果表
        if include_es_table_ids:
            _table_id_detail.update(
                self._compose_es_table_id_detail(table_id_list=table_id_list, bk_tenant_id=bk_tenant_id)
            )

        # 若开启多租户模式,则在table_id前拼接bk_tenant_id
        if settings.ENABLE_MULTI_TENANT_MODE:
            logger.info("push_table_id_detail: enable multi tenant mode,will append bk_tenant_id->[%s]", bk_tenant_id)
            for key in list(_table_id_detail.keys()):
                table_detail = _table_id_detail.pop(key)
                if table_detail.get("data_label"):
                    table_detail["data_label"] = ",".join(
                        [f"{dl}|{bk_tenant_id}" for dl in table_detail["data_label"].split(",") if dl]
                    )
                _table_id_detail[f"{key}|{bk_tenant_id}"] = table_detail

        # 推送数据
        if _table_id_detail:
            logger.info(
                "push_table_id_detail: try to set to key->[%s] with value->[%s]",
                RESULT_TABLE_DETAIL_KEY,
                json.dumps(_table_id_detail),
            )
            RedisTools.hmset_to_redis(
                RESULT_TABLE_DETAIL_KEY, {key: json.dumps(value) for key, value in _table_id_detail.items()}
            )
            if is_publish:
                logger.info(
                    "push_table_id_detail: try to push into channel->[%s] for ->[%s]",
                    RESULT_TABLE_DETAIL_CHANNEL,
                    list(_table_id_detail.keys()),
                )
                RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(_table_id_detail.keys()))
        logger.info("push_table_id_detail： push redis result_table_detail")

    # TODO: BkBase多租户 -- 预计算结果表多租户
    def _compose_record_rule_table_id_detail(self) -> dict[str, dict]:
        """组装预计算结果表的详情"""
        from metadata.models.record_rule.rules import RecordRule

        record_rule_objs = RecordRule.objects.values("table_id", "vm_cluster_id", "dst_vm_table_id", "rule_metrics")
        vm_cluster_id_name = {
            cluster["cluster_id"]: cluster["cluster_name"]
            for cluster in models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM).values(
                "cluster_id", "cluster_name"
            )
        }
        _table_id_detail: dict[str, dict] = {}
        for obj in record_rule_objs:
            _table_id_detail[obj["table_id"]] = {
                "vm_rt": obj["dst_vm_table_id"],
                "storage_id": obj["vm_cluster_id"],
                "cluster_name": "",
                "storage_name": vm_cluster_id_name.get(obj["vm_cluster_id"], ""),
                "db": "",
                "measurement": "",
                "tags_key": [],
                "fields": list(obj["rule_metrics"].values()),
                "measurement_type": "bk_split_measurement",
                "bcs_cluster_id": "",
                "data_label": "",
                "storage_type": models.RecordRule.STORAGE_TYPE,
                "bk_data_id": None,
            }

        return _table_id_detail

    def _get_field_alias_map(self, table_id_list: list[str], bk_tenant_id: str | None = DEFAULT_TENANT_ID):
        """
        构建字段别名映射map
        @param table_id_list: 结果表列表
        @param bk_tenant_id: 租户ID
        @return: 字段别名映射map
        """
        logger.info(
            "_get_field_alias_map: try to get field alias map,table_id_list->[%s],bk_tenant_id->[%s]",
            table_id_list,
            bk_tenant_id,
        )
        if not table_id_list:
            return {}
        try:
            # 获取指定table_id列表的未删除别名记录
            alias_records = models.ESFieldQueryAliasOption.objects.filter(
                table_id__in=table_id_list, is_deleted=False, bk_tenant_id=bk_tenant_id
            ).values("table_id", "query_alias", "field_path")

            # 按table_id分组构建别名映射
            field_alias_map = {}
            for record in alias_records:
                table_id = record["table_id"]
                query_alias = record["query_alias"]
                field_path = record["field_path"]

                if table_id not in field_alias_map:
                    field_alias_map[table_id] = {}

                field_alias_map[table_id][query_alias] = field_path

            logger.info("Field alias map generated: %s", field_alias_map)
            return field_alias_map

        except Exception as e:
            logger.error(
                "_get_field_alias_map:Error getting field alias map for table_ids: %s, error: %s",
                table_id_list,
                str(e),
                exc_info=True,
            )
            # 发生错误时返回空字典，确保不影响主流程
            return {}

    def _compose_es_table_id_detail(
        self, table_id_list: list[str] | None = None, bk_tenant_id: str = DEFAULT_TENANT_ID
    ) -> dict[str, dict]:
        """组装 es 结果表的详细信息"""
        logger.info("start to compose es table_id detail data")
        # 这里要过来的结果表不会太多
        if table_id_list:
            table_ids = models.ESStorage.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id).values(
                "table_id", "storage_cluster_id", "source_type", "index_set"
            )
            # 查询结果表选项
            tid_options = models.ResultTableOption.objects.filter(
                table_id__in=table_id_list, bk_tenant_id=bk_tenant_id
            ).values("table_id", "name", "value", "value_type")
            data_label_map = models.ResultTable.objects.filter(
                table_id__in=table_id_list, bk_tenant_id=bk_tenant_id
            ).values("table_id", "data_label")
            # 构建字段别名map
            field_alias_map = self._get_field_alias_map(table_id_list, bk_tenant_id)
        else:
            table_ids = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id).values(
                "table_id",
                "storage_cluster_id",
                "source_type",
                "index_set",
            )
            tids = [obj["table_id"] for obj in table_ids]
            tid_options = models.ResultTableOption.objects.filter(table_id__in=tids, bk_tenant_id=bk_tenant_id).values(
                "table_id", "name", "value", "value_type"
            )
            data_label_map = models.ResultTable.objects.filter(table_id__in=tids, bk_tenant_id=bk_tenant_id).values(
                "table_id", "data_label"
            )
            # 构建字段别名map
            field_alias_map = self._get_field_alias_map(tids, bk_tenant_id)

        # data_label字典 {table_id:data_label}
        data_label_map_dict = {item["table_id"]: item["data_label"] for item in data_label_map}
        tid_options_map = {}
        for option in tid_options:
            try:
                _option = (
                    {option["name"]: option["value"]}
                    if option["value_type"] == models.ResultTableOption.TYPE_STRING
                    else {option["name"]: json.loads(option["value"])}
                )
            except Exception:
                _option = {}

            tid_options_map.setdefault(option["table_id"], {}).update(_option)

        # 组装数据
        # NOTE: 这里针对一段式的追加一个`__default__`
        # 组装需要的数据，字段相同
        data = {}
        for record in table_ids:
            source_type = record["source_type"]
            index_set = record["index_set"]
            tid = record["table_id"]
            storage_id = record.get("storage_cluster_id", 0)
            table_id_db = index_set

            try:
                storage_record = models.StorageClusterRecord.compose_table_id_storage_cluster_records(
                    table_id=tid, bk_tenant_id=bk_tenant_id
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("get table_id storage cluster record failed, table_id: %s, error: %s", tid, e)
                storage_record = []

            # 索引集，直接按照存储进行路由
            data[tid] = {
                "storage_id": storage_id,
                "db": table_id_db,
                "measurement": DEFAULT_MEASUREMENT,
                "source_type": source_type,
                "options": tid_options_map.get(tid) or {},
                "storage_type": models.ESStorage.STORAGE_TYPE,
                "storage_cluster_records": storage_record,
                "data_label": data_label_map_dict.get(tid, ""),
                "field_alias": field_alias_map.get(tid, {}),  # 字段查询别名
            }

        return data

    def _compose_bkcc_space_table_ids(
        self,
        space: models.Space,
        from_authorization: bool | None = None,
    ) -> dict[str, dict[str, dict]]:
        """推送 bkcc 类型空间数据"""

        bk_tenant_id: str = space.bk_tenant_id
        space_type: str = space.space_type_id
        space_id: str = space.space_id

        logger.info("start to push bkcc space table_id, space_type: %s, space_id: %s", space_type, space_id)
        logger.info(
            "_push_bkcc_space_table_ids: space_type->[%s],space_id->[%s],bk_tenant_id->[%s]",
            space_type,
            space_id,
            bk_tenant_id,
        )

        _values = self._compose_data(
            space_type=space_type, space_id=space_id, from_authorization=from_authorization, bk_tenant_id=bk_tenant_id
        )

        # 追加预计算结果表
        _values.update(
            self._compose_record_rule_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )

        # 追加ES结果表
        _values.update(self._compose_es_table_ids(space_type, space_id))
        # 追加Doris结果表
        _values.update(self._compose_doris_table_ids(space_type, space_id))
        _values.update(self._compose_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id))

        # 追加关联的BKCI的ES结果表，适配ES多空间功能
        _values.update(
            self._compose_related_bkci_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )

        # 替换自定义过滤条件别名
        _values = update_filters_with_alias(space_type=space_type, space_id=space_id, values=_values)
        return _values

    def _compose_bkci_space_table_ids(
        self,
        space: models.Space,
    ) -> dict[str, dict[str, dict]]:
        """推送 bcs 类型空间下的关联业务的数据"""
        space_type: str = space.space_type_id
        space_id: str = space.space_id
        bk_tenant_id: str = space.bk_tenant_id
        logger.info("start to push biz of bcs space table_id, space_type: %s, space_id: %s", space_type, space_id)

        _values = self._compose_bcs_space_biz_table_ids(
            space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id
        )
        _values.update(self._compose_bcs_space_cluster_table_ids(space_type, space_id))
        _values.update(
            self._compose_bkci_level_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(
            self._compose_bkci_other_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )

        # 追加跨空间类型的数据源授权
        _values.update(self._compose_bkci_cross_table_ids(space_type, space_id))

        # 追加特殊的允许全空间使用的数据源
        _values.update(self._compose_all_type_table_ids(space_type, space_id))
        _values.update(
            self._compose_record_rule_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(self._compose_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id))
        # 追加Doris结果表
        _values.update(self._compose_doris_table_ids(space_type, space_id))
        # APM 真全局数据
        _values.update(self._compose_apm_all_type_table_ids(space_type, space_id))

        # 替换自定义过滤条件别名
        _values = update_filters_with_alias(space_type=space_type, space_id=space_id, values=_values)
        return _values

    def _compose_bksaas_space_table_ids(
        self,
        space: models.Space,
        table_id_list: list | None = None,
    ) -> dict[str, dict[str, dict]]:
        """推送 bksaas 类型空间下的数据"""
        space_type: str = space.space_type_id
        space_id: str = space.space_id
        bk_tenant_id: str = space.bk_tenant_id
        logger.info("start to push bksaas space table_id, space_type: %s, space_id: %s", space_type, space_id)

        _values = self._compose_bksaas_space_cluster_table_ids(
            space_type=space_type, space_id=space_id, table_id_list=table_id_list, bk_tenant_id=bk_tenant_id
        )

        # 获取蓝鲸应用使用的集群数据
        _values.update(
            self._compose_bksaas_other_table_ids(
                space_type=space_type, space_id=space_id, table_id_list=table_id_list, bk_tenant_id=bk_tenant_id
            )
        )
        # 追加特殊的允许全空间使用的数据源
        _values.update(self._compose_all_type_table_ids(space_type, space_id))
        _values.update(
            self._compose_record_rule_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(self._compose_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id))
        # 追加Doris结果表
        _values.update(self._compose_doris_table_ids(space_type, space_id))
        # APM 真全局数据
        _values.update(self._compose_apm_all_type_table_ids(space_type, space_id))
        # 替换自定义过滤条件别名
        _values = update_filters_with_alias(space_type=space_type, space_id=space_id, values=_values)
        return _values

    def _compose_bcs_space_biz_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID) -> dict:
        """推送 bcs 类型关联业务的数据，现阶段包含主机及部分插件信息"""
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
        # 追加空间访问指定插件的 filter
        rts = models.ResultTable.objects.filter(
            Q(table_id__startswith=BKCI_SYSTEM_TABLE_ID_PREFIX) | Q(table_id__in=settings.BKCI_SPACE_ACCESS_PLUGIN_LIST)
        )

        if settings.ENABLE_MULTI_TENANT_MODE:  # 若开启多租户模式,则这里应该会变成新版1001数据
            rts = rts.filter(bk_tenant_id=bk_tenant_id)
        tids = rts.values_list("table_id", flat=True)

        return {tid: {"filters": [{"bk_biz_id": str(obj.resource_id)}]} for tid in tids}

    def _compose_bcs_space_cluster_table_ids(
        self,
        space_type: str,
        space_id: str,
    ) -> dict:
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

    def _compose_bkci_level_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID) -> dict:
        """组装 bkci 全局下的结果表"""
        logger.info("start to push bkci level table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 过滤空间级的数据源
        data_ids = get_platform_data_ids(space_type=space_type, bk_tenant_id=bk_tenant_id)
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
        table_ids = self._refine_table_ids(table_is_list, bk_tenant_id=bk_tenant_id)
        # 组装数据
        for tid in table_ids:
            _values[tid] = {"filters": [{"projectId": space_id}]}

        return _values

    def _compose_bkci_other_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID) -> dict:
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

        table_ids = self._refine_table_ids(table_id_list=list(table_id_data_id.keys()), bk_tenant_id=bk_tenant_id)
        # 组装数据
        for tid in table_ids:
            # NOTE: 现阶段针对1001下 `system.` 或者 `dbm_system.` 开头的结果表不允许被覆盖
            if tid.startswith("system.") or tid.startswith("dbm_system."):
                continue
            _values[tid] = {"filters": []}

        return _values

    # TODO: 多租户改造,新版1001
    def _compose_bkci_cross_table_ids(self, space_type: str, space_id: str) -> dict:
        """组装跨空间类型的结果表数据"""
        logger.info(
            "start to push bkci space cross space_type table_id, space_type: %s, space_id: %s", space_type, space_id
        )
        tids = models.ResultTable.objects.filter(table_id__startswith=BKCI_1001_TABLE_ID_PREFIX).values_list(
            "table_id", flat=True
        )
        # bkci 访问 p4 主机数据对应的结果表
        p4_tids = models.ResultTable.objects.filter(table_id__startswith=P4_1001_TABLE_ID_PREFIX).values_list(
            "table_id", flat=True
        )
        # 组装结果表对应的 filter
        tid_filters = {tid: {"filters": [{"projectId": space_id}]} for tid in tids}
        tid_filters.update({tid: {"filters": [{"devops_id": space_id}]} for tid in p4_tids})
        return tid_filters

    def _compose_all_type_table_ids(self, space_type: str, space_id: str) -> dict:
        """组装非业务类型的全空间类型的结果表数据"""
        logger.info("start to push all space type table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 转换空间对应的bk_biz_id
        try:
            _id = models.Space.objects.get(space_type_id=space_type, space_id=space_id).id
        except models.Space.DoesNotExist:
            return {}
        return {tid: {"filters": [{"bk_biz_id": str(-_id)}]} for tid in ALL_SPACE_TYPE_TABLE_ID_LIST}

    def _compose_apm_all_type_table_ids(self, space_type: str, space_id: str) -> dict:
        """
        APM特殊逻辑--真正的全局数据, filter key使用配置的bk_biz_id_alias，value使用-id
        该方法仅对 BKCI 和 BKSAAS类型生效，BKCC类型走通用路由处理逻辑
        """
        # TODO： 该方法为临时支持，长期需要改造抽象为公共逻辑
        logger.info("start to push apm all space type table_id, space_type: %s, space_id: %s", space_type, space_id)
        try:
            space = models.Space.objects.get(space_type_id=space_type, space_id=space_id)
        except models.Space.DoesNotExist:
            return {}

        result_tables = models.ResultTable.objects.filter(
            table_id__contains="apm_global.precalculate_storage", bk_tenant_id=space.bk_tenant_id
        )
        return {rt.table_id: {"filters": [{rt.bk_biz_id_alias: str(-space.id)}]} for rt in result_tables}

    def _compose_bksaas_space_cluster_table_ids(
        self,
        space_type: str,
        space_id: str,
        table_id_list: list | None = None,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
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
        table_id_data_id = get_result_tables_by_data_ids(
            data_id_list=list(data_id_cluster_id.keys()), table_id_list=table_id_list
        )
        # 组装 filter
        _values = {}
        for tid, data_id in table_id_data_id.items():
            cluster_id = data_id_cluster_id.get(data_id)
            if not cluster_id:
                continue
            # 获取对应的集群及命名空间信息
            _values[tid] = {"filters": cluster_info.get(cluster_id) or []}

        return _values

    def _compose_bksaas_other_table_ids(
        self,
        space_type: str,
        space_id: str,
        table_id_list: list | None = None,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ):
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
            bk_tenant_id=bk_tenant_id,
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
        table_id_list: list | None = None,
        include_platform_data_id: bool | None = True,
        from_authorization: bool | None = None,
        default_filters: list | None = None,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ) -> dict:
        logger.info(
            "_push_bkcc_space_table_ids,start to _compose_data for space_type: %s, space_id: %s,bk_tenant_id: %s",
            space_type,
            space_id,
            bk_tenant_id,
        )
        # 过滤到对应的结果表
        table_id_data_id = get_space_table_id_data_id(
            space_type,
            space_id,
            table_id_list=table_id_list,
            include_platform_data_id=include_platform_data_id,
            from_authorization=from_authorization,
            bk_tenant_id=bk_tenant_id,
        )
        _values = {}
        # 如果为空，返回默认值
        if not table_id_data_id:
            logger.error("space_type: %s, space_id:%s not found table_id and data_id", space_type, space_id)
            return _values

        # 提取仅包含写入 influxdb 和 vm 的结果表
        table_ids = self._refine_table_ids(list(table_id_data_id.keys()), bk_tenant_id=bk_tenant_id)
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

        other_filter = {}
        if settings.ENABLE_MULTI_TENANT_MODE:
            other_filter = {"bk_tenant_id": bk_tenant_id}

        # 判断是否添加过滤条件
        _table_list = filter_model_by_in_page(
            model=models.ResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "schema_type", "data_label", "bk_biz_id_alias"],
            other_filter=other_filter,
        )  # 新增bk_biz_id_alias,部分业务存在自定义过滤规则别名需求，如bk_biz_id -> appid

        # 获取结果表对应的类型
        measurement_type_dict = get_measurement_type_by_table_id(
            table_ids=table_ids, table_list=_table_list, table_id_data_id=table_id_data_id, bk_tenant_id=bk_tenant_id
        )

        # 获取结果表-业务ID过滤别名 字典
        try:
            bk_biz_id_alias_dict = {data["table_id"]: data["bk_biz_id_alias"] for data in _table_list}
        except Exception as e:  # pylint: disable=broad-except
            logger.error("_push_bkcc_space_table_ids: get bk_biz_id_alias error->[%s]", e)
            bk_biz_id_alias_dict = {}

        # 获取空间所属的数据源 ID
        _space_data_ids = models.SpaceDataSource.objects.filter(
            space_type_id=space_type, space_id=space_id, from_authorization=False
        ).values_list("bk_data_id", flat=True)
        for tid in table_ids:
            # NOTE: 特殊逻辑，忽略跨空间类型的 bkci 的结果表; 如果有其它，再提取为常量
            if tid.startswith(BKCI_1001_TABLE_ID_PREFIX):
                continue

            # NOTE: 特殊逻辑，针对 `dbm_system` 开头的结果表，开放给DBM业务访问全量数据
            space_uid = f"{space_type}__{space_id}"
            if tid.startswith(DBM_1001_TABLE_ID_PREFIX) and space_uid in settings.ACCESS_DBM_RT_SPACE_UID:
                logger.info("table_id->[%s] is dbm_system, open to all for dbm space->[%s]", tid, space_uid)
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
            bk_biz_id_alias = bk_biz_id_alias_dict.get(tid, "")  # 获取业务ID别名
            # 拼装过滤条件, 如果有指定，则按照指定数据设置过滤条件
            if default_filters:
                _values[tid] = {"filters": default_filters}
            else:
                filters = []
                if self._is_need_filter_for_bkcc(
                    measurement_type, space_type, space_id, _data_id_detail, is_exist_space
                ):
                    bk_biz_id_key = "bk_biz_id"  # 默认按照业务ID过滤
                    if bk_biz_id_alias:  # 若存在业务ID别名，按照别名组装过滤条件
                        logger.info(
                            "_push_bkcc_space_table_ids: table_id->[%s] got bk_biz_id_alias ->[%s]",
                            tid,
                            bk_biz_id_alias,
                        )
                        bk_biz_id_key = bk_biz_id_alias
                    filters = [{bk_biz_id_key: space_id}]

                _values[tid] = {"filters": filters}

        return _values

    def _compose_record_rule_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID):
        """组装预计算的结果表"""
        from metadata.models.record_rule.rules import RecordRule

        logger.info(
            "_compose_record_rule_table_ids: space_type->[%s],space_id->[%s],bk_tenant_id->[%s]",
            space_type,
            space_id,
            bk_tenant_id,
        )
        objs = RecordRule.objects.filter(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        return {obj.table_id: {"filters": []} for obj in objs}

    def _compose_es_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID):
        """组装es的结果表"""
        biz_id = models.Space.objects.get_biz_id_by_space(space_type, space_id)
        tids = models.ResultTable.objects.filter(
            bk_biz_id=biz_id,
            default_storage=models.ClusterInfo.TYPE_ES,
            is_deleted=False,
            is_enable=True,
            bk_tenant_id=bk_tenant_id,
        ).values_list("table_id", flat=True)
        return {tid: {"filters": []} for tid in tids}

    def _compose_doris_table_ids(self, space_type: str, space_id: str):
        """
        组装Doris链路结果表
        """
        biz_id = models.Space.objects.get_biz_id_by_space(space_type, space_id)
        tids = models.ResultTable.objects.filter(
            bk_biz_id=biz_id, default_storage=models.ClusterInfo.TYPE_DORIS, is_deleted=False, is_enable=True
        ).values_list("table_id", flat=True)
        return {tid: {"filters": []} for tid in tids}

    def _compose_related_bkci_es_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        组装关联的BKCI类型的ES结果表
        """
        logger.info(
            "_compose_related_bkci_es_table_ids: space_type->[%s],space_id->[%s],bk_tenant_id->[%s]",
            space_type,
            space_id,
            bk_tenant_id,
        )

        space_ids = get_related_spaces(
            space_type_id=space_type, space_id=space_id, target_space_type_id=SpaceTypes.BKCI.value
        )
        biz_ids = get_biz_ids_by_space_ids(SpaceTypes.BKCI.value, space_ids)

        tids = models.ResultTable.objects.filter(
            bk_biz_id__in=biz_ids,
            default_storage=models.ClusterInfo.TYPE_ES,
            is_deleted=False,
            is_enable=True,
            bk_tenant_id=bk_tenant_id,
        ).values_list("table_id", flat=True)

        return {tid: {"filters": []} for tid in tids}

    def _is_need_filter_for_bkcc(
        self,
        measurement_type: str,
        space_type: str,
        space_id: str,
        data_id_detail: dict | None = None,
        is_exist_space: bool | None = True,
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

        is_platform_data_id = data_id_detail["is_platform_data_id"]
        # 对自定义插件的处理，兼容黑白名单对类型的更改
        # 黑名单时，会更改为单指标单表
        if is_platform_data_id and (
            measurement_type == MeasurementType.BK_EXPORTER.value
            or (
                data_id_detail["etl_config"]
                in [EtlConfigs.BK_EXPORTER.value, EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value]
                and measurement_type == MeasurementType.BK_SPLIT.value
            )
        ):
            # 如果space_id与data_id所属空间UID相同，则不需要过滤
            if data_id_detail["space_uid"] == f"{space_type}__{space_id}":
                return False
            else:
                return True

        # 可以执行到以下代码，必然是自定义时序的数据源
        # 1. 非公共的(全空间或指定空间类型)自定义时序，查询时，不需要任何查询条件
        if not is_platform_data_id:
            return False

        # 2. 公共自定义时序，如果存在在当前space，不需要添加过滤条件
        if is_exist_space:
            return False

        # 3. 此时，必然是自定义时序，且是公共的平台数据源，同时非该当前空间下，ß需要添加过滤条件
        return True

    def _refine_available_data_label(
        self,
        table_id_list: list | None = None,
        data_label_list: list | None = None,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ) -> list:
        """获取可以使用的结果表"""
        logger.info(
            "_refine_available_data_label: table_id_list->[%s],data_label_list->[%s],bk_tenant_id->[%s]",
            table_id_list,
            data_label_list,
            bk_tenant_id,
        )

        tids = models.ResultTable.objects.filter(is_deleted=False, is_enable=True, bk_tenant_id=bk_tenant_id).values(
            "table_id", "data_label"
        )

        if table_id_list:
            tids = tids.filter(table_id__in=table_id_list)

        # data_label可能存在逗号分割，需要拆分
        data_label_set: set[str] = set()
        if data_label_list:
            # data_label分割后去重
            for data_label in data_label_list:
                if not data_label:
                    continue
                data_label_set.update([dl for dl in data_label.split(",") if dl])

            # 如果data_label为空，则直接返回空
            if not data_label_set:
                return []

            # 组装查询条件
            new_data_label_list: list[str] = list(data_label_set)
            data_label_qs: Q = Q(data_label__contains=new_data_label_list[0])
            for data_label in new_data_label_list[1:]:
                data_label_qs |= Q(data_label__contains=data_label)

            tids = tids.filter(data_label_qs)

        # 获取结果表对应的data_label，且data_label可能存在逗号分割
        # 如果参数传入data_label_list，data_label必须在data_label_set中
        data_labels = list(
            itertools.chain(
                data_label
                for tid in tids
                if tid["data_label"]
                for data_label in tid["data_label"].split(",")
                if data_label and (not data_label_set or data_label in data_label_set)
            )
        )

        return list(set(data_labels))

    def _refine_table_ids(self, table_id_list: list | None = None, bk_tenant_id: str | None = DEFAULT_TENANT_ID) -> set:
        """提取写入到influxdb或vm的结果表数据"""
        # 过滤写入 influxdb 的结果表
        influxdb_table_ids = models.InfluxDBStorage.objects.values_list("table_id", flat=True)

        other_filter = None
        if settings.ENABLE_MULTI_TENANT_MODE:
            other_filter = {"bk_tenant_id": bk_tenant_id}
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
                other_filter=other_filter,
            )

        es_table_ids = models.ESStorage.objects.values_list("table_id", flat=True)
        if table_id_list:
            es_table_ids = filter_query_set_by_in_page(
                query_set=es_table_ids,
                field_op="table_id__in",
                filter_data=table_id_list,
                other_filter=other_filter,
            )

        table_ids = set(influxdb_table_ids).union(set(vm_table_ids)).union(set(es_table_ids))

        return table_ids

    def _filter_ts_info(self, table_ids: set) -> dict:
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

    def _compose_table_id_fields(self, table_ids: set | None = None, bk_tenant_id: str = DEFAULT_TENANT_ID) -> dict:
        """组装结果表对应的指标数据"""
        logger.info(
            "_compose_table_id_fields: try to compose table id fields,table_ids->[%s],bk_tenant_id->[%s]",
            table_ids,
            bk_tenant_id,
        )
        # 过滤到对应的结果表
        table_id_fields_qs = models.ResultTableField.objects.filter(
            tag=models.ResultTableField.FIELD_TAG_METRIC, table_id__in=table_ids, bk_tenant_id=bk_tenant_id
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
                bk_tenant_id=bk_tenant_id,
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
