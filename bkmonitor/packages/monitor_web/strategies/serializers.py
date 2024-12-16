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
from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from bkmonitor.views import serializers
from constants.strategy import TargetFieldType
from monitor_web.strategies.constant import (
    DETECT_ALGORITHM_FLOAT_OR_INT_LIST,
    DETECT_ALGORITHM_INT_LIST,
    DETECT_ALGORITHM_METHOD_LIST,
)


class Ipserializer(serializers.Serializer):
    ip = serializers.IPAddressField(required=True, label="IP地址")
    bk_cloud_id = serializers.IntegerField(required=True, label="云区域ID")


class TopoSerializer(serializers.Serializer):
    bk_inst_id = serializers.IntegerField(required=True, label="节点ID")
    bk_obj_id = serializers.CharField(required=True, label="节点层级")


class HostTargetIpSerializer(serializers.Serializer):
    bk_target_ip = serializers.IPAddressField(required=True, label="目标ip地址")
    bk_target_cloud_id = serializers.IntegerField(required=True, label="目标云区域ID")


class TemplateSerializer(serializers.Serializer):
    bk_inst_id = serializers.IntegerField(required=True, label="模板id")
    bk_obj_id = serializers.CharField(required=True, label="模板对象名")


def is_validate_target(value):
    if not isinstance(value, list):
        return ValidationError(_("target结构不符合要求"))
    if len(value) > 1:
        if not all(value):
            raise ValidationError(_("target结构不符合要求"))

    for value_msg in value:
        if not isinstance(value_msg, list):
            return ValidationError(_("target结构不符合要求"))


def handle_target(value):
    for value_list in value:
        for value_detail in value_list:
            if value_detail["field"] == TargetFieldType.host_ip and isinstance(value_detail["value"], list):
                value_detail["field"] = TargetFieldType.host_target_ip
                value_detail["value"] = [
                    {"bk_target_ip": x["ip"], "bk_target_cloud_id": x["bk_cloud_id"], "bk_host_id": x["bk_host_id"]}
                    for x in value_detail["value"]
                ]

            # 针对拓扑和模板，只保留bk_obj_id和bk_inst_id，避免脏数据
            if value_detail["field"] in [
                TargetFieldType.host_topo,
                TargetFieldType.service_topo,
                TargetFieldType.host_set_template,
                TargetFieldType.host_service_template,
                TargetFieldType.service_set_template,
                TargetFieldType.service_set_template,
            ] and isinstance(value_detail["value"], list):
                value_detail["value"] = [
                    {"bk_obj_id": x["bk_obj_id"], "bk_inst_id": x["bk_inst_id"]} for x in value_detail["value"]
                ]
    if not value:
        value = [[]]
    return value


def validate_algorithm_config_msg(value):
    def is_validate(value_msg):
        for algorithm_key, algorithm_value in list(value_msg.items()):
            if algorithm_key in DETECT_ALGORITHM_INT_LIST:
                if algorithm_value is None:
                    continue
                try:
                    value_msg[algorithm_key] = int(algorithm_value) if str(algorithm_value) else None
                except (ValueError, TypeError):
                    raise ValidationError(_("检测算法不符合要求，周期为正整数，值为正数"))
            elif algorithm_key in DETECT_ALGORITHM_FLOAT_OR_INT_LIST:
                if algorithm_value is None:
                    continue
                try:
                    value_msg[algorithm_key] = (
                        round(float(algorithm_value), settings.POINT_PRECISION) if str(algorithm_value) else None
                    )
                except (ValueError, TypeError):
                    raise ValidationError(_("检测算法不符合要求，周期为正整数，值为正数"))
            elif algorithm_key == "method":
                if algorithm_value not in DETECT_ALGORITHM_METHOD_LIST:
                    raise ValidationError(_("检测算法的计算方法不符合要求"))

        return value_msg

    if len(value) == 0:
        return value

    if isinstance(value, list):
        return_value = []
        for v in value:
            if not isinstance(v, list):
                raise ValidationError(_("静态阈值检测算法结构不符合要求"))
            return_value.append([is_validate(x) for x in v])
    else:
        return_value = is_validate(value)

    return return_value


def validate_algorithm_msg(value):
    # 校验检测算法是否合法
    for algorithm_msg in value:
        algorithm_type = algorithm_msg["algorithm_type"]
        check_config = algorithm_msg["algorithm_config"]
        type_serializer = algorithm_type + "Serializer"
        try:
            serializer_cls = import_string("bkmonitor.strategy.serializers.{}".format(type_serializer))
            serializer = serializer_cls(data=check_config)
            serializer.is_valid(raise_exception=True)
            algorithm_msg["algorithm_config"] = serializer.validated_data
        except ImportError:
            pass
        except Exception as e:
            raise e
    return value


def validate_trigger_config_msg(value):
    # 校验是否为合法触发配置
    try:
        value["check_window"] = int(value.get("check_window"))
        value["count"] = int(value.get("count"))

        if any([value["check_window"] < value["count"], value["check_window"] <= 0, value["count"] <= 0]):
            raise ValidationError(_("触发条件满足条件次数不能大于所填周期数,且为正整数"))
        return value
    except ValueError:
        raise ValidationError(_("触发条件满足条件次数不能大于所填周期数,且为正整数"))


def validate_recovery_config_msg(value):
    # 校验恢复配置
    try:
        value["check_window"] = int(value.get("check_window"))
        if value["check_window"] <= 0:
            raise ValidationError(_("恢复周期需要是正整数"))
    except ValueError:
        raise ValidationError(_("恢复周期需要是正整数"))

    return value


def validate_no_data_config_msg(value):
    # 无数据校验
    value["continuous"] = value.get("continuous", None)
    if value["is_enabled"] and value["continuous"] is None:
        raise ValidationError(_("启用无数据告警的周期数不能为空，且大于0"))

    if value["continuous"] is None:
        return value
    try:
        value["continuous"] = int(value["continuous"])
    except ValueError:
        raise ValidationError(_("无数据告警周期需要为正整数"))
    if value["continuous"] <= 0:
        raise ValidationError(_("无数据告警周期需要为正整数"))

    return value


def validate_action_config(value):
    # 校验通知动作配置
    try:
        if "alarm_interval" not in value:
            return value
        value["alarm_interval"] = int(value.get("alarm_interval"))
        if value["alarm_interval"] <= 0:
            raise ValidationError(_("通知间隔需要是正整数"))
        return value
    except ValueError:
        raise ValidationError(_("通知间隔需要是正整数"))


def validate_agg_condition_msg(value):
    # 校验是否为合法的监控条件
    for index, value_msg in enumerate(value):
        if not all([value_msg.get("key"), value_msg.get("method"), value_msg.get("value")]):
            raise ValidationError(_("监控条件填写错误，需要key、method、value键"))

        if index > 0 and value_msg.get("condition", "") not in ["and", "or"]:
            raise ValidationError(_("多个条件时，聚合条件中需要condition参数，且为and或or"))

    return value
