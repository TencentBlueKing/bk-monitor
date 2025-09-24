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
import copy
from typing import Dict, List, Any

from apps.log_search.models import Scenario
from apps.log_unifyquery.builder.tail import CreateSearchTailBodyCustomField, CreateSearchTailBodyScenarioBkData, \
    CreateSearchTailBodyScenarioLog
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
        body: Dict = {}
        target_fields = self.index_set.get("target_fields", [])
        sort_fields = self.index_set.get("sort_fields", [])

        if sort_fields:
            time_field, _, _ = UnifyQueryHandler.init_time_field(self.index_set["index_set_id"], self.scenario_id)
            body: Dict = CreateSearchTailBodyCustomField(
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
            body: Dict = CreateSearchTailBodyScenarioBkData(
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
            body: Dict = CreateSearchTailBodyScenarioLog(
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
                "list": self._analyze_empty_log(result.get("list")),
                "origin_log_list": self._analyze_empty_log(result.get("origin_log_list")),
            }
        )
        return result

    @staticmethod
    def _analyze_empty_log(log_list: List[Dict[str, Any]]):
        log_not_empty_list: List[Dict[str, Any]] = []
        for item in log_list:
            a_item_dict: Dict[str:Any] = item

            # 只要存在log字段则直接显示
            if "log" in a_item_dict:
                log_not_empty_list.append(a_item_dict)
                continue
            # 递归打平每条记录
            new_log_context_list: List[str] = []

            def get_field_and_get_context(_item: dict, fater: str = ""):
                for key in _item:
                    _key: str = ""
                    if isinstance(_item[key], dict):
                        get_field_and_get_context(_item[key], key)
                    else:
                        if fater:
                            _key = "{}.{}".format(fater, key)
                        else:
                            _key = "%s" % key
                    if _key:
                        a_context: str = "{}: {}".format(_key, _item[key])
                        new_log_context_list.append(a_context)

            get_field_and_get_context(a_item_dict)
            a_item_dict.update({"log": " ".join(new_log_context_list)})
            log_not_empty_list.append(a_item_dict)
        return log_not_empty_list
