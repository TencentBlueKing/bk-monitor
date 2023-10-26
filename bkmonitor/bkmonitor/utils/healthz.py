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


def deep_parsing_metric_info(metric_info):
    parent_value = metric_info["result"]
    value_list = parent_value["value"]
    for item in value_list:
        if not isinstance(item, dict):
            raise TypeError
        sub_metric_info = copy.deepcopy(metric_info)
        name = item.pop("name", parent_value["name"])
        value = item.pop("value", "")
        status = item.pop("status", parent_value["status"])
        message = item.pop("message", parent_value["message"])
        if not message:
            message = " ".join(["{}: {}".format(k, v) for k, v in list(item.items())])
        sub_metric_info["result"] = {
            "name": name,
            "value": value,
            "message": message,
            "status": status,
        }
        if "description" in sub_metric_info:
            sub_metric_info["description"] += name
        else:
            sub_metric_info["description"] = name
        yield sub_metric_info
