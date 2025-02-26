# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml
from django.conf import settings
from django.utils.translation import gettext as _
from kubernetes.client.models import v1_pod

from apps.api import CCApi
from apps.log_commons.adapt_ipv6 import get_ip_field
from apps.log_databus.constants import (
    BK_LOG_COLLECTOR_CONTAINER_NAME,
    BK_LOG_COLLECTOR_MAIN_CONFIG_NAME,
    BK_LOG_COLLECTOR_NAMESPACE,
    BK_LOG_COLLECTOR_SUB_CONFIG_PATH,
    CONFIGMAP_NAME,
    CRD_NAME,
    DAEMONSET_NAME,
    DAEMONSET_POD_LABELS,
    CollectStatus,
)
from apps.log_databus.handlers.check_collector.checker.base_checker import Checker
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.utils.bcs import Bcs


@dataclass
class Pod:
    # 可能一个采集项存在于多个Pod中, 一个Pod中可能存在多个采集子配置
    name: str = ""
    node: str = ""
    node_ip: str = ""
    main_config: str = ""
    sub_config_list: List[str] = field(default_factory=list)
    pod: v1_pod.V1Pod = field(default_factory=v1_pod.V1Pod)


class BkunifylogbeatChecker(Checker):
    """采集器检查"""

    CHECKER_NAME = _("采集器检查")

    def __init__(
        self,
        collector_config: CollectorConfig,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.collector_config = collector_config
        # target_server, 获取NodeIP, 作为target_server传递到agent_checker中
        self.target_server: Dict[str, Any] = {}
        # 初始化bcs_client
        self.k8s_client: Bcs = Bcs(cluster_id=collector_config.bcs_cluster_id)
        self.namespace: str = BK_LOG_COLLECTOR_NAMESPACE
        self.crd_name: str = CRD_NAME
        self.configmap_name: str = CONFIGMAP_NAME
        self.daemonset_name: str = DAEMONSET_NAME
        self.daemonset_pod_labels: str = DAEMONSET_POD_LABELS
        self.container_name: str = BK_LOG_COLLECTOR_CONTAINER_NAME
        # 主配置路径, 文件路径, 可直接使用
        self.main_config_dir = os.path.join(settings.CONTAINER_COLLECTOR_CONFIG_DIR, BK_LOG_COLLECTOR_MAIN_CONFIG_NAME)
        # 子配置目录, 目录路径, 需要拼接子配置文件名
        self.sub_config_dir = os.path.join(settings.CONTAINER_COLLECTOR_CONFIG_DIR, BK_LOG_COLLECTOR_SUB_CONFIG_PATH)

        # endpoint校验
        self.endpoint: str = ""

        # 匹配到bk_data_id的CR列表
        self.cr_list = []

        # 匹配到的pod列表
        self.pod_list: List[Pod] = []

    def _run(self):
        self.check_task_status()
        self.check_crd()
        self.check_cr()
        self.check_config_map()
        self.check_daemonset()
        self.get_match_pod()
        self.check_pod()
        self.filter_target_server()

    def check_task_status(self):
        """检查采集任务状态"""
        if self.collector_config.is_custom_container:
            self.append_normal_info(_("自定义容器采集, 不检查采集任务状态"))
            return
        task_status_contents = (
            CollectorHandler(self.collector_config.collector_config_id).get_task_status(id_list=[]).get("contents", [])
        )
        # contents为空不正常, 需提示
        if not task_status_contents:
            self.append_error_info(_("获取采集任务状态为空, 请检查采集配置"))
            return
        for single_collector_status in task_status_contents:
            # child为空不正常, 需提示
            if not single_collector_status.get("child", []):
                self.append_error_info(
                    _("采集项[{_id}]: {_name} 采集任务状态为空").format(
                        _id=single_collector_status.get("collector_config_id", ""),
                        _name=single_collector_status.get("collector_config_name", ""),
                    )
                )
                continue
            # 先将统计的信息输出, 全部成功才算成功, 只有失败才会输出具体信息
            if [i for i in single_collector_status["child"] if i["status"] != CollectStatus.SUCCESS]:
                self.append_error_info(
                    _("采集项[{_id}]: {_name} 采集任务状态异常").format(
                        _id=single_collector_status.get("collector_config_id", ""),
                        _name=single_collector_status.get("collector_config_name", ""),
                    )
                )
            else:
                self.append_normal_info(
                    _("采集项[{_id}]: {_name} 采集任务状态正常").format(
                        _id=single_collector_status.get("collector_config_id", ""),
                        _name=single_collector_status.get("collector_config_name", ""),
                    )
                )
                continue
            # 有失败的情况下, 输出失败的信息
            for single_task_status in single_collector_status["child"]:
                if single_task_status["status"] != CollectStatus.SUCCESS:
                    self.append_error_info(
                        _("[{_id}]({_name}) 采集任务状态异常, 详情: {message}").format(
                            _id=single_task_status.get("container_collector_config_id", ""),
                            _name=single_task_status.get("name", ""),
                            message=single_task_status.get("message", ""),
                        )
                    )

    def check_crd(self) -> None:
        """
        检查CRD
        """
        crd = self.k8s_client.get_crd(self.crd_name)
        if not crd:
            self.append_error_info(_("获取CRD失败"))
            return
        self.append_normal_info(
            _("获取CRD成功, apiVersion: {version}, status: {status}").format(version=crd.api_version, status=crd.status)
        )

    def check_cr(self):
        """检查CR"""
        get_cr_result = self.k8s_client.get_cr()
        if not get_cr_result or not get_cr_result.get("items", []):
            self.append_error_info(_("获取CR列表为空"))
            return
        items = get_cr_result["items"]
        match_items = [i for i in items if i["spec"]["dataId"] == self.collector_config.bk_data_id]
        if not match_items:
            self.append_error_info(
                _("未找到bk_data_id[{bk_data_id}]的CR").format(bk_data_id=self.collector_config.bk_data_id)
            )
            return
        self.append_normal_info(
            _("获取(bk_data_id[{bk_data_id}])的CR成功, 匹配到{cr_cnt}个").format(
                bk_data_id=self.collector_config.bk_data_id, cr_cnt=len(match_items)
            )
        )
        # TODO: 比对CR的spec和collector_config的配置是否一致
        for item in match_items:
            self.append_normal_info(
                _("CR: {name}, uid: {uid}, resourceVersion: {resourceVersion}, spec: {spec}").format(
                    name=item.get("metadata", {}).get("name", ""),
                    uid=item.get("metadata", {}).get("uid", ""),
                    resourceVersion=item.get("metadata", {}).get("resourceVersion", ""),
                    spec=item.get("spec", {}),
                )
            )
            self.cr_list.append(item.get("metadata", {}).get("name", ""))

    def check_config_map(self):
        """检查ConfigMap"""
        config_map = self.k8s_client.get_config_map(config_map_name=self.configmap_name, namespace=self.namespace)
        if not config_map:
            self.append_error_info(_("ConfigMap不存在"))
            return
        # 输出
        self.append_normal_info(
            _("获取ConfigMap成功, uid: {uid}, resourceVersion: {resourceVersion}").format(
                uid=config_map.metadata.uid, resourceVersion=config_map.metadata.resource_version
            )
        )
        bkunifylogbeat_main_config = config_map.data.get(BK_LOG_COLLECTOR_MAIN_CONFIG_NAME, "")
        if not bkunifylogbeat_main_config:
            self.append_error_info(_("ConfigMap中采集器主配置为空"))
            return
        # TODO: 可以考虑输出完整的配置
        bkunifylogbeat_main_config = bkunifylogbeat_main_config.splitlines()
        for line in bkunifylogbeat_main_config:
            if "endpoint:" not in line:
                continue
            # 保存endpoint, 用于后续主配置的比对
            self.endpoint = line.split("endpoint:")[-1].strip()
            self.append_normal_info(_("ConfigMap中采集器主配置中endpoint: {endpoint}").format(endpoint=self.endpoint))
            break

    def check_daemonset(self):
        """检查DaemonSet"""
        daemonset = self.k8s_client.get_daemonset(daemonset_name=self.daemonset_name, namespace=self.namespace)
        if not daemonset:
            self.append_error_info(_("DaemonSet不存在"))
            return
        self.append_normal_info(
            _("获取DaemonSet成功, 期望({desired})|已运行({current})|就绪({ready})").format(
                desired=daemonset.status.desired_number_scheduled,
                current=daemonset.status.current_number_scheduled,
                ready=daemonset.status.number_ready,
            )
        )

    def get_match_pod(self):
        """
        遍历所有pod, 对采集器容器进行子配置文件匹配, 即存在以cr_name为后缀的子配置文件被认定为匹配的pod
        """
        pod_list = self.k8s_client.list_pods(namespace=self.namespace, label_selector=self.daemonset_pod_labels)
        if not pod_list:
            self.append_error_info(_("获取采集器Pod列表为空"))
            return
        for pod in pod_list.items:
            # 先检查pod状态, 如果失败不进入 _check_pod_status
            if not pod.status.container_statuses:
                for condition in pod.status.conditions:
                    if condition.status == "False":
                        self.append_error_info(
                            _("Pod[{pod_name}]状态异常, 原因: {reason}").format(
                                pod_name=pod.metadata.name, reason=condition.message
                            )
                        )
                continue
            self._check_pod_status(pod=pod)
            pod_name = pod.metadata.name
            sub_config_list = self._match_sub_config(pod_name=pod_name)
            match_pod: Pod = Pod(
                name=pod_name,
                node=pod.spec.node_name,
                # node_ip用作后续gse检查
                node_ip=pod.status.host_ip,
                sub_config_list=sub_config_list,
                pod=pod,
            )
            self.pod_list.append(match_pod)

    def check_pod(self):
        """
        检查Pod, 需在get_match_pod之后执行, 因为只检查匹配的pod
        """
        if not self.pod_list:
            self.append_error_info(_("在Pod列表中没有匹配到配置文件"))
            return
        for pod in self.pod_list:
            if not pod.sub_config_list:
                self.append_error_info(_("Pod[{pod_name}]中没有匹配到配置文件").format(pod_name=pod.name))
                continue
            for sub_config in pod.sub_config_list:
                self._check_sub_config(pod_name=pod.name, sub_config=sub_config)

    def _match_sub_config(self, pod_name: str) -> List[str]:
        """
        匹配子配置文件, CR会成为配置文件的后缀, 所以认定Pod中有该后缀的配置文件的才是实际采集的Pod
        """
        config_list = []
        for cr_name in self.cr_list:
            command = ["/bin/ls", f"{self.sub_config_dir} | grep {cr_name}"]
            result = self.k8s_client.exec_command(
                pod_name=pod_name, namespace=self.namespace, command=command, container_name=self.container_name
            )
            if not result:
                continue
            for config_path in result.splitlines():
                if not config_path or "No such file or directory" in config_path:
                    continue
                config_list.append(config_path.splitlines()[0])
        return config_list

    def _check_pod_status(self, pod: v1_pod.V1Pod):
        """
        检查Pod状态, 包括容器状态, 重启次数, 等待原因, 退出原因等
        """
        for container_status in pod.status.container_statuses:
            if container_status.name != self.container_name:
                continue
            if container_status.state.waiting:
                self.append_warning_info(
                    _("Pod[{pod_name}]状态为等待, 原因: {reason}, 原因详情: {message}").format(
                        pod_name=pod.metadata.name,
                        reason=container_status.state.waiting.reason,
                        message=container_status.state.waiting.message,
                    )
                )
                continue
            if container_status.state.terminated:
                self.append_error_info(
                    _("Pod[{pod_name}]状态为退出, 原因: {reason}, 退出代码: {exit_code}").format(
                        pod_name=pod.metadata.name,
                        reason=container_status.state.terminated.reason,
                        exit_code=container_status.state.terminated.exit_code,
                    )
                )
                continue
            if container_status.state.running:
                self.append_normal_info(
                    _("Pod[{pod_name}]状态正常, 容器开始运行时间: {start_time}, 重启次数: {restart_cnt}").format(
                        pod_name=pod.metadata.name,
                        start_time=container_status.state.running.started_at,
                        restart_cnt=container_status.restart_count,
                    )
                )

    def _check_main_config(self, pod_name: str):
        """
        检查主配置内容, 包括endpoint, 子配置路径等
        """
        command = ["/bin/cat", self.main_config_dir]
        result = self.k8s_client.exec_command(
            pod_name=pod_name, namespace=self.namespace, command=command, container_name=self.container_name
        )
        if not result or "No such file or directory" in result:
            self.append_error_info(_("采集器主配置不存在"))
            return
        main_config = yaml.load(result, Loader=yaml.FullLoader)
        # 检查endpoint
        endpoint = main_config.get("output.bkpipe", {}).get("endpoint", "")
        if endpoint != self.endpoint:
            self.append_error_info(
                _("采集器主配置中endpoint: {endpoint}, 与ConfigMap: {configmap_endpoint} 不一致").format(
                    endpoint=endpoint, configmap_endpoint=self.endpoint
                )
            )
        else:
            self.append_normal_info(_("采集器主配置中endpoint: {endpoint}, 与ConfigMap一致").format(endpoint=endpoint))
        # 检查二级配置目录
        multi_config = main_config.get("bkunifylogbeat.multi_config", [])
        if not multi_config:
            self.append_error_info(_("采集器主配置中二级配置目录不存在"))
            return
        sub_path = multi_config[0].get("path", "")
        if sub_path != self.sub_config_dir:
            self.append_error_info(
                _("采集器主配置中二级配置目录: {incorrect_path}不正确, 应该为: {correct_path}").format(
                    incorrect_path=sub_path,
                    correct_path=self.sub_config_dir,
                )
            )

    def _check_sub_config(self, pod_name: str, sub_config: str):
        """
        检查子配置文件中的内容
        """
        command = ["/bin/cat", os.path.join(self.sub_config_dir, sub_config)]
        # 这个时候拿到的以及是一定存在的配置路径了, 所以可以不用判断是否存在
        sub_config_content = self.k8s_client.exec_command(
            pod_name=pod_name, namespace=self.namespace, command=command, container_name=self.container_name
        )
        sub_config_content = yaml.load(sub_config_content, Loader=yaml.FullLoader)
        local_content = sub_config_content.get("local", [])
        if not local_content:
            self.append_error_info(_("子配置文件中local为空"))
            return
        paths = local_content[0].get("paths", [])
        # remove_path_prefix = local_content[0].get("remove_path_prefix", "")
        for path in paths:
            self._check_file_stat(pod_name=pod_name, filepath=path)

    def _check_file_stat(self, pod_name: str, filepath: str) -> None:
        """
        tail 子配置文件中的路径, 检查是否存在, 打印最后的日志内容
        """
        command = ["/bin/stat", filepath]
        contents = self.k8s_client.exec_command(
            pod_name=pod_name, namespace=self.namespace, command=command, container_name=self.container_name
        )
        if "no such file or directory" in contents:
            self.append_error_info(_("子配置文件中路径: {filepath}不存在").format(filepath=filepath))
            return
        mtime, size = "", ""
        for content in contents.splitlines():
            if "Modify:" in content:
                mtime = content.split("Modify:")[-1].strip()
                continue
            if "Size:" in content:
                size = content.split("Size:")[-1].split("Blocks:")[0].strip()
                size = int(size) / 1024 / 1024
                continue
        self.append_normal_info(
            _("子配置文件中路径: {filepath}, 最后修改时间: {mtime}, 文件大小: {size}MB").format(filepath=filepath, mtime=mtime, size=size)
        )

    def filter_target_server(self):
        node_ip_list = [pod.node_ip for pod in self.pod_list]
        params = {
            "page": {
                "start": 0,
                "limit": len(node_ip_list),
            },
            "fields": ["bk_host_id", "bk_cloud_id", "bk_host_innerip", "bk_host_innerip_v6"],
            "host_property_filter": {"condition": "OR", "rules": []},
        }
        for node_ip in node_ip_list:
            params["host_property_filter"]["rules"].append(
                {"field": get_ip_field(node_ip), "operator": "equal", "value": node_ip}
            )
        result = CCApi.list_hosts_without_biz(params)
        if not result or not result["info"]:
            self.append_error_info(_("没有找到对应的主机"))
            return
        if len(node_ip_list) != len(result["info"]):
            self.append_error_info(
                _("找到的主机数量: {found}, 与期望的数量: {expected} 不一致").format(
                    found=len(result["info"]), expected=len(node_ip_list)
                )
            )
            return
        if settings.ENABLE_DHCP:
            self.target_server = {"host_id_list": [host["bk_host_id"] for host in result["info"]]}
        else:
            self.target_server = {
                "ip_list": [
                    {"ip": item["bk_host_innerip"], "bk_cloud_id": item["bk_cloud_id"]} for item in result["info"]
                ]
            }
