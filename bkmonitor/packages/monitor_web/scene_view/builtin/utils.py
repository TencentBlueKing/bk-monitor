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
import hashlib
from typing import Dict, List, Tuple

from django.utils.translation import gettext as _


def sort_panels(panels: List[Dict], order: List[Dict], hide_metric=True) -> Tuple[List[Dict], List[Dict]]:
    """
    对图表进行分组排序
    """
    panels: Dict[str, Dict] = {panel["id"]: panel for panel in panels}

    ordered_panels = []
    exists_panel_ids = set()
    no_group_row = None
    no_group_panels = []
    for row in order:
        # 过滤掉排序配置中不存在的图表
        row["panels"] = [panel for panel in row["panels"] if panel["id"] in panels]

        row_panels = []
        for panel in row["panels"]:
            # 补全排序配置信息
            panel["title"] = panels[panel["id"]]["title"]

            # 记录排序配置中存在的图表
            exists_panel_ids.add(panel["id"])

            # 是否隐藏图表
            if panel.get("hidden", False):
                continue
            row_panels.append(panels[panel["id"]])

        if row["id"] == "__UNGROUP__":
            no_group_row = row
            no_group_panels = row_panels

        ordered_panels.append({"id": row["id"], "title": str(row["title"]), "type": "row", "panels": row_panels})

    # 如果不存在未分组row，则创建
    if not no_group_row:
        no_group_row = {"id": "__UNGROUP__", "title": _("未分组的指标"), "panels": []}
        order.append(no_group_row)
        ordered_panels.append(
            {"id": no_group_row["id"], "title": no_group_row["title"], "type": "row", "panels": no_group_panels}
        )

    for panel in panels.values():
        if panel["id"] not in exists_panel_ids:
            no_group_row["panels"].append({"title": str(panel["title"]), "id": panel["id"], "hidden": hide_metric})
            if not hide_metric:
                no_group_panels.append(panel)

    return ordered_panels, order


def get_variable_filter_dict(variables: List):
    """
    根据变量配置生成过滤条件配置
    """
    variable_filters = {}
    for variable in variables:
        for target in variable["targets"]:
            for field in target["fields"].values():
                variable_filters[field] = f"${field}"
    return variable_filters


def gen_string_md5(input_string):
    # 创建一个 md5 对象
    md5_obj = hashlib.md5()

    # 更新 md5 对象，必须将字符串编码为字节
    md5_obj.update(input_string.encode('utf-8'))

    # 获取十六进制的 md5 哈希值
    return md5_obj.hexdigest()
