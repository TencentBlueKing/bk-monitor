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

from django.conf import settings
from django.db.models import Q

from constants.common import DEFAULT_TENANT_ID
from metadata import models
from metadata.models.space.constants import EtlConfigs, MeasurementType, SpaceTypes
from metadata.utils.db import filter_model_by_in_page

logger = logging.getLogger("metadata")


def get_result_tables_by_data_ids(
    data_id_list: list | None = None,
    table_id_list: list | None = None,
    bk_tenant_id: str | None = DEFAULT_TENANT_ID,
) -> dict:
    """通过数据源 ID 获取结果表数据"""
    query_filter = Q()
    if data_id_list:
        query_filter &= Q(bk_data_id__in=data_id_list)

    if table_id_list:
        query_filter &= Q(table_id__in=table_id_list)

    if settings.ENABLE_MULTI_TENANT_MODE:
        query_filter &= Q(bk_tenant_id=bk_tenant_id)

    qs = models.DataSourceResultTable.objects.filter(query_filter).values("bk_data_id", "table_id")
    return {data["table_id"]: data["bk_data_id"] for data in qs}


# 缓存平台或者类型级的数据源,区分多租户、分多租户环境,多租户环境下仅返回租户下的全局数据和平台全局数据(1001)
def get_platform_data_ids(space_type: str | None = None, bk_tenant_id=DEFAULT_TENANT_ID) -> dict[int, str]:
    """获取平台级的数据源
    NOTE: 仅针对当前空间类型，比如 bkcc，特殊的是 all 类型
    """
    qs = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, is_platform_data_id=True).values(
        "bk_data_id", "space_type_id"
    )

    # 如果是多租户的情况下，需要去除单租户模式下的全局数据源
    if settings.ENABLE_MULTI_TENANT_MODE:
        qs = qs.exclude(
            bk_data_id__in=[
                settings.SNAPSHOT_DATAID,
                settings.MYSQL_METRIC_DATAID,
                settings.REDIS_METRIC_DATAID,
                settings.APACHE_METRIC_DATAID,
                settings.NGINX_METRIC_DATAID,
                settings.TOMCAT_METRIC_DATAID,
                settings.PROCESS_PERF_DATAID,
                settings.PROCESS_PORT_DATAID,
                settings.UPTIMECHECK_HEARTBEAT_DATAID,
                settings.UPTIMECHECK_TCP_DATAID,
                settings.UPTIMECHECK_UDP_DATAID,
                settings.UPTIMECHECK_HTTP_DATAID,
                settings.UPTIMECHECK_ICMP_DATAID,
                settings.PING_SERVER_DATAID,
                settings.GSE_CUSTOM_EVENT_DATAID,
            ]
        )

    # 针对 bkcc 类型，这要是插件，不属于某个业务空间，也没有传递空间类型，因此，需要包含 all 类型
    if space_type and space_type != SpaceTypes.BKCC.value:
        qs = qs.filter(space_type_id=space_type)
    data_ids = {data["bk_data_id"]: data["space_type_id"] for data in qs}
    return data_ids


# TODO: BkBase多租户
def get_table_info_for_influxdb_and_vm(
    table_id_list: list | None = None,
    bk_tenant_id: str | None = DEFAULT_TENANT_ID,
) -> dict:
    """获取influxdb 和 vm的结果表"""
    vm_tables = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id).values(
        "result_table_id", "vm_cluster_id", "vm_result_table_id", "bk_tenant_id"
    )
    # 如果结果表存在，则过滤指定的结果表
    if table_id_list:
        vm_tables = vm_tables.filter(result_table_id__in=table_id_list)

    vm_table_map = {
        data["result_table_id"]: {"vm_rt": data["vm_result_table_id"], "storage_id": data["vm_cluster_id"]}
        for data in vm_tables
    }

    influxdb_tables = models.InfluxDBStorage.objects.values(
        "table_id", "database", "real_table_name", "influxdb_proxy_storage_id", "partition_tag"
    )
    # 如果结果表存在，则过滤指定的结果表
    if table_id_list:
        influxdb_tables = influxdb_tables.filter(table_id__in=table_id_list)
    influxdb_table_map = {
        data["table_id"]: {
            "influxdb_proxy_storage_id": data["influxdb_proxy_storage_id"],
            "db": data["database"],
            "measurement": data["real_table_name"],
            "tags_key": data["partition_tag"] != "" and data["partition_tag"].split(",") or [],
        }
        for data in influxdb_tables
    }
    # 获取proxy关联的集群信息
    storage_cluster_map = {
        data["id"]: {
            "proxy_cluster_id": data["proxy_cluster_id"],
            "instance_cluster_name": data["instance_cluster_name"],
        }
        for data in models.InfluxDBProxyStorage.objects.values("id", "proxy_cluster_id", "instance_cluster_name")
    }
    table_id_info = {}
    # 进行数据的匹配
    # 处理 influxdb 的数据信息
    for table_id, detail in influxdb_table_map.items():
        influxdb_proxy_storage_id = detail["influxdb_proxy_storage_id"]
        storage_clusters = storage_cluster_map.get(influxdb_proxy_storage_id, {})
        storage_id = storage_clusters.get("proxy_cluster_id") or 0
        cluster_name = storage_clusters.get("instance_cluster_name") or ""
        table_id_info[table_id] = {
            "storage_id": storage_id,
            "storage_name": "",
            "cluster_name": cluster_name,
            "db": detail["db"],
            "measurement": detail["measurement"],
            "vm_rt": "",
            "tags_key": detail["tags_key"],
            "storage_type": models.InfluxDBStorage.STORAGE_TYPE,
        }
    # 仅有几条记录，查询一次 vm 集群列表，获取到集群ID和名称关系
    vm_cluster_id_name = {
        cluster["cluster_id"]: cluster["cluster_name"]
        for cluster in models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM).values(
            "cluster_id", "cluster_name"
        )
    }
    # 处理 vm 的数据信息
    for table_id, detail in vm_table_map.items():
        cmdb_level_vm_rt_opts = models.ResultTableOption.objects.filter(
            table_id=table_id, name="cmdb_level_vm_rt", bk_tenant_id=bk_tenant_id
        ).first()
        if cmdb_level_vm_rt_opts:
            detail["cmdb_level_vm_rt"] = cmdb_level_vm_rt_opts.value
        else:
            detail["cmdb_level_vm_rt"] = ""

        storage_name = vm_cluster_id_name.get(detail["storage_id"], "")
        if table_id in table_id_info:
            table_id_info[table_id].update(
                {
                    "vm_rt": detail["vm_rt"],
                    "storage_name": storage_name,
                    "storage_type": models.ClusterInfo.TYPE_VM,
                    "cmdb_level_vm_rt": detail["cmdb_level_vm_rt"],
                }
            )
        else:
            detail.update(
                {
                    "cluster_name": "",
                    "storage_name": storage_name,
                    "db": "",
                    "measurement": MeasurementType.BK_SPLIT.value,
                    "tags_key": [],
                    "storage_type": models.ClusterInfo.TYPE_VM,
                }
            )
            table_id_info[table_id] = detail
    return table_id_info


def compose_monitor_table_detail_for_bkbase_type(table_id_list: list | None = None) -> dict:
    """
    针对接入过计算平台类型的结果表，组装其详情信息，为RESULT_TABLE_DETAIL使用,现阶段只有VM类型
    TODO 该方法暂时未启用
    @param table_id_list: 监控平台自身结果表列表
    """
    # 0. 先从BkBaseResultTable中提取必要信息：监控平台RT、计算平台RT、存储集群
    bkbase_tables = models.BkBaseResultTable.objects.values("monitor_table_id", "storage_cluster_id", "bkbase_table_id")
    # 1. 如果结果表存在，则过滤指定的结果表
    if table_id_list:
        bkbase_tables = bkbase_tables.filter(monitor_table_id__in=table_id_list)

    # 2. 拼接基本信息 监控RT:{vm_rt:vm_rt,storage_id:storage_id}
    bkbase_table_map = {
        data["monitor_table_id"]: {"vm_rt": data["bkbase_table_id"], "storage_id": data["storage_cluster_id"]}
        for data in bkbase_tables
    }

    # 3. 查询集群名称和ID的映射关系，现阶段只适配VM
    bkbase_cluster_id_name = {
        cluster["cluster_id"]: cluster["cluster_name"]
        for cluster in models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM).values(
            "cluster_id", "cluster_name"
        )
    }

    # 4. 循环遍历，拼接详情信息
    table_id_info = {}
    for table_id, detail in bkbase_table_map.items():
        storage_name = bkbase_cluster_id_name.get(detail["storage_id"], "")
        cmdb_level_vm_rt_opts = models.ResultTableOption.objects.filter(
            table_id=table_id, name="cmdb_level_vm_rt"
        ).first()
        if cmdb_level_vm_rt_opts:
            detail["cmdb_level_vm_rt"] = cmdb_level_vm_rt_opts.value
        else:
            detail["cmdb_level_vm_rt"] = ""

        if table_id in table_id_info:
            table_id_info[table_id].update(
                {"vm_rt": detail["vm_rt"], "storage_name": storage_name, "cmdb_level_vm_rt": detail["cmdb_level_vm_rt"]}
            )
        else:
            detail.update(
                {
                    "cluster_name": "",
                    "storage_name": storage_name,
                    "db": "",
                    "measurement": MeasurementType.BK_SPLIT.value,
                    "tags_key": [],
                    "storage_type": models.ClusterInfo.TYPE_VM,
                }
            )
            table_id_info[table_id] = detail
    return table_id_info


def get_space_table_id_data_id(
    space_type: str,
    space_id: str,
    table_id_list: list | None = None,
    from_authorization: bool | None = None,
    include_platform_data_id: bool | None = True,
    exclude_data_id_list: list | None = None,
    bk_tenant_id: str | None = DEFAULT_TENANT_ID,
) -> dict:
    """获取空间下的结果表和数据源信息"""
    logger.info(
        "get_space_table_id_data_id: try to get data,for space_type->[%s],space_id->[%s],bk_tenant_id->[%s]",
        space_type,
        space_id,
        bk_tenant_id,
    )

    # 如果结果表存在，则直接过滤对应的数据
    if table_id_list:
        logger.info("get_space_table_id_data_id: try to get data with table_id_list->[%s]", table_id_list)
        if settings.ENABLE_MULTI_TENANT_MODE:  # 若开启多租户,则需要携带租户信息进行过滤
            # Q: 为什么不在结果表生成时,在table_id中拼接租户属性，从而做到结果表全局唯一？
            # A: 外部导入的插件,如redis_exporter、mongodb_exporter以及一些内置采集,结果表命名相对固定,使用额外字段过滤更为稳定安全
            logger.info("get_space_table_id_data_id: try to get data with bk_tenant_id->[%s]", bk_tenant_id)
            qs = models.DataSourceResultTable.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id)
        else:
            qs = models.DataSourceResultTable.objects.filter(table_id__in=table_id_list)

        return {
            data["table_id"]: data["bk_data_id"]
            for data in qs.exclude(bk_data_id__in=exclude_data_id_list).values("bk_data_id", "table_id")
        }

    # 这里理论上不用携带租户信息进行查询,因为space_uid是全租户唯一的
    # 否则，查询空间下的所有数据源，再过滤对应的结果表
    sp_ds = models.SpaceDataSource.objects.filter(space_type_id=space_type, space_id=space_id)

    # 获取是否授权数据
    if from_authorization is not None:
        logger.info("get_space_table_id_data_id: try to get data with from_authorization->[%s]", from_authorization)
        sp_ds = sp_ds.filter(from_authorization=from_authorization)

    data_ids = set(sp_ds.values_list("bk_data_id", flat=True))

    # 过滤包含全局空间级的数据源,平台数据源、租户下全业务等
    if include_platform_data_id:
        data_ids |= set(get_platform_data_ids(space_type=space_type, bk_tenant_id=bk_tenant_id).keys())

    # 排除元素
    if exclude_data_id_list:
        data_ids = data_ids - set(exclude_data_id_list)

    # 组装数据
    # 采用分页过滤数据
    _filter_data = filter_model_by_in_page(
        model=models.DataSourceResultTable,
        field_op="bk_data_id__in",
        filter_data=data_ids,
        value_func="values",
        value_field_list=["bk_data_id", "table_id"],
    )
    return {data["table_id"]: data["bk_data_id"] for data in _filter_data}


def get_measurement_type_by_table_id(
    table_ids: set, table_list: list, table_id_data_id: dict, bk_tenant_id: str | None = DEFAULT_TENANT_ID
) -> dict:
    """通过结果表 ID, 获取节点表对应的 option 配置
    通过 option 转到到 measurement 类型
    """
    # 过滤对应关系，用以进行判断单指标单表、多指标单表

    logger.info(
        "get_measurement_type_by_table_id: try to get data,for table_ids->[%s],table_list->[%s],table_id_data_id->[%s]",
        table_ids,
        table_list,
        table_id_data_id,
    )

    if settings.ENABLE_MULTI_TENANT_MODE:
        logger.info("get_measurement_type_by_table_id: try to get data with bk_tenant_id->[%s]", bk_tenant_id)
        qs = models.ResultTableOption.objects.filter(
            table_id__in=table_ids, name=models.DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT, bk_tenant_id=bk_tenant_id
        ).values("table_id", "name", "value")
    else:
        qs = models.ResultTableOption.objects.filter(
            table_id__in=table_ids, name=models.DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT
        ).values("table_id", "name", "value")

    rto_dict = {rto["table_id"]: json.loads(rto["value"]) for rto in qs}

    # 过滤数据源对应的 etl_config
    data_etl_dict = {
        d["bk_data_id"]: d["etl_config"]
        for d in models.DataSource.objects.filter(bk_data_id__in=table_id_data_id.values()).values(
            "bk_data_id", "etl_config"
        )
    }
    # 获取到对应的类型
    measurement_type_dict = {}
    if settings.ENABLE_MULTI_TENANT_MODE:  # 若开启多租户,则需要携带租户信息进行过滤
        table_id_cutter = models.ResultTable.get_table_id_cutter(table_ids=table_ids, bk_tenant_id=bk_tenant_id)
    else:
        table_id_cutter = models.ResultTable.get_table_id_cutter(table_ids=table_ids)

    for table in table_list:
        table_id, schema_type = table["table_id"], table["schema_type"]
        etl_config = data_etl_dict.get(table_id_data_id.get(table_id))
        # 获取是否禁用指标切分模式
        is_disable_metric_cutter = table_id_cutter.get(table_id) or False
        measurement_type_dict[table_id] = get_measurement_type(
            schema_type, rto_dict.get(table_id, False), is_disable_metric_cutter, etl_config
        )

    return measurement_type_dict


def get_measurement_type(
    schema_type: str, is_split_measurement: bool, is_disable_metric_cutter: bool, etl_config: str | None = None
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
    if schema_type == models.ResultTable.SCHEMA_TYPE_FIXED:
        return MeasurementType.BK_TRADITIONAL.value
    if schema_type == models.ResultTable.SCHEMA_TYPE_FREE:
        if is_split_measurement:
            return MeasurementType.BK_SPLIT.value

        if etl_config != EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value:
            return MeasurementType.BK_EXPORTER.value

        if not is_disable_metric_cutter:
            return MeasurementType.BK_EXPORTER.value
        return MeasurementType.BK_STANDARD_V2_TIME_SERIES.value

    # 如果为其它，设置为未知
    return MeasurementType.BK_TRADITIONAL.value


def get_cluster_data_ids(
    cluster_id_list: list, table_id_list: list | None = None, bk_tenant_id: str | None = DEFAULT_TENANT_ID
) -> dict:
    """获取集群及数据源"""
    # 如果指定结果表, 则仅过滤结果表对应的数据源
    data_id_list = []
    if table_id_list:
        if settings.ENABLE_MULTI_TENANT_MODE:
            data_id_list.extend(
                list(
                    models.DataSourceResultTable.objects.filter(
                        table_id__in=table_id_list, bk_tenant_id=bk_tenant_id
                    ).values_list("bk_data_id", flat=True)
                )
            )
        else:
            data_id_list.extend(
                list(
                    models.DataSourceResultTable.objects.filter(table_id__in=table_id_list).values_list(
                        "bk_data_id", flat=True
                    )
                )
            )
    # 如果集群存在，则获取集群下的内置和自定义数据源
    elif cluster_id_list:  # 集群ID全租户唯一
        metric_data_ids = (
            models.BCSClusterInfo.objects.filter(cluster_id__in=cluster_id_list)
            .exclude(
                status__in=[
                    models.BCSClusterInfo.CLUSTER_STATUS_DELETED,
                    models.BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
                ],
            )
            .values("K8sMetricDataID", "CustomMetricDataID")
        )
        for data in metric_data_ids:
            data_id_list.append(data["K8sMetricDataID"])
            data_id_list.append(data["CustomMetricDataID"])

    # 过滤到集群的数据源，仅包含两类，集群内置和集群自定义
    data_id_cluster_id = {
        data["K8sMetricDataID"]: data["cluster_id"]
        for data in models.BCSClusterInfo.objects.filter(K8sMetricDataID__in=data_id_list).values(
            "K8sMetricDataID", "cluster_id"
        )
    }
    data_id_cluster_id.update(
        {
            data["CustomMetricDataID"]: data["cluster_id"]
            for data in models.BCSClusterInfo.objects.filter(CustomMetricDataID__in=data_id_list).values(
                "CustomMetricDataID", "cluster_id"
            )
        }
    )
    return data_id_cluster_id


def get_table_id_cluster_id(table_id_list: list | set, bk_tenant_id: str | None = DEFAULT_TENANT_ID) -> dict[str, str]:
    """获取结果表对应的集群 ID"""

    if settings.ENABLE_MULTI_TENANT_MODE:
        logger.info(
            "get_table_id_cluster_id: try to get data with bk_tenant_id->[%s],table_id_list->[%s]",
            bk_tenant_id,
            table_id_list,
        )
        table_id_data_id = {
            data["table_id"]: data["bk_data_id"]
            for data in models.DataSourceResultTable.objects.filter(
                table_id__in=table_id_list, bk_tenant_id=bk_tenant_id
            ).values("bk_data_id", "table_id")
        }
    else:
        table_id_data_id = {
            data["table_id"]: data["bk_data_id"]
            for data in models.DataSourceResultTable.objects.filter(table_id__in=table_id_list).values(
                "bk_data_id", "table_id"
            )
        }

    data_ids = table_id_data_id.values()
    # 过滤到集群的数据源，仅包含两类，集群内置和集群自定义
    data_id_cluster_id = {
        data["K8sMetricDataID"]: data["cluster_id"]
        for data in models.BCSClusterInfo.objects.filter(K8sMetricDataID__in=data_ids)
        .exclude(
            status__in=[
                models.BCSClusterInfo.CLUSTER_STATUS_DELETED,
                models.BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
            ]
        )
        .values("K8sMetricDataID", "cluster_id")
    }
    data_id_cluster_id.update(
        {
            data["CustomMetricDataID"]: data["cluster_id"]
            for data in models.BCSClusterInfo.objects.filter(CustomMetricDataID__in=data_ids)
            .exclude(
                status__in=[
                    models.BCSClusterInfo.CLUSTER_STATUS_DELETED,
                    models.BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
                ]
            )
            .values("CustomMetricDataID", "cluster_id")
        }
    )
    # 组装结果表到集群的信息
    table_id_cluster_id = {
        table_id: data_id_cluster_id.get(data_id) or "" for table_id, data_id in table_id_data_id.items()
    }

    return table_id_cluster_id
