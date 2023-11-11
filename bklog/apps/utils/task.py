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
from celery.task import periodic_task, task
from django.conf import settings


def high_priority_task(*args, **kwargs):
    """Deprecated decorator, please use :func:`celery.task`."""
    return task(*args, **dict({'queue': settings.BK_LOG_HIGH_PRIORITY_QUEUE}, **kwargs))


def high_priority_periodic_task(*args, **options):
    """Deprecated decorator, please use :setting:`beat_schedule`."""
    return periodic_task(**dict({'queue': settings.BK_LOG_HIGH_PRIORITY_QUEUE}, **options))
