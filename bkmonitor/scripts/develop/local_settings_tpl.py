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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "bk_monitor",
        "USER": "root",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": 3306,
        "TEST": {
            "NAME": "test_bk_monitor",
            "CHARSET": "utf8",
            "COLLATION": "utf8_general_ci",
        },
    },
    "monitor_api": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "bkdata_monitor_alert",
        "USER": "root",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": 3306,
        "TEST": {
            "NAME": "test_bkdata_monitor_alert",
            "CHARSET": "utf8",
            "COLLATION": "utf8_general_ci",
        },
    },
}
