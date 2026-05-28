"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Issue 合并/拆分功能单测：覆盖 Resolver fast-path noop + 异常类 + content JSON 格式。
"""

import pytest


class TestSplitReasonsOptional:
    """拆分依据 reasons 改为非必填：缺省 / 空列表均通过校验，validated_data 兜底为 []。

    下游 bulk_reset_for_split（reasons or []）、模型 split_reasons（null=True）、读侧
    split_info（split_reasons or []）本就容忍空，故只需放开两处 serializer。
    """

    # 合法 Issue ID：前 10 位为时间戳（IssueIDField → IssueDocument.parse_timestamp_by_id）
    VALID_ID = "1716000000abcdef01"

    @pytest.mark.skip(
        reason="跨层耦合：kernel_api.views.v4.issue 在 import 链上会 transitively 引入 "
        "alarm_backends.service.scheduler（模块级读取 worker-only 配置 DEFAULT_CRONTAB / "
        "ACTION_TASK_CRONTAB 等），纯 web/api 角色无法完成 import。待 feature owner 将该 import "
        "改为惰性或提供全栈测试配置后移除 skip。web 侧等价校验见 fta_web 的 "
        "test_web_split_serializer_reasons_optional。"
    )
    def test_api_split_serializer_reasons_optional(self):
        from kernel_api.views.v4.issue import SplitResource

        # 缺省 reasons
        s = SplitResource.RequestSerializer(
            data={"bk_biz_id": 2, "member_issue_id": self.VALID_ID, "operator": "alice"}
        )
        assert s.is_valid(), s.errors
        assert s.validated_data["reasons"] == []

        # 空列表 reasons
        s2 = SplitResource.RequestSerializer(
            data={"bk_biz_id": 2, "member_issue_id": self.VALID_ID, "reasons": [], "operator": "alice"}
        )
        assert s2.is_valid(), s2.errors
        assert s2.validated_data["reasons"] == []

        # 传入 reasons 仍正常
        s3 = SplitResource.RequestSerializer(
            data={"bk_biz_id": 2, "member_issue_id": self.VALID_ID, "reasons": ["误合并"], "operator": "alice"}
        )
        assert s3.is_valid(), s3.errors
        assert s3.validated_data["reasons"] == ["误合并"]
