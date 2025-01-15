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

from typing import Dict, List, Optional

from django.core.management import BaseCommand

from metadata import models


class Command(BaseCommand):
    """添加蓝盾的维度信息

    NOTE: 如果要同步 dbm 的数据，那么需要在执行完 dbm 命令后再执行当前命令
    """

    help = "add bkci system dimensions"
    # 空间类型
    space_type = "bkcc"
    # 默认的 data id
    default_data_id = 1001
    # 检测已经存在的 rt 名称
    table_id_prefix = "devx"
    rt_name = f"{table_id_prefix}_system.cpu_detail"
    # influxdb 保存时间
    default_duration_time = "90d"
    default_field_list = [
        "bk_biz_id",
        "bk_cloud_id",
        "bk_cmdb_level",
        "bk_supplier_id",
        "ip",
        "time",
        "bk_agent_id",
        "bk_host_id",
        "bk_target_host_id",
    ]
    extend_fields = [
        {
            "field_name": "projectId",
            "field_type": "string",
            "tag": "dimension",
            "default_value": None,
            "is_config_by_user": True,
            "description": "projectId",
            "unit": "",
            "alias_name": "projectId",
        },
        {
            "field_name": "workspaceName",
            "field_type": "string",
            "tag": "dimension",
            "default_value": None,
            "is_config_by_user": True,
            "description": "workspaceName",
            "unit": "",
            "alias_name": "workspaceName",
        },
        {
            "field_name": "owner",
            "field_type": "string",
            "tag": "dimension",
            "default_value": None,
            "is_config_by_user": True,
            "description": "owner",
            "unit": "",
            "alias_name": "owner",
        },
    ]
    extend_options = {
        "enable_devx_meta": True,
        "must_include_dimensions": [i["field_name"] for i in extend_fields],
    }

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=int, required=False, help="data source id, default is 1001")
        parser.add_argument("--proxy_cluster_id", type=int, required=False, help="influxdb proxy id, default is 2")
        parser.add_argument("--duration_time", type=str, required=False, help="influxdb duration time, default is 90d")
        parser.add_argument(
            "--cluster_name", type=str, required=False, help="influxdb cluster name, default is k8s_default_33"
        )

    def handle(self, *args, **options):
        # 获取参数, 默认为 default
        bk_data_id = options.get("bk_data_id") or self.default_data_id
        proxy_cluster_id = self._get_influxdb_proxy_cluster(options.get("proxy_cluster_id"))
        duration_time = options.get("duration_time") or self.default_duration_time
        cluster_name = self._get_influxdb_instance_cluster(options.get("cluster_name"))

        # 获取数据源下面对应的结果表，注意跳过 dbm_ 开头的数据
        table_ids = list(
            models.DataSourceResultTable.objects.filter(bk_data_id=bk_data_id)
            .exclude(table_id__startswith="dbm_")
            .values_list("table_id", flat=True)
        )
        # 判断表是否存在，如果已经存在，则直接返回
        if models.ResultTable.objects.filter(table_id=self.rt_name).exists():
            self.stdout.write("devx_system table is exist!")
            return

        table_id_map = {rt.table_id: rt for rt in models.ResultTable.objects.filter(table_id__in=table_ids)}

        self.stdout.write("start to create devx system data")
        # 组装数据
        # NOTE: 注意默认指标增加了部分，需要移除掉
        table_field_map = self._get_table_fields(table_ids)
        table_field_option_map = self._get_table_field_option(table_ids)
        table_option_map = self._get_table_option(table_ids)

        fields = {}
        # 添加字段 option 及组装字段列表
        for key, val in table_field_map.items():
            val["option"] = table_field_option_map.get(key)
            table_id = val.pop("table_id")
            if table_id in fields:
                fields[table_id].append(val)
            else:
                init_fields = [val]
                init_fields.extend(self.extend_fields)
                fields[table_id] = init_fields

        # 组装参数，创建结果表
        for table_id, table in table_id_map.items():
            option = table_option_map.get(table_id) or {}
            self.extend_options["mapping_result_table"] = table_id
            option.update(self.extend_options)
            params = {
                "bk_data_id": bk_data_id,
                "table_id": f"{self.table_id_prefix}_{table_id}",
                "table_name_zh": table.table_name_zh,
                "is_custom_table": False,
                "schema_type": models.ResultTable.SCHEMA_TYPE_FIXED,
                "operator": "system",
                "default_storage": models.ClusterInfo.TYPE_INFLUXDB,
                "field_list": fields.get(table_id) or self.extend_fields,
                "include_cmdb_level": False,
                "label": "os",
                "option": option,
                "default_storage_config": {
                    "storage_cluster_id": proxy_cluster_id,
                    "source_duration_time": duration_time,
                    "proxy_cluster_name": cluster_name,
                },
            }
            try:
                models.ResultTable.create_result_table(**params)
            except Exception as e:
                self.stderr.write(f"create result table: {self.table_id_prefix}__{table_id} error, {e}")
                return

        # 刷新配置
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        except models.DataSource.DoesNotExist:
            self.stderr.write(f"not found data source: {bk_data_id}")
            return
        try:
            ds.refresh_outer_config()
        except Exception as e:
            self.stderr.write(f"data_id: {bk_data_id} failed to refresh config, {e}")
            return

        # 因为空间级数据源不允许跨空间使用，因此，采用授权的方式
        try:
            self._add_space_datasource(bk_data_id)
        except Exception as e:
            self.stderr.write(f"create space datasource error: {e}")
            return

        self.stdout.write(self.style.SUCCESS("create devx data link success!"))

    def _get_influxdb_proxy_cluster(self, proxy_cluster_id: Optional[int] = None) -> int:
        """获取默认 influxdb proxy 集群 ID"""
        if proxy_cluster_id:
            return proxy_cluster_id
        # 防止有多个默认值的情况
        proxy_cluster_obj = models.ClusterInfo.objects.filter(
            cluster_type=models.ClusterInfo.TYPE_INFLUXDB, is_default_cluster=True
        ).first()
        if not proxy_cluster_obj:
            raise ValueError("not found default influxdb proxy cluster, please check metadata ClusterInfo")
        return proxy_cluster_obj.cluster_id

    def _get_influxdb_instance_cluster(self, cluster_name: Optional[str] = None) -> str:
        """获取 influxdb 实例集群"""
        if cluster_name:
            return cluster_name

        # 如果没有传递值，则使用默认 default 集群
        return models.InfluxDBClusterInfo.DEFAULT_CLUSTER_NAME

    def _get_table_fields(self, table_ids: List[str]) -> Dict:
        # 获取结果表对应的字段
        table_field_map = {}
        # 过滤数据
        table_fields = models.ResultTableField.objects.filter(table_id__in=table_ids)
        # 组装数据，便于后续的匹配
        for tf in table_fields:
            if tf.field_name in self.default_field_list:
                continue
            table_field_map[f"{tf.table_id}:{tf.field_name}"] = {
                "table_id": tf.table_id,
                "field_name": tf.field_name,
                "field_type": tf.field_type,
                "description": tf.description,
                "unit": tf.unit,
                "tag": tf.tag,
                "is_config_by_user": tf.is_config_by_user,
                "default_value": tf.default_value,
                "creator": tf.creator,
                "alias_name": tf.alias_name,
            }
        return table_field_map

    def _get_table_field_option(self, table_ids: List[str]) -> Dict:
        # 获取字段对应的option
        table_field_option_map = {}
        # 过滤数据
        table_field_options = models.ResultTableFieldOption.objects.filter(table_id__in=table_ids)
        # 组装数据，便于后续的匹配
        for tfo in table_field_options:
            key = f"{tfo.table_id}:{tfo.field_name}"
            item = tfo.to_json()
            if key in table_field_option_map:
                table_field_option_map[key].update(item)
            else:
                table_field_option_map[key] = item
        return table_field_option_map

    def _get_table_option(self, table_ids: List[str]) -> Dict:
        # 获取结果表关联的option
        table_option_map = {}
        # 过滤数据
        table_options = models.ResultTableOption.objects.filter(table_id__in=table_ids)
        # 组装数据，便于后续的匹配
        for to in table_options:
            item = to.to_json()
            if to.table_id in table_option_map:
                table_option_map[to.table_id].update(item)
            else:
                table_option_map[to.table_id] = item
        return table_option_map

    def _add_space_datasource(self, bk_data_id: int):
        """针对所有的 bkci 类型空间授权访问 1001 数据"""
        space_ids = models.Space.objects.filter(space_type_id=self.space_type).values_list("space_id", flat=True)
        for space_id in space_ids:
            models.SpaceDataSource.objects.get_or_create(
                space_type_id=self.space_type,
                space_id=space_id,
                bk_data_id=bk_data_id,
                defaults={"from_authorization": True},
            )

        self.stdout.write("create space datasource successfully")
