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

from typing import Dict, List


def get_metric_tag_from_metric_info(metric_info: Dict) -> List:
    # 获取 tag
    if "tag_value_list" in metric_info:
        tags = set(metric_info["tag_value_list"].keys())
    else:
        tags = {tag["field_name"] for tag in metric_info.get("tag_list", [])}
    # 添加特殊字段，兼容先前逻辑
    tags.add("target")
    return list(tags)
