from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkm_space.serializers import SpaceUIDField


class ContextSerializer(serializers.Serializer):
    role = serializers.ChoiceField(required=True, choices=["user", "assistant"])
    content = serializers.CharField(required=True)


class ChatSerializer(serializers.Serializer):
    """
    AI 助手聊天
    """

    space_uid = SpaceUIDField(label=_("空间ID"), required=True)
    bk_biz_id = serializers.IntegerField(label=_("业务ID"), required=True)
    index_set_id = serializers.IntegerField(label=_("索引集ID"), required=True)
    log_data = serializers.DictField(label=_("日志内容"), required=True)
    query = serializers.CharField(label=_("当前聊天输入内容"), required=True)
    chat_context = serializers.ListField(
        label=_("聊天上下文"), child=ContextSerializer(), allow_empty=True, default=list
    )
    stream = serializers.BooleanField(label=_("是否流式返回"), default=True)
    log_context_count = serializers.IntegerField(label=_("引用日志上下文条数"), default=0, min_value=0, max_value=50)
    type = serializers.ChoiceField(label=_("聊天类型"), choices=["log_interpretation"], required=True)


class AgentInfoSerializer(serializers.Serializer):
    """
    获取智能体信息
    """

    agent_code = serializers.CharField(label=_("Agent代码"), default=settings.BK_AIDEV_AGENT_APP_CODE)


class CreateChatSessionSerializer(serializers.Serializer):
    """
    创建会话
    """

    session_code = serializers.CharField(label=_("会话代码"))
    session_name = serializers.CharField(label=_("会话名称"))
    agent_code = serializers.CharField(label=_("Agent代码"), default=settings.BK_AIDEV_AGENT_APP_CODE)
    is_temporary = serializers.BooleanField(label="是否是临时会话", required=False, default=False)


class UpdateChatSessionSerializer(serializers.Serializer):
    """
    更新会话
    """

    session_code = serializers.CharField(label=_("会话代码"))
    session_name = serializers.CharField(label=_("会话名称"), required=False)
    model = serializers.CharField(label=_("模型名称"), required=False)
    role_info = serializers.DictField(label=_("角色信息"), required=False)


class CreateChatSessionContentSerializer(serializers.Serializer):
    """
    创建会话内容
    """

    session_code = serializers.CharField(label=_("会话代码"))
    role = serializers.CharField(label=_("角色"))
    content = serializers.CharField(label=_("内容"))
    property = serializers.DictField(label=_("属性"), required=False)


class UpdateChatSessionContentSerializer(serializers.Serializer):
    """
    更新单条会话内容
    """

    session_code = serializers.CharField(label=_("会话代码"))
    id = serializers.CharField(label=_("内容ID"))
    role = serializers.CharField(label=_("角色"))
    content = serializers.CharField(label=_("内容"))
    status = serializers.CharField(label=_("状态"), default="loading")
    property = serializers.DictField(label=_("属性"), required=False)


class GetChatSessionContentsSerializer(serializers.Serializer):
    """
    获取会话内容
    """

    session_code = serializers.CharField(label=_("会话代码"))


class BatchDeleteSessionContentSerializer(serializers.Serializer):
    """
    批量删除会话内容
    """

    ids = serializers.ListField(label=_("内容ID列表"))


class CreateFeedbackSessionContentSerializer(serializers.Serializer):
    """
    创建会话内容反馈
    """

    comment = serializers.CharField(label="评论内容", required=False, allow_blank=True, default="")
    labels = serializers.ListField(label="标签", required=False, allow_empty=True, default=[])
    rate = serializers.IntegerField(label="评分", required=True)
    session_code = serializers.CharField(label="会话代码", required=True)
    session_content_ids = serializers.ListField(label="内容ID列表", required=True)


class GetFeedbackReasonsSessionContentSerializer(serializers.Serializer):
    """
    获取反馈原因列表
    """

    rate = serializers.IntegerField(label="评分", required=True)


class CreateChatCompletionSerializer(serializers.Serializer):
    """
    创建流式会话
    """

    session_code = serializers.CharField(label=_("会话代码"))
    execute_kwargs = serializers.DictField(label=_("执行参数"))
    agent_code = serializers.CharField(label=_("Agent代码"), default=settings.BK_AIDEV_AGENT_APP_CODE)
