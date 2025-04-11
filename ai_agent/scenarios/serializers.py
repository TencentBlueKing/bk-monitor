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
import json

from rest_framework import serializers


class ScenariosChatSerializer(serializers.Serializer):
    """
    场景问答交互协议
    {
        # 指令
        "command": "",
        # 上下文列表
        "contexts": [],
        # 用户输入
        "input": "",
        # 流式返回
        "stream": true,
        # 会话ID，历史由后端保存
        "session_id": "",
        # 请求ID，可以与traceid对齐，代表本次请求，可用于请求重放，避免请求叠加
        "request_id": ""
    }
    """

    COMMAND_CHOICES = (
        ("chat", "聊天"),
        ("query", "问答"),
        ("explain", "解释"),
        ("guide", "指引"),
    )
    command = serializers.ChoiceField(choices=COMMAND_CHOICES, label="指令")
    contexts = serializers.ListField(child=serializers.DictField(), required=False, label="上下文列表", default=[])
    input = serializers.CharField(required=True, label="用户输入")
    stream = serializers.BooleanField(required=False, default=True, label="流式返回开关")
    session_id = serializers.CharField(required=False, label="会话ID")
    request_id = serializers.CharField(required=False, label="请求ID")

    def validate_input(self, input_str):
        """
        input_str 转换成格式化 数据
        """
        try:
            input_str = json.loads(input_str)
        except Exception:
            input_str = {"query": input_str}

        return input_str
