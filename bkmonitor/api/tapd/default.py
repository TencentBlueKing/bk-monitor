"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64

from django.conf import settings
from rest_framework import serializers

from core.drf_resource import APIResource
from core.errors.api import BKAPIError


class TapdAPIResource(APIResource):
    base_url = settings.TAPD_API_BASE_URL
    # 模块名
    module_name = "tapd"
    INSERT_BK_USERNAME_TO_REQUEST_DATA = False
    IS_STANDARD_FORMAT = False

    def get_headers(self):
        credentials = f"{settings.TAPD_APP_ID}:{settings.TAPD_APP_SECRET}"
        encoded_str = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_str}"}

        return headers

    def render_response_data(self, validated_request_data, response_data):
        status = response_data.get("status") if isinstance(response_data, dict) else None
        if str(status) != "1":
            error_data = {
                "code": status,
                "message": response_data.get("info", "") if isinstance(response_data, dict) else response_data,
                "data": response_data.get("data") if isinstance(response_data, dict) else response_data,
            }
            self.report_api_failure_metric(error_code=status, exception_type=BKAPIError.__name__)
            raise BKAPIError(system_name=self.module_name, url=self.action, result=error_data)

        return response_data.get("data")


class GetGrantedWorkspacesResource(TapdAPIResource):
    """
    获取已授权的项目列表
    """

    action = "app_auth/get_granted_workspaces"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID", required=False)
        type = serializers.IntegerField(
            label="安装类型", required=False, help_text="0: 应用商店安装, 1: 测试安装, 2: 插件安装"
        )
        created = serializers.DateTimeField(label="创建时间", required=False)
        limit = serializers.IntegerField(label="返回数量限制", required=False, default=30, min_value=1, max_value=200)
        page = serializers.IntegerField(label="页码", required=False, default=1)
        order = serializers.CharField(
            label="排序规则",
            required=False,
            help_text="排序规则，格式：字段名 ASC或者DESC，然后urlencode。例如：按创建时间逆序：order=created%20desc",
        )
        fields = serializers.CharField(
            label="设置获取的字段",
            required=False,
            help_text="设置获取的字段，多个字段间以逗号隔开。例如：fields=id,name,created",
        )


class GetWorkspaceInfoResource(TapdAPIResource):
    """
    根据项目ID（workspace_id）获取项目信息
    """

    action = "workspaces/get_workspace_info"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")


class AddStoryResource(TapdAPIResource):
    """
    新建tapd需求单据
    """

    action = "stories"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        name = serializers.CharField(label="需求标题")
        description = serializers.CharField(label="需求详细描述")
        owner = serializers.CharField(label="处理人", help_text="支持多成员，如：aaa;bbb;")
        priority_label = serializers.CharField(label="优先级", required=False)
        cc = serializers.CharField(label="抄送人", required=False)
        iteration_id = serializers.CharField(label="迭代ID", required=False)
        module = serializers.CharField(label="模块", required=False)
        effort = serializers.CharField(label="预估工时", required=False)
        source = serializers.CharField(label="需求来源", required=False)
        label = serializers.CharField(label="标签", required=False, help_text="多个以英文竖线分隔")


class AddBugResource(TapdAPIResource):
    """
    新建tapd缺陷单据
    """

    action = "bugs"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        title = serializers.CharField(label="缺陷标题")
        description = serializers.CharField(label="缺陷详细描述")
        current_owner = serializers.CharField(label="处理人", help_text="支持多成员，如：aaa;bbb;")
        priority_label = serializers.CharField(label="优先级", required=False)
        severity = serializers.CharField(label="严重程度", required=False)
        cc = serializers.CharField(label="抄送人", required=False)
        iteration_id = serializers.CharField(label="迭代ID", required=False)
        module = serializers.CharField(label="模块", required=False)
        effort = serializers.CharField(label="预估工时", required=False)
        source = serializers.CharField(label="缺陷来源", required=False)
        label = serializers.CharField(label="标签", required=False, help_text="多个以英文竖线分隔")


class AddTaskResource(TapdAPIResource):
    """
    新建tapd任务单据
    """

    action = "tasks"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        name = serializers.CharField(label="任务标题")
        description = serializers.CharField(label="任务详细描述")
        owner = serializers.CharField(label="处理人", help_text="支持多成员，如：aaa;bbb;")
        priority_label = serializers.CharField(label="优先级", required=False)
        cc = serializers.CharField(label="抄送人", required=False)
        iteration_id = serializers.CharField(label="迭代ID", required=False)
        effort = serializers.CharField(label="预估工时", required=False)
        label = serializers.CharField(label="标签", required=False, help_text="多个以英文竖线分隔")


class AddWebhookSettingResource(TapdAPIResource):
    """
    新建Webhook配置

    events 取值说明（可写多个，使用逗号分隔）：
      - launchform::create            : 发布评审创建
      - launchform::update            : 发布评审更新
      - bug::create                   : 缺陷创建
      - bug::update                   : 缺陷更新
      - bug::delete                   : 缺陷删除
      - story::create                 : 需求创建
      - story::update                 : 需求更新
      - story::delete                 : 需求删除
      - story::bug_link               : 需求关联缺陷
      - story::bug_unlink             : 需求解除关联缺陷
      - task::create                  : 任务创建
      - task::update                  : 任务更新
      - task::delete                  : 任务删除
      - release::create               : 发布计划创建
      - release::update               : 发布计划更新
      - release::delete               : 发布计划删除
      - branch::relate                : 需求缺陷任务绑定Git分支
      - branch::unrelate              : 需求缺陷任务解除绑定Git分支
      - story_comment::add            : 需求评论添加
      - story_comment::update         : 需求评论更新
      - story_comment::delete         : 需求评论删除
      - bug_comment::add              : 缺陷评论添加
      - bug_comment::update           : 缺陷评论更新
      - bug_comment::delete           : 缺陷评论删除
      - task_comment::add             : 任务评论添加
      - task_comment::update          : 任务评论更新
      - task_comment::delete          : 任务评论删除
      - iteration::create              : 迭代创建
      - iteration::update              : 迭代更新
      - iteration::delete              : 迭代删除
      - workitem_time_relation::bind   : 前后置对象绑定
      - workitem_time_relation::unbind : 前后置对象解绑
    """

    action = "webhook_settings"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        url = serializers.CharField(
            label="接收 Webhook 请求的URL",
            help_text="devcloud地址如使用端口号支持80，443，8080，8081，其他需要申请网络策略",
        )
        events = serializers.CharField(label="事件", help_text="多个事件以逗号分隔，如：story::create,story::update")
        content_type = serializers.ChoiceField(
            label="数据格式",
            choices=["json", "form"],
            required=False,
            default="json",
            help_text="json: json格式(默认); form: application/x-www-form-urlencoded形式，如 key1=value1&key2=value2",
        )
        secret = serializers.CharField(
            label="验证密码", required=False, help_text="非必选，给接入方验证请求是否来自 TAPD"
        )
        owner = serializers.CharField(label="配置负责人", required=False)
        rio_token = serializers.CharField(label="应用网关token", required=False)


class GetStoryTemplateListResource(TapdAPIResource):
    """
    获取需求模板列表
    """

    action = "stories/template_list"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        workitem_type_id = serializers.IntegerField(label="需求类别ID", required=False)


class GetBugTemplateListResource(TapdAPIResource):
    """
    获取缺陷模板列表
    """

    action = "bugs/template_list"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")


class GetDefaultStoryTemplateResource(TapdAPIResource):
    """
    获取指定需求模板的所有字段
    """

    action = "stories/get_default_story_template"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        template_id = serializers.IntegerField(label="模板ID")
        use_priority_label = serializers.IntegerField(
            label="是否替换优先级字段为priority_label", default=1, required=False
        )


class GetStoryFieldsLableResource(TapdAPIResource):
    """
    获取需求所有字段的中英文
    """

    action = "stories/get_fields_lable"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")


class GetDefaultBugTemplateResource(TapdAPIResource):
    """
    获取指定缺陷模板的所有字段
    """

    action = "bugs/get_default_bug_template"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        template_id = serializers.IntegerField(label="模板ID")
        use_priority_label = serializers.IntegerField(
            label="是否替换优先级字段为priority_label", default=1, required=False
        )


class GetBugFieldsLableResource(TapdAPIResource):
    """
    获取缺陷所有字段的中英文
    """

    action = "bugs/get_fields_lable"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")


class GetStoriesResource(TapdAPIResource):
    """
    获取需求列表
    """

    action = "stories"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        id = serializers.CharField(label="ID", required=False, help_text="支持多ID查询，多个以逗号分隔")
        name = serializers.CharField(label="标题", required=False, help_text="支持模糊匹配")
        priority_label = serializers.CharField(label="优先级", required=False)
        limit = serializers.IntegerField(label="返回数量限制", required=False, default=30, min_value=1, max_value=200)
        page = serializers.IntegerField(label="页码", required=False, default=1, min_value=1)
        order = serializers.CharField(
            label="排序规则",
            required=False,
            help_text="排序规则，格式：字段名 ASC或者DESC，然后urlencode。例如：按创建时间逆序：order=created%20desc",
        )
        fields = serializers.CharField(
            label="设置获取的字段", required=False, help_text="设置获取的字段，多个字段间以','逗号隔开"
        )


class GetBugsResource(TapdAPIResource):
    """
    获取缺陷列表
    """

    action = "bugs"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        id = serializers.CharField(label="ID", required=False, help_text="支持多ID查询，多个以逗号分隔")
        title = serializers.CharField(label="标题", required=False, help_text="支持模糊匹配")
        priority_label = serializers.CharField(label="优先级", required=False)
        severity = serializers.CharField(label="严重程度", required=False, help_text="支持枚举查询，多个以逗号分隔")
        limit = serializers.IntegerField(label="返回数量限制", required=False, default=30, min_value=1, max_value=200)
        page = serializers.IntegerField(label="页码", required=False, default=1, min_value=1)
        order = serializers.CharField(
            label="排序规则",
            required=False,
            help_text="排序规则，格式：字段名 ASC或者DESC，然后urlencode。例如：按创建时间逆序：order=created%20desc",
        )
        fields = serializers.CharField(
            label="设置获取的字段", required=False, help_text="设置获取的字段，多个字段间以','逗号隔开"
        )


class GetTasksResource(TapdAPIResource):
    """
    获取任务列表
    """

    action = "tasks"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
        id = serializers.CharField(label="ID", required=False, help_text="支持多ID查询，多个以逗号分隔")
        name = serializers.CharField(label="任务标题", required=False, help_text="支持模糊匹配")
        priority_label = serializers.CharField(label="优先级", required=False)
        limit = serializers.IntegerField(label="返回数量限制", required=False, default=30, min_value=1, max_value=200)
        page = serializers.IntegerField(label="页码", required=False, default=1, min_value=1)
        order = serializers.CharField(
            label="排序规则",
            required=False,
            help_text="排序规则，格式：字段名 ASC或者DESC，然后urlencode。例如：按创建时间逆序：order=created%20desc",
        )
        fields = serializers.CharField(
            label="设置获取的字段", required=False, help_text="设置获取的字段，多个字段间以','逗号隔开"
        )


class GetStoryFieldsInfo(TapdAPIResource):
    """
    获取需求所有字段信息
    """

    action = "stories/get_fields_info"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")


class GetBugFieldsInfo(TapdAPIResource):
    """
    获取缺陷所有字段信息
    """

    action = "bugs/get_fields_info"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        workspace_id = serializers.IntegerField(label="项目ID")
