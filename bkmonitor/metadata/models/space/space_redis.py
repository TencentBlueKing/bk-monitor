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
from typing import Dict, List, Optional

from django.conf import settings
from django.utils.timezone import now as tz_now

from metadata.models import (
    DataSource,
    DataSourceOption,
    DataSourceResultTable,
    InfluxDBStorage,
    ResultTable,
    ResultTableField,
    ResultTableOption,
    TimeSeriesGroup,
    TimeSeriesMetric,
)
from metadata.utils.redis_tools import RedisTools

from . import utils
from .constants import (
    SPACE_DETAIL_REDIS_KEY_PREFIX,
    SPACE_REDIS_KEY,
    BCSClusterTypes,
    EtlConfigs,
    MeasurementType,
    SpaceTypes,
)
from .space import Space, SpaceDataSource, SpaceResource

logger = logging.getLogger("metadata")


class SpaceRedis:
    def __init__(self):
        self.space_detail_key = f"{SPACE_DETAIL_REDIS_KEY_PREFIX}:{{space_type_id}}__{{space_id}}"

    def push_bkcc_type_space(self, space_id: str, table_id: Optional[str] = None):
        """推送业务类型的空间到 redis"""
        space_type_id = SpaceTypes.BKCC.value
        self.get_data(space_type_id, space_id, table_id=table_id)
        self._compose_and_push_biz_data(
            space_type_id,
            space_id,
            space_type_id,
            space_id,
        )

    def push_bcs_type_space(
        self,
        space_id: str,
        push_bkcc_type: Optional[bool] = True,
        push_bcs_type: Optional[bool] = True,
        table_id: Optional[str] = None,
    ):
        """推送容器类型空间"""
        space_type_id = SpaceTypes.BKCI.value
        # 关联的业务，BCS 项目只关联一个业务
        if push_bkcc_type:
            self._push_biz_resource_for_bcs_type(space_type_id, space_id, table_id=table_id)
        # 关联的集群
        if push_bcs_type:
            self._push_bcs_resource_for_bcs_type(space_type_id, space_id, table_id=table_id)

    def push_bkci_type_space(self, space_id: str, table_id: Optional[str] = None):
        """推送蓝盾流水线资源的"""
        space_type_id = SpaceTypes.BKCI.value

        # 排除集群的数据源，因为需要单独处理
        exclude_data_id_list = utils.cached_cluster_data_id_list()

        self.get_data(space_type_id, space_id, table_id=table_id, exclude_data_id_list=exclude_data_id_list)
        self._compose_and_push_biz_data(
            space_type_id,
            space_id,
            space_type_id,
            space_id,
            dimension_values=[{"projectId": space_id}],
            skip_system=True,
        )

    def push_bksaas_type_space(self, space_id: str, table_id: Optional[str] = None):
        """推送 bksaas 类型的空间信息"""
        space_type_id = SpaceTypes.BKSAAS.value
        self.get_data(space_type_id, space_id, table_id=table_id, from_authorization=False)
        self._push_space_with_type(space_type_id, space_id)

    def push_not_biz_type_space(self, space_type: str, space_id: str, table_id: Optional[str] = None):
        """推送 bksaas 类型的空间信息"""
        # 排除掉集群的数据源信息，因为集群的过滤条件需要特殊处理
        exclude_data_id_list = utils.cached_cluster_data_id_list()
        self.get_data(
            space_type, space_id, table_id=table_id, from_authorization=False, exclude_data_id_list=exclude_data_id_list
        )
        self._push_space_with_type(space_type, space_id)

    def _push_space_with_type(self, space_type: str, space_id: str):
        field_value = {}
        # 组装需要的数据
        resource_type = space_type
        for table_id, data_id in self.table_data_id_dict.items():
            # 过滤掉格式不符合预期的结果表
            if "." not in table_id:
                continue
            fields = self.table_field_dict.get(table_id) or []
            measurement_type = self.measurement_type_dict.get(table_id)
            # 兼容脏数据导致获取不到，如果不存在，则忽略
            if not measurement_type:
                logger.error("table_id: %s not find measurement type", table_id)
                continue

            field_value[table_id] = json.dumps(
                {
                    "type": resource_type,
                    "field": fields,
                    "measurement_type": measurement_type,
                    "bk_data_id": str(data_id),
                    "filters": [],
                    "segmented_enable": self.segment_option_dict.get(table_id, False),
                }
            )
        # 推送数据
        redis_key = self.space_detail_key.format(space_type_id=space_type, space_id=space_id)
        if field_value:
            RedisTools.hmset_to_redis(redis_key, field_value)

    def _push_biz_resource_for_bcs_type(self, space_type_id: str, space_id: str, table_id: Optional[str] = None):
        """推送容器关联的业务"""
        resource_type_id = SpaceTypes.BKCC.value
        obj = SpaceResource.objects.filter(
            space_type_id=space_type_id, space_id=space_id, resource_type=resource_type_id
        ).first()
        if not obj:
            logger.error("space: %s__%s, resource: %s not found", space_type_id, space_id, resource_type_id)
            return
        biz_id_str = obj.resource_id

        # 过滤业务下的资源信息(仅含有归属于当前业务的数据源)
        self.get_data(resource_type_id, biz_id_str, table_id=table_id, from_authorization=False)
        self._compose_and_push_biz_data(
            space_type_id,
            space_id,
            resource_type_id,
            biz_id_str,
        )

    def _is_need_add_filter(self, measurement_type: str, space_type_id: str, space_id: str, data_id: int) -> bool:
        """判断是否需要添加filter"""
        # NOTE: 防止脏数据导致查询不到异常抛出的情况
        try:
            data_source = DataSource.objects.get(bk_data_id=data_id)
        except Exception as e:
            logger.error("query data source: [%s] error: %s", data_id, e)
            return True
        # NOTE: 为防止查询范围放大，先功能开关控制，针对归属到具体空间的数据源，不需要添加过滤条件
        if not settings.IS_RESTRICT_DS_BELONG_SPACE and (data_source.space_uid == f"{space_type_id}__{space_id}"):
            return False
        # 如果不是自定义时序，则不需要关注类似的情况，必须增加过滤条件
        if (
            measurement_type
            not in [
                MeasurementType.BK_SPLIT.value,
                MeasurementType.BK_STANDARD_V2_TIME_SERIES.value,
                MeasurementType.BK_EXPORTER.value,
            ]
            and data_source.etl_config != EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value
        ):
            return True

        # 对自定义插件的处理，兼容黑白名单对类型的更改
        # 黑名单时，会更改为单指标单表
        if measurement_type == MeasurementType.BK_EXPORTER.value or (
            data_source.etl_config == EtlConfigs.BK_EXPORTER.value
            and measurement_type == MeasurementType.BK_SPLIT.value
        ):
            # 如果space_id与data_id所属空间UID相同，则不需要过滤
            if data_source.space_uid == f"{space_type_id}__{space_id}":
                return False
            else:
                return True

        is_platform_data_id = data_source.is_platform_data_id
        try:
            space_data_source = SpaceDataSource.objects.get(
                space_type_id=space_type_id, space_id=space_id, bk_data_id=data_id
            )
        except SpaceDataSource.DoesNotExist:
            logger.error("space: %s__%s, data_id:%s not found", space_type_id, space_id, data_id)
            return True

        # 可以执行到以下代码，必然是自定义时序的数据源
        # 1. 非公共的(全空间或指定空间类型)自定义时序，查询时，不需要任何查询条件
        if not is_platform_data_id:
            return False

        # 可以执行 到以下代码，必然是自定义时序，且是公共平台数据源
        # 2. 公共自定义时序，如果属于当前space，不需要添加过滤条件
        if space_data_source.space_id == space_id:
            return False

        # 3. 此时，必然是自定义时序，且是公共的平台数据源，同时非该当前空间下，ß需要添加过滤条件
        return True

    def _push_bcs_resource_for_bcs_type(self, space_type_id: str, space_id: str, table_id: Optional[str] = None):
        """推送关联的容器资源"""
        resource_type_id = SpaceTypes.BCS.value
        # 获取项目相关联的容器资源
        # 优先进行判断，减少等待
        sr_objs = SpaceResource.objects.filter(
            space_type_id=space_type_id, space_id=space_id, resource_type=resource_type_id, resource_id=space_id
        )
        if not sr_objs.exists():
            return
        # 获取项目下归属的 data id
        (
            table_data_id_dict,
            measurement_type_dict,
            table_field_dict,
            segment_option_dict,
            table_data_label_dict,
        ) = self._get_data(space_type_id, space_id, table_id=table_id, include_platform_data_id=False)
        res_list = sr_objs.first().dimension_values
        # 获取集群对应的data id
        # NOTE: 共享集群的直接通过关联资源获取，减少对接口的依赖
        data_id_cluster_dict, cluster_data_ids, cluster_id_type, shared_cluster_ns_dict = {}, {}, {}, {}
        for res in res_list:
            cluster_id_type[res["cluster_id"]] = res.get("cluster_type", BCSClusterTypes.SINGLE.value)
            data_id_set = utils.get_data_id_by_cluster(res["cluster_id"])
            cluster_data_ids.update(data_id_set)
            for data_id in data_id_set.get(res["cluster_id"]) or set():
                data_id_cluster_dict[data_id] = res["cluster_id"]
            if res.get("cluster_type") == BCSClusterTypes.SHARED.value and res.get("namespace"):
                shared_cluster_ns_dict[res["cluster_id"]] = res.get("namespace") or []
        # 组装数据
        field_value = {}
        redis_key = self.space_detail_key.format(space_type_id=space_type_id, space_id=space_id)
        for table_id, data_id in table_data_id_dict.items():
            # 优先判断 table id 符合要求
            try:
                table_id.split(".")
            except Exception:
                continue
            fields = table_field_dict.get(table_id) or []
            if not fields:
                logging.warning(
                    f"space_type:{space_type_id}, space:{space_id}, "
                    f"data_id:{data_id}, table_id:{table_id} not found fields"
                )

            cluster_id = data_id_cluster_dict.get(data_id)
            if not cluster_id:
                continue
            cluster_type = cluster_id_type.get(cluster_id, BCSClusterTypes.SINGLE.value)
            filter_data = []
            # 如果为独立集群，则仅需要集群 ID
            # 如果为共享集群
            # - 命名空间为空，则忽略
            # - 命名空间不为空，则添加集群和命名空间
            if cluster_type == BCSClusterTypes.SINGLE.value:
                filter_data = [{"bcs_cluster_id": cluster_id, "namespace": None}]
            elif cluster_type == BCSClusterTypes.SHARED.value and cluster_id in shared_cluster_ns_dict:
                filter_data = [
                    {
                        "bcs_cluster_id": cluster_id,
                        "namespace": ns,
                    }
                    for ns in shared_cluster_ns_dict[cluster_id]
                    if ns
                ]

            # 兼容脏数据导致获取不到，如果不存在，则忽略
            measurement_type = measurement_type_dict.get(table_id)
            if not measurement_type:
                logger.error("table_id: %s not find measurement type", table_id)
                continue

            field_value[table_id] = json.dumps(
                {
                    "type": resource_type_id,
                    "field": fields,
                    "measurement_type": measurement_type,
                    "segmented_enable": segment_option_dict.get(table_id, False),
                    "bk_data_id": str(data_id),
                    "filters": filter_data,
                    "data_label": table_data_label_dict.get(table_id, ""),
                }
            )
        # 推送数据到redis
        if field_value:
            RedisTools.hmset_to_redis(redis_key, field_value)

    def compose_biz_data(
        self,
        space_type_id: str,
        space_id: str,
        resource_type: str,
        resource_id: str,
        dimension_values: Optional[List] = None,
        skip_system: Optional[bool] = False,
    ):
        field_value = {}
        for table_id, data_id in self.table_data_id_dict.items():
            # NOTE: 现阶段针对1001下 `system.` 或者 `dbm_system.` 开头的结果表不允许被覆盖
            if skip_system and (table_id.startswith("system.") or table_id.startswith("dbm_system.")):
                continue
            fields = self.table_field_dict.get(table_id) or []
            if not fields:
                logging.warning(
                    f"space_type:{space_type_id}, space:{space_id}, "
                    f"data_id:{data_id}, table_id:{table_id} not found fields"
                )
            try:
                table_id.split(".")
            except Exception:
                logger.error(f"table_id:{table_id} not split by `.`")
                continue

            filters = []
            measurement_type = self.measurement_type_dict.get(table_id)
            # 兼容脏数据导致获取不到，如果不存在，则忽略
            if not measurement_type:
                logger.error("table_id: %s not find measurement type", table_id)
                continue
            if self._is_need_add_filter(measurement_type, space_type_id, space_id, data_id):
                dimension_values = dimension_values or [{"bk_biz_id": resource_id}]
                filters = dimension_values

            field_value[table_id] = json.dumps(
                {
                    "type": resource_type,
                    "field": fields,
                    "measurement_type": measurement_type,
                    "bk_data_id": str(data_id),
                    "filters": filters,
                    "segmented_enable": self.segment_option_dict.get(table_id, False),
                    "data_label": self.table_data_label_dict.get(table_id, ""),
                }
            )
        return field_value

    def _compose_and_push_biz_data(
        self,
        space_type_id: str,
        space_id: str,
        resource_type: str,
        resource_id: str,
        dimension_values: Optional[List] = None,
        skip_system: Optional[bool] = False,
    ):
        field_value = self.compose_biz_data(
            space_type_id,
            space_id,
            resource_type,
            resource_id,
            dimension_values,
            skip_system,
        )
        redis_key = self.space_detail_key.format(space_type_id=space_type_id, space_id=space_id)
        # 推送数据到redis
        if field_value:
            RedisTools.hmset_to_redis(redis_key, field_value)

    def get_data(
        self,
        space_type_id: str,
        space_id: str,
        table_id: Optional[str] = None,
        from_authorization: Optional[bool] = None,
        include_platform_data_id: Optional[bool] = True,
        exclude_data_id_list: Optional[List] = None,
    ):
        (
            self.table_data_id_dict,
            self.measurement_type_dict,
            self.table_field_dict,
            self.segment_option_dict,
            self.table_data_label_dict,
        ) = self._get_data(
            space_type_id,
            space_id,
            table_id=table_id,
            from_authorization=from_authorization,
            include_platform_data_id=include_platform_data_id,
            exclude_data_id_list=exclude_data_id_list,
        )

    def _get_data(
        self,
        space_type_id: str,
        space_id: str,
        table_id: Optional[str] = None,
        from_authorization: Optional[bool] = None,
        include_platform_data_id: Optional[bool] = True,
        exclude_data_id_list: Optional[List] = None,
    ):
        data_id_list = None
        if not table_id:
            # 过滤到对应的 data id
            sd_objs = SpaceDataSource.objects.filter(space_type_id=space_type_id, space_id=space_id)
            if from_authorization is not None:
                sd_objs = sd_objs.filter(from_authorization=from_authorization)
            data_id_list = list(sd_objs.values_list("bk_data_id", flat=True))
            # 获取空间级的 data id
            data_id_list.extend(utils.get_space_data_id_list(space_type_id))
            # 获取全空间的 data id
            if include_platform_data_id:
                data_id_list.extend(utils.get_platform_data_id_list())
            # 过滤掉部分data id，避免重复处理
            if exclude_data_id_list is not None:
                data_id_list = list(set(data_id_list) - set(exclude_data_id_list))
        # 通过 data id 获取到结果表
        table_data_id_dict = utils.get_result_table_data_id_dict(data_id_list, table_id)
        table_id_list = list(table_data_id_dict.keys())
        table_list = utils.get_result_table_list(table_id_list=table_id_list)
        # 获取table的data_label
        table_data_label_dict = {table["table_id"]: table["data_label"] for table in table_list}
        # 获取table的measurement type
        measurement_type_dict = get_measurement_type_by_table_id(table_id_list, table_list)
        # 获取结果表对应的属性
        table_field_dict = get_table_field_by_table_id(table_id_list)
        segment_option_dict = get_segmented_option_by_table_id(table_id_list)
        return table_data_id_dict, measurement_type_dict, table_field_dict, segment_option_dict, table_data_label_dict


def get_measurement_type(
    schema_type: str, is_split_measurement: bool, is_disable_metric_cutter: bool, etl_config: Optional[str] = None
) -> str:
    """获取表类型
    - 当 schema_type 为 fixed 时，为多指标单表
    - 当 schema_type 为 free 时，
        - 如果 is_split_measurement 为 True, 则为单指标单表
        - 如果 is_split_measurement 为 False
            - 如果 etl_config 为`bk_standard_v2_time_series`，
                - 如果 is_disable_metric_cutter 为 False，则为固定 metric_name，metric_value
                - 否则为自定义多指标单表
            - 否则，为固定 metric_name，metric_value
    """
    # TODO: 优化内容如下
    # - schema 为fixed 多指标单表
    # - schema 为free时，如果disable_metric_cutter为False，指标不转换(也就是先前为什么就是什么)
    # - schema 为free时，如果disable_metric_cutter为True，则转换为metric_name, metric_value
    # - is_split_measurement为True, 单指标单表
    # - is_split_measurement为False, 多指标单表

    if schema_type == ResultTable.SCHEMA_TYPE_FIXED:
        return MeasurementType.BK_TRADITIONAL.value
    if schema_type == ResultTable.SCHEMA_TYPE_FREE:
        if is_split_measurement:
            return MeasurementType.BK_SPLIT.value

        if etl_config != EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value:
            return MeasurementType.BK_EXPORTER.value

        if not is_disable_metric_cutter:
            return MeasurementType.BK_EXPORTER.value
        return MeasurementType.BK_STANDARD_V2_TIME_SERIES.value

    # 如果为其它，设置为未知
    return MeasurementType.BK_TRADITIONAL.value


def get_measurement_type_by_table_id(table_id_list: List, table_list: List) -> Dict:
    """通过结果表 ID, 获取节点表对应的 option 配置

    通过 option 转到到 measurement 类型
    """
    # 过滤对应关系，用以进行判断单指标单表、多指标单表
    rto_dict = {
        rto["table_id"]: json.loads(rto["value"])
        for rto in ResultTableOption.objects.filter(
            table_id__in=table_id_list, name=DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT
        ).values("table_id", "name", "value")
    }

    # 过滤数据源和table id的关系
    table_data_dict = {
        drt["table_id"]: drt["bk_data_id"]
        for drt in DataSourceResultTable.objects.filter(table_id__in=table_id_list).values("table_id", "bk_data_id")
    }
    data_etl_dict = {
        d["bk_data_id"]: d["etl_config"]
        for d in DataSource.objects.filter(bk_data_id__in=table_data_dict.values()).values("bk_data_id", "etl_config")
    }
    # 获取到对应的类型
    measurement_type_dict = {}
    for table in table_list:
        table_id, schema_type = table["table_id"], table["schema_type"]
        etl_config = data_etl_dict.get(table_data_dict.get(table_id))
        # 获取是否禁用指标切分模式
        is_disable_metric_cutter = ResultTable.is_disable_metric_cutter(table_id)
        measurement_type_dict[table_id] = get_measurement_type(
            schema_type, rto_dict.get(table_id, False), is_disable_metric_cutter, etl_config
        )

    return measurement_type_dict


def get_table_field_by_table_id(table_id_list: List) -> Dict:
    """获取结果表属性"""
    # 针对黑白名单，如果不是自动发现，则不采用最后更新时间过滤
    white_tables = set(
        ResultTableOption.objects.filter(
            table_id__in=table_id_list, name=ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST, value="false"
        ).values_list("table_id", flat=True)
    )
    table_id_list = list(set(table_id_list) - white_tables)

    # NOTE: 针对自定义时序，过滤掉历史废弃的指标，时间在`TIME_SERIES_METRIC_EXPIRED_SECONDS`的为有效数据
    # 其它类型直接获取所有指标和维度
    begin_time = tz_now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
    # 获取时序的结果表
    ts_groups = TimeSeriesGroup.objects.filter(table_id__in=table_id_list)
    # 获取时序的结果表及关联的group id
    ts_group_id_list, ts_table_id_group_id_map = [], {}
    for ts_group in ts_groups:
        ts_group_id_list.append(ts_group.time_series_group_id)
        ts_table_id_group_id_map[ts_group.time_series_group_id] = ts_group.table_id
    # 获取其它非自定义时序的结果表
    other_table_id_list = set(table_id_list) - set(ts_table_id_group_id_map.values())
    # 通过结果表属性过滤相应数据
    other_table_id_list |= white_tables
    # 针对自定义时序，按照时间过滤数据
    group_field_list = TimeSeriesMetric.objects.filter(
        group_id__in=ts_group_id_list, last_modify_time__gte=begin_time
    ).values("group_id", "field_name")
    # 组装结果表及对应的metric
    table_field_list = []
    for f in group_field_list:
        table_field_list.append({"table_id": ts_table_id_group_id_map[f["group_id"]], "field_name": f["field_name"]})
    # 其它则获取所有指标数据
    other_table_field_list = ResultTableField.objects.filter(table_id__in=other_table_id_list, tag="metric").values(
        "table_id", "field_name"
    )
    table_field_list.extend(other_table_field_list)

    table_field_dict = {}
    for tf in table_field_list:
        table_id = tf["table_id"]
        field_name = tf["field_name"]
        if table_id in table_field_dict:
            table_field_dict[table_id].append(field_name)
        else:
            table_field_dict[table_id] = [field_name]

    return table_field_dict


def get_metadata_bcs_project_data_id() -> Dict:
    """获取项目下的 data id

    格式为{project_id: [data_id1, data_id2]}
    """
    project_cluster_dict = utils.get_metadata_project_dict(desire_all_data=True)
    cluster_data_id_list = utils.get_data_id_by_cluster(desire_all_data=True)
    # 组装数据
    project_data_id_dict = {}
    for p_id, c_id_list in project_cluster_dict.items():
        for c_id in c_id_list:
            # 如果不存在 data id，则跳过
            data_ids = cluster_data_id_list.get(c_id) or set()
            if not data_ids:
                continue
            # 添加数据
            if p_id in project_data_id_dict:
                project_data_id_dict[p_id].union(data_ids)
            else:
                project_data_id_dict[p_id] = data_ids

    return project_data_id_dict


def get_segmented_option_by_table_id(table_id_list: List) -> Dict:
    """通过结果表获取结果表下的分段处理是否开启"""
    rto_list = ResultTableOption.objects.filter(
        table_id__in=table_id_list, name=ResultTableOption.OPTION_SEGMENTED_QUERY_ENABLE
    ).values("table_id", "name", "value")
    return {rto["table_id"]: json.loads(rto["value"]) for rto in rto_list}


def get_influxdb_proxy_cluster_id() -> Dict[str, int]:
    """获取 influxdb proxy 集群的 ID"""
    # 获取结果表对应的实际存储表的映射关系
    influxdb_storage = InfluxDBStorage.objects.all()
    return {
        i.table_id: {
            "storage_cluster_id": i.storage_cluster_id,
            "storage_cluster_name": i.proxy_cluster_name,
            "db": i.database,
            "measurement": i.real_table_name,
            "tag_key": i.consul_cluster_config.get("partition_tag") or [],
        }
        for i in influxdb_storage
    }


def push_redis_data(
    space_type_id: str,
    space_id: str,
    space_code: Optional[str] = None,
    table_id: Optional[str] = None,
):
    """推送 redis 数据

    TODO: 待移除
    """
    space_redis = SpaceRedis()
    if space_type_id == SpaceTypes.BKCC.value:
        space_redis.push_bkcc_type_space(space_id, table_id=table_id)
        logger.info("push bkcc type space: %s successfully", space_id)
        return
    if space_type_id == SpaceTypes.BKCI.value:
        # 针对 bkci 分为蓝盾和容器服务，分别处理
        # 如果 space_code 存在，添加 bcs 的处理
        if space_code:
            space_redis.push_bcs_type_space(space_id, table_id=table_id)
            logger.info("push bcs type space: %s, space_code: %s successfully", space_id, space_code)

        space_redis.push_bkci_type_space(space_id, table_id=table_id)
        logger.info("push bkci type space: %s successfully", space_id)
        return
    if space_type_id == SpaceTypes.BKSAAS.value:
        space_redis.push_bksaas_type_space(space_id, table_id=table_id)
    else:
        logger.error("space_type:%s not found", space_type_id)


def push_and_publish_all_space(
    space_type_id: Optional[str] = None, space_id: Optional[str] = None, is_publish: Optional[bool] = True
):
    """推送redis数据并发布通知

    TODO: 待移除
    """
    # 根据参数过滤出要更新的空间信息
    all_spaces = Space.objects.all()
    if space_type_id:
        all_spaces = all_spaces.filter(space_type_id=space_type_id)
    if space_id:
        all_spaces = all_spaces.filter(space_id=space_id)
    # 获取空间数据
    spaces = all_spaces.values("space_type_id", "space_id", "space_code")
    # 推送相关空间
    redis_space_id_list = []
    for s in spaces:
        push_redis_data(s["space_type_id"], s["space_id"], s["space_code"])
        logger.info(
            "push redis data, space_type_id: %s, space_id: %s, space_code: %s",
            s["space_type_id"],
            s["space_id"],
            s["space_code"],
        )
        redis_space_id_list.append(f"{s['space_type_id']}__{s['space_id']}")

    # 推送空间数据到 redis，用于创建时，推送失败或者没有推送的场景
    RedisTools.push_space_to_redis(SPACE_REDIS_KEY, redis_space_id_list)

    # 参数指定是否需要发布通知
    if is_publish:
        # 发布空间信息，以便依赖服务及时获取变动内容
        RedisTools.publish(SPACE_REDIS_KEY, redis_space_id_list)
        logger.info("all space publish redis")
