# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Type
from urllib.parse import urljoin

from django.conf import settings
from django.utils.translation import ugettext as _
from rest_framework import serializers

from apm_web.topo.constants import SourceType
from core.drf_resource import api, resource


class ResourceDetail:
    def __init__(self, bk_biz_id, app_name, start_time, end_time, source_info):
        ser = self.serializer(data=source_info)
        ser.is_valid(raise_exception=True)
        self.source_info = ser.validated_data
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.start_time = start_time
        self.end_time = end_time

    @property
    def serializer(self) -> Type[serializers.Serializer]:
        raise NotImplementedError

    @property
    def detail(self):
        raise NotImplementedError

    def search_and_handle_alert(self, query_string):
        alert_infos = self.search_alert(query_string)
        if not alert_infos:
            return {}
        return {
            "alert_display": {
                "alert_id": [i["id"] for i in alert_infos][0],
                "alert_name": [i["id"] for i in alert_infos][0],
            },
            "alert_ids": [i["id"] for i in alert_infos],
        }

    def search_alert(self, query_string):
        full_query_string = f"{query_string} AND status: ABNORMAL"
        query_params = {
            "bk_biz_ids": [self.bk_biz_id],
            "query_string": full_query_string,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "page_size": 1000,
        }
        return resource.fta_web.alert.search_alert(**query_params).get("alerts", [])

    @classmethod
    def _list_info_raws(cls, infos, columns):
        res = []
        for i in infos:
            if i["name"] not in columns:
                continue

            v = i["value"]
            if isinstance(v, dict):
                v = v.get("value")
            res.append(
                {
                    "name": i["name"],
                    "value": v,
                }
            )

        return res


class SystemDetail(ResourceDetail):
    # 需要进行显示的主机信息列
    # 因为 GetHostOrTopoNodeDetailResource.get_host_info 处没有使用 id 所以这里使用中文进行过滤 两边需要保持一致
    _host_info_columns = [_("主机名"), _("云区域"), _("云区域ID"), _("所属模块")]

    @property
    def serializer(self):
        class systemFields(serializers.Serializer):  # noqa
            bk_target_ip = serializers.CharField()

        return systemFields

    @property
    def detail(self):
        ip = self.source_info["bk_target_ip"]
        # 获取主机 bk_host_id
        response = api.cmdb.get_host_by_ip(
            # TODO 等待关联接口增加 bk_cloud_id 后 再增加查询条件
            ips=[{"ip": ip}],
            bk_biz_id=self.bk_biz_id,
            search_outer_ip=True,
        )
        if not response:
            raise ValueError(f"没有从 CMDB 中找到主机 IP: {ip} 的信息，原因可能是此 IP 为历史快照数据不存在于当前 CMDB 中")

        bk_host_id = response[0].bk_host_id

        # 获取主机基础信息
        host_infos = resource.scene_view.get_host_or_topo_node_detail.get_host_info(self.bk_biz_id, bk_host_id)

        return {
            "title": {
                "name": ip,
                "url": f"/performance/detail/{bk_host_id}?from={self.start_time}&to={self.end_time}",
            },
            "resource_link": urljoin(settings.BK_CC_URL, f"#/business/{self.bk_biz_id}/index/host/{bk_host_id}"),
            "raws": self._list_info_raws(host_infos, self._host_info_columns),
            **self.search_and_handle_alert(f"(ip: {ip} OR tags.ip: {ip})"),
        }

    def _list_alert_raws(self, bk_target_ip, alert_infos):
        return [
            {
                "name": "包含未恢复告警",
                "type": "alert",
                "value": {
                    "total": len(alert_infos),
                    "alert_ids": [i["id"] for i in alert_infos],
                    "url": f'/event-center?queryString="ip: {bk_target_ip}"&from={self.start_time}&to={self.end_time}',
                },
            }
        ]


class K8sPodDetail(ResourceDetail):
    _pod_info_columns = [
        _("运行状态"),
        _("集群ID"),
        _("集群名称"),
        _("名字空间"),
        _("Pod IP"),
        _("节点IP"),
        _("节点名称"),
    ]

    @property
    def serializer(self) -> Type[serializers.Serializer]:
        class podSerializer(serializers.Serializer):  # noqa
            bcs_cluster_id = serializers.CharField()
            namespace = serializers.CharField()
            pod = serializers.CharField()

        return podSerializer

    @property
    def detail(self):
        bcs_cluster_id = self.source_info["bcs_cluster_id"]
        namespace = self.source_info["namespace"]
        pod = self.source_info["pod"]

        # 获取 Pod 信息
        pod_infos = resource.scene_view.get_kubernetes_pod(
            bk_biz_id=self.bk_biz_id,
            bcs_cluster_id=bcs_cluster_id,
            namespace=namespace,
            pod_name=pod,
        )
        if not pod_infos:
            raise ValueError(f"没有从集群中获取到 {pod} 的信息，原因可能是此 Pod 为历史快照数据并且当前已经销毁")

        return {
            "title": {
                "name": pod,
                "url": f"/k8s?"
                f"filter-bcs_cluster_id={bcs_cluster_id}&"
                f"filter-namespace={namespace}&"
                f"filter-pod_name={pod}&"
                f"from={self.start_time}&to={self.end_time}",
            },
            "resource_link": urljoin(
                settings.BK_BCS_HOST,
                f"bcs/projects/bkce/clusters/{bcs_cluster_id}/workloads/pods/namespaces/{namespace}/{pod}?kind=Pod",
            ),
            "raws": self._list_info_raws(pod_infos, self._pod_info_columns),
            **self.search_and_handle_alert(
                f'tags.pod: "{pod}" AND tags.bcs_cluster_id: "{bcs_cluster_id}" AND tags.namespace: "{namespace}"'
            ),
        }


class K8sServiceDetail(ResourceDetail):
    _service_info_columns = [
        _("集群ID"),
        _("集群名称"),
        _("名字空间"),
        _("类型"),
        _("Pod数量"),
    ]

    @property
    def serializer(self) -> Type[serializers.Serializer]:
        class serviceSerializer(serializers.Serializer):  # noqa
            bcs_cluster_id = serializers.CharField()
            namespace = serializers.CharField()
            service = serializers.CharField()

        return serviceSerializer

    @property
    def detail(self):
        bcs_cluster_id = self.source_info["bcs_cluster_id"]
        namespace = self.source_info["namespace"]
        service = self.source_info["service"]

        # 获取 Service 信息
        service_infos = resource.scene_view.get_kubernetes_service(
            bk_biz_id=self.bk_biz_id,
            bcs_cluster_id=bcs_cluster_id,
            namespace=namespace,
            service_name=service,
        )
        if not service_infos:
            raise ValueError(f"没有从集群中获取到 {service} 的信息，原因可能是此 Service 为历史快照数据并且当前已经销毁")

        return {
            "title": {
                "name": service,
                "url": f"/k8s?"
                f"filter-bcs_cluster_id={bcs_cluster_id}&"
                f"filter-namespace={namespace}&"
                f"filter-service_name={service}&"
                f"from={self.start_time}&to={self.end_time}",
            },
            "raws": self._list_info_raws(service_infos, self._service_info_columns),
            **self.search_and_handle_alert(
                f'tags.service: "{service}" '
                f'AND tags.bcs_cluster_id: "{bcs_cluster_id}" AND tags.namespace: "{namespace}"'
            ),
        }


class NodeRelationDetailHandler:
    mapping = {
        SourceType.SYSTEM.value: SystemDetail,
        SourceType.POD.value: K8sPodDetail,
        SourceType.SERVICE.value: K8sServiceDetail,
    }

    @classmethod
    def get_detail(cls, bk_biz_id, app_name, source_type, source_info, start_time, end_time):
        if source_type not in cls.mapping:
            raise ValueError(f"不支持查询资源类型为 {source_info} 的节点信息")

        return cls.mapping[source_type](bk_biz_id, app_name, start_time, end_time, source_info).detail
