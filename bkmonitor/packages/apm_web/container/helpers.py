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
from apm_web.topo.handle.relation.define import SourceK8sPod, SourceService
from apm_web.topo.handle.relation.query import RelationQ


class ContainerHelper:
    @classmethod
    def list_pod_relations(cls, bk_biz_id, app_name, service_name, start_time, end_time):
        """获取服务的 Pod 关联信息"""
        return RelationQ.query(
            RelationQ.generate_q(
                bk_biz_id=bk_biz_id,
                source_info=SourceService(
                    apm_application_name=app_name,
                    apm_service_name=service_name,
                ),
                target_type=SourceK8sPod,
                start_time=start_time,
                end_time=end_time,
            )
        )
