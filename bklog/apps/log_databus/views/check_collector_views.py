# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import os

from packaging.utils import _

from apps.generic import APIViewSet
from apps.log_databus.constants import CheckStatusEnum
from apps.log_databus.handlers.check_collector.base import CheckCollectorRecord
from apps.log_databus.handlers.check_collector.checker.path_check import LogPathChecker
from apps.log_databus.handlers.check_collector.handler import async_run_check, async_atomic_check
from apps.log_databus.serializers import (
    CheckCollectorSerializer,
    GetCollectorCheckResultSerializer, CheckCollectorAtomicResultSerializer,
)
from apps.utils.drf import list_route
from rest_framework import serializers
from rest_framework.response import Response
from apps.log_databus.models import CollectorConfig


class CheckCollectorViewSet(APIViewSet):
    serializer_class = serializers.Serializer
    HANDLER_NAME = _("启动入口")

    @list_route(methods=["POST"], url_path="get_check_collector_infos")
    def get_check_collector_infos(self, request, *args, **kwargs):
        data = self.params_valid(GetCollectorCheckResultSerializer)
        record = CheckCollectorRecord(**data)
        result = {"infos": record.get_infos(), "finished": record.finished}
        return Response(result)

    @list_route(methods=["POST"], url_path="run_check_collector")
    def run_check_collector(self, request, *args, **kwargs):
        data = self.params_valid(CheckCollectorSerializer)
        key = CheckCollectorRecord.generate_check_record_id(**data)
        CheckCollectorRecord(check_record_id=key).append_init()
        async_run_check.delay(**data)
        return Response({"check_record_id": key})

    """
        原子日志链路检查接口
        参数:
            bk_data_id
            hosts
    """

    @list_route(methods=["POST"], url_path="atomic_check_collector")
    def atomic_check_collector(self, request, *args, **kwargs):
        data = self.params_valid(CheckCollectorAtomicResultSerializer)
        bk_data_id = data.get("bk_data_id")
        assert bk_data_id is not None, "bk_data_id不能为空"
        collector_config = CollectorConfig.objects.get(bk_data_id=bk_data_id)
        key = CheckCollectorRecord.generate_check_record_id(
            collector_config_id=collector_config.collector_config_id,
            hosts=data.get("hosts")
        )
        record = CheckCollectorRecord(check_record_id=key)
        record.append_init()
        # 同步执行日志路径检查
        path_check = LogPathChecker(
            collector_config_id=collector_config.collector_config_id,
            check_collector_record=record
        )
        path_check.run()
        # 异步执行AgentChecker或BkunifylogbeatChecker
        task = async_atomic_check.delay(
            collector_config_id=collector_config.collector_config_id,
            hosts=data.get("hosts"),
            check_record_id=key
        )
        result = {"infos": record.get_infos(),
                  "finished": record.finished,
                  "msg": "日志路径检测完成，开始异步检测async_atomic_check，task_id:" + str(task.id)}
        record.change_status(CheckStatusEnum.STARTED.value)
        return Response(result)
