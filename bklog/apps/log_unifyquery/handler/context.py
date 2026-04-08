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
import json
from typing import Any

from apps.log_search.models import Scenario
from apps.log_unifyquery.builder.context import (
    CreateSearchContextBodyCustomField,
    CreateSearchContextBodyScenarioBkData,
    CreateSearchContextBodyScenarioLog,
)
from apps.log_unifyquery.handler.tail import UnifyQueryTailHandler


class UnifyQueryContextHandler(UnifyQueryTailHandler):
    def search(self, *args):
        # 仅支持单索引集
        if self.scenario_id == Scenario.ES and not (self.index_set["target_fields"] or self.index_set["sort_fields"]):
            return {"total": 0, "took": 0, "list": []}

        if self.zero:
            # up
            body: dict = self._get_context_body("-")
            params_up = copy.deepcopy(self.base_dict)
            params_up.update(body)
            result_up: dict = self.query_ts_raw(params_up)
            result_up: dict = self._deal_query_result(result_up)
            result_up.update(
                {
                    "list": list(reversed(result_up.get("list"))),
                    "origin_log_list": list(reversed(result_up.get("origin_log_list"))),
                }
            )

            # down
            body: dict = self._get_context_body("+")

            params_down = copy.deepcopy(self.base_dict)
            params_down.update(body)
            result_down: dict = self.query_ts_raw(params_down)

            result_down: dict = self._deal_query_result(result_down)
            result_down.update({"list": result_down.get("list"), "origin_log_list": result_down.get("origin_log_list")})
            total = result_up["total"] + result_down["total"]
            took = result_up["took"] + result_down["took"]
            new_list = result_up["list"] + result_down["list"]
            origin_log_list = result_up["origin_log_list"] + result_down["origin_log_list"]
            target_fields = self.index_set["target_fields"] if self.index_set else []
            sort_fields = self.index_set["sort_fields"] if self.index_set else []
            if sort_fields:
                analyze_result_dict: dict = self._analyze_context_result(
                    new_list, target_fields=target_fields, sort_fields=sort_fields
                )
            else:
                analyze_result_dict: dict = self._analyze_context_result(
                    new_list, mark_gseindex=self.gseindex, mark_gseIndex=self.gseIndex
                )
            zero_index: int = analyze_result_dict.get("zero_index", -1)
            count_start: int = analyze_result_dict.get("count_start", -1)

            return {
                "total": total,
                "took": took,
                "list": new_list,
                "origin_log_list": origin_log_list,
                "zero_index": zero_index,
                "count_start": count_start,
                "dsl": json.dumps(body),
            }
        if self.start < 0:
            body: dict = self._get_context_body("-")

            params_up = copy.deepcopy(self.base_dict)
            params_up.update(body)
            result_up = self.query_ts_raw(params_up)

            result_up: dict = self._deal_query_result(result_up)
            result_up.update(
                {
                    "list": list(reversed(result_up.get("list"))),
                    "origin_log_list": list(reversed(result_up.get("origin_log_list"))),
                }
            )
            result_up.update(
                {
                    "list": result_up.get("list"),
                    "origin_log_list": result_up.get("origin_log_list"),
                }
            )
            return result_up
        if self.start > 0:
            body: dict = self._get_context_body("+")

            params_down = copy.deepcopy(self.base_dict)
            params_down.update(body)
            result_down = self.query_ts_raw(params_down)

            result_down = self._deal_query_result(result_down)
            result_down.update({"list": result_down.get("list"), "origin_log_list": result_down.get("origin_log_list")})
            result_down.update(
                {
                    "list": result_down.get("list"),
                    "origin_log_list": result_down.get("origin_log_list"),
                }
            )
            return result_down

        return {"list": []}

    def _get_context_body(self, order):
        target_fields = self.index_set["target_fields"]
        sort_fields = self.index_set["sort_fields"]
        body_data = copy.deepcopy(self.base_dict)

        if sort_fields:
            return CreateSearchContextBodyCustomField(
                body_data=body_data,
                size=self.size,
                start=self.start,
                order=order,
                target_fields=target_fields,
                sort_fields=sort_fields,
                params=self.search_params,
            ).body

        elif self.scenario_id == Scenario.BKDATA:
            return CreateSearchContextBodyScenarioBkData(
                body_data=body_data,
                size=self.size,
                start=self.start,
                gse_index=self.gseindex,
                iteration_idx=self._iteration_idx,
                dt_event_time_stamp=self.dtEventTimeStamp,
                path=self.path,
                ip=self.ip,
                bk_host_id=self.bk_host_id,
                container_id=self.container_id,
                logfile=self.logfile,
                order=order,
                sort_list=["dtEventTimeStamp", "gseindex", "_iteration_idx"],
            ).body

        elif self.scenario_id == Scenario.LOG:
            return CreateSearchContextBodyScenarioLog(
                body_data=body_data,
                size=self.size,
                start=self.start,
                gse_index=self.gseIndex,
                iteration_index=self.iterationIndex,
                dt_event_time_stamp=self.dtEventTimeStamp,
                path=self.path,
                server_ip=self.serverIp,
                bk_host_id=self.bk_host_id,
                container_id=self.container_id,
                logfile=self.logfile,
                order=order,
                sort_list=["dtEventTimeStamp", "gseIndex", "iterationIndex"],
            ).body

        return {}

    def _analyze_context_result(
        self,
        log_list: list[dict[str, Any]],
        mark_gseindex: int = None,
        mark_gseIndex: int = None,
        target_fields: list = None,
        sort_fields: list = None,
        # pylint: disable=invalid-name
    ) -> dict[str, Any]:
        log_list_reversed: list = log_list
        if self.start < 0:
            log_list_reversed = list(reversed(log_list))

        # find the search one
        _index: int = -1

        target_fields = target_fields or []
        sort_fields = sort_fields or []

        if sort_fields:
            for index, item in enumerate(log_list):
                for field in sort_fields + target_fields:
                    tmp_item = item.copy()
                    sub_field = field
                    while "." in sub_field:
                        prefix, sub_field = sub_field.split(".", 1)
                        tmp_item = tmp_item.get(prefix, {})
                        if sub_field in tmp_item:
                            break
                    item_field = tmp_item.get(sub_field)
                    if str(item_field) != str(self.search_params.get(field)):
                        break
                else:
                    _index = index
                    break
        elif self.scenario_id == Scenario.BKDATA:
            for index, item in enumerate(log_list):
                gseindex: str = item.get("gseindex")
                ip: str = item.get("ip")
                bk_host_id: int = item.get("bk_host_id")
                path: str = item.get("path")
                container_id: str = item.get("container_id")
                logfile: str = item.get("logfile")
                _iteration_idx: str = item.get("_iteration_idx")

                if (
                    (
                        self.gseindex == str(gseindex)
                        and self.bk_host_id == bk_host_id
                        and self.path == path
                        and self._iteration_idx == str(_iteration_idx)
                    )
                    or (
                        self.gseindex == str(gseindex)
                        and self.ip == ip
                        and self.path == path
                        and self._iteration_idx == str(_iteration_idx)
                    )
                    or (
                        self.gseindex == str(gseindex)
                        and self.container_id == container_id
                        and self.logfile == logfile
                        and self._iteration_idx == str(_iteration_idx)
                    )
                ):
                    _index = index
                    break
        elif self.scenario_id == Scenario.LOG:
            for index, item in enumerate(log_list):
                gseIndex: str = item.get("gseIndex")  # pylint: disable=invalid-name
                serverIp: str = item.get("serverIp")  # pylint: disable=invalid-name
                bk_host_id: int = item.get("bk_host_id")
                path: str = item.get("path", "")
                iterationIndex: str = item.get("iterationIndex")  # pylint: disable=invalid-name

                if (
                    self.gseIndex == str(gseIndex)
                    and self.bk_host_id == bk_host_id
                    and self.path == path
                    and self.iterationIndex == str(iterationIndex)
                ) or (
                    self.gseIndex == str(gseIndex)
                    and self.serverIp == serverIp
                    and self.path == path
                    and self.iterationIndex == str(iterationIndex)
                ):
                    _index = index
                    break

        _count_start = _index
        return {"list": log_list_reversed, "zero_index": _index, "count_start": _count_start}
