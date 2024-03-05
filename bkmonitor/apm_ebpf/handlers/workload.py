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
import typing
from dataclasses import asdict, dataclass, field

from dacite import from_dict
from django.utils.datetime_safe import datetime

from apm_ebpf.apps import logger
from apm_ebpf.constants import WorkloadType
from apm_ebpf.handlers.relation import RelationHandler
from apm_ebpf.models.workload import DeepflowWorkload


@dataclass
class _BaseContent:
    name: str
    is_normal: bool
    workload_type: WorkloadType


@dataclass
class _DeploymentSpecPort:
    name: str
    containerPort: int
    protocol: str


@dataclass
class DeploymentContent(_BaseContent):
    replicas: int = None
    image: str = None
    image_name: str = None
    ports: typing.List[_DeploymentSpecPort] = field(default_factory=list)

    workload_type: str = WorkloadType.DEPLOYMENT.value


@dataclass
class _ServicePort:
    name: str
    port: int
    target_port: int
    protocol: typing.Union[str, None]
    node_port: typing.Union[int, None]


@dataclass
class ServiceContent(_BaseContent):
    ports: typing.List[_ServicePort] = field(default_factory=list)
    type: str = None
    workload_type: str = WorkloadType.SERVICE.value


class WorkloadContent:
    _normal_predicate = {
        WorkloadType.DEPLOYMENT.value: lambda i: any(
            True for j in i.conditions if j.type == "Available" and j.status == "True"
        )
    }

    @classmethod
    def deployment_to(cls, describe) -> DeploymentContent:
        """
        将K8S SDK返回的Workload转为DB存储格式
        """
        spec_describe = describe.spec
        image = spec_describe.template.spec.containers[0]

        status_describe = describe.status

        return DeploymentContent(
            name=describe.metadata.name,
            replicas=spec_describe.replicas,
            image=image.image,
            image_name=image.name,
            ports=[
                _DeploymentSpecPort(name=i.name, containerPort=i.container_port, protocol=i.protocol)
                for i in image.ports
            ]
            if image.ports
            else [],
            is_normal=cls._normal_predicate[WorkloadType.DEPLOYMENT.value](status_describe),
        )

    @classmethod
    def json_to_deployment(cls, content_json) -> DeploymentContent:
        return from_dict(DeploymentContent, content_json)

    @classmethod
    def json_to_service(cls, content_json):
        return from_dict(ServiceContent, content_json)

    @classmethod
    def service_to(cls, describe) -> ServiceContent:
        spec_describe = describe.spec

        return ServiceContent(
            name=describe.metadata.name,
            ports=[
                _ServicePort(
                    name=i.name,
                    port=i.port,
                    node_port=i.node_port,
                    target_port=i.target_port,
                    protocol=i.protocol,
                )
                for i in spec_describe.ports
            ]
            if spec_describe.ports
            else [],
            type=describe.spec.type,
            is_normal=True,
        )

    @classmethod
    def extra_port(cls, content, name) -> int:
        """
        从NodePort Service定义中提取指定名称的端口号
        """
        service = from_dict(ServiceContent, content)

        if service.type != "NodePort":
            logger.warning(f"service: {service.name} does not match support type({service.type}) NodePort.")
            return 0

        for port in service.ports:
            if port.name == name:
                return port.node_port

        return 0


class WorkloadHandler:
    @classmethod
    def upsert(cls, cluster_id, namespace, content: _BaseContent):
        """
        创建/更新集群workload
        因为下游仪表盘只会创建一次所以不进行删除
        """
        # 在此集群关联的所有业务中都建立workload信息
        bk_biz_ids = RelationHandler.list_biz_ids(cluster_id)
        for bk_biz_id in bk_biz_ids:
            params = {
                "bk_biz_id": bk_biz_id,
                "cluster_id": cluster_id,
                "namespace": namespace,
                "name": content.name,
                "type": content.workload_type,
            }
            record = DeepflowWorkload.objects.filter(**params).first()
            if record:
                record.content = asdict(content)
                record.is_normal = content.is_normal
                record.last_check_time = datetime.now()
                record.save()
            else:
                DeepflowWorkload.objects.create(
                    bk_biz_id=bk_biz_id,
                    cluster_id=cluster_id,
                    namespace=namespace,
                    name=content.name,
                    content=asdict(content),
                    type=content.workload_type,
                    is_normal=content.is_normal,
                    last_check_time=datetime.now(),
                )

    @classmethod
    def list_deployments(cls, bk_biz_id, namespace):
        return DeepflowWorkload.objects.filter(
            bk_biz_id=bk_biz_id, namespace=namespace, type=WorkloadType.DEPLOYMENT.value
        )

    @classmethod
    def list_services(cls, bk_biz_id, namespace, cluster_id, service_name=None):
        f = DeepflowWorkload.objects.filter(
            bk_biz_id=bk_biz_id, cluster_id=cluster_id, namespace=namespace, type=WorkloadType.SERVICE.value
        )
        if service_name:
            f = f.filter(name=service_name)

        return f

    @classmethod
    def list_deepflow_cluster_ids(cls, bk_biz_id):
        return list(set(DeepflowWorkload.objects.filter(bk_biz_id=bk_biz_id).values_list("cluster_id", flat=True)))

    @classmethod
    def list_exist_biz_ids(cls):
        """获取具有workload的业务ID集合"""
        return list(set(DeepflowWorkload.objects.values_list("bk_biz_id", flat=True)))
