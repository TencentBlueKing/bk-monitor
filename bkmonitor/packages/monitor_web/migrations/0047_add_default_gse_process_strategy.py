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


from django.db import migrations


def add_gse_process_event_strategies(apps, *args, **kwargs):
    """
    增加gse进程托管默认策略
    5种事件，2种创建类型：
    1. 用户侧的进程托管类策略，创建5种事件对应的策略, 通知组默认使用主备负责人
    2. 平台侧的进程托管类策略，创建1种统一进程事件策略，通知组通知插件负责人
    """
    # **已迁移至manager执行**
    # do nothing
    return


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0046_merge_20210330_1134"),
    ]

    operations = [
        migrations.RunPython(add_gse_process_event_strategies),
    ]
