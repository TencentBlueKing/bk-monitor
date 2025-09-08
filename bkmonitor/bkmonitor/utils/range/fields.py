# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from six.moves import map

from bkmonitor.utils.common_utils import safe_float, to_host_id


class DimensionField(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def get_value_from_data(self, data):
        is_exists = self.name in data
        return is_exists, data.get(self.name, "")

    def to_str_list(self):
        """trans self.value to str list"""
        val_list = self.value
        if not isinstance(val_list, (list, tuple)):
            val_list = [val_list]
        return [self.strip_str(v) for v in val_list]

    def to_float_list(self):
        """trans self.value to float list"""
        val_list = self.value
        if not isinstance(val_list, (list, tuple)):
            val_list = [val_list]

        return list(map(safe_float, val_list))

    @staticmethod
    def strip_str(value) -> str:
        """
        字符型值处理
        1. 转换为字符串
        2. 去除两侧空白符
        """
        return str(value).strip()


class IpDimensionField(DimensionField):
    """
    The following formats need to be compatible
    Format1: '1.1.1.1'
    Format2: ['1.1.1.1', '2.2.2.2']
    Format3: [{'ip': '1.1.1.1', 'bk_cloud_id': '1'},
              {'ip': '2.2.2.2', 'bk_cloud_id': '2'}]
    Format4: [{'ip': '1.1.1.1', 'bk_cloud_id': '1', 'bk_supplier_id': '0'},
              {'ip': '2.2.2.2', 'bk_cloud_id': '2', 'bk_supplier_id': '0'}]
    """

    def get_value_from_data(self, data):
        is_exists, ip_value = super(IpDimensionField, self).get_value_from_data(data)

        first_value = self.value
        if self.value and isinstance(self.value, (list, tuple)):
            first_value = self.value[0]

        if isinstance(first_value, dict) and "bk_cloud_id" in first_value:
            bk_cloud_id = data.get("bk_cloud_id", data.get("plat_id", "0"))
            bk_supplier_id = data.get("bk_supplier_id", "0")
            return True, [{"ip": ip_value, "bk_cloud_id": bk_cloud_id, "bk_supplier_id": bk_supplier_id}]

        return is_exists, ip_value

    def to_str_list(self):
        val_list = self.value
        if not isinstance(val_list, (list, tuple)):
            val_list = [val_list]

        ret = []
        for v in val_list:
            if isinstance(v, dict):
                v = to_host_id(v)
            else:
                v = self.strip_str(v)
            ret.append(v)

        return ret


class BkTargetIpDimensionField(DimensionField):
    """
    The following formats need to be compatible
    Format1: '1.1.1.1'
    Format2: ['1.1.1.1', '2.2.2.2']
    Format3: [{'bk_target_ip': '1.1.1.1', 'bk_target_cloud_id': '1'},
              {'bk_target_ip': '2.2.2.2', 'bk_target_cloud_id': '2'}]
    Format4: [{'bk_target_ip': '1.1.1.1', 'bk_target_cloud_id': '1', 'bk_supplier_id': '0'},
              {'bk_target_ip': '2.2.2.2', 'bk_target_cloud_id': '2', 'bk_supplier_id': '0'}]
    """

    def get_value_from_data(self, data):
        is_exists, ip_value = super(BkTargetIpDimensionField, self).get_value_from_data(data)

        first_value = self.value
        if self.value and isinstance(self.value, (list, tuple)):
            first_value = self.value[0]

        if isinstance(first_value, dict) and "bk_target_cloud_id" in first_value:
            bk_cloud_id = data.get("bk_target_cloud_id", data.get("plat_id", "0"))
            bk_supplier_id = data.get("bk_supplier_id", "0")
            return (
                True,
                [{"bk_target_ip": ip_value, "bk_target_cloud_id": bk_cloud_id, "bk_supplier_id": bk_supplier_id}],
            )

        return is_exists, ip_value

    def to_str_list(self):
        val_list = self.value
        if not isinstance(val_list, (list, tuple)):
            val_list = [val_list]

        ret = []
        for v in val_list:
            if isinstance(v, dict):
                v = f"{v['bk_target_ip']}|{v.get('bk_target_cloud_id', '0')}"
            else:
                v = self.strip_str(v)
            ret.append(v)

        return ret


class TopoSetDimensionField(DimensionField):
    pass


class TopoModuleDimensionField(DimensionField):
    pass


class AppModuleDimensionField(DimensionField):
    pass


class TopoNodeDimensionField(DimensionField):
    """
    The following formats need to be compatible
    Format1: 'set|1'
    Format2: ['set|1', 'set|2']
    Format3: [{"bk_obj_id":"set","bk_inst_id":1},
              {"bk_obj_id":"set","bk_inst_id":2}]
    """

    def get_value_from_data(self, data):
        is_exists, topo_node_value = super(TopoNodeDimensionField, self).get_value_from_data(data)

        if not is_exists and "bk_topo_node" in data:
            return True, data.get("bk_topo_node")

        if not is_exists and "bk_obj_id" in data and "bk_inst_id" in data:
            return True, [{"bk_obj_id": data["bk_obj_id"], "bk_inst_id": data["bk_inst_id"]}]
        return is_exists, topo_node_value

    def to_str_list(self):
        val_list = self.value
        if not isinstance(val_list, (list, tuple)):
            val_list = [val_list]

        ret = []
        for v in val_list:
            if isinstance(v, dict):
                v = f"{v.get('bk_obj_id')}|{v.get('bk_inst_id')}"
            else:
                v = self.strip_str(v)
            ret.append(v)

        return ret


class HostTopoNodeDimensionField(TopoNodeDimensionField):
    pass


class ServiceTopoNodeDimensionField(TopoNodeDimensionField):
    pass
