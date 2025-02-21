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

API_TIME_SERIES_RESPONSE = {
    "series": [
        {
            "dimensions": {"type": "Normal"},
            "target": "SUM(_index){type=Normal}",
            "metric_field": "_result_",
            "datapoints": [
                [1240, 1739499000000],
                [174, 1739499600000],
            ],
            "alias": "_result_",
            "type": "bar",
            "dimensions_translation": {},
            "unit": "",
        },
        {
            "dimensions": {"type": "Warning"},
            "target": "SUM(_index){dimensions.type=Warning}",
            "metric_field": "_result_",
            "datapoints": [
                [33, 1739499000000],
                [19, 1739499600000],
            ],
            "alias": "_result_",
            "type": "bar",
            "dimensions_translation": {},
            "unit": "",
        },
    ],
    "metrics": [],
    # 用于跳转策略回填
    "query_config": {
        "query_configs": [
            {
                "data_source_label": "bk_apm",
                "data_type_label": "event",
                "table": "k8s_event",
                "filter_dict": {},
                "where": [{"key": "kind", "method": "eq", "value": ["Job"]}],
                "query_string": "*",
                "functions": [],
                "group_by": ["type"],
                "interval": 600,
                "metrics": [{"field": "_index", "method": "SUM", "alias": "a"}],
            }
        ],
        "expression": "a",
        "start_time": 1739499301,
        "end_time": 1739502901,
    },
}

API_LOGS_RESPONSE = {
    "list": [
        {
            # alias - 展示值、value - 原始数据值。
            "time": {"value": 1736927543000, "alias": 1736927543000},
            "type": {"value": "Normal", "alias": "Normal"},
            "source": {"value": "SYSTEM", "type": "icon", "alias": "系统/主机"},
            "event_name": {"value": "oom", "alias": "进程 OOM"},
            "event.content": {
                "value": "oom",
                "alias": "发现主机（0-127.0.0.1）存在进程（chrome）OOM 异常事件",
                "detail": {
                    "target": {
                        "label": "主机",
                        "value": "127.0.0.1",
                        "alias": "直连区域[0] / 127.0.0.1",
                        # 展示成链接
                        "type": "link",
                        "url": "https://bk.monitor.com/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1",
                    },
                    "bk_target_cloud_id": {"label": "管控区域", "value": "0", "alias": "直连区域[0]"},
                    "bk_target_ip": {"label": "IP", "value": "127.0.0.1", "alias": "127.0.0.1"},
                    "process": {"label": "进程", "value": "chrome"},
                    "task_memcg": {
                        "label": "任务（进程）所属的内存 cgroup",
                        "value": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                    },
                },
            },
            "target": {
                "value": "127.0.0.1",
                "alias": "127.0.0.1",
                "url": "https://bk.monitor.com/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1",
            },
            "origin_data": {
                "time": 1737281113,
                "dimensions.ip": "127.0.0.1",
                "dimensions.task_memcg": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                "dimensions.message": "系统发生OOM异常事件",
                "dimensions.process": "chrome",
                "dimensions.constraint": "CONSTRAINT_MEMCG",
                "dimensions.task": "chrome",
                "dimensions.bk_biz_id": "11",
                "dimensions.oom_memcg": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                "dimensions.bk_target_cloud_id": "0",
                "dimensions.bk_target_ip": "127.0.0.1",
                "dimensions.bk_cloud_id": "0",
                "event.content": "oom",
                "event.count": 1,
                "target": "0:127.0.0.1",
                "event_name": "OOM",
            },
        },
        {
            "time": {"value": 1736927543000, "alias": 1736927543000},
            "source": {"value": "BCS", "alias": "Kubernetes/BCS"},
            "event_name": {"value": "FailedMount", "alias": "卷挂载失效（FailedMount）"},
            "event.content": {
                "value": "MountVolume.SetUp failed for volume bk-log-main-config: "
                "failed to sync configmap cache: timed out waiting for the condition",
                "alias": "MountVolume.SetUp failed for volume bk-log-main-config: "
                "failed to sync configmap cache: timed out waiting for the condition",
                "detail": {
                    "bcs_cluster_id": {
                        "label": "集群",
                        "value": "BCS-K8S-90001",
                        "alias": "[共享集群] 蓝鲸公共-广州(BCS-K8S-90001)",
                        "type": "link",
                        # 带集群 ID 跳转到新版容器监控页面
                        "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001",
                    },
                    "namespace": {
                        "label": "NameSpace",
                        "value": "127.0.0.1",
                        "alias": "kube-system",
                        # 带 namespace & 集群 ID 跳转到新版容器监控页面
                        "type": "link",
                        "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",
                    },
                    "name": {
                        "label": "工作负载",
                        "value": "bk-log-collector-fx97q",
                        "alias": "Pod / bk-log-collector-fx97q",
                    },
                    "event.content": {
                        "label": "事件内容",
                        "value": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                        "alias": "MountVolume.SetUp failed for volume bk-log-main-config: "
                        "failed to sync configmap cache: timed out waiting for the condition",
                    },
                },
            },
            "target": {
                "value": "127.0.0.1",
                "alias": "BCS-K8S-90001 / kube-system / Pod / bk-log-collector-fx97q",
                # 带 namespace & bcs_cluster_id & workload_type & workload_name 跳转到新版容器监控页面
                "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",
            },
            "origin_data": {
                # 前端在展示原始数据（JSON）时需要把 dimensions、event 这一层解成结构化的数据。
                "dimensions.apiVersion": "v1",
                "dimensions.bcs_cluster_id": "BCS-K8S-90001",
                "dimensions.bk_biz_id": "7",
                "dimensions.host": "127.0.0.1",
                "dimensions.kind": "Pod",
                "dimensions.name": "bk-log-collector-fx97q",
                "dimensions.namespace": "kube-system",
                "dimensions.type": "Warning",
                "dimensions.uid": "bbeea166-7b09-487a-bed5-66756c25b7b5",
                "event.content": "MountVolume.SetUp failed for volume bk-log-main-config: "
                "failed to sync configmap cache: timed out waiting for the condition",
                "event.count": 1,
                "event_name": "FailedMount",
                "target": "kubelet",
                "time": "1736927543000",
            },
        },
    ]
}

API_VIEW_CONFIG_RESPONSE = {
    # 字段类型：
    # 缺省 - 字符串
    # icon - 带 icon
    # descriptions - hover 弹出详情
    # link：超链接
    # attach：附加在行边框，用于事件级别展示
    "display_fields": [
        {"name": "time", "alias": "数据上报时间"},
        {"name": "type", "alias": "事件级别", "type": "attach"},
        # APM 比事件检索页面多一个 source，后台返回时区分。
        {"name": "source", "alias": "事件来源", "type": "icon"},
        {"name": "event_name", "alias": "事件名"},
        {"name": "event.content", "alias": "内容", "type": "descriptions"},
        {"name": "target", "alias": "目标", "type": "link"},
    ],
    # 关联实体
    "entities": [
        # 规则越靠前解析优先级越高。
        # 跳转到容器监控（仅当存在 bcs_cluster_id），默认跳转到新版。
        # 注意：bcs_cluster_id 存在的情况下，host 形式是 "node-127-0-0-1"，此时跳转到旧版容器监控页面的 Node
        {
            "type": "k8s",
            "alias": "容器",
            "fields": ["container_id", "namespace", "bcs_cluster_id", "host"],
            # 原始数据存在这个字段，本规则才生效
            "dependent_fields": ["bcs_cluster_id"],
        },
        # 跳转到主机监控
        {"type": "ip", "alias": "主机", "fields": ["host", "bk_target_ip", "ip", "serverip", "bk_host_id"]},
    ],
    "fields": [
        {
            "name": "time",
            "alias": "数据上报时间（time）",
            # 字段类型：date、integer、keyword（string）、text
            "type": "date",
            # 为 true 时需要拉取候选值、启用字段分析功能
            "is_option_enabled": False,
            "supported_operations": [
                {"alias": "=", "value": "eq"},
                {"alias": "!=", "value": "ne"},
            ],
        },
        {
            "name": "event_name",
            "alias": "事件名（event_name）",
            "type": "keyword",
            "is_option_enabled": True,
            "supported_operations": [
                {"alias": "=", "value": "eq"},
                {"alias": "!=", "value": "ne"},
                {"alias": "包含", "value": "include"},
                {"alias": "不包含", "value": "exclude"},
            ],
        },
        {
            "name": "event.content",
            "alias": "内容（event.content）",
            "type": "text",
            "is_option_enabled": False,
            "supported_operations": [
                # options：额外的配置，用于过滤操作增加配置项。
                {"alias": "包含", "value": "include", "options": {"label": "使用通配符", "name": "is_wildcard"}},
                {"alias": "不包含", "value": "exclude", "options": {"label": "使用通配符", "name": "is_wildcard"}},
            ],
        },
        {
            "name": "target",
            "alias": "目标（target）",
            "type": "keyword",
            "is_option_enabled": True,
            "supported_operations": [
                {"alias": "=", "value": "eq"},
                {"alias": "!=", "value": "ne"},
                {"alias": "包含", "value": "include"},
                {"alias": "不包含", "value": "exclude"},
            ],
        },
        # dimensions 下全部的维度都是 keyword
        {
            # source 维度在过滤、维度值获取需要在「APM」侧特殊处理，例如系统事件是没有 source 字段的。
            "name": "source",
            "alias": "事件来源（source）",
            "type": "keyword",
            # 是否为维度字段。
            # 语句查询模式，需要补成 dimensions.{name} 去做查询。
            # 为什么不直接用 dimensions.{name}？考虑到事件检索在此之前的 where 都是没有 dimensions 前缀，保持和之前一致。
            "is_dimensions": True,
            "is_option_enabled": True,
            "supported_operations": [
                {"alias": "=", "value": "eq"},
                {"alias": "!=", "value": "ne"},
                {"alias": "包含", "value": "include"},
                {"alias": "不包含", "value": "exclude"},
            ],
        },
        {
            "name": "bcs_cluster_id",
            "alias": "集群 ID（bcs_cluster_id）",
            "type": "keyword",
            "is_dimensions": True,
            "is_option_enabled": True,
            "supported_operations": [
                {"alias": "=", "value": "eq"},
                {"alias": "!=", "value": "ne"},
                {"alias": "包含", "value": "include"},
                {"alias": "不包含", "value": "exclude"},
            ],
        },
    ],
}

API_TOPK_RESPONSE = [
    {
        "distinct_count": 3,
        "field": "source",
        "list": [
            {"value": "HOST", "alias": "系统/主机", "count": 5, "proportions": 50},
            {"value": "CICD", "alias": "CICD/蓝盾", "count": 3, "proportions": 30},
            {"value": "BCS", "alias": "Kubernetes/BCS", "count": 2, "proportions": 20},
        ],
    },
    {
        "distinct_count": 1,
        "field": "bcs_cluster_id",
        "list": [{"value": "BCS-K8S-90001", "alias": "BCS-K8S-90001", "count": 20, "proportions": 100}],
    },
]

API_TOTAL_RESPONSE = {"total": 100}
