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


# 配置类型


class ConfigType(object):
    COLLECT = "collect"
    STRATEGY = "strategy"
    PLUGIN = "plugin"
    VIEW = "view"


# 导入详情状态类型
class ImportDetailStatus(object):
    IMPORTING = "importing"
    SUCCESS = "success"
    FAILED = "failed"


# 导入历史状态
class ImportHistoryStatus(object):
    UPLOAD = "upload"
    IMPORTED = "imported"
    IMPORTING = "importing"


# 配置类型对应的文件夹名称
class ConfigDirectoryName(object):
    plugin = "plugin_directory"
    collect = "collect_config_directory"
    strategy = "strategy_config_directory"
    view = "view_config_directory"


DIRECTORY_LIST = [
    ConfigDirectoryName.plugin,
    ConfigDirectoryName.collect,
    ConfigDirectoryName.strategy,
    ConfigDirectoryName.view,
]
