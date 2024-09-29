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

import datetime
from unittest.mock import Mock, patch

import pytest


# 定义一个 mock 的 localtime 方法
def mock_localtime():
    mock_time = Mock()
    mock_time.utcoffset.return_value = datetime.timedelta(seconds=0)
    return mock_time


def mock_get_current_timezone():
    mock_timezone = Mock()
    mock_timezone.zone = "UTC"
    return mock_timezone


@pytest.fixture(autouse=True)
def mock_timezone_localtime():
    """不同单测环境时区可能不一样，这里统一为 UTC"""
    with patch("django.utils.timezone.get_current_timezone_name", return_value="UTC"):
        with patch("django.utils.timezone.get_current_timezone", mock_get_current_timezone):
            with patch("django.utils.timezone.localtime", mock_localtime):
                yield
