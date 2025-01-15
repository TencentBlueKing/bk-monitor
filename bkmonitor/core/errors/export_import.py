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

"""
导入导出模块错误
"""


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class ExportImportError(Error):
    status_code = 400
    code = 3317001
    name = _lazy("导入导出模块错误")
    message_tpl = _lazy("导入导出模块错误：{msg}")


class ImportHistoryNotExistError(ExportImportError):
    status_code = 400
    code = 3317002
    name = _lazy("导入历史不存在")
    message_tpl = _lazy("导入历史不存在，检查导入历史ID")


class AddTargetError(ExportImportError):
    status_code = 400
    code = 3317003
    name = _lazy("添加统一监控目标失败")
    message_tpl = _lazy("添加统一监控目标失败: {msg}")


class UploadPackageError(ExportImportError):
    status_code = 400
    code = 3317004
    name = _lazy("上传导入包失败")
    message_tpl = _lazy("上传导入包失败: {msg}")


class ImportConfigError(ExportImportError):
    status_code = 400
    code = 3317005
    name = _lazy("导入配置失败")
    message_tpl = _lazy("导入配置失败: {msg}")


class DuplicatePackageError(ExportImportError):
    status_code = 400
    code = 3317006
    name = _lazy("上传导入包失败")
    message_tpl = _lazy("上传导入包失败: 该包已导入过，请选择其他导入包")
