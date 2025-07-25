"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from bkmonitor.iam.drf import ViewBusinessPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class IncidentViewSet(ResourceViewSet):
    query_post_actions = []

    def get_permissions(self):
        if self.action in ["incident_overview"]:
            return []

        # 业务开启故障分析才有权限校验，未开启不需要校验，因为查不出数据
        if self.request.biz_id in settings.AIOPS_INCIDENT_BIZ_WHITE_LIST:
            return [ViewBusinessPermission()]
        return []

    resource_routes = [
        # 故障列表接口
        ResourceRoute("POST", resource.incident.incident_list, endpoint="incident_list"),
        # 故障导出接口
        ResourceRoute("POST", resource.incident.export_incident, endpoint="export_incident"),
        # 故障汇总统计接口
        ResourceRoute("POST", resource.incident.incident_overview, endpoint="incident_overview"),
        # 获取故障维度topn频率值
        ResourceRoute("POST", resource.incident.incident_top_n, endpoint="top_n"),
        # 验证搜索的值是否符合规范
        ResourceRoute("POST", resource.incident.incident_validate_query_string, endpoint="validate_query_string"),
        # 故障详情接口
        ResourceRoute("GET", resource.incident.incident_detail, endpoint="incident_detail"),
        # 故障拓扑图接口
        ResourceRoute("POST", resource.incident.incident_topology, endpoint="incident_topology"),
        # 故障拓扑图聚合目录接口
        ResourceRoute("GET", resource.incident.incident_topology_menu, endpoint="incident_topology_menu"),
        # 故障拓扑图上下游接口
        ResourceRoute("GET", resource.incident.incident_topology_upstream, endpoint="incident_topology_upstream"),
        # 故障时序图接口
        ResourceRoute("GET", resource.incident.incident_time_line, endpoint="incident_time_line"),
        # 故障告警对象接口
        ResourceRoute("POST", resource.incident.incident_alert_aggregate, endpoint="incident_alert_aggregate"),
        # 故障告警处理人接口
        ResourceRoute("GET", resource.incident.incident_handlers, endpoint="incident_handlers"),
        # 故障流转列表接口
        ResourceRoute("GET", resource.incident.incident_operations, endpoint="incident_operations"),
        # 故障流转记录接口
        ResourceRoute("POST", resource.incident.incident_record_operation, endpoint="incident_record_operation"),
        # 故障流转类型接口
        ResourceRoute("GET", resource.incident.incident_operation_types, endpoint="incident_operation_types"),
        # 编辑故障
        ResourceRoute("POST", resource.incident.edit_incident, endpoint="edit_incident"),
        # 反馈故障根因
        ResourceRoute("POST", resource.incident.feedback_incident_root, endpoint="feedback_incident_root"),
        # 故障告警明细接口
        ResourceRoute("POST", resource.incident.incident_alert_list, endpoint="incident_alert_list"),
        # 故障告警视图接口
        ResourceRoute("POST", resource.incident.incident_alert_view, endpoint="incident_alert_view"),
        # 告警所属故障接口
        ResourceRoute("GET", resource.incident.alert_incident_detail, endpoint="alert_incident_detail"),
        # 故障页结果状态概览
        ResourceRoute("GET", resource.incident.incident_results, endpoint="incident_results"),
        # 故障诊断页结果接口
        ResourceRoute("POST", resource.incident.incident_diagnosis, endpoint="incident_diagnosis"),
    ]
