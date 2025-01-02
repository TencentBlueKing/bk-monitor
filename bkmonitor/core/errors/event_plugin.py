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


class KafkaConnectError(Error):
    status_code = 500
    code = 3323001
    name = _lazy("Kafka 连接失败")
    message_tpl = _lazy("Kafka 连接失败: {msg}")


class KafkaPartitionError(Error):
    status_code = 500
    code = 3323002
    name = _lazy("Kafka Partition 信息获取失败")
    message_tpl = _lazy("Kafka Partition 信息获取失败")


class DataIDNotSetError(Error):
    status_code = 400
    code = 3323003
    name = _lazy("插件 DataID 未设置")
    message_tpl = _lazy("插件 DataID 未设置，请确认插件是否已经正确保存")


class PluginParseError(Error):
    status_code = 400
    code = 3323004
    name = _lazy("插件包解析错误")
    message_tpl = _lazy("插件包解析错误: {msg}")


class GetKafkaConfigError(Error):
    status_code = 500
    code = 3323005
    name = _lazy("Kafka 配置获取失败")
    message_tpl = _lazy("Kafka 配置获取失败: {msg}")


class PluginIDExistError(Error):
    status_code = 400
    code = 3323006
    name = _lazy("插件版本已存在")
    message_tpl = _lazy("插件ID ({plugin_id}) 对应的版本({version})已存在，请修改后重试")
