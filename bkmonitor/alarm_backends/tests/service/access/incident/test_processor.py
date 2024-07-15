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

import pytest
from mock import Mock, patch

from alarm_backends.service.access.incident.processor import AccessIncidentProcess


@pytest.fixture(scope="function", autouse=False)
def patch_rabbitmq_client():
    mock_obj = Mock()
    mock_obj.start_consuming.return_value = None
    with patch(target="alarm_backends.service.access.incident.processor.RabbitMQClient", new=mock_obj):
        yield


@pytest.fixture(scope="function", autouse=False)
def patch_snapshot_api():
    mock_obj = Mock()
    mock_obj.bkdata.get_incident_snapshot.return_value = json.loads(
        '''{
        "snapshot_id": "fpp:3524245362402428931_1",
        "timestamp": null,
        "alerts": 14,
        "bk_biz_id": 2,
        "incident_alerts": [
            {
                "id": "171151054379656",
                "strategy_id": "63979",
                "entity_id": "0#0.0.0.0"
            },
            {
                "id": "171151054379650",
                "strategy_id": "25",
                "entity_id": "BCS-K8S-00000#k8s-mainquest-trunk#uid-0"
            },
            {
                "id": "171151007779600",
                "strategy_id": "25",
                "entity_id": "BCS-K8S-00000#k8s-ngr-trunk#session-rrcxk"
            },
            {
                "id": "171150978579566",
                "strategy_id": "2",
                "entity_id": "BCS-K8S-00000#k8s-markqian-publish#home-0"
            },
            {
                "id": "171150895579436",
                "strategy_id": "27",
                "entity_id": "BCS-K8S-00000#k8s-devqas-test#home-0"
            },
            {
                "id": "171150885679397",
                "strategy_id": "19",
                "entity_id": "BCS-K8S-00000#k8s-markqian-publish#statistic-0"
            },
            {
                "id": "171150893779417",
                "strategy_id": "40",
                "entity_id": "BCS-K8S-00000#k8s-pvp-merge#role-0"
            },
            {
                "id": "171150885479387",
                "strategy_id": "62839",
                "entity_id": "BCS-K8S-00000#k8s-release-sony#note-0"
            },
            {
                "id": "171151000879594",
                "strategy_id": "62849",
                "entity_id": "BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#room-0"
            },
            {
                "id": "171145509178145",
                "strategy_id": "25",
                "entity_id": "BCS-K8S-00000#k8s-idc-br#uid-0"
            },
            {
                "id": "171133649877446",
                "strategy_id": "62841",
                "entity_id": "BCS-K8S-00000#k8s-engine-publish#gate-cm8zd"
            },
            {
                "id": "171150979579592",
                "strategy_id": "25",
                "entity_id": "BCS-K8S-00000#k8s-pvp-merge#uid-0"
            },
            {
                "id": "171142072177725",
                "strategy_id": "62841",
                "entity_id": "BCS-K8S-00000#k8s-yueleiayue#idip-64ljv"
            },
            {
                "id": "171094729874469",
                "strategy_id": "18",
                "entity_id": "BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#mail-0"
            }
        ],
        "incident_name": "故障聚集在('BkNodeHost', '0#0.0.0.0')，影响3个BcsPod，大部分为死机/重启",
        "incident_name_template": {
            "template": "故障聚集在{0}，影响{1}",
            "elements": [
                [
                    "BkNodeHost",
                    "0#0.0.0.0"
                ],
                "3个BcsPod，大部分为死机/重启"
            ],
            "affected_types": [
                [
                    "3个BcsPod，大部分为死机/重启",
                    [
                        "BCS-K8S-00000#k8s-idc-br#uid-0",
                        "BCS-K8S-00000#k8s-yueleiayue#idip-64ljv",
                        "BCS-K8S-00000#k8s-release-sony#note-0"
                    ]
                ]
            ]
        },
        "incident_root": [
            "BkNodeHost",
            "0#0.0.0.0"
        ],
        "incident_label": [
            "cpu",
            "pod",
            "cputhrottlinghigh",
            "kube",
            "\\u5f53\\u524d\\u503c"
        ],
        "product_hierarchy_category": {
            "service": {
                "category_id": 0,
                "category_name": "service",
                "category_alias": "服务"
            },
            "host_platform": {
                "category_id": 1,
                "category_name": "host_platform",
                "category_alias": "主机/云平台"
            },
            "data_center": {
                "category_id": 2,
                "category_name": "data_center",
                "category_alias": "数据中心"
            }
        },
        "product_hierarchy_rank": {
            "service_module": {
                "rank_id": 0,
                "rank_name": "service_module",
                "rank_alias": "服务模块",
                "rank_category": "service"
            },
            "k8s": {
                "rank_id": 1,
                "rank_name": "k8s",
                "rank_alias": "K8S",
                "rank_category": "host_platform"
            },
            "operate_system": {
                "rank_id": 2,
                "rank_name": "operate_system",
                "rank_alias": "操作系统",
                "rank_category": "host_platform"
            },
            "rack": {
                "rank_id": 3,
                "rank_name": "rack",
                "rank_alias": "Rack",
                "rank_category": "data_center"
            },
            "idc_unit": {
                "rank_id": 4,
                "rank_name": "idc_unit",
                "rank_alias": "IDC Unit",
                "rank_category": "data_center"
            },
            "idc": {
                "rank_id": 5,
                "rank_name": "idc",
                "rank_alias": "IDC",
                "rank_category": "data_center"
            }
        },
        "incident_propagation_graph": {
            "entities": [
                {
                    "entity_id": "BCS-K8S-00000#k8s-idc-br#uid-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-idc-br:uid-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": true,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": "死机/重启",
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-idc-br",
                        "pod_name": "uid-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-yueleiayue#idip-64ljv",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-yueleiayue:idip-64ljv",
                    "entity_type": "BcsPod",
                    "is_anomaly": true,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": "死机/重启",
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-yueleiayue",
                        "pod_name": "idip-64ljv"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-release-sony#note-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-release-sony:note-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": true,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": "死机/重启",
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-release-sony",
                        "pod_name": "note-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-pvp-merge#uid-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-pvp-merge:uid-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-pvp-merge",
                        "pod_name": "uid-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-mainquest-trunk#uid-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-mainquest-trunk:uid-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-mainquest-trunk",
                        "pod_name": "uid-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-ngr-trunk#session-rrcxk",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-ngr-trunk:session-rrcxk",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-ngr-trunk",
                        "pod_name": "session-rrcxk"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-markqian-publish#home-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-markqian-publish:home-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-markqian-publish",
                        "pod_name": "home-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-devqas-test#home-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-devqas-test:home-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-devqas-test",
                        "pod_name": "home-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-markqian-publish#statistic-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-markqian-publish:statistic-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-markqian-publish",
                        "pod_name": "statistic-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-pvp-merge#role-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-pvp-merge:role-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-pvp-merge",
                        "pod_name": "role-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#room-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-qiuqiuwu-verify-publish:room-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-qiuqiuwu-verify-publish",
                        "pod_name": "room-0"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-engine-publish#gate-cm8zd",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-engine-publish:gate-cm8zd",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-engine-publish",
                        "pod_name": "gate-cm8zd"
                    }
                },
                {
                    "entity_id": "BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#mail-0",
                    "entity_name": "BcsPod:BCS-K8S-00000:k8s-qiuqiuwu-verify-publish:mail-0",
                    "entity_type": "BcsPod",
                    "is_anomaly": false,
                    "anomaly_score": 0.3333333333333333,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BcsPod",
                        "cluster_id": "BCS-K8S-00000",
                        "namespace": "k8s-qiuqiuwu-verify-publish",
                        "pod_name": "mail-0"
                    }
                },
                {
                    "entity_id": "0#0.0.0.0",
                    "entity_name": "BkNodeHost:0:0.0.0.0",
                    "entity_type": "BkNodeHost",
                    "is_anomaly": true,
                    "anomaly_score": 0.4,
                    "anomaly_type": "死机/重启",
                    "is_root": true,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BkNodeHost",
                        "bk_cloud_id": "0",
                        "inner_ip": "0.0.0.0"
                    }
                },
                {
                    "entity_id": "0#0.0.0.1",
                    "entity_name": "BkNodeHost:0:0.0.0.1",
                    "entity_type": "BkNodeHost",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BkNodeHost",
                        "bk_cloud_id": "0",
                        "inner_ip": "0.0.0.1"
                    }
                },
                {
                    "entity_id": "0#0.0.0.2",
                    "entity_name": "BkNodeHost:0:0.0.0.2",
                    "entity_type": "BkNodeHost",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BkNodeHost",
                        "bk_cloud_id": "0",
                        "inner_ip": "0.0.0.2"
                    }
                },
                {
                    "entity_id": "0#0.0.0.3",
                    "entity_name": "BkNodeHost:0:0.0.0.3",
                    "entity_type": "BkNodeHost",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "k8s",
                    "dimensions": {
                        "node_type": "BkNodeHost",
                        "bk_cloud_id": "0",
                        "inner_ip": "0.0.0.3"
                    }
                },
                {
                    "entity_id": "rack#0",
                    "entity_name": "Rack:0",
                    "entity_type": "Rack",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "rack",
                    "dimensions": {
                        "node_type": "Rack",
                        "rack_id": "0"
                    }
                },
                {
                    "entity_id": "rack#1",
                    "entity_name": "Rack:1",
                    "entity_type": "Rack",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "rack",
                    "dimensions": {
                        "node_type": "Rack",
                        "rack_id": "1"
                    }
                },
                {
                    "entity_id": "rack#2",
                    "entity_name": "Rack:2",
                    "entity_type": "Rack",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "rack",
                    "dimensions": {
                        "node_type": "Rack",
                        "rack_id": "2"
                    }
                },
                {
                    "entity_id": "rack#3",
                    "entity_name": "Rack:3",
                    "entity_type": "Rack",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "rack",
                    "dimensions": {
                        "node_type": "Rack",
                        "rack_id": "3"
                    }
                },
                {
                    "entity_id": "idc_unit#0",
                    "entity_name": "IdcUnit:idc_unit0",
                    "entity_type": "IdcUnit",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "idc_unit",
                    "dimensions": {
                        "node_type": "IdcUnit",
                        "idc_unit_id": "idc_unit0"
                    }
                },
                {
                    "entity_id": "idc_unit#1",
                    "entity_name": "IdcUnit:idc_unit1",
                    "entity_type": "IdcUnit",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "idc_unit",
                    "dimensions": {
                        "node_type": "IdcUnit",
                        "idc_unit_id": "idc_unit1"
                    }
                },
                {
                    "entity_id": "idc#0",
                    "entity_name": "Idc:idc0",
                    "entity_type": "Idc",
                    "is_anomaly": false,
                    "anomaly_score": 0.4,
                    "anomaly_type": null,
                    "is_root": false,
                    "rank_name": "idc",
                    "dimensions": {
                        "node_type": "Idc",
                        "idc_id": "idc0"
                    }
                }
            ],
            "edges": [
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-idc-br#uid-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-yueleiayue#idip-64ljv"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-release-sony#note-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.1",
                    "target_id": "BCS-K8S-00000#k8s-pvp-merge#uid-0"
                },
                {
                    "source_type": "Rack",
                    "target_type": "BkNodeHost",
                    "source_id": "rack#0",
                    "target_id": "0#0.0.0.0"
                },
                {
                    "source_type": "Rack",
                    "target_type": "BkNodeHost",
                    "source_id": "rack#0",
                    "target_id": "0#0.0.0.1"
                },
                {
                    "source_type": "Rack",
                    "target_type": "BkNodeHost",
                    "source_id": "rack#1",
                    "target_id": "0#0.0.0.2"
                },
                {
                    "source_type": "Rack",
                    "target_type": "BkNodeHost",
                    "source_id": "rack#1",
                    "target_id": "0#0.0.0.3"
                },
                {
                    "source_type": "IdcUnit",
                    "target_type": "Rack",
                    "source_id": "idc_unit#0",
                    "target_id": "rack#0"
                },
                {
                    "source_type": "IdcUnit",
                    "target_type": "Rack",
                    "source_id": "idc_unit#0",
                    "target_id": "rack#1"
                },
                {
                    "source_type": "IdcUnit",
                    "target_type": "Rack",
                    "source_id": "idc_unit#1",
                    "target_id": "rack#2"
                },
                {
                    "source_type": "IdcUnit",
                    "target_type": "Rack",
                    "source_id": "idc_unit#1",
                    "target_id": "rack#3"
                },
                {
                    "source_type": "Idc",
                    "target_type": "IdcUnit",
                    "source_id": "idc#0",
                    "target_id": "idc_unit#0"
                },
                {
                    "source_type": "Idc",
                    "target_type": "IdcUnit",
                    "source_id": "idc#0",
                    "target_id": "idc_unit#1"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-mainquest-trunk#uid-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.1",
                    "target_id": "BCS-K8S-00000#k8s-ngr-trunk#session-rrcxk"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-markqian-publish#home-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.1",
                    "target_id": "BCS-K8S-00000#k8s-devqas-test#home-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-markqian-publish#statistic-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.1",
                    "target_id": "BCS-K8S-00000#k8s-pvp-merge#role-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#room-0"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.1",
                    "target_id": "BCS-K8S-00000#k8s-engine-publish#gate-cm8zd"
                },
                {
                    "source_type": "BkNodeHost",
                    "target_type": "BcsPod",
                    "source_id": "0#0.0.0.0",
                    "target_id": "BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#mail-0"
                }
            ]
        },
        "one_hop_neighbors": [
            "BcsPod##BCS-K8S-00000#k8s-release-sony#note-0",
            "BcsPod##BCS-K8S-00000#k8s-sice-publish#note-0",
            "BcsCluster##BCS-K8S-00000",
            "BcsPod##BCS-K8S-00000#k8s-ngr-gitops-trunk#aoi-0",
            "BcsPod##BCS-K8S-00000#kube-system#kube-proxy-t8w4x",
            "BcsPod##BCS-K8S-00000#deepflow#deepflow-agent-9wkfq",
            "BcsPod##BCS-K8S-00000#kube-system#bk-log-collector-d25zz",
            "BcsPod##BCS-K8S-00000#k8s-oriding-trunk#gate-n4k7l",
            "BcsPod##BCS-K8S-00000#k8s-idc-br#mail-0",
            "BcsPod##BCS-K8S-00000#k8s-idc-br#uid-0",
            "BcsPod##BCS-K8S-00000#kube-system#ip-masq-agent-6xtsn",
            "BcsPod##BCS-K8S-00000#k8s-idc-dev-br#statistic-0",
            "BCS-K8S-00000#k8s-pvp-merge#uid-0",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#aoi-0",
            "BcsPod##BCS-K8S-00000#k8s-ds-profiler#uid-0",
            "BcsPod##BCS-K8S-00000#k8s-oriding-trunk#team-0",
            "BcsPod##BCS-K8S-00000#k8s-devqas-test#friend-0",
            "BcsPod##BCS-K8S-00000#kube-system#tke-cni-agent-gtgb8",
            "BcsPod##BCS-K8S-00000#k8s-markqian-publish#mail-0",
            "BcsPod##BCS-K8S-00000#k8s-release-sony#statistic-0",
            "BcsPod##BCS-K8S-00000#k8s-ai-agent#statistic-0",
            "BcsPod##BCS-K8S-00000#k8s-sice-publish#query-0",
            "BcsPod##BCS-K8S-00000#kube-system#tke-monitor-agent-q2gcp",
            "BcsPod##BCS-K8S-00000#k8s-engine-publish#room-0",
            "BcsPod##BCS-K8S-00000#k8s-idc-br#gate-d4jvj",
            "BcsPod##BCS-K8S-00000#k8s-ngr-publish#aoi-0",
            "BcsPod##BCS-K8S-00000#k8s-yueleiayue#note-0",
            "BcsPod##BCS-K8S-00000#kube-system#csi-cbs-node-bpzcl",
            "BcsPod##BCS-K8S-00000#bkmonitor-operator#bkm-prometheus-node-exporter-774nb",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#gate-2zk2g",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#room-0",
            "BcsPod##BCS-K8S-00000#bkmonitor-operator#bkm-daemonset-worker-sl6xk",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#session-xctqz",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#friend-0",
            "BcsPod##BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#team-0",
            "BcsPod##BCS-K8S-00000#kube-system#tke-log-agent-sbx6m",
            "BcsPod##BCS-K8S-00000#k8s-ngr-gitops-trunk#session-k45jr",
            "BcsPod##BCS-K8S-00000#k8s-ds-profiler#chat-0",
            "BcsPod##BCS-K8S-00000#k8s-yueleiayue#idip-64ljv",
            "BcsPod##BCS-K8S-00000#k8s-pvp-ce#uid-0",
            "BcsPod##BCS-K8S-00000#k8s-andrewge-trunk#mail-0",
            "BcsPod##BCS-K8S-00000#k8s-engine-trunk#mail-0",
            "BcsPod##BCS-K8S-00000#k8s-ngr-trunkdev-smoke#note-0",
            "BcsPod##BCS-K8S-00000#k8s-engine-publish#team-0",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#role-0",
            "BcsPod##BCS-K8S-00000#kube-system#tke-bridge-agent-6s29n",
            "BcsPod##BCS-K8S-00000#bcs-system#log-pull-bs6lb",
            "BcsPod##BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#session-lwxgd",
            "BcsPod##BCS-K8S-00000#k8s-ngr-publish#role-0",
            "BcsPod##BCS-K8S-00000#k8s-oriding-trunk#mail-0",
            "BcsPod##BCS-K8S-00000#k8s-yunyou-publish#home-0",
            "BcsPod##BCS-K8S-00000#k8s-engine-trunk#im-w8jg2",
            "BcsPod##BCS-K8S-00000#k8s-ngr-trunkdev-smoke#team-0",
            "BcsPod##BCS-K8S-00000#bcs-system#bcs-hook-operator-v2mtw",
            "BcsPod##BCS-K8S-00000#k8s-yueleiayue#chat-0",
            "BcsPod##BCS-K8S-00000#k8s-pvp-merge#statistic-0",
            "BcsPod##BCS-K8S-00000#k8s-qiuqiuwu-verify-publish#gate-bdbql"
        ],
        "anomaly_time": null,
        "graph_snapshot_id": null
    }'''
    )
    with patch(target="alarm_backends.service.access.incident.processor.api", new=mock_obj):
        yield


class TestIncidentAccessProcesor(object):
    @pytest.mark.usefixtures("patch_rabbitmq_client")
    @pytest.mark.usefixtures("patch_snapshot_api")
    def test_processor(self):
        processor = AccessIncidentProcess("xx", "queue1")

        create_sync_info = json.loads(
            '''{
            "sync_type": "create",
            "sync_time": 1720061828,
            "incident_id": 16235,
            "incident_info": {
                "incident_name": "故障聚集在('BkNodeHost', '0#xx.xx.xx.xx')，影响3个BcsPod，大部分为死机/重启",
                "incident_reason": "我是故障原因占位",
                "status": "abnormal",
                "level": "ERROR",
                "labels": ["游戏", "异常", "时序"],
                "create_time": null,
                "update_time": null,
                "begin_time": null,
                "assignees": ["admin"],
                "handlers": ["admin"],
                "bk_biz_id": 2
            },
            "fpp_snapshot_id": "fpp:3524245362402428931_1",
            "scope": {
                "bk_biz_ids": [2],
                "alerts": [171151054379656, 171151054379650],
                "events": []
            }
        }
        '''
        )
        processor.handle_sync_info(create_sync_info)

        update_sync_info = json.loads(
            '''{
            "sync_type": "update",
            "sync_time": 1720061828,
            "incident_id": 16235,
            "incident_info": {
                "incident_name": "故障聚集在('BkNodeHost', '0#xx.xx.xx.xx')，影响3个BcsPod，大部分为死机/重启",
                "incident_reason": "我是故障原因占位",
                "status": "recovering",
                "level": "ERROR",
                "labels": ["游戏", "异常", "时序"],
                "create_time": 1720061828,
                "update_time": 1720061828,
                "begin_time": 1720061828,
                "assignees": ["admin"],
                "handlers": ["admin"],
                "bk_biz_id": 2
            },
            "fpp_snapshot_id": "fpp:3524245362402428931_1",
            "scope": {
                "bk_biz_ids": [2],
                "alerts": [171151054379656, 171151054379650],
                "events": []
            }
        }
        '''
        )

        processor.handle_sync_info(update_sync_info)
