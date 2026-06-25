"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any, ClassVar

import json
import math

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.user import get_global_user
from common.log import logger
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from metadata import models as metadata_models
from rum.constants import DATABASE_CONNECTION_NAME, RUM_ELASTICSEARCH_CLUSTER_ID, RUM_KAFKA_CLUSTER_ID
from constants.rum import (
    RumDataSourceConfig,
    RUM_RESULT_TABLE_OPTION,
)


class RumDataSourceConfigBase(models.Model):
    """
    RUM 数据源基类
    """

    RUM_DATASOURCE = "rum"
    METRIC_DATASOURCE = "metric"

    TABLE_SPACE_PREFIX = "space"

    DATASOURCE_CHOICE = (
        (RUM_DATASOURCE, "Rum"),
        (METRIC_DATASOURCE, "Metric"),
    )

    DATA_NAME_PREFIX = "bkrum"

    DATASOURCE_TYPE_MAP = {
        RUM_DATASOURCE: "rum",
        METRIC_DATASOURCE: "metric",
    }

    # 子类需要定义的类变量
    DATA_ID_PARAM: ClassVar[dict[str, Any]]
    DATASOURCE_TYPE: ClassVar[str]

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("所属应用", max_length=255)
    bk_data_id = models.IntegerField("数据id", default=-1)
    result_table_id = models.CharField("结果表id", max_length=128, default="")

    class Meta:
        abstract = True
        index_together = [["bk_biz_id", "app_name"]]

    @staticmethod
    def to_safe_name(app_name: str) -> str:
        """将 app_name 中的点号和中划线替换为下划线"""
        return app_name.replace(".", "_").replace("-", "_")

    @property
    def safe_app_name(self) -> str:
        return self.to_safe_name(self.app_name)

    @property
    def data_name(self) -> str:
        bk_biz_id = int(self.bk_biz_id)

        if bk_biz_id > 0:
            return f"{bk_biz_id}_{self.DATA_NAME_PREFIX}_{self.DATASOURCE_TYPE}_{self.safe_app_name}"
        else:
            return (
                f"{self.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{self.DATA_NAME_PREFIX}"
                f"_{self.DATASOURCE_TYPE}_{self.safe_app_name}"
            )

    @property
    def table_id(self) -> str:
        raise NotImplementedError

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        raise NotImplementedError

    @classmethod
    def start(cls, bk_biz_id, app_name):
        instance = cls.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        if instance:
            instance.switch_result_table(True)

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        instance = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if instance:
            instance.switch_result_table(False)

    def switch_result_table(self, is_enable=True):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        resource.metadata.modify_result_table(
            {
                "table_id": self.result_table_id,
                "is_enable": is_enable,
                "bk_tenant_id": bk_tenant_id,
                "operator": get_global_user(bk_tenant_id=bk_tenant_id),
            }
        )

    def create_data_id(self):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        if self.bk_data_id != -1:
            return self.bk_data_id
        try:
            data_id_info = resource.metadata.query_data_source(bk_tenant_id=bk_tenant_id, data_name=self.data_name)
        except metadata_models.DataSource.DoesNotExist:
            data_link_param = {}
            if RUM_KAFKA_CLUSTER_ID:
                data_link_param["mq_cluster"] = RUM_KAFKA_CLUSTER_ID  # 从settings中获取
            data_id_info = resource.metadata.create_data_id(
                {
                    "bk_tenant_id": bk_tenant_id,
                    "bk_biz_id": self.bk_biz_id,
                    "data_name": self.data_name,
                    "operator": get_global_user(bk_tenant_id=bk_tenant_id),
                    "data_description": self.data_name,
                    **self.DATA_ID_PARAM,
                    **data_link_param,
                }
            )
        bk_data_id = data_id_info["bk_data_id"]
        self.bk_data_id = bk_data_id
        self.save()
        return bk_data_id

    def create_or_update_result_table(self, **option):
        pass

    def to_json(self):
        return {"bk_data_id": self.bk_data_id, "result_table_id": self.result_table_id}

    @classmethod
    @atomic(using=DATABASE_CONNECTION_NAME)
    def apply_datasource(cls, bk_biz_id, app_name, **options):
        obj = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not obj:
            obj = cls.objects.create(bk_biz_id=bk_biz_id, app_name=app_name)
        # 创建 data_id
        obj.create_data_id()
        # 创建结果表
        obj.create_or_update_result_table(**options)

        option = options["option"]
        if not option:
            # 关闭
            obj.stop(bk_biz_id, app_name)
            return


class MetricDataSource(RumDataSourceConfigBase):
    DATASOURCE_TYPE = RumDataSourceConfigBase.METRIC_DATASOURCE

    DEFAULT_MEASUREMENT = "__default__"

    DATA_ID_PARAM = {
        "etl_config": "bk_standard_v2_time_series",
        "type_label": DataTypeLabel.TIME_SERIES,
        "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
        "option": {"inject_local_time": True},
    }

    METRIC_NAME = "bk_rum_duration"

    time_series_group_id = models.IntegerField("时序分组ID", default=0)
    data_label = models.CharField("数据标签", max_length=128, default="")
    bk_data_virtual_metric_config = JsonField("数据平台虚拟指标配置", null=True)

    def to_json(self):
        return {
            "bk_data_id": self.bk_data_id,
            "result_table_id": self.result_table_id,
            "time_series_group_id": self.time_series_group_id,
        }

    @property
    def event_group_name(self) -> str:
        return f"bkrum_{self.safe_app_name}_{self.DATASOURCE_TYPE}"

    @property
    def table_id(self) -> str:
        bk_biz_id = int(self.bk_biz_id)
        return self.get_table_id(bk_biz_id, self.safe_app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        safe_name = cls.to_safe_name(app_name)
        if bk_biz_id > 0:
            return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}_{cls.DATASOURCE_TYPE}_{safe_name}.{cls.DEFAULT_MEASUREMENT}"
        else:
            return (
                f"{cls.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{cls.DATA_NAME_PREFIX}_"
                f"{cls.DATASOURCE_TYPE}_{safe_name}.{cls.DEFAULT_MEASUREMENT}"
            )

    def create_or_update_result_table(self, **option):
        if self.result_table_id != "":
            return

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        global_user = get_global_user(bk_tenant_id=bk_tenant_id)
        params = {
            "operator": global_user,
            "bk_data_id": self.bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "bk_tenant_id": bk_tenant_id,
            "time_series_group_name": self.event_group_name,
            "label": "application_check",
            "table_id": self.table_id,
            "is_split_measurement": True,
        }

        group_info = resource.metadata.create_time_series_group(params)
        resource.metadata.modify_time_series_group(
            {
                "bk_tenant_id": bk_tenant_id,
                "time_series_group_id": group_info["time_series_group_id"],
                "field_list": [
                    {
                        "field_name": self.METRIC_NAME,
                        "field_type": "float",
                        "tag": "metric",
                        "description": f"{self.app_name}",
                        "unit": "ns",
                    }
                ],
                "operator": global_user,
            }
        )
        self.time_series_group_id = group_info["time_series_group_id"]
        self.result_table_id = group_info["table_id"]
        self.data_label = group_info.get("data_label", "")
        self.save()

    def update_fields(self, field_list):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        return resource.metadata.modify_time_series_group(
            {
                "bk_tenant_id": bk_tenant_id,
                "time_series_group_id": self.time_series_group_id,
                "field_list": field_list,
                "operator": get_global_user(bk_tenant_id=bk_tenant_id),
            }
        )


class RumDataSource(RumDataSourceConfigBase):
    DATASOURCE_TYPE = RumDataSourceConfigBase.RUM_DATASOURCE

    DATA_ID_PARAM = {
        "etl_config": "bk_flat_batch",
        "type_label": DataTypeLabel.LOG,
        "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
        "option": {
            "encoding": "UTF-8",
            "is_log_data": True,
            "allow_metrics_missing": True,
        },
    }

    STORAGE_TYPE = "elasticsearch"

    # 默认的动态维度发现配置
    ES_DYNAMIC_CONFIG = {
        "dynamic_templates": [
            {
                "strings_as_keywords": {
                    "match_mapping_type": "string",
                    "mapping": {"norms": "false", "type": "keyword"},
                }
            }
        ]
    }

    DEFAULT_ES_WARM_RETENTION_RATIO = 0.5

    index_set_id = models.IntegerField("索引集id", null=True)
    index_set_name = models.CharField("索引集名称", max_length=512, null=True)

    def to_json(self):
        return {**super().to_json(), "index_set_id": self.index_set_id}

    @property
    def table_id(self) -> str:
        return self.get_table_id(int(self.bk_biz_id), self.safe_app_name)

    @classmethod
    def get_table_id(cls, bk_biz_id: int, app_name: str, **kwargs) -> str:
        safe_name = cls.to_safe_name(app_name)
        if bk_biz_id > 0:
            return f"{bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{safe_name}"
        else:
            return f"{cls.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{cls.DATA_NAME_PREFIX}.{cls.DATASOURCE_TYPE}_{safe_name}"

    def create_or_update_result_table(self, **option):
        table_id = self.table_id
        if self.result_table_id:
            table_id = self.result_table_id

        es_storage_cluster = option.get("es_storage_cluster") or RUM_ELASTICSEARCH_CLUSTER_ID
        if not es_storage_cluster:
            raise ValueError(
                "es_storage_cluster is required, either from option or RUM_ELASTICSEARCH_CLUSTER_ID setting"
            )

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        params = {
            "bk_data_id": self.bk_data_id,
            "table_id": table_id,
            "bk_tenant_id": bk_tenant_id,
            "operator": get_global_user(bk_tenant_id=bk_tenant_id),
            "is_enable": True,
            "table_name_zh": self.app_name,
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": "elasticsearch",
            "default_storage_config": {
                "cluster_id": es_storage_cluster,
                "storage_cluster_id": es_storage_cluster,
                "index_set": self.table_id.replace(".", "_"),
                "slice_size": option.get("es_slice_size", settings.RUM_APP_DEFAULT_ES_SLICE_LIMIT),
                "retention": option.get("es_retention", settings.RUM_APP_DEFAULT_ES_RETENTION),
                "slice_gap": 60 * 24,
                "date_format": "%Y%m%d",
                "mapping_settings": self.ES_DYNAMIC_CONFIG,
                "index_settings": {
                    "number_of_shards": option.get("es_shards", settings.RUM_APP_DEFAULT_ES_SHARDS),
                    "number_of_replicas": option.get("es_number_of_replicas", settings.RUM_APP_DEFAULT_ES_REPLICAS),
                },
            },
            "field_list": RumDataSourceConfig.RUM_FIELD_LIST,
            "is_time_field_only": True,
            "bk_biz_id": self.bk_biz_id,
            "label": "application_check",
            "option": RUM_RESULT_TABLE_OPTION,
            "time_option": {
                "es_type": "date",
                "es_format": "epoch_millis",
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "time_zone": 0,
            },
        }

        # 获取集群信息，处理冷热集群
        try:
            cluster_info_list = api.metadata.query_cluster_info(
                bk_tenant_id=bk_biz_id_to_bk_tenant_id(self.bk_biz_id),
                cluster_id=es_storage_cluster,
                cluster_type="elasticsearch",
            )
            cluster_info = cluster_info_list[0]
            custom_option = json.loads(cluster_info["cluster_config"].get("custom_option"))
            hot_warm_config = custom_option.get("hot_warm_config", {})
        except Exception as e:
            hot_warm_config = {}
            logger.error(f"集群ID:{es_storage_cluster}, error: {e}")

        if hot_warm_config and hot_warm_config.get("is_enabled"):
            es_retention = option.get("es_retention", settings.RUM_APP_DEFAULT_ES_RETENTION)
            allocation_min_days = math.ceil(es_retention * self.DEFAULT_ES_WARM_RETENTION_RATIO)

            params["default_storage_config"]["index_settings"].update(
                {
                    f"index.routing.allocation.include.{hot_warm_config['hot_attr_name']}": hot_warm_config[
                        "hot_attr_value"
                    ],
                }
            )
            params["default_storage_config"].update(
                {
                    "warm_phase_days": allocation_min_days,
                    "warm_phase_settings": {
                        "allocation_attr_name": hot_warm_config["warm_attr_name"],
                        "allocation_attr_value": hot_warm_config["warm_attr_value"],
                        "allocation_type": "include",
                    },
                }
            )

        index_set_id, index_set_name = self.update_or_create_index_set(es_storage_cluster, self.index_set_id)

        if self.result_table_id != "":
            # 更新存储
            params["external_storage"] = {
                "elasticsearch": params["default_storage_config"],
            }
            resource.metadata.modify_result_table(params)
            return

        params["is_sync_db"] = False
        resource.metadata.create_result_table(params)

        self.result_table_id = self.table_id
        self.index_set_name = index_set_name
        self.index_set_id = index_set_id
        self.save()

    def update_or_create_index_set(self, storage_id, index_set_id=None):
        table_id = self.table_id
        if self.result_table_id:
            table_id = self.result_table_id

        params = {
            "index_set_name": self.index_set,
            "bk_biz_id": self.bk_biz_id,
            "category_id": "application_check",
            "scenario_id": "es",
            "view_roles": [],
            "indexes": [
                {
                    "bk_biz_id": self.bk_biz_id,
                    "result_table_id": f"{table_id.replace('.', '_')}_*",
                }
            ],
            "storage_cluster_id": storage_id,
            "time_field": "time",
            "time_field_unit": "microsecond",
            "time_field_type": "date",
            "is_editable": False,
        }

        if not index_set_id:
            try:
                res = api.log_search.create_index_set(**params)
            except Exception as e:  # noqa
                logger.error(f"[RumDataSource] create index set failed {e} \nparams: {params}")
                return None, None
        else:
            try:
                res = api.log_search.update_index_set(index_set_id=index_set_id, **params)
            except Exception as e:  # noqa
                logger.error(
                    f"[RumDataSource] update index set failed {e} \n index set id: {index_set_id} params: {params}"
                )
                return self.index_set_id, self.index_set_name

        return res.get("index_set_id"), res.get("index_set_name")

    @property
    def index_set(self) -> str:
        return f"{self.table_id.replace('.', '_')}_index_set"

    @cached_property
    def retention(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).values_list(
            "retention", flat=True
        )[0]

    @cached_property
    def es_client(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).first().get_client()

    @cached_property
    def storage(self):
        return metadata_models.ESStorage.objects.filter(table_id=self.result_table_id).first()

    @classmethod
    def stop(cls, bk_biz_id, app_name):
        super().stop(bk_biz_id, app_name)
        # 删除关联的索引集
        ins = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if ins and ins.index_set_id:
            try:
                api.log_search.delete_index_set(index_set_id=ins.index_set_id)
                logger.info(f"[StopRumDatasource] delete index_set_id: {ins.index_set_id} of ({bk_biz_id}){app_name}")
            except Exception as e:
                logger.error(f"[StopRumDatasource] delete index_set_id: {ins.index_set_id} failed, error: {e}")
