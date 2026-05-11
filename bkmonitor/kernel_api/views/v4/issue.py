"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from constants.issue import IssuePriority, IssueStatus
from core.drf_resource import Resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from bkmonitor.documents.issue import IssueDocument
from fta_web.issue.resources import IssueIDField


class AssignResource(Resource):
    """指派/改派 Issue 负责人"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        assignee = serializers.ListField(label="负责人列表", child=serializers.CharField(min_length=1), min_length=1)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        assignee = validated_request_data["assignee"]
        operator = validated_request_data["operator"]
        if issue.status == IssueStatus.PENDING_REVIEW:
            activities = issue.assign(assignees=assignee, operator=operator)
        else:
            activities = issue.reassign(assignees=assignee, operator=operator)
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "assignee": list(issue.assignee or []),
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class ResolveResource(Resource):
    """标记 Issue 为已解决"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.resolve(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "resolved_time": issue.resolved_time,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class ArchiveResource(Resource):
    """归档 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.archive(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class ReopenResource(Resource):
    """重新打开 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.reopen(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class RestoreResource(Resource):
    """恢复归档 Issue"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.restore(operator=validated_request_data["operator"])
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class UpdatePriorityResource(Resource):
    """修改 Issue 优先级"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        priority = serializers.ChoiceField(
            label="优先级",
            choices=[IssuePriority.P0, IssuePriority.P1, IssuePriority.P2],
        )
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        activities = issue.update_priority(
            priority=validated_request_data["priority"], operator=validated_request_data["operator"]
        )
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "priority": issue.priority,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class AddFollowUpResource(Resource):
    """向 Issue 添加跟进评论"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        issue_id = IssueIDField(label="Issue ID")
        content = serializers.CharField(label="跟进内容", min_length=1)
        operator = serializers.CharField(label="操作人")

    def perform_request(self, validated_request_data):
        issue = IssueDocument.get_issue_or_raise(
            validated_request_data["issue_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        content = validated_request_data["content"]
        operator = validated_request_data["operator"]
        activities = issue.add_comment(content=content, operator=operator)
        return {
            "bk_biz_id": issue.bk_biz_id,
            "issue_id": issue.id,
            "status": issue.status,
            "update_time": issue.update_time,
            "activities": activities or [],
        }


class IssueViewSet(ResourceViewSet):
    """
    Issue 接口
    """

    resource_routes = [
        # 指派或改派 issue 负责人
        ResourceRoute("POST", AssignResource(), endpoint="assign"),
        # 标记 issue 已解决
        ResourceRoute("POST", ResolveResource(), endpoint="resolve"),
        # 归档 issue
        ResourceRoute("POST", ArchiveResource(), endpoint="archive"),
        # 重新打开已解决 issue
        ResourceRoute("POST", ReopenResource(), endpoint="reopen"),
        # 恢复归档 issue
        ResourceRoute("POST", RestoreResource(), endpoint="restore"),
        # 修改 issue 优先级
        ResourceRoute("POST", UpdatePriorityResource(), endpoint="update_priority"),
        # 向 Issue 添加跟进评论
        ResourceRoute("POST", AddFollowUpResource(), endpoint="add_follow_up"),
    ]
