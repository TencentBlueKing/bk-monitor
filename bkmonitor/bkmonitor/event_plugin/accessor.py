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

from bkmonitor.event_plugin.constant import EVENT_NORMAL_FIELDS
from bkmonitor.models import DataSourceLabel, DataTypeLabel, EventPluginInstance
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.request import get_request_username
from constants.data_source import ResultTableLabelObj
from core.drf_resource import api
from core.errors.api import BKAPIError


class EventPluginInstAccessor:
    def __init__(self, plugin_inst: EventPluginInstance):
        self.plugin_inst = plugin_inst

    def access(self, option=None):
        """
        接入数据链路 幂等操作
        """
        data_id = self.create_or_update_dataid(option)
        self.create_or_update_rt(data_id)
        return data_id

    def switch_dataid(self, is_enabled: bool):
        data_id = self.get_data_id()
        operator = get_request_username(self.plugin_inst.update_user)
        api.metadata.modify_data_id({"data_id": data_id, "is_enable": is_enabled, "operator": operator})

    def create_or_update_dataid(self, option=None):
        param = {
            "data_name": self.data_name,
            "etl_config": "bk_fta_event",
            "operator": self.plugin_inst.update_user,
            "data_description": self.data_name,
            "type_label": DataTypeLabel.EVENT,
            "source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,  # TODO 需要修改为FTA
            "option": option,
            "is_enable": self.plugin_inst.is_enabled,
        }
        data_id = self.get_data_id()
        if data_id:
            param["data_id"] = data_id
            return api.metadata.modify_data_id(param)["bk_data_id"]
        return api.metadata.create_data_id(param)["bk_data_id"]

    def create_or_update_rt(self, data_id: int):
        """
        创建结果表
        """
        fields = []
        time_option = {}

        for field in EVENT_NORMAL_FIELDS:
            # 根据标准字段去生成RT配置
            option = {}
            for config in self.plugin_inst.normalization_config:
                # 将用户的自定义配置注入字段配置中
                if config["field"] == field["field"]:
                    option = config["option"]

            if field["field"] == "time":
                # field 字段是内置的，无需append
                time_option = option
            else:
                fields.append(
                    {
                        "field_name": field["field"],
                        "field_type": field["field_type"],
                        "tag": "metric",
                        "description": str(field["display_name"]),
                        "option": option,
                        "is_reserved_check": False,
                    }
                )

        param = {
            "bk_data_id": data_id,
            "is_custom_table": True,
            "operator": self.plugin_inst.update_user,
            "schema_type": "free",
            "default_storage": "kafka",
            "label": ResultTableLabelObj.OthersObj.other_rt,
            "bk_biz_id": self.plugin_inst.bk_biz_id,
            "table_id": f"{self.data_name}.base",
            "table_name_zh": "base",
            "field_list": fields,
            "is_time_field_only": True,
            "time_option": time_option,
            "is_reserved_check": False,
        }

        result_table = api.metadata.list_result_table({"datasource_type": self.data_name})
        if result_table:
            return api.metadata.modify_result_table(param)
        return api.metadata.create_result_table(param)

    @property
    def data_name(self):
        """
        全局的默认只带plugin_id参数，按业务安装的，适配对应的业务和插件ID
        :return:
        """
        name = f"fta_{self.plugin_inst.plugin_id}"
        if self.plugin_inst.bk_biz_id:
            name = f"{self.plugin_inst.bk_biz_id}_{name}_{self.plugin_inst.id}"
        return name

    def get_data_id(self):
        # 先查询记录中是否存在dataid，若不存在，则到元数据进行查询
        if self.plugin_inst.data_id:
            return self.plugin_inst.data_id
        try:
            data_id_info = api.metadata.get_data_id({"data_name": self.data_name, "with_rt_info": False})
            data_id = safe_int(data_id_info["data_id"])
        except BKAPIError:
            data_id = 0
        return data_id
