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
from datetime import datetime

from django.utils import timezone
from humanize import naturaldelta


def test_age():
    creation_timestamp = "2022-01-01T00:00:00Z"
    # 获得UTC时间
    create_at = datetime.strptime(creation_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    create_at_utc = timezone.make_aware(create_at, timezone.utc)
    # 转换为当前时区的时间
    create_at_current_timezone = create_at_utc.astimezone(timezone.get_current_timezone())
    create_at_current_timezone_naive = timezone.make_naive(create_at_current_timezone)
    assert create_at_current_timezone_naive == datetime(2022, 1, 1, 8, 0)

    actual = naturaldelta(create_at_current_timezone_naive)
    expect = naturaldelta(datetime.utcnow() - create_at)
    assert actual == expect
