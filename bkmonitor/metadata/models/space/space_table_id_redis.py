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
import json
import logging
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now as tz_now

from constants.apm import ApmGlobalTablePrefix
from constants.common import DEFAULT_TENANT_ID
from metadata import models
from metadata.models.constants import DEFAULT_MEASUREMENT, DataIdCreatedFromSystem
from metadata.models.record_rule.constants import RECORD_RULE_V4_DELETED_RETENTION_DAYS
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
)
from metadata.utils.db import filter_model_by_in_page, filter_query_set_by_in_page
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class SpaceTableIDRedis:
    """
    空间路由结果表数据推送 redis 相关功能
    多租户环境下,不允许跨租户推送路由,即每次操作的目标数据,必须是同一租户下的,不能跨租户
    """

    SUPPORT_SPACE_TYPES = {SpaceTypes.BKCC.value, SpaceTypes.BKCI.value, SpaceTypes.BKSAAS.value}
    TABLE_ID_DETAIL_BATCH_SIZE = 500

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
            values_to_redis[reformat_table_id(key)] = value

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
        bk_tenant_id: str = DEFAULT_TENANT_ID,
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

        # 若开启多租户模式,则data_label都需要在前面拼接bk_tenant_id
        if settings.ENABLE_MULTI_TENANT_MODE:
            rt_dl_map = {f"{data_label}|{bk_tenant_id}": table_ids for data_label, table_ids in rt_dl_map.items()}

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
        bkbase_rt_records = models.ResultTable.objects.filter(
            default_storage=models.ClusterInfo.TYPE_BKDATA,
            bk_tenant_id=bk_tenant_id,
        )
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
                "labels": record.labels or {},
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
                            "push_bkbase_table_id_detail: key(table_id)->[%s] is invalid, contains too many dots", key
                        )

                # 更新 _table_id_detail
                _table_id_detail = updated_table_id_detail

                # 若开启多租户模式,则在table_id前拼接bk_tenant_id
                if settings.ENABLE_MULTI_TENANT_MODE:
                    logger.info(
                        "push_bkbase_table_id_detail: enable multi tenant mode,will append bk_tenant_id->[%s]",
                        bk_tenant_id,
                    )
                    _table_id_detail = {f"{key}|{bk_tenant_id}": value for key, value in _table_id_detail.items()}

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
        *,
        bk_tenant_id: str,
        table_id_list: list[str] | None = None,
        is_publish: bool = False,
    ) -> None:
        """刷新一个租户的 ``result_table_detail`` 路由。

        本入口同时处理两类结构不同的路由：

        * InfluxDB、VM 和预计算指标表沿用原有 payload，不增加日志历史字段；
        * ES/Doris 日志表以 ``ResultTable.default_storage`` 作为顶层当前存储，
          再从实体表的 ``StorageClusterRecord`` 补齐可用于历史查询的存储分段。

        ``table_id_list`` 为 ``None`` 或空列表时均表示刷新当前租户的全部路由；
        非空列表限制候选结果表，但命中普通指标表时仍按旧行为附带该租户的 RecordRule。
        数据库查询始终使用 ``bk_tenant_id`` 隔离数据，``ENABLE_MULTI_TENANT_MODE``
        只决定 Redis field 和通知内容是否追加租户后缀。

        为保持向前兼容，日志路由按批次写入并延续原专用入口的异常容错，普通指标
        路由则在最后统一写入并保留原有的异常传播行为。

        :param bk_tenant_id: 本次刷新唯一允许读取和写入的租户 ID，不能为空。
        :param table_id_list: 待刷新的结果表 ID；``None`` 或 ``[]`` 表示租户全量刷新。
        :param is_publish: 写入 Redis 后是否向 ``RESULT_TABLE_DETAIL_CHANNEL`` 发布变更 field。
        """

        if not bk_tenant_id:
            raise ValueError("bk_tenant_id is required")

        logger.info(
            "push_table_id_detail: start, tenant->[%s], table_count->[%s], is_publish->[%s]",
            bk_tenant_id,
            len(table_id_list) if table_id_list else "all",
            is_publish,
        )

        # 先按旧流程组装指标路由，后续由日志路由“认领”同名 table_id。这样既能保持
        # 指标和 RecordRule 的原有行为，又不会让已切换到 ES/Doris 的表回退成指标路由。
        metric_table_id_detail = self._compose_metric_table_id_detail(
            bk_tenant_id=bk_tenant_id,
            table_id_list=table_id_list,
        )

        if table_id_list:
            log_table_ids = list(dict.fromkeys(table_id_list))
        else:
            # 全量刷新时取三个集合的并集：Storage 集合兼容没有 ResultTable 的早期路由；
            # default_storage 集合用于发现 Storage 配置缺失的日志 RT，并阻止同名指标覆盖旧值。
            es_table_ids = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id).values_list("table_id", flat=True)
            doris_table_ids = models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id).values_list(
                "table_id", flat=True
            )
            default_log_table_ids = models.ResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id,
                default_storage__in=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
            ).values_list("table_id", flat=True)
            log_table_ids = sorted(set(es_table_ids) | set(doris_table_ids) | set(default_log_table_ids))

        log_result_table_count = 0
        failed_log_batch_count = 0
        # 每批独立完成 ORM 预加载、内存组装和 Redis 写入，限制全量刷新时的查询参数、
        # Python 映射及单次 Redis payload 大小；批次内部不会再发起逐表 ORM 查询。
        for start in range(0, len(log_table_ids), self.TABLE_ID_DETAIL_BATCH_SIZE):
            batch_table_ids = log_table_ids[start : start + self.TABLE_ID_DETAIL_BATCH_SIZE]
            batch_detail, claimed_table_ids = self._compose_log_table_id_detail(
                bk_tenant_id=bk_tenant_id,
                table_id_list=batch_table_ids,
            )

            # claimed_table_ids 与是否成功组装 payload 分开返回。即使当前 ES/Doris 配置
            # 不完整，也不能回退并写入已经非默认的指标存储路由，否则会覆盖 Redis 旧值。
            for table_id in claimed_table_ids:
                metric_table_id_detail.pop(table_id, None)

            if not batch_detail:
                continue
            try:
                self._write_table_id_detail(
                    bk_tenant_id=bk_tenant_id,
                    table_id_detail=batch_detail,
                    is_publish=is_publish,
                    normalize_table_id=True,
                )
            except Exception:  # pylint: disable=broad-except
                # 延续原 ES/Doris 路由后处理的容错；普通指标路由写入仍按旧语义向上抛错。
                logger.exception(
                    "push_table_id_detail: failed to write log route batch, tenant->[%s], batch_start->[%s]",
                    bk_tenant_id,
                    start,
                )
                failed_log_batch_count += 1
            else:
                log_result_table_count += len(batch_detail)

        # 日志批次已经移除了其认领的 table_id，此处只剩普通指标及预计算路由。
        self._write_table_id_detail(
            bk_tenant_id=bk_tenant_id,
            table_id_detail=metric_table_id_detail,
            is_publish=is_publish,
            normalize_table_id=False,
        )

        if failed_log_batch_count:
            logger.warning(
                "push_table_id_detail: completed with failed log batches, tenant->[%s], "
                "metric_count->[%s], log_count->[%s], failed_batch_count->[%s]",
                bk_tenant_id,
                len(metric_table_id_detail),
                log_result_table_count,
                failed_log_batch_count,
            )
        else:
            logger.info(
                "push_table_id_detail: success, tenant->[%s], metric_count->[%s], log_count->[%s]",
                bk_tenant_id,
                len(metric_table_id_detail),
                log_result_table_count,
            )

    def _compose_metric_table_id_detail(
        self,
        *,
        bk_tenant_id: str,
        table_id_list: list[str] | None,
    ) -> dict[str, dict]:
        """按旧契约组装 InfluxDB、VM 及预计算结果表详情。

        该函数刻意不复用 ES/Doris 的历史路由结构：指标 payload 的字段、默认值、
        measurement type、字段顺序和 Redis field 都保持不变。指定列表中只要命中普通
        指标表，就延续旧行为附带当前租户的全部 RecordRule；仅指定日志表时则不附带。

        :param bk_tenant_id: 用于约束所有具备租户字段的指标元数据查询。
        :param table_id_list: 指定结果表；``None`` 或空列表沿用底层函数的全量语义。
        :return: 以原始 table_id 为 key 的指标和预计算路由详情。
        """

        # 先复用旧 helper 生成存储主体，再批量补齐字段、measurement 类型、集群、
        # 标签和 data ID；这些默认值及组装顺序属于既有指标 payload 契约。
        table_id_detail = get_table_info_for_influxdb_and_vm(
            table_id_list=table_id_list,
            bk_tenant_id=bk_tenant_id,
        )
        table_ids = set(table_id_detail)
        tenant_filter = {"bk_tenant_id": bk_tenant_id}

        rt_filter_data = filter_model_by_in_page(
            model=models.ResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "schema_type", "data_label", "labels"],
            other_filter=tenant_filter,
        )
        table_id_dict = {rt["table_id"]: rt for rt in rt_filter_data}
        table_list = list(table_id_dict.values())

        ds_rt_filter_data = filter_model_by_in_page(
            model=models.DataSourceResultTable,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "bk_data_id"],
            other_filter=tenant_filter,
        )
        table_id_data_id = {drt["table_id"]: drt["bk_data_id"] for drt in ds_rt_filter_data}
        measurement_type_dict = get_measurement_type_by_table_id(
            table_ids,
            table_list,
            table_id_data_id,
            bk_tenant_id=bk_tenant_id,
        )
        table_id_cluster_id = get_table_id_cluster_id(
            table_id_list=table_ids,
            bk_tenant_id=bk_tenant_id,
        )
        table_id_fields = self._compose_table_id_fields(table_ids=table_ids, bk_tenant_id=bk_tenant_id)

        result: dict[str, dict] = {}
        for table_id, detail in table_id_detail.items():
            detail["fields"] = table_id_fields.get(table_id) or []
            detail["measurement_type"] = measurement_type_dict.get(table_id) or ""
            detail["bcs_cluster_id"] = table_id_cluster_id.get(table_id) or ""
            detail["data_label"] = table_id_dict.get(table_id, {}).get("data_label") or ""
            detail["labels"] = table_id_dict.get(table_id, {}).get("labels") or {}
            detail["bk_data_id"] = table_id_data_id.get(table_id, 0)
            result[table_id] = detail

        # 指标定向或全量刷新时附带当前租户的预计算路由。
        if table_id_detail or not table_id_list:
            result.update(self._compose_record_rule_table_id_detail(bk_tenant_id=bk_tenant_id))
        return result

    def _compose_log_table_id_detail(
        self,
        *,
        bk_tenant_id: str,
        table_id_list: list[str],
    ) -> tuple[dict[str, dict], set[str]]:
        """批量组装 ES/Doris 当前路由及混合存储历史分段。

        ResultTable 存在时，顶层路由只由 ``default_storage`` 决定，保留下来的另一类
        Storage 仅提供历史查询配置；没有 ResultTable 时才兼容早期孤立 Storage。
        虚拟表的顶层标签、别名、options 和同类型 Storage 配置优先取虚拟表自身，
        缺失时回退实体表；历史分段则来自 ``origin_table_id`` 指向的实体表。

        返回的 ``claimed_table_ids`` 表示应由日志路由占用的 table_id。它有意包含当前
        配置不完整、因而未出现在详情结果中的日志表，供调用方阻止指标路由覆盖 Redis
        中仍可用的旧日志配置。

        :param bk_tenant_id: 用于隔离 ResultTable、Storage、历史记录、集群和扩展配置。
        :param table_id_list: 当前批次的候选结果表 ID，调用方保证批次大小受控。
        :return: ``(可写入 Redis 的路由详情, 被日志路由认领的 table_id 集合)``。
        """

        if not table_id_list:
            return {}, set()

        # 先把当前批次涉及的 ResultTable 和两类 Storage 全部加载为内存映射；从当前
        # 存储判定到最终 payload 组装，循环内部都不能再按 table_id 发起 ORM 查询。
        rt_map = {
            row["table_id"]: row
            for row in models.ResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=table_id_list,
            ).values("table_id", "default_storage", "data_label", "labels")
        }
        # ResultTable 的最终默认存储拥有最高判定优先级；不能用某个仍存在的 Storage，
        # 或 StorageClusterRecord.is_current，反向推断当前查询/写入存储。
        claimed_table_ids = {
            table_id
            for table_id, result_table in rt_map.items()
            if result_table["default_storage"] in {models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS}
        }

        es_rows = list(
            models.ESStorage.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=table_id_list,
            ).values("table_id", "storage_cluster_id", "source_type", "index_set", "origin_table_id")
        )
        doris_rows = list(
            models.DorisStorage.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=table_id_list,
            ).values(
                "table_id",
                "storage_cluster_id",
                "bkbase_table_id",
                "origin_table_id",
            )
        )
        es_map = {row["table_id"]: row for row in es_rows}
        doris_map = {row["table_id"]: row for row in doris_rows}
        storage_table_ids = set(es_map) | set(doris_map)
        if not storage_table_ids:
            return {}, claimed_table_ids

        # 无 ResultTable 的早期 Storage 也属于日志路由，不得被同名指标存储覆盖。
        claimed_table_ids.update(storage_table_ids - set(rt_map))

        selected_storage_type: dict[str, str] = {}
        record_source_table_id: dict[str, str] = {}
        for table_id in table_id_list:
            rt = rt_map.get(table_id)
            if rt:
                # 有 ResultTable 时严格服从 default_storage；另一类 Storage 即使仍保留，
                # 也只能作为历史查询配置，不能成为顶层当前存储。
                storage_type = rt["default_storage"]
                if storage_type == models.ClusterInfo.TYPE_ES and table_id not in es_map:
                    logger.error(
                        "compose log detail: default ES storage missing, tenant->[%s], table_id->[%s]",
                        bk_tenant_id,
                        table_id,
                    )
                    continue
                if storage_type == models.ClusterInfo.TYPE_DORIS and table_id not in doris_map:
                    logger.error(
                        "compose log detail: default Doris storage missing, tenant->[%s], table_id->[%s]",
                        bk_tenant_id,
                        table_id,
                    )
                    continue
                if storage_type not in {models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS}:
                    continue
            elif table_id in es_map:
                # 兼容早期只有 ESStorage、没有 ResultTable 的路由。
                storage_type = models.ClusterInfo.TYPE_ES
            elif table_id in doris_map:
                storage_type = models.ClusterInfo.TYPE_DORIS
            else:
                continue

            selected_storage_type[table_id] = storage_type
            selected_storage = (
                es_map.get(table_id) if storage_type == models.ClusterInfo.TYPE_ES else doris_map.get(table_id)
            )
            fallback_storage = (
                doris_map.get(table_id) if storage_type == models.ClusterInfo.TYPE_ES else es_map.get(table_id)
            )
            # log-router 虚拟表不维护自己的 StorageClusterRecord，其历史来源于关联实体表。
            # 优先读取当前 Storage 的 origin；为兼容切换后两类 Storage 配置不完全同步的
            # 旧数据，再回退另一类 Storage，最后才把当前表视为实体表。
            record_source_table_id[table_id] = (
                (selected_storage or {}).get("origin_table_id")
                or (fallback_storage or {}).get("origin_table_id")
                or table_id
            )

        if not selected_storage_type:
            return {}, claimed_table_ids

        # 实体表可能不在本次候选批次内，需要单独批量加载；已在目标 Storage 映射中的
        # table_id 可直接复用，避免重复查询。
        origin_table_ids = set(record_source_table_id.values()) - storage_table_ids
        origin_rt_map = {
            row["table_id"]: row
            for row in models.ResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=origin_table_ids,
            ).values("table_id", "data_label", "labels")
        }
        origin_es_map = {
            row["table_id"]: row
            for row in models.ESStorage.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=origin_table_ids,
            ).values("table_id", "storage_cluster_id", "source_type", "index_set", "origin_table_id")
        }
        origin_doris_map = {
            row["table_id"]: row
            for row in models.DorisStorage.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=origin_table_ids,
            ).values(
                "table_id",
                "storage_cluster_id",
                "bkbase_table_id",
                "origin_table_id",
            )
        }

        selected_table_ids = list(selected_storage_type)
        options_map: dict[str, dict] = {}
        options = models.ResultTableOption.objects.filter(
            bk_tenant_id=bk_tenant_id,
            table_id__in=selected_table_ids,
        ).values("table_id", "name", "value", "value_type")
        for option in options:
            try:
                value = (
                    option["value"]
                    if option["value_type"] == models.ResultTableOption.TYPE_STRING
                    else json.loads(option["value"])
                )
            except Exception:  # pylint: disable=broad-except
                # 单个脏 option 不应阻断整个批次，保持旧路由仅忽略该配置项的行为。
                continue
            options_map.setdefault(option["table_id"], {})[option["name"]] = value

        # 虚拟表别名优先，实体表别名仅在虚拟表没有配置时作为兼容回退，因此一次查询并集。
        field_alias_map = self._get_field_alias_map(
            list(set(selected_table_ids) | set(record_source_table_id.values())),
            bk_tenant_id,
        )
        # storage_cluster_records 需要同时包含 current 和 previous 分段，不能只筛
        # is_current=True；查询侧会依据相邻 enable_time 推导每一段的有效时间范围。
        storage_records = list(
            models.StorageClusterRecord.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id__in=set(record_source_table_id.values()),
                is_deleted=False,
            ).values("id", "table_id", "cluster_id", "enable_time")
        )
        records_by_table_id: dict[str, list[dict]] = {}
        for record in storage_records:
            # 兼容早期 enable_time 为空或异常的数据；0 仍能让消费端构造一个稳定的历史边界。
            try:
                record["enable_timestamp"] = int(record["enable_time"].timestamp())
            except (AttributeError, TypeError, ValueError):
                record["enable_timestamp"] = 0
            records_by_table_id.setdefault(record["table_id"], []).append(record)
        for records in records_by_table_id.values():
            # 不按 cluster_id 去重：A -> B -> A 是三个有效时间段。相同时间用自增 ID
            # 保证输出稳定，并按最新启用时间在前的顺序交给查询侧推导区间。
            records.sort(key=lambda item: (item["enable_timestamp"], item["id"]), reverse=True)

        # ClusterInfo 是全局配置入口，但仍必须通过租户和 ES/Doris 类型双重过滤。
        # 缺失、跨租户或类型不匹配的 cluster 会在组装时被视为不完整配置并跳过。
        cluster_ids = {record["cluster_id"] for record in storage_records}
        cluster_ids.update(row["storage_cluster_id"] for row in es_rows)
        cluster_ids.update(row["storage_cluster_id"] for row in doris_rows)
        cluster_map = {
            row["cluster_id"]: row
            for row in models.ClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id,
                cluster_id__in=cluster_ids,
                cluster_type__in=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
            ).values("cluster_id", "cluster_name", "cluster_type")
        }

        result: dict[str, dict] = {}
        for table_id, storage_type in selected_storage_type.items():
            source_table_id = record_source_table_id[table_id]
            target_es = es_map.get(table_id) or {}
            origin_es = es_map.get(source_table_id) or origin_es_map.get(source_table_id) or {}
            target_doris = doris_map.get(table_id) or {}
            origin_doris = doris_map.get(source_table_id) or origin_doris_map.get(source_table_id) or {}

            # 历史分段配置必须与存储类型一致：ES 只读取 ESStorage，Doris 只读取
            # DorisStorage。虚拟表没有对应 Storage 配置时，再回退关联实体表的同类型配置。
            es_db = target_es.get("index_set") or origin_es.get("index_set")
            es_source_type = target_es.get("source_type") or origin_es.get("source_type")
            # Doris 物理表名只存在于 DorisStorage；虚拟表未单独配置时回退实体表。
            doris_db = target_doris.get("bkbase_table_id") or origin_doris.get("bkbase_table_id")

            # 虽名为 history，该列表实际包含实体表所有未删除的当前和历史分段；
            # 顶层字段描述当前默认存储，列表则供查询侧按时间选择具体集群。
            history: list[dict] = []
            for record in records_by_table_id.get(source_table_id, []):
                # 每条 StorageClusterRecord 都代表一次独立启用时间段。单段配置不完整时
                # 只跳过该段，不能让一条坏历史记录阻断当前路由及其他可用历史段。
                cluster = cluster_map.get(record["cluster_id"])
                if not cluster:
                    logger.warning(
                        "compose log history: cluster missing or tenant mismatch, tenant->[%s], table_id->[%s], record_id->[%s]",
                        bk_tenant_id,
                        table_id,
                        record["id"],
                    )
                    continue
                if cluster["cluster_type"] == models.ClusterInfo.TYPE_ES:
                    if not es_db or not es_source_type:
                        logger.warning(
                            "compose log history: ES storage config missing, tenant->[%s], "
                            "table_id->[%s], record_id->[%s]",
                            bk_tenant_id,
                            table_id,
                            record["id"],
                        )
                        continue
                    history.append(
                        {
                            "storage_id": record["cluster_id"],
                            "storage_type": models.ESStorage.STORAGE_TYPE,
                            "db": es_db,
                            "measurement": DEFAULT_MEASUREMENT,
                            "source_type": es_source_type,
                            "enable_time": record["enable_timestamp"],
                        }
                    )
                elif doris_db:
                    history.append(
                        {
                            "storage_id": record["cluster_id"],
                            "storage_type": "bk_sql",
                            "storage_name": cluster["cluster_name"],
                            "cluster_name": cluster["cluster_name"],
                            "db": doris_db,
                            "measurement": models.ClusterInfo.TYPE_DORIS,
                            "enable_time": record["enable_timestamp"],
                        }
                    )
                else:
                    logger.warning(
                        "compose log history: Doris storage config missing, tenant->[%s], table_id->[%s], record_id->[%s]",
                        bk_tenant_id,
                        table_id,
                        record["id"],
                    )

            rt = rt_map.get(table_id, {})
            origin_rt = rt_map.get(source_table_id) or origin_rt_map.get(source_table_id) or {}
            data_label = rt.get("data_label") or origin_rt.get("data_label") or ""
            labels = rt.get("labels") or origin_rt.get("labels") or {}
            field_alias = field_alias_map.get(table_id) or field_alias_map.get(source_table_id) or {}
            # 顶层配置代表当前存储。ES/Doris 任一严格校验失败时都不返回该 table_id，
            # 调用方仍会认领它，从而既不写入残缺 payload，也不以指标 payload 覆盖旧配置。
            if storage_type == models.ClusterInfo.TYPE_ES:
                storage = target_es or origin_es
                storage_id = storage.get("storage_cluster_id", 0)
                cluster = cluster_map.get(storage_id)
                if (
                    not cluster
                    or cluster["cluster_type"] != models.ClusterInfo.TYPE_ES
                    or not es_db
                    or not es_source_type
                ):
                    logger.error(
                        "compose log detail: ES config incomplete, cluster missing, tenant mismatch or type mismatch, "
                        "tenant->[%s], table_id->[%s], cluster_id->[%s]",
                        bk_tenant_id,
                        table_id,
                        storage_id,
                    )
                    continue
                result[table_id] = {
                    "storage_id": storage_id,
                    "db": es_db,
                    "measurement": DEFAULT_MEASUREMENT,
                    "source_type": es_source_type,
                    "options": options_map.get(table_id) or {},
                    "storage_type": models.ESStorage.STORAGE_TYPE,
                    "storage_cluster_records": history,
                    "data_label": data_label,
                    "labels": labels,
                    "field_alias": field_alias,
                }
                continue
            elif storage_type == models.ClusterInfo.TYPE_DORIS:
                storage = target_doris or origin_doris
                storage_id = storage.get("storage_cluster_id", 0)
                cluster = cluster_map.get(storage_id)
                if not cluster or cluster["cluster_type"] != models.ClusterInfo.TYPE_DORIS or not doris_db:
                    logger.error(
                        "compose log detail: Doris config incomplete, tenant->[%s], table_id->[%s], cluster_id->[%s]",
                        bk_tenant_id,
                        table_id,
                        storage_id,
                    )
                    continue
                result[table_id] = {
                    "storage_type": "bk_sql",
                    "storage_id": storage_id,
                    "storage_name": cluster["cluster_name"],
                    "cluster_name": cluster["cluster_name"],
                    "db": doris_db,
                    "measurement": models.ClusterInfo.TYPE_DORIS,
                    "storage_cluster_records": history,
                    "data_label": data_label,
                    "labels": labels,
                    "field_alias": field_alias,
                }
            else:
                continue

        return result, claimed_table_ids

    @staticmethod
    def _write_table_id_detail(
        *,
        bk_tenant_id: str,
        table_id_detail: dict[str, dict],
        is_publish: bool,
        normalize_table_id: bool,
    ) -> None:
        """将一批结果表详情写入 Redis，并按需发布同一批 field。

        ``normalize_table_id`` 只对 ES/Doris 路由启用，用于延续原专用入口对一段式
        table_id 补 ``.__default__``、对超过两段的非法 ID 跳过的行为。普通指标 key
        不经过该转换。多租户开关只影响 Redis field，数据库隔离已在组装阶段完成。

        :param bk_tenant_id: 多租户模式下追加到 Redis field 的租户 ID。
        :param table_id_detail: 以原始 table_id 为 key 的单批路由详情。
        :param is_publish: 是否在 hmset 成功后发布实际写入的 Redis field 列表。
        :param normalize_table_id: 是否应用日志路由的一段式 table_id 兼容规则。
        """

        if not table_id_detail:
            return

        redis_values: dict[str, str] = {}
        for table_id, detail in table_id_detail.items():
            # reformat_table_id 只负责一段式补齐；超过两段会产生歧义，保持旧逻辑直接跳过。
            if normalize_table_id and len(table_id.split(".")) > 2:
                logger.error(
                    "write log detail: invalid table_id contains too many dots, tenant->[%s], table_id->[%s]",
                    bk_tenant_id,
                    table_id,
                )
                continue
            redis_table_id = reformat_table_id(table_id) if normalize_table_id else table_id
            if settings.ENABLE_MULTI_TENANT_MODE:
                redis_table_id = f"{redis_table_id}|{bk_tenant_id}"
            redis_values[redis_table_id] = json.dumps(detail)

        if not redis_values:
            return
        # publish 必须复用实际写入的 field，避免非法 table_id 被过滤后仍通知消费端刷新。
        RedisTools.hmset_to_redis(RESULT_TABLE_DETAIL_KEY, redis_values)
        if is_publish:
            RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, list(redis_values))

    def _compose_record_rule_table_id_detail(self, bk_tenant_id: str) -> dict[str, dict]:
        """组装预计算结果表的详情"""
        from metadata.models.record_rule.rules import RecordRule

        record_rule_objs = RecordRule.objects.filter(bk_tenant_id=bk_tenant_id).values(
            "table_id", "vm_cluster_id", "dst_vm_table_id", "rule_metrics"
        )
        vm_cluster_id_name = {
            cluster["cluster_id"]: cluster["cluster_name"]
            for cluster in models.ClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_VM
            ).values("cluster_id", "cluster_name")
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
                "labels": {},
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
            "_get_field_alias_map: try to get field alias map,table_count->[%s],bk_tenant_id->[%s]",
            len(table_id_list),
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

            logger.info(
                "_get_field_alias_map: generated, table_count->[%s], alias_table_count->[%s]",
                len(table_id_list),
                len(field_alias_map),
            )
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

        # 追加 ES/Doris 结果表
        _values.update(
            self._compose_doris_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(self._compose_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id))

        # 追加关联的BKCI的ES结果表，适配ES多空间功能
        _values.update(
            self._compose_related_bkci_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(self._compose_vm_short_link_table_ids(space_type, space_id, bk_tenant_id))
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
        _values.update(
            self._compose_bcs_space_cluster_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )
        _values.update(
            self._compose_bkci_level_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(
            self._compose_bkci_other_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )

        # 追加跨空间类型的数据源授权
        _values.update(
            self._compose_bkci_cross_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )

        # 追加特殊的允许全空间使用的数据源
        _values.update(
            self._compose_all_type_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )
        _values.update(
            self._compose_record_rule_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(self._compose_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id))
        # 追加Doris结果表
        _values.update(
            self._compose_doris_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        # APM 真全局数据
        _values.update(
            self._compose_apm_all_type_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )
        _values.update(self._compose_vm_short_link_table_ids(space_type, space_id, bk_tenant_id))
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
        _values.update(
            self._compose_all_type_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )
        _values.update(
            self._compose_record_rule_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        _values.update(self._compose_es_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id))
        # 追加Doris结果表
        _values.update(
            self._compose_doris_table_ids(space_type=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        )
        # APM 真全局数据
        _values.update(
            self._compose_apm_all_type_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )
        _values.update(self._compose_vm_short_link_table_ids(space_type, space_id, bk_tenant_id))
        return _values

    def _compose_vm_short_link_table_ids(
        self, space_type: str, space_id: str, bk_tenant_id: str = DEFAULT_TENANT_ID
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """组装 VM 短链路结果表。

        单业务短链路只进入归属空间；全局短链路按 query_router_config.space_type 进入目标空间。
        归属空间可查询全量数据，非归属空间沿用业务过滤语义。
        """
        logger.info(
            "_compose_vm_short_link_table_ids: space_type->[%s], space_id->[%s], bk_tenant_id->[%s]",
            space_type,
            space_id,
            bk_tenant_id,
        )
        records = models.VMShortLinkRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_enabled=True,
            is_deleted=False,
        ).filter(Q(space_type=space_type, space_id=space_id) | Q(is_global=True))
        if not records:
            return {}

        values: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for record in records:
            table_id = record.table_id
            # 单业务表只会命中归属空间；全局表在归属空间也不需要额外业务过滤。
            if not record.is_global or (record.space_type == space_type and record.space_id == space_id):
                values[table_id] = {"filters": []}
                continue

            if not record.match_query_router_space_type(space_type):
                continue

            # 非归属空间访问全局表时按 query_router_config 生成过滤条件。
            query_filter = record.get_query_router_filter(space_type, space_id)
            if query_filter is None:
                logger.warning(
                    "_compose_vm_short_link_table_ids: table_id->[%s] cannot compose filter for "
                    "space_type->[%s], space_id->[%s]",
                    table_id,
                    space_type,
                    space_id,
                )
                continue
            values[table_id] = {"filters": [query_filter]}

        return values

    def _compose_bcs_space_biz_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID) -> dict:
        """推送 bcs 类型关联业务的数据，现阶段包含主机及部分插件信息"""
        logger.info("start to push cluster of bcs space table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 首先获取关联业务的数据
        resource_type = SpaceTypes.BKCC.value
        obj = models.SpaceResource.objects.filter(
            space_type_id=space_type,
            space_id=space_id,
            resource_type=resource_type,
            bk_tenant_id=bk_tenant_id,
        ).first()
        if not obj:
            logger.error("space: %s__%s, resource_type: %s not found", space_type, space_id, resource_type)
            return {}
        # 获取空间关联的业务，注意这里业务 ID 为字符串类型
        # 追加空间访问指定插件的 filter
        rts = models.ResultTable.objects.filter(
            Q(table_id__startswith=BKCI_SYSTEM_TABLE_ID_PREFIX)
            | Q(table_id__in=settings.BKCI_SPACE_ACCESS_PLUGIN_LIST),
            bk_tenant_id=bk_tenant_id,
        )
        tids = rts.values_list("table_id", flat=True)

        return {tid: {"filters": [{"bk_biz_id": str(obj.resource_id)}]} for tid in tids}

    def _compose_bcs_space_cluster_table_ids(
        self,
        space_type: str,
        space_id: str,
        bk_tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        """推送 bcs 类型空间下的集群数据"""
        logger.info("start to push cluster of bcs space table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 获取空间的集群数据
        resource_type = SpaceTypes.BCS.value
        # 优先进行判断项目相关联的容器资源，减少等待
        sr_objs = models.SpaceResource.objects.filter(
            space_type_id=space_type,
            space_id=space_id,
            resource_type=resource_type,
            resource_id=space_id,
            bk_tenant_id=bk_tenant_id,
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
        data_id_cluster_id = get_cluster_data_ids(cluster_id_list, bk_tenant_id=bk_tenant_id)
        if not data_id_cluster_id:
            logger.error("space: %s__%s not found cluster", space_type, space_id)
            return default_values
        # 获取结果表及数据源
        table_id_data_id = get_result_tables_by_data_ids(
            data_id_list=list(data_id_cluster_id.keys()),
            bk_tenant_id=bk_tenant_id,
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

    def _compose_bkci_level_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID) -> dict:
        """组装 bkci 全局下的结果表"""
        logger.info("start to push bkci level table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 过滤空间级的数据源
        data_ids = get_platform_data_ids(space_type=space_type, bk_tenant_id=bk_tenant_id)
        # 一个空间下 data_id 不会太多
        table_is_list = list(
            models.DataSourceResultTable.objects.filter(
                bk_data_id__in=data_ids.keys(),
                bk_tenant_id=bk_tenant_id,
            ).values_list("table_id", flat=True)
        )
        _values = {}
        if not table_is_list:
            return _values
        # 过滤仅写入influxdb和vm的数据
        table_ids = self._refine_table_ids(table_is_list, bk_tenant_id=bk_tenant_id)
        # 组装数据
        for tid in table_ids:
            if tid in settings.SPECIAL_RT_ROUTE_ALIAS_RESULT_TABLE_LIST:
                rt_ins = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=tid)
                logger.info(
                    "_compose_bkci_level_table_ids: table_id->[%s] in special_rt_list, will use filter key->[%s]",
                    tid,
                    rt_ins.bk_biz_id_alias,
                )
                _values[tid] = {"filters": [{rt_ins.bk_biz_id_alias: space_id}]}
                continue
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
            bk_tenant_id=bk_tenant_id,
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

    def _compose_bkci_cross_table_ids(
        self,
        space_type: str,
        space_id: str,
        bk_tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        """组装跨空间类型的结果表数据"""
        logger.info(
            "start to push bkci space cross space_type table_id, space_type: %s, space_id: %s", space_type, space_id
        )
        tids = models.ResultTable.objects.filter(
            table_id__startswith=BKCI_1001_TABLE_ID_PREFIX,
            bk_tenant_id=bk_tenant_id,
        ).values_list("table_id", flat=True)
        # bkci 访问 p4 主机数据对应的结果表
        p4_tids = models.ResultTable.objects.filter(
            table_id__startswith=P4_1001_TABLE_ID_PREFIX,
            bk_tenant_id=bk_tenant_id,
        ).values_list("table_id", flat=True)
        # 组装结果表对应的 filter
        tid_filters = {tid: {"filters": [{"projectId": space_id}]} for tid in tids}
        tid_filters.update({tid: {"filters": [{"devops_id": space_id}]} for tid in p4_tids})
        return tid_filters

    def _compose_all_type_table_ids(
        self,
        space_type: str,
        space_id: str,
        bk_tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        """组装非业务类型的全空间类型的结果表数据"""
        logger.info("start to push all space type table_id, space_type: %s, space_id: %s", space_type, space_id)
        # 转换空间对应的bk_biz_id
        try:
            _id = models.Space.objects.get(
                space_type_id=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            ).id
        except models.Space.DoesNotExist:
            return {}
        return {tid: {"filters": [{"bk_biz_id": str(-_id)}]} for tid in ALL_SPACE_TYPE_TABLE_ID_LIST}

    def _compose_apm_all_type_table_ids(
        self,
        space_type: str,
        space_id: str,
        bk_tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        """
        APM特殊逻辑--真正的全局数据, filter key使用配置的bk_biz_id_alias，value使用-id
        该方法仅对 BKCI 和 BKSAAS类型生效，BKCC类型走通用路由处理逻辑
        """
        # TODO： 该方法为临时支持，长期需要改造抽象为公共逻辑
        logger.info("start to push apm all space type table_id, space_type: %s, space_id: %s", space_type, space_id)
        try:
            space = models.Space.objects.get(
                space_type_id=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        except models.Space.DoesNotExist:
            return {}

        result_tables = models.ResultTable.objects.filter(
            table_id__startswith=ApmGlobalTablePrefix.COMMON, bk_tenant_id=space.bk_tenant_id
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
            space_type_id=space_type,
            space_id=space_id,
            resource_type=resource_type,
            resource_id=space_id,
            bk_tenant_id=bk_tenant_id,
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
        data_id_cluster_id = get_cluster_data_ids(
            cluster_id_list,
            table_id_list,
            bk_tenant_id=bk_tenant_id,
        )
        if not data_id_cluster_id:
            logger.error("space: %s__%s not found cluster", space_type, space_id)
            return default_values
        # 获取结果表及数据源
        table_id_data_id = get_result_tables_by_data_ids(
            data_id_list=list(data_id_cluster_id.keys()),
            table_id_list=table_id_list,
            bk_tenant_id=bk_tenant_id,
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
        table_ids = self._refine_table_ids(
            list(table_id_data_id.keys()),
            bk_tenant_id=bk_tenant_id,
        )
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
            other_filter={"bk_tenant_id": bk_tenant_id},
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
            value_field_list=["table_id", "schema_type", "data_label", "bk_biz_id_alias", "default_storage"],
            other_filter={"bk_tenant_id": bk_tenant_id},
        )  # 新增bk_biz_id_alias,部分业务存在自定义过滤规则别名需求，如bk_biz_id -> appid

        # ES / Doris 路由由后续独立流程处理，这里仅按 default_storage 排除，不再根据 RT 启用或删除状态过滤。
        _table_list = [
            data
            for data in _table_list
            if data["default_storage"] not in [models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS]
        ]
        table_ids = {data["table_id"] for data in _table_list}
        table_id_data_id = {tid: table_id_data_id.get(tid) for tid in table_ids}

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
            space_type_id=space_type,
            space_id=space_id,
            from_authorization=False,
            bk_tenant_id=bk_tenant_id,
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
        values = {obj.table_id: {"filters": []} for obj in objs}
        values.update(
            self._compose_record_rule_v4_table_ids(
                space_type=space_type,
                space_id=space_id,
                bk_tenant_id=bk_tenant_id,
            )
        )
        return values

    def _compose_record_rule_v4_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID):
        """组装 V4 预计算输出结果表。

        V4 输出 RT 没有普通 DataSourceResultTable 链路，空间可查询表索引
        需要显式追加。停用只停止后续写入，不影响历史数据查询；删除完成
        后也保留半年查询窗口，超过窗口后才从空间路由中移除。
        """

        from metadata.models.record_rule.v4 import RecordRuleV4

        queryable_deleted_at = tz_now() - datetime.timedelta(days=RECORD_RULE_V4_DELETED_RETENTION_DAYS)
        objs = RecordRuleV4.objects.filter(
            space_type=space_type,
            space_id=space_id,
            bk_tenant_id=bk_tenant_id,
        ).filter(Q(deleted_at__isnull=True) | Q(deleted_at__gt=queryable_deleted_at))
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

    def _compose_doris_table_ids(
        self,
        space_type: str,
        space_id: str,
        bk_tenant_id: str = DEFAULT_TENANT_ID,
    ):
        """
        组装Doris链路结果表
        """
        biz_id = models.Space.objects.get_biz_id_by_space(space_type, space_id)
        tids = models.ResultTable.objects.filter(
            bk_biz_id=biz_id,
            default_storage=models.ClusterInfo.TYPE_DORIS,
            is_deleted=False,
            is_enable=True,
            bk_tenant_id=bk_tenant_id,
        ).values_list("table_id", flat=True)
        return {tid: {"filters": []} for tid in tids}

    def _compose_related_bkci_table_ids(self, space_type: str, space_id: str, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        组装关联的BKCI类型的Es/Doris结果表
        """
        logger.info(
            "_compose_related_bkci_table_ids: space_type->[%s],space_id->[%s],bk_tenant_id->[%s]",
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
            default_storage__in=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
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
        influxdb_table_ids = models.InfluxDBStorage.objects.filter(bk_tenant_id=bk_tenant_id).values_list(
            "table_id", flat=True
        )
        if table_id_list:
            influxdb_table_ids = filter_query_set_by_in_page(
                query_set=influxdb_table_ids,
                field_op="table_id__in",
                filter_data=table_id_list,
            )
        # 过滤写入 vm 的结果表
        vm_table_ids = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id).values_list(
            "result_table_id", flat=True
        )
        if table_id_list:
            vm_table_ids = filter_query_set_by_in_page(
                query_set=vm_table_ids,
                field_op="result_table_id__in",
                filter_data=table_id_list,
            )

        es_table_ids = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id).values_list("table_id", flat=True)
        if table_id_list:
            es_table_ids = filter_query_set_by_in_page(
                query_set=es_table_ids,
                field_op="table_id__in",
                filter_data=table_id_list,
            )

        table_ids = set(influxdb_table_ids).union(set(vm_table_ids)).union(set(es_table_ids))

        return table_ids

    def _get_ts_metric_group_ids_by_datalink_version(
        self, table_id_ts_group_id: dict[str, int], bk_tenant_id: str = DEFAULT_TENANT_ID
    ) -> tuple[set[int], set[int]]:
        """根据结果表所属数据链路版本拆分时序分组 ID"""
        if not table_id_ts_group_id:
            return set(), set()

        table_id_data_id = {
            data["table_id"]: data["bk_data_id"]
            for data in filter_model_by_in_page(
                model=models.DataSourceResultTable,
                field_op="table_id__in",
                filter_data=list(table_id_ts_group_id.keys()),
                value_func="values",
                value_field_list=["table_id", "bk_data_id"],
                other_filter={"bk_tenant_id": bk_tenant_id},
            )
        }

        if not table_id_data_id:
            return set(table_id_ts_group_id.values()), set()

        v4_data_ids = set(
            filter_model_by_in_page(
                model=models.DataSource,
                field_op="bk_data_id__in",
                filter_data=set(table_id_data_id.values()),
                value_func="values_list",
                value_field_list=["bk_data_id"],
                other_filter={
                    "bk_tenant_id": bk_tenant_id,
                    "created_from": DataIdCreatedFromSystem.BKDATA.value,
                },
            )
        )
        v4_group_ids = {
            group_id
            for table_id, group_id in table_id_ts_group_id.items()
            if table_id_data_id.get(table_id) in v4_data_ids
        }
        v3_group_ids = set(table_id_ts_group_id.values()) - v4_group_ids
        return v3_group_ids, v4_group_ids

    def _filter_v4_ts_metric_fields(self, group_ids: set[int], begin_time: datetime.datetime) -> list[dict]:
        """V4 链路下，指标满足活跃或近期更新任一条件即可"""
        if not group_ids:
            return []

        active_fields = filter_model_by_in_page(
            model=models.TimeSeriesMetric,
            field_op="group_id__in",
            filter_data=group_ids,
            value_func="values",
            value_field_list=["field_name", "group_id"],
            other_filter={"is_active": True},
        )
        recent_fields = filter_model_by_in_page(
            model=models.TimeSeriesMetric,
            field_op="group_id__in",
            filter_data=group_ids,
            value_func="values",
            value_field_list=["field_name", "group_id"],
            other_filter={"last_modify_time__gte": begin_time},
        )
        return list(
            {
                (data["group_id"], data["field_name"]): data for data in itertools.chain(active_fields, recent_fields)
            }.values()
        )

    def _filter_ts_info(self, table_ids: set, bk_tenant_id: str = DEFAULT_TENANT_ID) -> dict:
        """根据结果表获取对应的时序数据"""
        if not table_ids:
            return {}
        _filter_data = filter_model_by_in_page(
            model=models.TimeSeriesGroup,
            field_op="table_id__in",
            filter_data=table_ids,
            value_func="values",
            value_field_list=["table_id", "time_series_group_id"],
            other_filter={"bk_tenant_id": bk_tenant_id},
        )
        if not _filter_data:
            return {}

        table_id_ts_group_id = {data["table_id"]: data["time_series_group_id"] for data in _filter_data}
        # NOTE: 针对自定义时序，过滤掉历史废弃的指标
        # V4 链路满足 is_active 或近期更新任一条件即可，V3/兜底场景仍只使用过期时间过滤
        begin_time = tz_now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        v3_group_ids, v4_group_ids = self._get_ts_metric_group_ids_by_datalink_version(
            table_id_ts_group_id=table_id_ts_group_id,
            bk_tenant_id=bk_tenant_id,
        )
        ts_group_fields = []
        if v4_group_ids:
            ts_group_fields.extend(self._filter_v4_ts_metric_fields(group_ids=v4_group_ids, begin_time=begin_time))
        if v3_group_ids:
            ts_group_fields.extend(
                filter_model_by_in_page(
                    model=models.TimeSeriesMetric,
                    field_op="group_id__in",
                    filter_data=v3_group_ids,
                    value_func="values",
                    value_field_list=["field_name", "group_id"],
                    other_filter={"last_modify_time__gte": begin_time},
                )
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
        ts_info = self._filter_ts_info(table_id_set, bk_tenant_id=bk_tenant_id)
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
