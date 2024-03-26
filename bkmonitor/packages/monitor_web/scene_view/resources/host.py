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
import json
from typing import Dict, List
from urllib.parse import urljoin

from django.conf import settings
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.cmdb.define import Host, TopoNode
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.ip import is_v6
from bkmonitor.utils.request import get_request
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, api, resource
from monitor_web.constants import AGENT_STATUS


class GetHostProcessPortStatusResource(Resource):
    """
    获取主机进程端口状态（用于port-status图表）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        bk_target_ip = serializers.CharField(required=False)
        bk_target_cloud_id = serializers.CharField(required=False)
        display_name = serializers.CharField(required=False)
        bk_host_id = serializers.IntegerField(required=False)

        # 主机场景，以关联资源身份请求
        def validate_bk_biz_id(self, value):
            return validate_bk_biz_id(value)

    def perform_request(self, params):
        if params.get("bk_host_id"):
            hosts = api.cmdb.get_host_by_id(bk_biz_id=params["bk_biz_id"], bk_host_ids=[params["bk_host_id"]])
            if not hosts:
                return []
            host = hosts[0]
            ip, bk_cloud_id = host.bk_host_innerip, host.bk_cloud_id
        else:
            ip, bk_cloud_id = params["bk_target_ip"], params["bk_target_cloud_id"]

        data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
        promql_statement = f"system:proc_port:proc_exists{{bk_target_ip='{ip}', " \
                           f"display_name='{params['display_name']}', bk_cloud_id='{bk_cloud_id}'}}"
        query_config = {"promql": promql_statement, "interval": 60}
        data_source = data_source_class(bk_biz_id=params["bk_biz_id"], **query_config)
        query = UnifyQuery(bk_biz_id=params["bk_biz_id"], data_sources=[data_source], expression="")
        data: List = query.query_data(limit=1, slimit=1)
        if not data:
            return []
        else:
            data: Dict = data[-1]

        # 不同状态的展示信息
        status_mapping = {
            "listen": {"statusBgColor": "#e7f9f2", "statusColor": "#3FC06D", "name": _("正常")},
            "nonlisten": {"statusBgColor": "#f0f1f5", "statusColor": "#c4c6cc", "name": _("停用")},
            "not_accurate_listen": {"statusBgColor": "#ffe8c3", "statusColor": "#EA3636", "name": _("异常")},
        }

        result = []
        for key in status_mapping.keys():
            ports = json.loads(data[key])
            if not ports:
                continue
            for port in ports:
                if key == "not_accurate_listen":
                    # not_accurate_listen 字段格式：IP:PORT
                    actual_port = port.rsplit(":", 1)[-1]
                else:
                    actual_port = port
                result.append({"value": str(actual_port), **status_mapping[key]})
        return result


class GetHostOrTopoNodeDetailResource(ApiAuthResource):
    """
    获取主机或拓扑节点详情（用于对象详情面板）
    """

    protocol_map = {"1": "TCP", "2": "UDP", "3": "TCP6", "4": "UDP6"}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        bk_process_name = serializers.CharField(required=False, allow_blank=True)
        bk_inst_id = serializers.IntegerField(required=False)
        bk_obj_id = serializers.CharField(required=False)
        bk_host_id = serializers.IntegerField(required=False)

        def validate(self, attrs):
            if not attrs.get("bk_host_id") and not attrs.get("bk_inst_id") and not attrs.get("bk_obj_id"):
                raise serializers.ValidationError(_("bk_host_id和(bk_obj_id/bk_inst_id)不能同时为空"))
            return attrs

    @classmethod
    def get_process_info(cls, bk_biz_id: int, bk_process_name: str, bk_host_id: int = None) -> List:
        if not bk_process_name:
            return []

        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=[bk_host_id])
        if not hosts:
            return []

        host = hosts[0]
        processes = api.cmdb.get_process(
            bk_biz_id=bk_biz_id, bk_host_id=host.bk_host_id, include_multiple_bind_info=True
        )

        # 获得指定进程名的端口绑定信息
        bind_info_list = []
        for p in processes:
            if p.bk_process_name != bk_process_name:
                continue

            protocol = cls.protocol_map.get(p.protocol)
            if is_v6(p.bind_ip):
                bind_ip = f"{protocol} [{p.bind_ip}]"
            else:
                bind_ip = f"{protocol} {p.bind_ip}"
            if p.port:
                bind_ip = f"{bind_ip}:{p.port}"
            bind_info_list.append(bind_ip)

            return [
                {"name": _("名称"), "type": "string", "value": p.bk_process_name},
                {"name": _("别名"), "type": "string", "value": p.bk_func_name},
                {"name": _("绑定信息"), "type": "list", "value": bind_info_list},
            ]
        return []

    @classmethod
    def get_host_info(cls, bk_biz_id: int, bk_host_id: int):
        hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=[bk_host_id])
        if not hosts:
            return {}
        host = hosts[0]

        # 查询拓扑信息
        topo_links: Dict[str, List[TopoNode]] = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id).convert_to_topo_link()
        topo_links = {key: value for key, value in topo_links.items() if int(key.split("|")[1]) in host.bk_module_ids}

        # 查询Agent状态
        status = resource.cc.get_agent_status(bk_biz_id=bk_biz_id, hosts=[host]).get(host.bk_host_id)
        status_mapping = {
            AGENT_STATUS.ON: {"type": "normal", "text": _("正常")},
            AGENT_STATUS.NOT_EXIST: {"type": "disabled", "text": _("Agent未安装")},
            AGENT_STATUS.NO_DATA: {"type": "failed", "text": _("无数据")},
            AGENT_STATUS.UNKNOWN: {"type": "disabled", "text": _("未知")},
        }

        bk_os_display_name = " ".join(
            [getattr(host, "bk_os_name", ""), getattr(host, "bk_os_version", ""), getattr(host, "bk_os_bit", "")]
        )

        bk_os_display_type = ""
        if getattr(host, "bk_os_type", ""):
            bk_os_display_type = settings.OS_TYPE_NAME_DICT.get(int(host.bk_os_type))

        docker_info = ""
        if getattr(host, "docker_client_version", "") or getattr(host, "docker_server_version", ""):
            docker_info = (
                str(getattr(host, "docker_client_version", "")) + " " + str(getattr(host, "docker_server_version", ""))
            )

        host_state = str(host.bk_state)
        monitor_mapping = {
            # 不告警
            "is_shielding": {"type": "is_shielding", "text": host_state},
            # 不监控
            "ignore_monitoring": {"type": "ignore_monitoring", "text": host_state},
            "normal": {"type": "normal", "text": host_state},
        }
        monitor_status = "normal"
        if host.is_shielding:
            monitor_status = "is_shielding"
        if host.ignore_monitoring:
            monitor_status = "ignore_monitoring"

        return [
            # 运营状态作为特殊类型
            {"name": _("运营状态"), "type": "monitor_status", "value": monitor_mapping[monitor_status]},
            {"name": _("采集状态"), "type": "status", "value": status_mapping[status]},
            {"name": _("主机名"), "type": "string", "value": host.bk_host_name, "need_copy": bool(host.bk_host_name)},
            {
                "name": _("内网IP"),
                "count": 2,
                "type": "link",
                "need_copy": bool(host.bk_host_innerip),
                "value": {
                    "url": urljoin(settings.BK_CC_URL, f"/#/resource/host/{host.bk_host_id}"),
                    "value": host.bk_host_innerip,
                },
                "children": [
                    {
                        "name": "IPv4",
                        "type": "string",
                        "value": host.bk_host_innerip,
                    },
                    {
                        "name": "IPv6",
                        "type": "string",
                        "value": host.bk_host_innerip_v6,
                    },
                ],
            },
            {
                "name": _("外网IP"),
                "type": "string",
                "value": host.bk_host_outerip,
                "count": 2,
                "need_copy": bool(host.bk_host_outerip),
                "children": [
                    {
                        "name": "IPv4",
                        "type": "string",
                        "value": host.bk_host_outerip,
                    },
                    {
                        "name": "IPv6",
                        "type": "string",
                        "value": host.bk_host_outerip_v6,
                    },
                ],
            },
            {
                "name": _("操作系统"),
                "type": "string",
                "value": str(bk_os_display_name),
                "count": 4,
                "children": [
                    {
                        "name": _("名称"),
                        "type": "string",
                        "value": str(getattr(host, "bk_os_name", "")),
                    },
                    {
                        "name": _("版本"),
                        "type": "string",
                        "value": str(getattr(host, "bk_os_version", "")),
                    },
                    {
                        "name": _("类型"),
                        "type": "string",
                        "value": bk_os_display_type,
                    },
                    {
                        "name": _("位数"),
                        "type": "string",
                        "value": str(getattr(host, "bk_os_bit", "")),
                    },
                ],
            },
            {"name": "CPU", "type": "string", "value": str(getattr(host, "bk_cpu", ""))},
            {"name": _("内存容量(MB)"), "type": "string", "value": str(getattr(host, "bk_mem", ""))},
            {"name": _("磁盘容量(GB)"), "type": "string", "value": str(getattr(host, "bk_disk", ""))},
            {
                "name": "Docker",
                "type": "string",
                "value": docker_info,
                "count": 2,
                "children": [
                    {
                        "name": _("docker client版本"),
                        "type": "string",
                        "value": str(getattr(host, "docker_client_version", "")),
                    },
                    {
                        "name": _("docker server版本"),
                        "type": "string",
                        "value": str(getattr(host, "docker_server_version", "")),
                    },
                ],
            },
            {"name": _("云区域"), "type": "string", "value": str(getattr(host, "bk_cloud_name", ""))},
            {"name": _("云区域ID"), "type": "string", "value": str(getattr(host, "bk_cloud_id", ""))},
            {
                "name": _("所属模块"),
                "type": "list",
                "value": [
                    " / ".join(topo.bk_inst_name for topo in reversed(topo_link) if topo.bk_obj_id != "biz")
                    for topo_link in topo_links.values()
                ],
            },
        ]

    @classmethod
    def get_node_info(cls, bk_biz_id: int, bk_obj_id: str, bk_inst_id: str):
        """
        获取节点信息
        """
        topo_nodes = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id).get_all_nodes_with_relation()
        node = topo_nodes.get(f"{bk_obj_id}|{bk_inst_id}")
        hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id, topo_nodes={bk_obj_id: [bk_inst_id]})

        result = [
            {"name": _("节点ID"), "type": "number", "value": bk_inst_id},
            {"name": _("节点类型"), "type": "string", "value": node.bk_obj_name if node else ""},
            {"name": _("节点名称"), "type": "string", "value": node.bk_inst_name if node else ""},
            {
                "name": _("子级数量"),
                "type": "number",
                "value": len(hosts) if bk_obj_id == "module" else len(node.child),
            },
            {"name": _("主机数量"), "type": "number", "value": len(hosts)},
        ]

        # 如果是模块，则补充"主备负责人"信息
        if bk_obj_id == "module":
            modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, bk_module_ids=[bk_inst_id])
            if modules:
                result.extend(
                    [
                        {"name": _("主要维护人"), "type": "string", "value": ",".join(modules[0].operator)},
                        {"name": _("备份维护人"), "type": "string", "value": ",".join(modules[0].bk_bak_operator)},
                    ]
                )
        return result

    def perform_request(self, params):
        if "bk_obj_id" in params and "bk_inst_id" in params:
            info = self.get_node_info(params["bk_biz_id"], params["bk_obj_id"], params["bk_inst_id"])
        else:
            if "bk_process_name" in params:
                info = self.get_process_info(
                    bk_biz_id=params["bk_biz_id"],
                    bk_host_id=params["bk_host_id"],
                    bk_process_name=params["bk_process_name"],
                )
            else:
                info = self.get_host_info(bk_biz_id=params["bk_biz_id"], bk_host_id=params["bk_host_id"])

        for item in info:
            if "children" in item:
                item["children"] = list(filter(lambda c: c["value"], item["children"]))
                item["count"] = len(item["children"])

        # 临时分享处理返回链接数据
        request = get_request(peaceful=True)
        if request and getattr(request, "token", None):
            for info_item in info:
                if info_item["type"] == "link":
                    info_item["type"] = "string"
                    info_item["value"] = info_item["value"].get("value", "")

        return info


class GetHostProcessUptimeResource(Resource):
    """
    获取主机/进程启动时间（用于场景视图text-unit图表）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        display_name = serializers.CharField()
        bk_host_id = serializers.IntegerField()

    def perform_request(self, params):
        hosts = api.cmdb.get_host_by_id(bk_biz_id=params["bk_biz_id"], bk_host_ids=[params["bk_host_id"]])
        if not hosts:
            return []
        host = hosts[0]
        ip, bk_cloud_id = host.bk_host_innerip, host.bk_cloud_id

        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            table="system.proc",
            interval=60,
            group_by=["bk_target_ip", "bk_target_cloud_id", "display_name"],
            metrics=[{"field": "uptime", "method": "MIN", "alias": "A"}],
            filter_dict={
                "bk_target_ip": ip,
                "bk_target_cloud_id": bk_cloud_id,
                "display_name": params["display_name"],
            },
        )
        query = UnifyQuery(bk_biz_id=params["bk_biz_id"], data_sources=[data_source], expression="A")
        data: List = query.query_data()
        if data:
            value = data[-1]["_result_"]
        else:
            value = ""
        return {"value": value, "unit": "s"}


class GetHostProcessListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bk_host_id = serializers.IntegerField(required=False)
        bk_target_ip = serializers.CharField(required=False)
        bk_target_cloud_id = serializers.IntegerField(required=False)

        def validate(self, attrs):
            if not attrs.get("bk_host_id") and (
                not attrs.get("bk_target_ip") or attrs.get("bk_target_cloud_id") is None
            ):
                raise ValidationError("bk_host_id or bk_target_ip and bk_target_cloud_id must be provided")
            return attrs

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]

        if params.get("bk_host_id"):
            hosts = api.cmdb.get_host_by_id(bk_host_ids=[params["bk_host_id"]], bk_biz_id=bk_biz_id)
        else:
            hosts = api.cmdb.get_host_by_ip(
                bk_biz_id=bk_biz_id, ips=[{"ip": params["bk_target_ip"], "bk_cloud_id": params["bk_target_cloud_id"]}]
            )

        if not hosts:
            return []
        else:
            host = hosts[0]

        processes = resource.cc.get_process_info(bk_biz_id, hosts=[host])
        if host.bk_host_id not in processes:
            return []

        return [
            {"status": process["status"], "name": process["name"], "id": process["name"]}
            for process in processes[host.bk_host_id]
        ]


class GetHostListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, params):
        hosts: List[Host] = api.cmdb.get_host_by_topo_node(bk_biz_id=params["bk_biz_id"])
        return [
            {
                "id": host.bk_host_id,
                "name": host.display_name,
                "ip": host.ip,
                "bk_cloud_id": host.bk_cloud_id,
                "target": {
                    "bk_target_ip": host.ip,
                    "bk_target_cloud_id": host.bk_cloud_id,
                },
            }
            for host in hosts
        ]


class GetHostInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bk_host_id = serializers.IntegerField(required=False)
        ip = serializers.CharField(required=False)
        bk_cloud_id = serializers.IntegerField(required=False)

    def validate(self, params):
        if not (params.get("bk_host_id") or (params.get("ip") and params.get("bk_cloud_id"))):
            raise ValidationError(_("bk_host_id和ip/bk_cloud_id必须有一个"))
        return params

    def perform_request(self, params):
        if params.get("bk_host_id"):
            hosts = api.cmdb.get_host_by_id(bk_biz_id=params["bk_biz_id"], bk_host_ids=[params["bk_host_id"]])
        else:
            hosts = api.cmdb.get_host_by_ip(
                bk_biz_id=params["bk_biz_id"], ips=[{"ip": params["ip"], "bk_cloud_id": params["bk_cloud_id"]}]
            )
        if not hosts:
            return None

        host = hosts[0]
        return {
            "display_name": host.display_name,
            "ip": host.ip,
            "bk_cloud_id": host.bk_cloud_id,
            "bk_host_id": host.bk_host_id,
            "bk_os_type": settings.OS_TYPE_NAME_DICT.get(int(host.bk_os_type)) if host.bk_os_type else "",
        }
