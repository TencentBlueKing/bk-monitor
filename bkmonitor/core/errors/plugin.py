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
插件模块错误
"""

from django.utils.translation import gettext_lazy as _

from core.errors import Error


class PluginError(Error):
    status_code = 400
    code = 3310001
    name = _("插件模块错误")
    message_tpl = _("插件模块错误：{msg}")


class PluginParseError(PluginError):
    code = 3310002
    name = _("插件包解析错误")
    message_tpl = _("插件包解析错误: {msg}")


class PluginIDExist(PluginError):
    status_code = 200
    code = 3310003
    name = _("插件ID已存在")
    message_tpl = _("插件ID错误: 已存在的插件ID({msg})")


class PluginIDNotExist(PluginParseError):
    code = 3310004
    name = _("插件ID不存在")
    message_tpl = _("插件ID错误: 不存在的plugin_id")


class MakePackageError(PluginParseError):
    code = 3310005
    name = _("打包失败")
    message_tpl = _("打包失败: {msg}")


class RegisterPackageError(PluginParseError):
    code = 3310006
    name = _("注册插件失败")
    message_tpl = _("注册插件失败: {msg}")


class PluginVersionNotExist(PluginParseError):
    code = 3310007
    name = _("插件版本不存在")
    message_tpl = _("插件版本不存在: 不存在的插件版本")


class SignatureTypeError(PluginError):
    code = 3310008
    name = _("插件签名格式无效")
    message_tpl = _("插件签名解析失败，无效的签名格式")


class SignatureProtocolNotExist(PluginError):
    code = 3310009
    name = _("插件签名协议不存在")
    message_tpl = _("{plugin}插件签名协议: {protocol} 不存在")


class SignatureNotSupported(PluginError):
    code = 3310010
    name = _("不支持签名的插件类型")
    message_tpl = _("不支持签名的插件类型: {plugin_type}")


class EditPermissionDenied(PluginError):
    code = 3310011
    name = _("无插件编辑权限")
    message_tpl = _("编辑失败！无插件编辑权限: {plugin_id}")


class DeletePermissionDenied(PluginError):
    code = 3310012
    name = _("无插件删除权限")
    message_tpl = _("删除失败！无插件删除权限: {plugin_id}")


class UnsupportedPluginTypeError(PluginError):
    code = 3310013
    name = _("不支持的插件类型")
    message_tpl = _("不支持的插件类型: {plugin_type}")


class RelatedItemsExist(PluginError):
    code = 3310014
    name = _("插件存在关联项")
    message_tpl = _("插件存在关联项: {msg}")


class ExportPluginError(PluginError):
    code = 3310015
    name = _("插件导出错误")
    message_tpl = _("插件导出错误: {msg}")


class RemoteCollectError(PluginError):
    code = 3310016
    name = _("是否支持远程采集冲突")
    message_tpl = _("是否支持远程采集冲突: {msg}")


class ExportPluginTimeout(PluginError):
    code = 3310017
    name = _("节点管理导出超时")
    message_tpl = _("节点管理导出超时，请联系管理员检查后台环境")


class NodeManDeleteError(PluginError):
    code = 3310018
    name = _("节点管理删除插件失败")
    message_tpl = _("节点管理删除插件失败，请联系管理员检查后台环境")


class BizChangedError(PluginError):
    code = 3310018
    name = _("插件业务切换错误")
    message_tpl = _("不支持单业务之间的互相切换")


class SNMPMetricNumberError(PluginError):
    code = 3310020
    name = _("SNMP指标设置错误")
    message_tpl = _("SNMP设置指标数量超过{snmp_max_metric_num}，请删减非必要指标")


class MetricNumberError(PluginError):
    code = 3310021
    name = _("指标设置错误")
    message_tpl = _("设置指标数量超过{max_metric_num}，请删减非必要指标")


class PluginIDFormatError(PluginError):
    status_code = 200
    code = 3310022
    name = _("插件ID格式不规范")
    message_tpl = _("插件ID格式错误: {msg}")


class ParsingDataError(PluginError):
    code = 3310023
    name = _("解析数据错误")
    message_tpl = _("解析节点管理返回数据异常，错误原因可能为：1. 插件采集的指标数量过多，2. 插件采集的数据量过大")
