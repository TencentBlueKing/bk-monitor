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

from django.conf import settings


def get_real_biz_id(bk_biz_id):
    bk_biz_id = int(bk_biz_id)

    if bk_biz_id < settings.RT_TABLE_PREFIX_VALUE:
        bk_biz_id = bk_biz_id + settings.RT_TABLE_PREFIX_VALUE

    return bk_biz_id
