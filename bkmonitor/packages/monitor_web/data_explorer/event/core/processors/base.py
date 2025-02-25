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

import abc
from typing import Any, Dict, List


class BaseEventProcessor(abc.ABC):
    """事件处理基类"""

    def __init__(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """丰富原始事件，输出丰富后的事件数据列表
        :param origin_events: 原始事件列表
        :return:
        """
        raise NotImplementedError
