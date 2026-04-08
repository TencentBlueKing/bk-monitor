"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy

from apps.log_search.models import Scenario
from apps.log_unifyquery.builder.tail import (
    CreateSearchTailBodyCustomField,
    CreateSearchTailBodyScenarioBkData,
    CreateSearchTailBodyScenarioLog,
)
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnifyQueryTailHandler(UnifyQueryHandler):
    def __init__(self, params):
        super().__init__(params)
        # 上下文检索参数
        self.gseindex: int = params.get("gseindex")
        self.gseIndex: int = params.get("gseIndex")  # pylint: disable=invalid-name
        self.serverIp: str = params.get("serverIp")  # pylint: disable=invalid-name
        self.ip: str = params.get("ip", "undefined")
        self.path: str = params.get("path", "")
        self.container_id: str = params.get("container_id", None) or params.get("__ext.container_id", None)
        self.logfile: str = params.get("logfile", None)
        self._iteration_idx: str = params.get("_iteration_idx", None)
        self.iterationIdx: str = params.get("iterationIdx", None)  # pylint: disable=invalid-name
        self.iterationIndex: str = params.get("iterationIndex", None)  # pylint: disable=invalid-name
        self.dtEventTimeStamp = params.get("dtEventTimeStamp", None)  # pylint: disable=invalid-name
        self.bk_host_id = params.get("bk_host_id", None)  # pylint: disable=invalid-name

        # 上下文初始化标记
        self.zero: bool = params.get("zero", False)

        # 透传start
        self.start: int = params.get("begin", 0)

        # 透传size
        self.size: int = params.get("size", 30)

    def search(self, *args):
        base_params = copy.deepcopy(self.base_dict)
        body: dict = {}
        target_fields = self.index_set.get("target_fields", [])
        sort_fields = self.index_set.get("sort_fields", [])

        if sort_fields:
            time_field, _, _ = UnifyQueryHandler.init_time_field(self.index_set["index_set_id"], self.scenario_id)
            body: dict = CreateSearchTailBodyCustomField(
                start=self.search_params.get("start", 0),
                size=self.search_params.get("size", 30),
                zero=self.zero,
                time_field=time_field,
                target_fields=target_fields,
                sort_fields=sort_fields,
                params=self.search_params,
                base_params=base_params,
            ).body

        elif self.scenario_id == Scenario.BKDATA:
            body: dict = CreateSearchTailBodyScenarioBkData(
                sort_list=["dtEventTimeStamp", "gseindex", "_iteration_idx"],
                size=self.search_params.get("size", 30),
                start=self.search_params.get("start", 0),
                gseindex=self.gseindex,
                path=self.path,
                ip=self.ip,
                bk_host_id=self.bk_host_id,
                container_id=self.container_id,
                logfile=self.logfile,
                zero=self.zero,
                base_params=base_params,
            ).body
        elif self.scenario_id == Scenario.LOG:
            body: dict = CreateSearchTailBodyScenarioLog(
                sort_list=["dtEventTimeStamp", "gseIndex", "iterationIndex"],
                size=self.search_params.get("size", 30),
                start=self.search_params.get("start", 0),
                gseIndex=self.gseIndex,
                path=self.path,
                bk_host_id=self.bk_host_id,
                serverIp=self.serverIp,
                container_id=self.container_id,
                logfile=self.logfile,
                zero=self.zero,
                base_params=base_params,
            ).body

        result = self.query_ts_raw(body)

        result: dict = self._deal_query_result(result)
        if self.zero:
            result.update(
                {
                    "list": list(reversed(result.get("list"))),
                    "origin_log_list": list(reversed(result.get("origin_log_list"))),
                }
            )
        result.update(
            {
                "list": result.get("list"),
                "origin_log_list": result.get("origin_log_list"),
            }
        )
        return result
