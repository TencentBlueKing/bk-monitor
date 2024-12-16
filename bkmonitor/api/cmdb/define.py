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

import copy
from typing import Dict, List, Optional

import six
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from bkmonitor.utils.country import CHINESE_PROVINCE_MAP, COUNTRY_MAP, ISP_MAP


def _split_member_list(member_str):
    """
    将字符串类型的人员数据转换为列表
    :param member_str: 人员数据字符串，例如 a,b,c,d
    :return: list[str]
    """
    if not member_str:
        return []
    if not isinstance(member_str, six.string_types):
        return member_str
    return [member for member in member_str.split(",") if member]


class BaseNode:
    """
    基础节点
    """

    def __init__(self, attrs: dict):
        super().__setattr__("_extra_attr", attrs)

    def __getattribute__(self, item: str):
        try:
            return super().__getattribute__(item)
        except AttributeError as e:
            attrs = super().__getattribute__("_extra_attr")
            if item in attrs:
                return attrs[item]
            raise e

    def __setattr__(self, key: str, value):
        attrs = super().__getattribute__("_extra_attr")
        if key not in attrs:
            super().__setattr__(key, value)
        else:
            attrs[key] = value

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        setattr(self, key, value)


class TopoNode(object):
    """
    拓扑节点
    {
        "bk_inst_id": 2,
        "bk_inst_name": "blueking",
        "bk_obj_id": "biz",
        "bk_obj_name": "business",
    }
    """

    def __init__(self, bk_obj_id, bk_inst_id, bk_obj_name="", bk_inst_name="", **kwargs):
        """
        :param str bk_obj_id: 节点对象(层级)ID
        :param int bk_inst_id: 节点实例ID
        :param str bk_obj_name: 节点对象(层级)名称
        :param str bk_inst_name: 节点实例名称
        """
        self.bk_inst_id = int(bk_inst_id)
        self.bk_inst_name = bk_inst_name or ""
        self.bk_obj_id = bk_obj_id or ""
        self.bk_obj_name = bk_obj_name or ""

    @property
    def id(self):
        return "{}|{}".format(self.bk_obj_id, self.bk_inst_id)

    def __eq__(self, other):
        return (self.bk_inst_id, self.bk_obj_id) == (other.bk_inst_id, other.bk_obj_id)

    def __hash__(self):
        return hash((self.bk_inst_id, self.bk_obj_id))

    def __repr__(self):
        return "<TopoNode: {}({})-{}({})>".format(self.bk_obj_name, self.bk_obj_id, self.bk_inst_name, self.bk_inst_id)

    def get_attrs(self):
        node_attrs = {}
        for key, value in self.__dict__.items():
            if key == "_extra_attr":
                node_attrs.update(value)
            else:
                node_attrs[key] = value
        return node_attrs


class Business(TopoNode):
    """
    业务
    {
        "bk_biz_id": 2,
        "language": "1",
        "life_cycle": "2",
        "bk_biz_developer": ["layman", "durant2"],
        "bk_biz_maintainer": ["admin", "layman", "durant2", "selina-test"],
        "bk_biz_tester": ["duranttest"],
        "time_zone": "Asia/Shanghai",
        "default": 0,
        "create_time": "2019-08-12T17:47:37.737+08:00",
        "bk_biz_productor": ["duranttest", "durant2"],
        "bk_supplier_account": "0",
        "operator": "",
        "bk_biz_name": "蓝鲸",
        "last_time": "2019-08-26T21:13:19.464+08:00",
        "bk_supplier_id": 0
    }
    """

    def __init__(
        self,
        bk_biz_id,
        bk_biz_name="",
        bk_biz_developer=None,
        bk_biz_maintainer=None,
        bk_biz_tester=None,
        bk_biz_productor=None,
        operator=None,
        time_zone="Asia/Shanghai",
        **kwargs,
    ):
        """
        :param int bk_biz_id: 业务ID
        :param str or unicode bk_biz_name: 业务名称
        :param str time_zone: 时区
        """
        kwargs.pop("bk_obj_id", "")
        super(Business, self).__init__(
            bk_obj_id="biz", bk_obj_name="business", bk_inst_id=bk_biz_id, bk_inst_name=bk_biz_name, **kwargs
        )
        self.bk_biz_id = int(bk_biz_id)
        if not bk_biz_name:
            space_name = kwargs.get("space_name", "")
            space_id = kwargs.get("space_id", "")
            if space_id and space_name:
                bk_biz_name = f"[{space_id}]{space_name}"

        self.bk_biz_name = bk_biz_name
        self.bk_biz_developer = _split_member_list(bk_biz_developer)
        self.bk_biz_maintainer = _split_member_list(bk_biz_maintainer)
        self.bk_biz_tester = _split_member_list(bk_biz_tester)
        self.bk_biz_productor = _split_member_list(bk_biz_productor)
        self.operator = _split_member_list(operator)
        self.time_zone = kwargs.get("extend", {}).get("time_zone") or time_zone
        self.language = kwargs.pop("language", "1")
        self.life_cycle = kwargs.pop("life_cycle", "2")

        # 将自定义属性置于外层，便于通过 __dict__ 取到
        for field in kwargs.copy():
            if not hasattr(self, field):
                setattr(self, field, kwargs.pop(field))

        # 自定义属性
        self._extra_attr = kwargs

    def __getattr__(self, item):
        """
        获取自定义属性
        """
        if item == "_extra_attr":
            return super(Business, self).__getattribute__(item)
        if item in self._extra_attr:
            return self._extra_attr[item]
        return super(Business, self).__getattribute__(item)

    def __repr__(self):
        return "<Business: {}-{}>".format(self.bk_biz_id, self.display_name)

    @property
    def display_name(self):
        # bk_biz_name:
        # "蓝鲸"
        # "[xxx]xx系统"

        # display_name:
        # '[xxx]xx系统 (研发项目)'
        # '[2]蓝鲸 (业务)'
        type_name = _(getattr(self, "type_name", "业务"))
        return (f"[{self.bk_biz_id}]{self.bk_biz_name} " if self.bk_biz_id > 0 else self.bk_biz_name) + f"({type_name})"


class Set(TopoNode):
    """
    模块(最底层的拓扑节点)
    """

    def __init__(self, bk_set_id, bk_set_name: str = "", set_template_id: int = 0, **kwargs):
        """
        :param int bk_set_id: 模块ID
        :param str bk_set_name: 模块名称
        """
        super(Set, self).__init__(
            bk_obj_id="set", bk_obj_name="set", bk_inst_id=bk_set_id, bk_inst_name=bk_set_name, **kwargs
        )
        self.bk_set_id = int(bk_set_id)
        self.bk_set_name = bk_set_name or ""
        self.set_template_id = set_template_id

        self._extra_attr = kwargs

    def __getattr__(self, item):
        """
        获取自定义属性
        """
        if item == "_extra_attr":
            return super(Set, self).__getattribute__(item)
        if item in self._extra_attr:
            return self._extra_attr[item]
        return super(Set, self).__getattribute__(item)

    def __repr__(self):
        return "<Set: {}-{}>".format(self.bk_set_id, self.bk_set_name)


class Module(TopoNode):
    """
    模块(最底层的拓扑节点)
    """

    def __init__(
        self,
        bk_module_id,
        bk_module_name="",
        service_category_id=0,
        service_template_id=0,
        operator=None,
        bk_bak_operator=None,
        **kwargs,
    ):
        """
        :param int bk_module_id: 模块ID
        :param str bk_module_name: 模块名称
        :param int service_category_id: 服务分类ID
        :param int service_template_id: 服务实例ID
        :param list[str] operator: 主负责人
        :param list[str] bk_bak_operator: 备份负责人
        """
        super(Module, self).__init__(
            bk_obj_id="module", bk_obj_name="module", bk_inst_id=bk_module_id, bk_inst_name=bk_module_name, **kwargs
        )
        self.bk_module_id = int(bk_module_id)
        self.bk_module_name = bk_module_name or ""
        self.service_category_id = int(service_category_id)
        self.service_template_id = int(service_template_id)
        self.operator = operator or []
        self.bk_bak_operator = bk_bak_operator or []

        # 自定义属性
        self._extra_attr = kwargs

    def __getattr__(self, item):
        """
        获取自定义属性
        """
        if item == "_extra_attr":
            return super(Module, self).__getattribute__(item)
        if item in self._extra_attr:
            return self._extra_attr[item]
        return super(Module, self).__getattribute__(item)

    def __repr__(self):
        return "<Module: {}-{}>".format(self.bk_module_id, self.bk_module_name)


class TopoTree(TopoNode):
    """
    拓扑树
    {
        "bk_inst_id": 2,
        "bk_inst_name": "blueking",
        "bk_obj_id": "biz",
        "bk_obj_name": "business",
        "child": [
            {
                "bk_inst_id": 3,
                "bk_inst_name": "job",
                "bk_obj_id": "set",
                "bk_obj_name": "set",
                "child": [
                    {
                        "bk_inst_id": 5,
                        "bk_inst_name": "job",
                        "bk_obj_id": "module",
                        "bk_obj_name": "module",
                        "child": []
                    }
                ]
            }
        ]
    }
    """

    def __init__(self, tree_data, parent=None):
        child = tree_data.pop("child", [])
        super(TopoTree, self).__init__(**tree_data)
        self._parent = parent
        # 子节点信息
        self.child = [TopoTree(c, parent=copy.deepcopy(self)) for c in child]

    def get_node_info(self):
        return TopoNode(**self.__dict__)

    @classmethod
    def get_leaf_nodes(cls, tree, leaf_nodes):
        """
        找出所有叶子节点
        :param TopoTree tree: 拓扑树对象
        :param list leaf_nodes: 叶子节点
        """
        if not tree.child:
            # 没有子节点说明是叶子节点
            leaf_nodes.append(tree)
            return

        for child in tree.child:
            cls.get_leaf_nodes(child, leaf_nodes)

    def convert_to_topo_link(self) -> Dict[str, List[TopoNode]]:
        """
        将拓扑树对象转换为拓扑链，拓扑链从叶子节点开始，自底向上
        :return: example: {
            "module|1": [<TopoNode module-1>, <TopoNode set-2>, <TopoNode biz-3>],
            "module|2": [<TopoNode module-1>, <TopoNode set-2>, <TopoNode biz-3>],
        }
        """
        leaf_nodes = []  # type: list[TopoTree]
        self.get_leaf_nodes(self, leaf_nodes)

        topo_link_dict = {}
        for node in leaf_nodes:
            # 向上遍历父节点
            topo_link = []
            while True:
                topo_link.append(node.get_node_info())
                if not node._parent:
                    break
                node = node._parent
            topo_link_dict[topo_link[0].id] = topo_link
        return topo_link_dict

    @classmethod
    def get_all_nodes(cls, tree, nodes):
        """
        获取所有节点
        :param TopoTree tree: 拓扑树对象
        :param list nodes: 节点列表
        """
        nodes.append(tree.get_node_info())

        if not tree.child:
            # 没有子节点说明是叶子节点
            return

        for child in tree.child:
            cls.get_all_nodes(child, nodes)

    def get_all_nodes_with_relation(self):
        """
        获取所有节点（带关联信息）
        """
        nodes = {}
        queue = [self]
        while queue:
            topo = queue.pop()
            nodes[f"{topo.bk_obj_id}|{topo.bk_inst_id}"] = topo
            queue.extend(topo.child)

        return nodes

    def convert_to_flat_nodes(self):
        """
        将拓扑树扁平化为多个节点
        :return:
        """
        nodes = []  # type: list[TopoTree]
        self.get_all_nodes(self, nodes)
        return nodes


class Host(BaseNode):
    """
    主机
    """

    bk_host_id: int
    bk_agent_id: str

    Fields = (
        "bk_host_innerip",
        "bk_host_innerip_v6",
        "bk_cloud_id",
        "bk_host_id",
        "bk_biz_id",
        "bk_agent_id",
        "bk_host_outerip",
        "bk_host_outerip_v6",
        "bk_host_name",
        "bk_os_name",
        "bk_os_type",
        "operator",
        "bk_bak_operator",
        "bk_state_name",
        "bk_isp_name",
        "bk_province_name",
        "bk_supplier_account",
        "bk_state",
        "bk_os_version",
        "service_template_id",
        "srv_status",
        "bk_comment",
        "idc_unit_name",
        "net_device_id",
        "rack_id",
        "bk_svr_device_cls_name",
        "svr_device_class",
        "docker_client_version",
        "docker_server_version",
        "bk_mem",
        "bk_disk",
        "bk_os_bit",
        "bk_os_version",
        "bk_cpu_module",
        "bk_cpu",
    )

    def __init__(self, attrs: Optional[dict] = None, **kwargs):
        if attrs is None:
            attrs = {}
        attrs.update(kwargs)

        # 主要必须字段的默认值补全
        attrs["ip"] = attrs["bk_host_innerip"]
        attrs["bk_state"] = attrs.get("srv_status") or attrs.get("bk_state") or ""
        attrs["bk_set_ids"] = attrs.get("bk_set_ids") or []
        attrs["bk_module_ids"] = attrs.get("bk_module_ids") or []
        for field in self.Fields:
            if field in ["bk_cloud_id", "bk_host_id", "bk_biz_id"]:
                attrs[field] = int(attrs.get(field) or 0)
                continue
            empty_value = ""
            if field in ["operator", "bk_bak_operator"]:
                empty_value = []
            attrs[field] = attrs.get(field) or empty_value
        for field in settings.HOST_DYNAMIC_FIELDS:
            attrs[field] = attrs.get(field) or ""

        # 补充展示字段display_name
        for field in settings.HOST_DISPLAY_FIELDS:
            if attrs.get(field):
                if field == "bk_host_innerip_v6":
                    value = attrs[field]
                else:
                    value = attrs[field]
                attrs["display_name"] = value
                break
        if not attrs.get("display_name"):
            attrs["display_name"] = attrs["bk_host_innerip"] or attrs["bk_host_innerip_v6"]

        if "topo_link" in attrs:
            topo_link = {}
            for node_id, nodes in attrs["topo_link"].items():
                topo_link[node_id] = [TopoNode(**node) for node in nodes]
            attrs["topo_link"] = topo_link

        super().__init__(attrs)

    @cached_property
    def ignore_monitoring(self):
        return self.bk_state in settings.HOST_DISABLE_MONITOR_STATES

    @cached_property
    def is_shielding(self):
        return self.bk_state in settings.HOST_DISABLE_NOTICE_STATES

    @cached_property
    def bk_province_name(self):
        name = self._extra_attr.get("bk_province_name", "")
        if name in CHINESE_PROVINCE_MAP:
            return str(CHINESE_PROVINCE_MAP[name]["cn"])
        else:
            return name

    @cached_property
    def bk_state_name(self):
        name = self._extra_attr.get("bk_state_name", "")
        if name in COUNTRY_MAP:
            return str(COUNTRY_MAP[name]["cn"])
        else:
            return name

    @cached_property
    def bk_isp_name(self):
        name = self._extra_attr["bk_isp_name"]
        if name in ISP_MAP:
            return str(ISP_MAP[name]["cn"])
        else:
            return name

    @cached_property
    def bk_os_type_name(self):
        """
        操作系统类型名
        """
        if self.bk_os_type:
            return settings.OS_TYPE_NAME_DICT.get(int(self.bk_os_type), "")
        return None

    @cached_property
    def host_id(self):
        return f"{self.ip}|{self.bk_cloud_id}"

    def __eq__(self, other):
        return self.bk_host_id == other.bk_host_id

    def __hash__(self):
        return self.bk_host_id

    def __repr__(self):
        return f"<Host: {self.display_name}>"

    def get_attrs(self):
        return super().__getattribute__("_extra_attr")


class Process(object):
    """
    进程信息
    {
        "bk_supplier_account": "0",
        "bind_ip": "1",
        "description": "",
        "start_cmd": "",
        "restart_cmd": "",
        "pid_file": "",
        "auto_start": false,
        "timeout": 30,
        "protocol": "1",
        "auto_time_gap": 60,
        "reload_cmd": "",
        "bk_func_name": "java",
        "work_path": "/data/bkee",
        "stop_cmd": "",
        "face_stop_cmd": "",
        "port": "8008,8443",
        "bk_process_name": "job_java",
        "user": "",
        "proc_num": 1,
        "priority": 1,
        "bk_biz_id": 2,
        "bk_func_id": "",
        "bk_process_id": 1
    }
    """

    def __init__(
        self,
        bk_process_id,
        bk_process_name,
        bk_func_name,
        service_instance_id,
        bk_host_id,
        bind_ip="",
        port="",
        protocol="",
        process_template_id=0,
        **kwargs,
    ):
        """
        :param int bk_process_id: 进程ID
        :param str bk_process_name: 进程名称
        :param str bk_func_name: 进程功能名称
        :param str bind_ip: 绑定IP
        :param str port: 绑定端口，格式: 1,2,3-5,7-10
        :param str service_instance_id: 服务实例ID
        :param str process_template_id: 进程模板ID
        :param str bk_host_id: 主机ID
        """
        self.bk_process_id = int(bk_process_id)
        self.bk_process_name = bk_process_name
        self.bk_func_name = bk_func_name
        self.bind_ip = bind_ip or ""
        self.port = port or ""
        self.service_instance_id = int(service_instance_id)
        self.process_template_id = int(process_template_id)
        self.bk_host_id = int(bk_host_id)
        self.protocol = protocol

    def __eq__(self, other):
        return self.bk_process_id == other.bk_process_id

    def __hash__(self):
        return hash(self.bk_process_id)

    def __repr__(self):
        return "<Process: {}({})>".format(self.bk_process_name, self.bk_func_name)

    @classmethod
    def _parse_port_num(cls, port_num):
        """
        检查端口号是否合法
        """
        if isinstance(port_num, six.string_types) and port_num.strip().isdigit():
            port_num = int(port_num)
        elif isinstance(port_num, int):
            pass
        else:
            raise ValueError(_("无法解析的端口号：%s") % port_num)

        if 0 <= port_num <= 65535:
            return port_num

        raise ValueError(_("不在合法范围内的端口号：%s") % port_num)

    @property
    def port_range(self):
        """
        将端口范围字符串解析为结构化数据
        :return: 二元组列表，元组的两个元素分别代表起始端口和结束端口（闭区间）
        :example [(1, 1), (3, 5), (7, 10)]
        """

        port_range_list = []

        # 为空直接返回
        if not self.port:
            return port_range_list

        try:
            # 以逗号拆开
            range_str_list = [p for p in self.port.split(",") if p != ""]
            for range_str in range_str_list:
                try:
                    # 先判断是不是单个数字
                    port_num = self._parse_port_num(range_str)
                    # 如果是单个数字，则转化为区间并保存
                    port_range_list.append((port_num, port_num))
                except ValueError:
                    # 如果不是单个数字，尝试识别为区间字符串
                    port_range_tuple = range_str.split("-")

                    # 尝试拆分为上界和下界
                    if len(port_range_tuple) != 2:
                        raise ValueError(_("不合法的端口范围定义格式：%s") % range_str)

                    # 对上界和下界分别进行解析
                    port_num_min, port_num_max = port_range_tuple
                    port_num_min = self._parse_port_num(port_num_min)
                    port_num_max = self._parse_port_num(port_num_max)

                    if port_num_min > port_num_max:
                        # 下界 > 上界 也是不合法的范围
                        raise ValueError(_("不合法的端口范围定义格式：%s") % range_str)
                    port_range_list.append((port_num_min, port_num_max))

        except Exception as e:
            raise ValueError(_("端口范围字符串解析失败：%s") % e)

        return port_range_list


class ServiceInstance(object):
    """
    服务实例
    """

    def __init__(
        self,
        service_instance_id,
        name=None,
        bk_host_id=None,
        bk_module_id=None,
        service_category_id=0,
        labels=None,
        topo_link=None,
        **kwargs,
    ):
        """
        :param int service_instance_id: 服务实例ID
        :param str or unicode name: 服务实例名称
        :param int bk_host_id: 绑定的主机ID
        :param int bk_module_id: 所属模块ID
        :param int service_category_id: 所属服务分类ID
        :param dict[str, list[TopoNode]] topo_link: 服务实例所属拓扑链
        """
        self.service_instance_id = int(service_instance_id)
        self.name = name
        self.bk_host_id = int(bk_host_id or 0)
        self.bk_module_id = int(bk_module_id or 0)
        self.service_category_id = int(service_category_id or 0)
        self.labels = labels or {}
        self.topo_link = {}

        if topo_link:
            for node_id, nodes in topo_link.items():
                self.topo_link[node_id] = [TopoNode(**node) if isinstance(node, dict) else node for node in nodes]

        # 自定义属性
        self._extra_attr = kwargs

    def __getattr__(self, item):
        """
        获取自定义属性
        """
        if item == "_extra_attr":
            return super(ServiceInstance, self).__getattribute__(item)
        if item in self._extra_attr:
            return self._extra_attr[item]
        return super(ServiceInstance, self).__getattribute__(item)

    def __eq__(self, other):
        return self.service_instance_id == other.service_instance_id

    def __hash__(self):
        return hash(self.service_instance_id)

    def __repr__(self):
        return "<ServiceInstance: {}({})>".format(self.name, self.service_instance_id)


class ServiceCategoryNode(object):
    """
    服务分类节点
    """

    def __init__(self, category_id, category_name, parent_id=0, root_id=0, **kwargs):
        """
        :param int category_id: 分类ID
        :param str category_name: 分类名称
        :param int parent_id: 父节点ID
        :param int root_id: 根节点ID
        """
        self.category_id = int(category_id)
        self.category_name = category_name
        self.parent_id = int(parent_id)
        self.root_id = int(root_id)


class ServiceCategoryTopo(ServiceCategoryNode):
    """
    服务分类拓扑
    {
        "id": 1,
        "name":"数据库",
        "parent_id": 0,
        "root_id": 0,
        "child": [
            {
                "id": 2,
                "name":"mysql",
                "parent_id": 1,
                "root_id": 1,
            }
        ]
    }
    """

    def __init__(self, tree_data):
        child = tree_data.pop("child", [])
        super(ServiceCategoryTopo, self).__init__(**tree_data)
        # 子节点信息
        self.child = [ServiceCategoryTopo(**c) for c in child]
