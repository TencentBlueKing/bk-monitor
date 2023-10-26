# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from typing import List

from apps.log_desensitize.handlers.entity.desensitize_config_entity import DesensitizeConfigEntity


def desensitize_params_init(desensitize_configs: List = None):
    """
    脱敏工厂参数初始化逻辑
    """

    if not desensitize_configs:
        return []

    # 初始化脱敏工厂参数
    desensitize_entities = list()

    for _config in desensitize_configs:
        # 初始化实体对象

        desensitize_entity = DesensitizeConfigEntity(
            field_name=_config.get("field_name"),
            operator=_config.get("operator"),
            params=_config.get("params"),
            match_pattern=_config.get("match_pattern"),
            rule_id=_config.get("rule_id"),
            exclude_rules=_config.get("exclude_rules"),
            match_fields=_config.get("match_fields")
        )
        desensitize_entities.append(desensitize_entity)

    return desensitize_entities
