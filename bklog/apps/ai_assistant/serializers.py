# -*- coding: utf-8 -*-
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
    chat_context = serializers.ListField(label=_("聊天上下文"), child=ContextSerializer(), allow_empty=True, default=list)
    stream = serializers.BooleanField(label=_("是否流式返回"), default=True)
    log_context_count = serializers.IntegerField(label=_("引用日志上下文条数"), default=0, min_value=0, max_value=50)
    type = serializers.ChoiceField(label=_("聊天类型"), choices=["log_interpretation"], required=True)
