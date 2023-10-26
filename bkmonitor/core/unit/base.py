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


from collections import OrderedDict

import six

from core.errors.metric_meta import MetricUnitCategoryNotExist, MetricUnitIdInvalid

from .init_data import define
from .models import UnitMeta, create_default_unit

UNITS = None


def load_units():
    units = OrderedDict()
    for cat in define:
        category = cat["name"]

        units.setdefault(category, OrderedDict())
        for _format in cat["formats"]:
            unit = UnitMeta(_format["id"], _format["name"], category, _format["fn"])
            units[category][unit.gid] = unit

    return units


def load_unit(unit_id):
    if UNITS is None:
        setup()

    information = unit_id.split("||")
    if len(information) > 2:
        raise MetricUnitIdInvalid(unit_id=unit_id)

    if len(information) == 2:
        cat, gid = information
        category = UNITS.get(cat)
        if not category:
            raise MetricUnitCategoryNotExist(unit_id=unit_id)
        unit = category.get(gid)
        if not unit:
            raise MetricUnitIdInvalid(unit_id=unit_id)

    else:
        gid = information[0]
        for item in six.itervalues(UNITS or {}):
            if gid in item:
                unit = item[gid]
                break
        else:
            unit = create_default_unit(gid)

    return unit


def setup():
    global UNITS
    UNITS = load_units()


setup()
