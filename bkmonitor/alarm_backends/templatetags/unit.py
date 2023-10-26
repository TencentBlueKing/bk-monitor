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

from django import template
from django.conf import settings

from core.unit import load_unit

register = template.Library()


@register.filter(name="auto_unit")
def unit_auto_convert(value, unit):
    """
    自动单位转换
    """
    value, suffix = load_unit(unit).auto_convert(value, decimal=settings.POINT_PRECISION)
    return f"{value}{suffix}"


def unit_convert_min(value, unit, suffix=None):
    unit = load_unit(unit)
    return unit.convert_to_max(value, suffix, decimal=settings.POINT_PRECISION)[0]


@register.filter(name="unit_suffix")
def unit_suffix(unit, suffix):
    unit = load_unit(unit)

    if not suffix or suffix not in unit.suffix_list:
        suffix = ""

    return f"{suffix}{unit._suffix}"
