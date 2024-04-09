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
from alarm_backends.service.new_report.handler.clustering import ClusteringReportHandler
from alarm_backends.service.new_report.handler.dashboard import DashboardReportHandler
from alarm_backends.service.new_report.handler.scene import SceneReportHandler
from bkmonitor.models.report import ScenarioEnum

SUPPORTED_SCENARIO = {
    ScenarioEnum.CLUSTERING.value: ClusteringReportHandler,
    ScenarioEnum.DASHBOARD.value: DashboardReportHandler,
    ScenarioEnum.SCENE.value: SceneReportHandler,
}


class ReportFactory(object):
    @classmethod
    def get_handler(cls, report):
        report_handler_cls = SUPPORTED_SCENARIO[report.scenario]
        return report_handler_cls(report)
