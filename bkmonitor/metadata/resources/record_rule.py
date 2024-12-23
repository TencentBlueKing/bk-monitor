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

from rest_framework import serializers

from core.drf_resource import Resource
from core.errors.api import BKAPIError
from metadata.models.record_rule.rules import RecordRule
from metadata.models.record_rule.service import BkDataFlow, RecordRuleService
from metadata.models.record_rule.utils import generate_rule_config

logger = logging.getLogger("metadata")


class CreatePrecomputationRecordResource(Resource):
    """
    创建并启动预计算任务
    """

    class RequestSerializer(serializers.Serializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        record_name = serializers.CharField(required=True, label="指标分组名称")
        expr = serializers.CharField(required=True, label="预计算指标表达式")
        metric_name = serializers.CharField(required=True, label="指标名称")
        interval = serializers.CharField(required=False, label="预计算周期", default="1m")

    def perform_request(self, validated_request_data):
        space_type = validated_request_data.get("space_type")
        space_id = validated_request_data.get("space_id")
        record_name = validated_request_data.get("record_name")
        expr = validated_request_data.get("expr")
        metric_name = validated_request_data.get("metric_name")
        interval = validated_request_data.get("interval")

        # 生成预计算规则
        rule_config = generate_rule_config(expr, metric_name, record_name, interval)
        logger.info("CreatePrecomputationRecordResource:generated rule_config: %s" % rule_config)

        # 创建预计算实例
        try:
            service = RecordRuleService(
                space_type=space_type, space_id=space_id, record_name=record_name, rule_config=rule_config
            )
            service.create_record_rule()
        except Exception as e:
            logger.error("CreatePrecomputationRecordResource: create record rule service error: %s" % e)
            raise e

        # 获取预计算创建的table_id
        table_id = RecordRule.objects.get(record_name=record_name).table_id

        # 创建并启动预计算任务
        flow = BkDataFlow(space_type, space_id, table_id)
        res = flow.start_flow()
        logger.info("CreatePrecomputationRecordResource: start flow result: %s" % res)
        if not res:  # 若res为False，说明预计算任务启动失败
            raise BKAPIError("CreatePrecomputationRecordResource: start flow error")
        # 预计算指标检索表达式
        new_expr = f"bkmonitor_{space_type}_{space_id}_tsdb:{table_id}:{metric_name}"
        return {"new_expr": new_expr}
