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
from api.cmdb.define import Host, Module, ServiceInstance, TopoTree

TOPO_TREE = TopoTree(
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
                        "child": [],
                    },
                    {
                        "bk_inst_id": 6,
                        "bk_inst_name": "mysql",
                        "bk_obj_id": "module",
                        "bk_obj_name": "module",
                        "child": [],
                    },
                ],
            }
        ],
    }
)


ALL_HOSTS = [
    Host(
        bk_host_innerip="10.0.0.1", bk_cloud_id=1, bk_host_id=1, bk_biz_id=2, bk_module_ids=[5, 6], bk_state="运营中[无告警]"
    ),
    Host(bk_host_innerip="10.0.0.2", bk_cloud_id=2, bk_host_id=2, bk_biz_id=2),
    Host(bk_host_innerip="10.0.0.3", bk_cloud_id=3, bk_host_id=3, bk_biz_id=3),
    Host(bk_host_innerip="10.0.0.4", bk_cloud_id=4, bk_host_id=4, bk_biz_id=3),
    Host(bk_host_innerip="10.0.0.5", bk_cloud_id=5, bk_host_id=5, bk_biz_id=4),
    Host(bk_host_innerip="10.0.0.6", bk_cloud_id=6, bk_host_id=6, bk_biz_id=4),
]

ALL_MODULES = [
    Module(bk_module_id=1, bk_module_name="m1", bk_biz_id=2),
    Module(bk_module_id=2, bk_module_name="m2", bk_biz_id=2),
    Module(bk_module_id=3, bk_module_name="m3", bk_biz_id=3),
    Module(bk_module_id=4, bk_module_name="m4", bk_biz_id=3),
]


ALL_SERVICE_INSTANCES = [
    ServiceInstance(service_instance_id=1, name="s1", bk_host_id=1, bk_module_id=5, bk_biz_id=2),
    ServiceInstance(service_instance_id=2, name="s2", bk_host_id=2, bk_module_id=2, bk_biz_id=2),
    ServiceInstance(service_instance_id=3, name="s3", bk_host_id=3, bk_module_id=3, bk_biz_id=3),
    ServiceInstance(service_instance_id=4, name="s4", bk_host_id=4, bk_module_id=4, bk_biz_id=3),
]
