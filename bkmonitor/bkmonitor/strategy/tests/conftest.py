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

import pytest
from django.test import TestCase

from bkmonitor.models import (
    Action,
    ActionConfig,
    ActionNoticeMapping,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    NoticeTemplate,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyModel,
)

pytestmark = pytest.mark.django_db


def pytest_configure():
    TestCase.databases = {"default", "monitor_api"}


def _clean_all_model():
    StrategyModel.objects.all().delete()
    ItemModel.objects.all().delete()
    Action.objects.all().delete()
    ActionConfig.objects.all().delete()
    ActionNoticeMapping.objects.all().delete()
    DetectModel.objects.all().delete()
    QueryConfigModel.objects.all().delete()
    AlgorithmModel.objects.all().delete()
    NoticeTemplate.objects.all().delete()
    StrategyActionConfigRelation.objects.all().delete()


@pytest.fixture()
def clean_model():
    _clean_all_model()
    yield
    _clean_all_model()
