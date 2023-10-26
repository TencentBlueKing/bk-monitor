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


import logging

from django.db import migrations

from monitor_web.collecting.constant import (
    OperationResult,
    OperationType,
    Status,
    TaskStatus,
)

logger = logging.getLogger("monitor_web")


def update_cache_data_item(conf, field, value):
    """
    更新缓存数据某字段
    :param conf: 采集配置
    :param field: 字段
    :param value: 值
    :return: conf
    """
    if not isinstance(conf.cache_data, dict):
        conf.cache_data = {}
    conf.cache_data[field] = value
    return conf


def config_status(config):
    """
    采集配置状态
    STARTING,  启用中
    STARTED,   已启用
    STOPPING,  停用中
    STOPPED,   已停用
    DEPLOYING, 执行中
    PREPARING, 准备中
    """
    deploying_mapping = {OperationType.STOP: Status.STOPPING, OperationType.START: Status.STARTING}
    if config.operation_result == OperationResult.PREPARING:
        config_status = Status.PREPARING
    elif config.operation_result == OperationResult.DEPLOYING:
        config_status = deploying_mapping.get(config.last_operation, Status.DEPLOYING)
    else:
        config_status = Status.STOPPED if config.last_operation == OperationType.STOP else Status.STARTED

    return config_status


def task_status(config):
    """
    获取任务状态
    FAILED: 上次任务调用失败/任务执行下发全部失败
    WARNING：任务执行下发部分失败
    SUCCESS：上次任务执行下发全部成功
    STOPPED：已停用
    PREPARING: 准备中
    DEPLOYING：执行中
    AUTO_DEPLOYING: 自动执行中
    STOPPING: 停用中
    STARTING: 启用中
    """
    deploying_mapping = {OperationType.STOP: TaskStatus.STOPPING, OperationType.START: TaskStatus.STARTING}
    if config.operation_result == OperationResult.PREPARING:
        task_status = Status.PREPARING
    elif config.operation_result == OperationResult.DEPLOYING:
        task_status = deploying_mapping.get(config.last_operation, TaskStatus.DEPLOYING)
    else:
        # 任务状态不应该以最后一次任务结果为依据，否则会出现"异常"任务单击进入详情后主机状态却全部正常的情况

        # 如果不是在部署中，则优先提取缓存信息中的数量信息进行任务状态判断
        cache_data = config.cache_data
        if (
            cache_data
            and cache_data.get("error_instance_count") is not None
            and cache_data.get("total_instance_count") is not None
        ):
            error_count = cache_data["error_instance_count"]
            total_count = cache_data["total_instance_count"]
            if error_count == 0 and total_count >= 0:
                task_status = TaskStatus.SUCCESS
            elif error_count == total_count:
                task_status = TaskStatus.FAILED
            else:
                task_status = TaskStatus.WARNING
        else:
            # 如果没有缓存，则只能以最后一次任务结果为依据
            task_status = config.operation_result

        # 已停止的采集配置单独控制
        if config.last_operation == OperationType.STOP:
            task_status = TaskStatus.STOPPED

    return task_status


def get_cache_data(config, key, default_value):
    """
    获取缓存数据
    """
    if config.cache_data:
        return config.cache_data.get(key, default_value)

    return default_value


def add_collect_meta_cache_data(apps, schema_editor):
    CollectConfigMeta = apps.get_model("monitor_web", "CollectConfigMeta")
    PluginVersionHistory = apps.get_model("monitor_web", "PluginVersionHistory")
    configs = CollectConfigMeta.objects.all()
    plugin_release_version = {}
    for config in configs:

        config = update_cache_data_item(config, "status", config_status(config))
        config = update_cache_data_item(config, "task_status", task_status(config))

        if task_status(config) == "STOPPED" or get_cache_data(config, "total_instance_count", 0) == 0:
            config = update_cache_data_item(config, "need_upgrade", False)
        else:
            config_version = plugin_release_version.get(config.plugin.plugin_id)
            if not config_version:
                config_version = PluginVersionHistory.objects.filter(stage="RELEASE").last().config_version
                plugin_release_version[config.plugin.plugin_id] = config_version
            config = update_cache_data_item(
                config, "need_upgrade", config.deployment_config.plugin_version.config_version < config_version
            )
        config.save(update_fields=["cache_data"])


class Migration(migrations.Migration):
    dependencies = [
        ("monitor_web", "0051_add_linux_aarch64"),
    ]

    operations = [migrations.RunPython(add_collect_meta_cache_data)]
