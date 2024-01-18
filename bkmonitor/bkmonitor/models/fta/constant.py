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
from django.utils.translation import ugettext as _


class PluginType:
    HTTP_PUSH = "http_push"
    HTTP_PULL = "http_pull"
    EMAIL_PULL = "email_pull"
    KAFKA_PUSH = "kafka_push"
    COLLECTOR = "bk_collector"

    @classmethod
    def to_choice(cls):
        return (
            (cls.HTTP_PUSH, _("HTTP 推送")),
            (cls.HTTP_PULL, _("HTTP 拉取")),
            (cls.EMAIL_PULL, _("Email 拉取")),
            (cls.KAFKA_PUSH, _("kafka 推送")),
            (cls.COLLECTOR, _("HTTP 推送")),
        )


class PluginMainType:
    PUSH = "push"
    PULL = "pull"

    @classmethod
    def to_choice(cls):
        return (
            (cls.PUSH, _("推送")),
            (cls.PULL, _("拉取")),
        )


class PluginSourceFormat:
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    TEXT = "text"

    @classmethod
    def to_choice(cls):
        return (cls.JSON, "JSON"), (cls.YAML, "YAML"), (cls.XML, "XML"), (cls.TEXT, _("文本"))


class PluginStatus:
    NO_DATA = "NO_DATA"
    REMOVE_SOON = "REMOVE_SOON"
    REMOVED = "REMOVED"
    DISABLED = "DISABLED"
    AVAILABLE = "AVAILABLE"
    DEBUG = "DEBUG"

    @classmethod
    def to_choice(cls):
        return (
            (cls.NO_DATA, _("无数据")),
            (cls.REMOVE_SOON, _("将下架")),
            (cls.REMOVED, _("已下架")),
            (cls.DISABLED, _("已停用")),
            (cls.AVAILABLE, _("可用")),
            (cls.DEBUG, _("调试中")),
        )

    @classmethod
    def active_statuses(cls):
        """
        可用的状态列表
        """
        return [
            cls.NO_DATA,
            cls.REMOVE_SOON,
        ]


class Scenario:
    MONITOR = "MONITOR"
    REST_API = "REST_API"
    EMAIL = "EMAIL"
    KAFKA = "KAFKA"

    @classmethod
    def to_choice(cls):
        return (
            (cls.MONITOR, _("监控工具")),
            (cls.REST_API, "Rest API"),
            (cls.EMAIL, "Email"),
            (cls.KAFKA, "Kafka"),
        )
