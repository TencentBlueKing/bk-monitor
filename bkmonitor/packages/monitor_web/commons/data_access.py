"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from django.conf import settings
from django.utils.encoding import force_str
from django.utils.translation import gettext as _

from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api
from core.errors.api import BKAPIError
from monitor.constants import UptimeCheckProtocol
from monitor_web.plugin.constant import (
    ORIGIN_PLUGIN_EXCLUDE_DIMENSION,
    PLUGIN_REVERSED_DIMENSION,
    ParamMode,
    PluginType,
)


class ResultTableField:
    FIELD_TYPE_FLOAT = ("double",)
    FIELD_TYPE_STRING = ("text",)

    def __init__(self, field_name, description, tag, field_type, unit="", is_config_by_user=True, alias_name=""):
        """
        field_name: 字段名
        description: 字段描述
        tag: metric 或 dimension 或 group
        field_type: 字段类型,metadata支持int,long,float,string,boolean,timestamp
        is_config_by_user:是否启用
        alias_name: 字段别名
        """
        self.field_name = field_name
        self.description = description
        self.tag = tag
        self.unit = unit
        self.is_config_by_user = is_config_by_user

        if field_type in self.FIELD_TYPE_FLOAT:
            self.field_type = "float"
        elif field_type in self.FIELD_TYPE_STRING:
            self.field_type = "string"
        else:
            self.field_type = field_type

        if alias_name:
            self.alias_name = alias_name


class ResultTable:
    def __init__(self, table_name, description, fields):
        self.table_name = table_name.lower()
        self.description = description
        self.fields = [field.__dict__ for field in fields]
        self.field_instance_list = fields

    @classmethod
    def time_series_group_to_result_table(cls, time_series_group_data):
        """
        将time_series_group数据转换成 result_table 格式
        :param time_series_group_data:
        [
            {
                "time_series_group_id": 91,
                "time_series_group_name": "script_wwwwxzzzz",
                "bk_data_id": 1573259,
                "bk_biz_id": 0,
                "table_id": "script_wwwwxzzzz.disk_usage",
                "label": "os",
                "is_enable": true,
                "metric_info_list": [
                    {
                        "field_name": "disk_usage",
                        "metric_display_name": "",
                        "unit": "",
                        "type": "float",
                        "tag_list": [],
                        "table_id": "script_wwwwxzzzz.disk_usage",
                        "description": "",
                        "is_disabled": false
                    }
                ]
            }
        ]
        :return: ResultTable
        """
        fields = []
        table_name = f"{time_series_group_data[0]['time_series_group_name']}.__default__"
        for group_data in time_series_group_data:
            for metric in group_data["metric_info_list"]:
                fields.append(
                    ResultTableField(
                        field_name=metric["field_name"],
                        description=metric.get("description") or metric["field_name"],
                        tag="metric",
                        field_type=metric["type"],
                        unit=metric.get("unit", ""),
                    )
                )
        return cls(table_name=table_name, description=table_name, fields=fields)

    @classmethod
    def new_result_table(cls, table_dict):
        """
        :param table_dict: 结果表存入数据库的格式
        {
            "fields":[
                {
                    "source_name":"",
                    "name":"collector",
                    "type":"string",
                    "monitor_type":"dimension",
                    "unit":"",
                    "description":"collector"
                },
            ],
            "table_name":"mysql_exporter_collector_duration_seconds",
            "table_desc":"mysql_exporter_collector_duration_seconds"
        }
        :return: ResultTable
        """
        fields = []
        for field in table_dict.get("fields", []):
            if field.get("is_active"):
                fields.append(
                    ResultTableField(
                        field_name=field["name"],
                        description=field.get("description") or field["name"],
                        tag=field["monitor_type"],
                        field_type=field["type"],
                        unit=field.get("unit", ""),
                    )
                )

        return cls(table_name=table_dict["table_name"], description=table_dict.get("table_desc", ""), fields=fields)


class DataAccessor:
    """
    申请数据链路资源
    """

    def __init__(
        self,
        bk_tenant_id: str,
        bk_biz_id,
        db_name,
        tables,
        etl_config,
        operator,
        type_label,
        source_label,
        label,
        data_label: str | None = None,
    ):
        """
        :param bk_biz_id: 业务ID
        :param db_name: 数据库名
        :param tables: ResultTable列表
        :param etl_config: 清洗方式
        :param operator: 操作人
        """
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = bk_tenant_id
        self.db_name = db_name.lower()
        self.data_label = data_label.lower() if data_label else self.db_name
        self.tables = tables
        self.operator = operator
        self.etl_config = etl_config
        self.modify = False
        self.type_label = type_label
        self.source_label = source_label
        self.label = label
        try:
            self.data_id = self.get_data_id()
        except BKAPIError:
            self.data_id = None

    @property
    def data_name(self):
        return f"{self.bk_biz_id}_{self.db_name}" if self.bk_biz_id else self.db_name

    def create_dataid(self):
        """
        创建/修改dataid
        """
        param = {
            "bk_tenant_id": self.bk_tenant_id,
            "bk_biz_id": self.bk_biz_id,
            "data_name": self.data_name,
            "etl_config": self.etl_config,
            "operator": self.operator,
            "data_description": self.data_name,
            "type_label": self.type_label,
            "source_label": self.source_label,
            # 新增入库时间
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                # 新建data_id时都是单指标单表
                "is_split_measurement": True,
            },
        }
        self.data_id = api.metadata.create_data_id(param)["bk_data_id"]
        return self.data_id

    def contrast_rt(self) -> tuple[dict[str, Any], dict[str, ResultTable]]:
        """
        Returns:
            dict[str, Any]: 结果表信息
            dict[str, ResultTable]: 结果表信息映射，包含表的详细信息
        """
        # 向前兼容，优先查询不带业务ID的结果表
        without_biz_result_table_list = api.metadata.list_result_table(
            bk_tenant_id=self.bk_tenant_id,
            datasource_type=self.db_name,
            is_config_by_user=True,
        )
        if without_biz_result_table_list or self.bk_biz_id == 0:
            result_table_list = without_biz_result_table_list
            table_infos = {f"{self.db_name}.{table.table_name}": table for table in self.tables}
        else:
            db_name_with_biz = f"{self.bk_biz_id}_{self.db_name}"
            result_table_list = api.metadata.list_result_table(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                datasource_type=db_name_with_biz,
                is_config_by_user=True,
            )
            table_infos = {f"{db_name_with_biz}.{table.table_name}": table for table in self.tables}

        new_table_id_set = {i for i in list(table_infos.keys())}

        old_table_id_set = set()
        for old_table in result_table_list:
            old_table_id = old_table["table_id"]
            old_table_id_set.add(old_table_id)
            if old_table_id not in new_table_id_set:
                table_infos[old_table_id] = ResultTable(
                    table_name=old_table_id.split(".")[-1],
                    description=old_table["table_name_zh"],
                    fields=[],
                )

        # 检查结果表关键配置，如果没有修改，则不调用modify接口进行更新
        modify_table_id_set = new_table_id_set & old_table_id_set
        for result_table in result_table_list:
            if result_table["table_id"] in modify_table_id_set:
                if not self.check_table_modify(table_infos[result_table["table_id"]], result_table):
                    modify_table_id_set.remove(result_table["table_id"])

        return {
            "create": new_table_id_set - old_table_id_set,
            "modify": modify_table_id_set,
            "clean": old_table_id_set - new_table_id_set,
        }, table_infos

    def check_table_modify(self, new_table_info: ResultTable, old_result_table: dict) -> bool:
        """判断表配置是否修改

        :param new_table_info: 新提交的配置
        :param old_result_table: 从接口获取的之前的配置
        :return: 是否修改
        """
        if old_result_table["table_name_zh"] != new_table_info.description:
            return True

        if len(old_result_table["field_list"]) != len(new_table_info.fields):
            return True

        new_table_fields = {field["field_name"]: field for field in new_table_info.fields}
        for old_field_info in old_result_table["field_list"]:
            if old_field_info["field_name"] not in new_table_fields:
                return True

            if old_field_info["field_name"] in ORIGIN_PLUGIN_EXCLUDE_DIMENSION:
                continue

            # 有些属性的值虽然不想等，但是其实是同一个含义
            special_value_mappings = {"tag": {"group": "dimension"}}
            old_field_info["field_type"] = old_field_info["type"]
            for field_key in ["field_type", "tag", "description", "unit", "is_config_by_user"]:
                old_field_value = special_value_mappings.get(field_key, {}).get(
                    old_field_info[field_key], old_field_info[field_key]
                )
                new_field_value = new_table_fields[old_field_info["field_name"]][field_key]
                new_field_value = special_value_mappings.get(field_key, {}).get(new_field_value, new_field_value)

                if old_field_value != new_field_value:
                    return True

        return False

    def create_rt(self):
        """
        创建结果表
        """
        contrast_result, table_infos = self.contrast_rt()
        func_list = []
        params_list = []

        for operation in contrast_result:
            param = {
                "bk_tenant_id": self.bk_tenant_id,
                "bk_data_id": self.data_id,
                "is_custom_table": True,
                "operator": self.operator,
                "schema_type": "free",
                "default_storage": "influxdb",
                "label": self.label,
                "data_label": self.data_label,
            }
            for table_id in contrast_result[operation]:
                external_storage = {"kafka": {"expired_time": 1800000}}
                if settings.IS_ACCESS_BK_DATA:
                    external_storage["bkdata"] = {}
                param.update(
                    {
                        "bk_biz_id": self.bk_biz_id,
                        "table_id": table_id,
                        "table_name_zh": table_infos[table_id].description,
                        "field_list": [
                            field
                            for field in table_infos[table_id].fields
                            if field["field_name"] not in ORIGIN_PLUGIN_EXCLUDE_DIMENSION
                        ],
                        "external_storage": external_storage,
                    }
                )
                if operation == "create":
                    if self.etl_config == "bk_exporter":
                        param.update({"option": {"enable_default_value": False}})
                    func_list.append(api.metadata.create_result_table)
                else:
                    func_list.append(api.metadata.modify_result_table)
                params_list.append(copy.deepcopy(param))

        return self.request_multi_thread(func_list, params_list, get_data=lambda x: x)

    def access(self):
        """
        接入数据链路
        :return: 创建的 data id
        """
        if not self.data_id:
            self.create_dataid()

        self.create_rt()
        return self.data_id

    def get_data_id(self):
        data_id_info = api.metadata.get_data_id(
            bk_tenant_id=self.bk_tenant_id, data_name=self.data_name, with_rt_info=False
        )
        self.data_id = safe_int(data_id_info["data_id"])
        return self.data_id

    def modify_label(self, label):
        """
        修改label
        """
        result_table_list = api.metadata.list_result_table(bk_tenant_id=self.bk_tenant_id, datasource_type=self.db_name)
        if not result_table_list and self.bk_biz_id != 0:
            result_table_list = api.metadata.list_result_table(
                bk_tenant_id=self.bk_tenant_id, datasource_type=f"{self.bk_biz_id}_{self.db_name}"
            )

        params_list = []
        for table in result_table_list:
            external_storage = {"kafka": {"expired_time": 1800000}}
            if settings.IS_ACCESS_BK_DATA:
                external_storage["bkdata"] = {}
            param = {
                "bk_tenant_id": self.bk_tenant_id,
                "bk_data_id": self.data_id,
                "is_custom_table": True,
                "operator": self.operator,
                "schema_type": "free",
                "default_storage": "influxdb",
                "label": label,
                "bk_biz_id": self.bk_biz_id,
                "table_id": table["table_id"],
                "table_name_zh": table["table_name_zh"],
                "external_storage": external_storage,
            }
            params_list.append(param)

        self.request_multi_thread(
            [api.metadata.modify_result_table] * len(params_list), params_list, get_data=lambda x: x
        )

        return "success"

    def request_multi_thread(self, func_list, params_list, get_data=lambda x: []):
        """
        并发请求接口，每次按不同参数请求最后叠加请求结果
        :param func: 请求方法
        :param params_list: 参数列表
        :param get_data: 获取数据函数，通常CMDB的批量接口应该设置为 get_data=lambda x: x["info"]，其它场景视情况而定
        :return: 请求结果累计
        """
        result = []
        with ThreadPoolExecutor(max_workers=12) as executor:
            tasks = [executor.submit(func, **params) for func, params in zip(func_list, params_list)]
        for future in as_completed(tasks):
            _result = get_data(future.result())
            if isinstance(_result, list):
                result.extend(_result)
            else:
                result.append(_result)
        return result


class PluginDataAccessor(DataAccessor):
    def __init__(self, plugin_version, operator: str, data_label: str | None = None):
        def get_field_instance(field):
            # 将field字典转化为ResultTableField对象
            return ResultTableField(
                field_name=field["name"],
                tag=field["monitor_type"],
                field_type=field["type"],
                description=force_str(field.get("description", "")),
                unit=field.get("unit", ""),
                is_config_by_user=field.get("is_active", True),
                alias_name=field.get("source_name", ""),
            )

        self.metric_json = plugin_version.info.metric_json
        self.enable_field_blacklist = plugin_version.info.enable_field_blacklist
        # 获取表结构信息
        tables = []

        add_fields = []
        add_fields_names = copy.deepcopy(PLUGIN_REVERSED_DIMENSION)
        plugin_type = plugin_version.plugin.plugin_type
        if plugin_type == PluginType.SNMP:
            add_fields_names.append(("bk_target_device_ip", _("远程采集目标IP")))
        config_json = plugin_version.config.config_json
        self.dms_field = []

        # 维度注入参数名称，更新至group的添加参数信息中
        for param in config_json or []:
            if param["mode"] == ParamMode.DMS_INSERT:
                for dms_key in param["default"].keys():
                    add_fields_names.append((dms_key, dms_key))
                    self.dms_field.append((dms_key, dms_key))

        for name, description in add_fields_names:
            add_fields.append(
                {"name": name, "description": force_str(description), "monitor_type": "group", "type": "string"}
            )

        for table in self.metric_json:
            # 获取字段信息
            fields = list(
                map(
                    get_field_instance,
                    [i for i in table["fields"] if i["monitor_type"] == "dimension" or i.get("is_active")],
                )
            )
            fields.extend(list(map(get_field_instance, add_fields)))
            tables.append(ResultTable(table_name=table["table_name"], description=table["table_desc"], fields=fields))

        db_name = f"{plugin_type}_{plugin_version.plugin.plugin_id}"
        if plugin_type in [PluginType.SCRIPT, PluginType.DATADOG]:
            etl_config = "bk_standard"
        elif plugin_type == PluginType.K8S:
            etl_config = "bk_standard_v2_time_series"
        else:
            etl_config = "bk_exporter"
        super().__init__(
            bk_tenant_id=plugin_version.plugin.bk_tenant_id,
            bk_biz_id=plugin_version.plugin.bk_biz_id,
            db_name=db_name,
            tables=tables,
            etl_config=etl_config,
            operator=operator,
            type_label="time_series",
            source_label="bk_monitor",
            label=plugin_version.plugin.label,
            data_label=data_label,
        )

    def merge_dimensions(self, tag_list: list):
        """
        拼接维度：将默认的维度和用户编辑的维度拼接
        :return:
        """
        tag_list_field_name = [tag["field_name"] for tag in tag_list]
        for dimension_name, description in PLUGIN_REVERSED_DIMENSION + self.dms_field:
            if dimension_name in tag_list_field_name:
                continue
            tag_list.append(
                {
                    "field_name": dimension_name,
                    "unit": "none",
                    "type": "string",
                    "description": force_str(description),
                }
            )

    def format_time_series_metric_info_data(self, metric_json, enable_field_blacklist):
        """
        将 saas 侧的 metric_json 数据处理为后台 timeseriesmetric 需要的指标维度信息
        :param metric_json:
        :param enable_field_blacklist:
        :return:
        """
        result = []
        for table in metric_json:
            table_tag_list = [
                {"field_name": field["name"], "unit": "none", "type": "string", "description": field["description"]}
                for field in table["fields"]
                if field["monitor_type"] == "dimension"
            ]
            for field in table["fields"]:
                if enable_field_blacklist:
                    tag_list = field.get("tag_list", [])
                else:
                    tag_list = table_tag_list
                self.merge_dimensions(tag_list)
                if field["monitor_type"] == "metric":
                    result.append(
                        {
                            "field_name": field["name"],
                            "tag_list": tag_list,
                            "label": self.label,
                            "is_active": field.get("is_active", False),
                        }
                    )
        return result

    def modify_is_split_measurement(self):
        """将 datasource option 的 is_split_measurement 改为 True"""
        return api.metadata.modify_data_id(
            bk_tenant_id=self.bk_tenant_id,
            data_id=self.data_id,
            operator=self.operator,
            option={"is_split_measurement": True},
        )

    @property
    def data_name(self):
        return self.db_name

    def access(self):
        """
        接入数据链路
        :return: 创建的 data id
        """
        # 背景：
        # 1. 新增插件/导入插件，没有黑白名单配置信息，因此自动发现的配置(enable_field_blacklist)为False
        # 2. 当前基于自动发现判断是否开启单指标单表，因此针对新增/导入，做一层dataid的判断：当dataid不存在，则默认 单指标单表（白名单）

        # 开启自动发现，一定是单指标单表
        is_split_measurement = self.enable_field_blacklist

        if not self.data_id:
            # 新增插件均为单指标单表
            is_split_measurement = True
            self.create_dataid()
            # todo 当后续流程失败时，通过`ModifyDataIdResource`将 dataname 重名即可。

        if not is_split_measurement:
            # 没开自动发现，且非新增插件
            try:
                result_table_info = api.metadata.get_result_table(
                    bk_tenant_id=self.bk_tenant_id, table_id=f"{self.db_name}.__default__"
                )
                # 对于白名单模式，如果resulttableoption 的 is_split_measurement 为 True，则说明开启过单指标单表
                if result_table_info["option"].get("is_split_measurement"):
                    is_split_measurement = True
            except Exception:
                # 兼容非单指标单表插件
                pass
        if is_split_measurement:
            self.modify_is_split_measurement()
            metric_info_list = self.format_time_series_metric_info_data(self.metric_json, self.enable_field_blacklist)
            params = {
                "bk_tenant_id": self.bk_tenant_id,
                "operator": self.operator,
                "bk_data_id": self.data_id,
                "bk_biz_id": self.bk_biz_id,
                "time_series_group_name": self.db_name,
                "label": self.label,
                "table_id": f"{self.db_name}.__default__",
                "is_split_measurement": is_split_measurement,
                "metric_info_list": metric_info_list,
                "data_label": self.data_label,
            }
            # 插件数据在这里需要去掉业务id
            # 单指标单表，不需要补齐schema: "enable_default_value": False,
            group_list = api.metadata.query_time_series_group.request.refresh(
                bk_tenant_id=self.bk_tenant_id, time_series_group_name=self.db_name
            )
            if group_list:
                params.update(
                    {
                        "time_series_group_id": group_list[0]["time_series_group_id"],
                        "enable_field_black_list": self.enable_field_blacklist,
                        "additional_options": {
                            "enable_field_black_list": self.enable_field_blacklist,
                            "enable_default_value": False,
                        },
                    }
                )

                api.metadata.modify_time_series_group(**params)
            else:
                params.update(
                    {
                        "additional_options": {
                            "enable_field_black_list": self.enable_field_blacklist,
                            "enable_default_value": False,
                        }
                    }
                )
                api.metadata.create_time_series_group(**params)
        else:
            self.create_rt()
        return self.data_id


class EventDataAccessor:
    def __init__(self, current_version, operator):
        self.bk_biz_id = current_version.plugin.bk_biz_id
        self.bk_tenant_id = current_version.plugin.bk_tenant_id
        self.name = f"{current_version.plugin.plugin_type}_{current_version.plugin_id}"
        self.label = current_version.plugin.label
        self.operator = operator

    def get_data_id(self):
        data_id_info = api.metadata.get_data_id(
            bk_tenant_id=self.bk_tenant_id, data_name=f"{self.name}_{self.bk_biz_id}", with_rt_info=False
        )
        return safe_int(data_id_info["bk_data_id"])

    def create_data_id(self, source_label, type_label):
        data_name = f"{self.name}_{self.bk_biz_id}"
        try:
            data_id_info = api.metadata.get_data_id(
                bk_tenant_id=self.bk_tenant_id, data_name=data_name, with_rt_info=False
            )
        except BKAPIError:
            param = {
                "bk_tenant_id": self.bk_tenant_id,
                "bk_biz_id": self.bk_biz_id,
                "data_name": data_name,
                "etl_config": "bk_standard_v2_event",
                "operator": self.operator,
                "data_description": data_name,
                "type_label": type_label,
                "source_label": source_label,
                "option": {"inject_local_time": True},
            }
            data_id_info = api.metadata.create_data_id(param)
        bk_data_id = data_id_info["bk_data_id"]
        return bk_data_id

    def create_result_table(self, bk_data_id, event_info_list):
        params = {
            "bk_tenant_id": self.bk_tenant_id,
            "operator": self.operator,
            "bk_data_id": bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "event_group_name": self.name,
            # 目前metadata中米有hardware标签
            "label": self.label,
            "event_info_list": event_info_list,
        }
        group_info = api.metadata.create_event_group(params)
        return group_info

    def modify_result_table(self, event_info_list):
        event_groups = api.metadata.query_event_group(bk_tenant_id=self.bk_tenant_id, event_group_name=self.name)
        if event_groups:
            event_group_id = event_groups[0]["event_group_id"]
            params = {
                "bk_tenant_id": self.bk_tenant_id,
                "operator": self.operator,
                "event_group_id": event_group_id,
                "event_info_list": event_info_list,
            }
            params = {key: value for key, value in params.items() if value is not None}
            group_info = api.metadata.modify_event_group(params)
            return group_info
        raise Exception(_("结果表不存在，请确认后重试"))

    def delete_result_table(self):
        event_groups = api.metadata.query_event_group(bk_tenant_id=self.bk_tenant_id, event_group_name=self.name)
        if event_groups:
            event_group_id = event_groups[0]["event_group_id"]
            api.metadata.delete_event_group(event_group_id=event_group_id, operator=self.operator)
            return event_group_id


class UptimecheckDataAccessor:
    """
    拨测数据接入
    """

    version = "v1"

    DATAID_MAP = {
        UptimeCheckProtocol.HTTP: settings.UPTIMECHECK_HTTP_DATAID,
        UptimeCheckProtocol.TCP: settings.UPTIMECHECK_TCP_DATAID,
        UptimeCheckProtocol.UDP: settings.UPTIMECHECK_UDP_DATAID,
        UptimeCheckProtocol.ICMP: settings.UPTIMECHECK_ICMP_DATAID,
    }

    def __init__(self, task) -> None:
        self.task = task
        self.bk_biz_id = task.bk_biz_id
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)

    def get_data_id(self) -> tuple[bool, int]:
        """
        TODO: 获取拨测数据链路ID
        :return: 是否是自定义上报，数据链路ID
        """
        if not self.use_custom_report():
            return False, self.DATAID_MAP[self.task.protocol.upper()]

        data_id_info = api.metadata.get_data_id(
            bk_tenant_id=self.bk_tenant_id, data_name=self.data_name, with_rt_info=False
        )
        return True, safe_int(data_id_info["bk_data_id"])

    def use_custom_report(self) -> bool:
        """
        是否使用自定义上报
        """
        return self.task.indepentent_dataid

    @property
    def data_label(self) -> str:
        return f"uptimecheck_{self.task.protocol.lower()}"

    @property
    def db_name(self) -> str:
        """
        获取数据库名
        """
        return f"uptimecheck_{self.task.protocol.lower()}_{self.bk_biz_id}"

    @property
    def data_name(self) -> str:
        return self.db_name

    def create_data_id(self) -> int:
        """
        创建数据ID
        """
        try:
            data_id_info = api.metadata.get_data_id(
                bk_tenant_id=self.bk_tenant_id, data_name=self.data_name, with_rt_info=False
            )
            return safe_int(data_id_info["bk_data_id"])
        except BKAPIError:
            pass

        params = {
            "bk_tenant_id": self.bk_tenant_id,
            "bk_biz_id": self.bk_biz_id,
            "data_name": self.data_name,
            "etl_config": "bk_standard_v2_time_series",
            "operator": "admin",
            "data_description": self.data_name,
            "type_label": "time_series",
            "source_label": "bk_monitor",
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
        }
        return safe_int(api.metadata.create_data_id(params)["bk_data_id"])

    def access(self):
        """
        接入数据链路
        """
        from monitor.models import ApplicationConfig

        if not self.use_custom_report():
            return

        config = ApplicationConfig.objects.filter(
            cc_biz_id=self.bk_biz_id, key=f"access_uptime_check_{self.task.protocol.lower()}_biz_dataid"
        ).first()
        if config and config.value == UptimecheckDataAccessor.version:
            return

        # 创建数据ID
        data_id = self.create_data_id()

        # 创建自定义上报
        params = {
            "bk_tenant_id": self.bk_tenant_id,
            "operator": "admin",
            "bk_data_id": data_id,
            "bk_biz_id": self.bk_biz_id,
            "time_series_group_name": self.db_name,
            "label": "uptimecheck",
            "is_split_measurement": True,
            "metric_info_list": [],
            "data_label": self.data_label,
            "additional_options": {
                "enable_field_black_list": True,
                "enable_default_value": False,
            },
        }
        api.metadata.create_time_series_group(params)

        # 更新配置
        if not config:
            ApplicationConfig.objects.create(
                cc_biz_id=self.bk_biz_id,
                key=f"access_uptime_check_{self.task.protocol.lower()}_biz_dataid",
                value=UptimecheckDataAccessor.version,
            )
        else:
            config.value = UptimecheckDataAccessor.version
            config.save()
