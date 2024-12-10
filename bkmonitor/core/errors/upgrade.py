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


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class UpgradeError(Error):
    status_code = 400
    code = 3318001
    name = _lazy("升级模块错误")
    message_tpl = _lazy("升级模块错误：{msg}")


class UpgradeNotAllowedError(UpgradeError):
    code = 3318002
    name = _lazy("当前不允许数据迁移")
    message_tpl = _lazy("当前不允许数据迁移，请确认并存版本号为 3.0.x 或 3.1.x")


class MakeMigrationError(UpgradeError):
    code = 3318003
    name = _lazy("获取待迁移内容失败")
    message_tpl = _lazy("获取待迁移内容失败：{msg}")


class MigrateError(UpgradeError):
    code = 3318004
    name = _lazy("数据迁移失败")
    message_tpl = _lazy("数据迁移失败：{msg}")


class SyncHistoryFileError(UpgradeError):
    code = 3318005
    name = _lazy("同步旧版本文件失败")
    message_tpl = _lazy("同步旧版本文件失败：{msg}")


class ExportCollectorError(UpgradeError):
    code = 3318006
    name = _lazy("插件导出失败")
    message_tpl = _lazy("插件导出失败：{msg}")


class CreateDefaultStrategyError(UpgradeError):
    code = 3318007
    name = _lazy("创建默认策略失败")
    message_tpl = _lazy("创建默认策略失败：{msg}")
