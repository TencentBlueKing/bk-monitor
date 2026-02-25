"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging

from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from jinja2.exceptions import TemplateSyntaxError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from bkmonitor.models import ActionConfig, ActionPlugin, UserGroup
from bkmonitor.utils.template import Jinja2Renderer
from constants.action import (
    ALL_CONVERGE_DIMENSION,
    CONVERGE_FUNCTION,
    GLOBAL_BIZ_ID,
    ActionSignal,
    IntervalNotifyMode,
    NoticeChannel,
    NotifyStep,
    VoiceNoticeMode,
)
from constants.alert import EVENT_SEVERITY
from core.errors.api import BKAPIError
from core.errors.strategy import CreateStrategyError

logger = logging.getLogger(__name__)


class ConvergeConditionSlz(serializers.Serializer):
    """套餐收敛"""

    DIMENSION_CHOICE = [(key, value) for key, value in ALL_CONVERGE_DIMENSION.items()]

    dimension = serializers.ChoiceField(help_text="收敛时间窗口", required=True, choices=DIMENSION_CHOICE)
    value = serializers.ListField(child=serializers.CharField(), required=True)


class ConvergeConfigDetailSlz(serializers.Serializer):
    """套餐收敛详情"""

    class ConditionSlz(serializers.Serializer):
        """套餐收敛"""

        DIMENSION_CHOICE = [(key, value) for key, value in ALL_CONVERGE_DIMENSION.items()]

        dimension = serializers.ChoiceField(help_text="收敛时间窗口", required=True, choices=DIMENSION_CHOICE)
        value = serializers.ListField(child=serializers.CharField(), required=True)

    CONVERGE_FUNCTION_CHOICES = [(key, value) for key, value in CONVERGE_FUNCTION.items()]

    is_enabled = serializers.BooleanField(label="是否启用防御", default=True)
    converge_func = serializers.ChoiceField(
        help_text="收敛函数", choices=CONVERGE_FUNCTION_CHOICES, default="skip_when_exceed"
    )
    timedelta = serializers.IntegerField(required=False, help_text="收敛时间窗口", default=60, min_value=0)
    count = serializers.IntegerField(required=False, help_text="收敛数量", default=1, min_value=1)
    condition = serializers.ListField(
        required=False,
        child=ConditionSlz(),
        help_text="收敛条件",
        default=[
            {"dimension": "strategy_id", "value": ["self"]},
        ],
    )


class ConvergeConfigSlz(ConvergeConfigDetailSlz):
    """
    一级收敛：包含二级收敛的内容
    二级收敛的优先级 > 一级收敛
    """

    sub_converge_config = ConvergeConfigDetailSlz(required=False)
    need_biz_converge = serializers.BooleanField(required=False, default=True, help_text="是否需要业务汇总")


class NoiseReduceConfigSlz(serializers.Serializer):
    """
    降噪收敛配置
    """

    is_enabled = serializers.BooleanField(required=False, default=False, help_text="是否开启降噪")
    dimensions = serializers.ListField(child=serializers.CharField(), help_text="降噪的对比维度", required=False)
    count = serializers.IntegerField(help_text="降噪阈值", allow_null=True, required=False)
    unit = serializers.CharField(default="percent")
    timedelta = serializers.IntegerField(default=settings.NOISE_REDUCE_TIMEDELTA, help_text="降噪时间窗口, 单位（min）")

    def run_validation(self, data=empty):
        """
        根据is_enable进行参数是否必填校验
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data
        if data.get("is_enabled") and not (data.get("dimensions") and data.get("count")):
            raise ValidationError(detail=_("已开启降噪，请填写正确的维度信息和降噪阈值"))
        return super().run_validation(data)


class UpgradeConfigSlz(serializers.Serializer):
    is_enabled = serializers.BooleanField(help_text="是否开启", default=False)
    upgrade_interval = serializers.IntegerField(help_text="升级间隔", default=24 * 60)
    user_groups = serializers.ListField(child=serializers.IntegerField(), default=[])

    def run_validation(self, data=empty):
        """
        根据is_enable进行参数是否必填校验
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data
        if data.get("is_enabled") and not (data.get("upgrade_interval") and data.get("user_groups")):
            raise ValidationError(detail=_("已开启通知升级配置，请填写正确的升级时间间隔和升级通知组成员"))
        return super().run_validation(data)


class NoticeWaySerializer(serializers.Serializer):
    name = serializers.CharField(required=True, label="通知方式")
    receivers = serializers.ListField(required=False, label="接收人员人员", default=[], child=serializers.CharField())


class BaseNotifyConfigSerializer(serializers.Serializer):
    # 兼容一段时间
    type = serializers.ListField(child=serializers.CharField(), default=[], allow_empty=True)
    chatid = serializers.CharField(required=False)
    notice_ways = serializers.ListField(child=NoticeWaySerializer(), default=[], allow_empty=True)

    def to_internal_value(self, data):
        # 转换原来的数据结构之新的数据结构
        internal_data = super().to_internal_value(data)

        for notice_way_config in internal_data.get("notice_ways"):
            # 已经存在的数据，表示为新版本接口存储
            notice_way = notice_way_config["name"]
            if notice_way in NoticeChannel.RECEIVER_CHANNELS and not notice_way_config["receivers"]:
                raise ValidationError(
                    detail=_("通知方式为{}的接收人不能为空").format(
                        NoticeChannel.NOTICE_CHANNEL_MAPPING.get(notice_way, notice_way)
                    )
                )
        # 兼容一下老的数据结构
        UserGroup.translate_notice_ways(internal_data)
        return internal_data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # 兼容一下老得数据结构
        UserGroup.translate_notice_ways(data)
        return data


class PollModeConfig(serializers.Serializer):
    need_poll = serializers.BooleanField(required=False, default=True)
    notify_interval = serializers.IntegerField(required=False, min_value=60, default=60 * 60)
    interval_notify_mode = serializers.ChoiceField(
        required=False,
        default=IntervalNotifyMode.STANDARD,
        choices=IntervalNotifyMode.CHOICES,
    )


class TemplateSerializer(serializers.Serializer):
    signal = serializers.ChoiceField(label="触发信号", required=True, choices=ActionSignal.ACTION_SIGNAL_CHOICE)
    message_tmpl = serializers.CharField(required=False, allow_blank=True, default="")
    title_tmpl = serializers.CharField(required=False, allow_blank=True, default="")

    @staticmethod
    def validate_title_tmpl(value):
        try:
            Jinja2Renderer.render(value, {})
        except TemplateSyntaxError:
            raise CreateStrategyError(msg=_("通知自定义标题格式不正确，请重新确认"))
        except Exception as e:
            logger.warning(f"render template error: {e}")
        return value

    @staticmethod
    def validate_message_tmpl(value):
        try:
            Jinja2Renderer.render(value, {})
        except TemplateSyntaxError:
            raise CreateStrategyError(msg=_("通知自定义内容格式不正确，请重新确认"))
        except Exception as e:
            logger.warning(f"render template error: {e}")
        return value


class AlertSerializer(serializers.Serializer):
    class NotifyConfigSerializer(BaseNotifyConfigSerializer):
        level = serializers.ChoiceField(required=True, choices=EVENT_SEVERITY)

    time_range = serializers.CharField(required=True)
    notify_config = serializers.ListField(child=NotifyConfigSerializer())


class ExecutionSerializer(serializers.Serializer):
    class NotifyConfigSerializer(BaseNotifyConfigSerializer):
        phase = serializers.ChoiceField(
            label="执行阶段", required=True, choices=[NotifyStep.BEGIN, NotifyStep.SUCCESS, NotifyStep.FAILURE]
        )

    time_range = serializers.CharField(required=True)
    notify_config = serializers.ListField(label="通知配置", child=NotifyConfigSerializer())


class NotifyActionConfigSlz(PollModeConfig):
    template = TemplateSerializer(label="通知模板配置", many=True)
    # 多通知组对应多个语音接收组，默认并行通知，设置serial则合并接收组后通知一次
    voice_notice = serializers.ChoiceField(
        label="语音通知模式",
        required=False,
        default=VoiceNoticeMode.PARALLEL,
        choices=[(VoiceNoticeMode.PARALLEL, "PARALLEL"), (VoiceNoticeMode.SERIAL, "SERIAL")],
    )


class KVPairSlz(serializers.Serializer):
    """
    通用key value 格式
    {
        "key": "content—type",
        "value": "application/json",
        "desc": "xxxx",
        "is_builtin": True,
        "is_enabled": True
    }
    """

    key = serializers.CharField(required=True, max_length=64)
    value = serializers.CharField(required=False, allow_blank=True, default="")
    desc = serializers.CharField(required=False, allow_blank=True, default="")
    is_builtin = serializers.BooleanField(required=False, default=False)
    is_enabled = serializers.BooleanField(required=False, default=True)


class AuthorizeConfigSlz(serializers.Serializer):
    """
    "authorize": {
        "type": "basic_auth",
        "basic_auth": {
            "username": "robot,email",
            "password": "wwerwrxfsdfsfsdfdsfsdf12312sd"
        },
        "bearer_token": {
            "token": "xxxx"
        }
    },
    """

    auth_type = serializers.ChoiceField(
        required=True,
        choices=[
            ("none", "No Auth"),
            ("basic_auth", "Basic Auth"),
            ("bearer_token", "Bearer Token"),
            ("tencent_auth", _("腾讯云API验证")),
        ],
    )
    auth_config = serializers.DictField(required=False)


class BodyConfigSlz(serializers.Serializer):
    data_type = serializers.ChoiceField(
        required=False,
        default="text",
        choices=[
            ("default", ""),
            ("raw", "raw"),
            ("form_data", "form-data"),
            ("x_www_form_urlencoded", "x-www-form-urlencoded"),
        ],
    )
    params = serializers.ListField(child=KVPairSlz(), required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.ChoiceField(
        choices=[("text", "TEXT"), ("json", "JSON"), ("html", "HTML"), ("xml", "XML")],
        default="text",
        allow_blank=True,
        required=False,
    )


class FailedRetryConfigSlz(serializers.Serializer):
    """
    失败重试机制的设置序列化
    """

    is_enabled = serializers.BooleanField(required=False, default=True)
    timeout = serializers.IntegerField(required=False, min_value=1, max_value=7 * 24 * 60 * 60, default=1)
    max_retry_times = serializers.IntegerField(required=True, min_value=0)
    retry_interval = serializers.IntegerField(required=True, min_value=0)


class HttpCallBackConfigSlz(PollModeConfig):
    method = serializers.ChoiceField(
        required=False, default="GET", choices=[("GET", "GET"), ("POST", "POST"), ("PUT", "PUT")]
    )
    url = serializers.URLField(required=True)
    headers = serializers.ListField(child=KVPairSlz(), default=[])
    authorize = AuthorizeConfigSlz(required=False)
    body = BodyConfigSlz(required=False)
    query_params = serializers.ListField(child=KVPairSlz(), default=[])
    failed_retry = FailedRetryConfigSlz(required=False)

    def is_valid(self, raise_exception=False):
        return super().is_valid(raise_exception=raise_exception)


class ExecuteConfigSlz(serializers.Serializer):
    template_detail = serializers.JSONField(required=True)
    template_id = serializers.CharField(required=False, allow_blank=True)
    timeout = serializers.IntegerField(required=False, default=600, min_value=60, max_value=7 * 24 * 60 * 60)


class ActionConfigBaseInfoSlz(serializers.ModelSerializer):
    plugin_id = serializers.IntegerField(required=True)
    desc = serializers.CharField(required=False, default="", allow_blank=True)
    execute_config = serializers.JSONField(required=True)

    class Meta:
        model = ActionConfig
        fields = "__all__"

    @cached_property
    def all_plugins(self) -> dict[str, dict[str, str]]:
        """
        所有插件信息
        """
        plugin_objs = ActionPlugin.objects.all().values("id", "name", "plugin_type", "plugin_key")
        all_plugin_info = {str(item["id"]): item for item in plugin_objs}
        return all_plugin_info

    def to_representation(self, instance):
        data = super().to_representation(instance)
        plugin = self.all_plugins.get(str(data["plugin_id"]), {})
        data["plugin_name"] = plugin.get("name", "--")
        data["plugin_type"] = plugin.get("plugin_type", "--")
        return data

    @staticmethod
    def validate_execute_config(value):
        if not value:
            return {}

        execute_slz = ExecuteConfigSlz(data=value)
        execute_slz.is_valid(raise_exception=True)
        return execute_slz.data

    def validate_plugin_id(self, value):
        if str(value) not in self.all_plugins:
            raise ValidationError(detail=_("提供的插件类型不正确，请重新确认"))
        return value

    def run_validation(self, data=empty):
        value = super().run_validation(data)
        try:
            value = self.run_execute_detail_validation(value)
        except ValidationError as exc:
            raise ValidationError(detail=serializers.as_serializer_error(exc))
        return json.loads(json.dumps(value))

    def run_execute_detail_validation(self, value):
        """
        针对执行参数的详情进行序列化校验
        """
        if "plugin_id" not in value:
            return value

        detail_slz_class = self.get_detail_slz_class(value.get("plugin_id"))
        if detail_slz_class is None:
            return self.validate_general_template_detail(value)

        detail_slz = detail_slz_class(data=value["execute_config"]["template_detail"])
        detail_slz.is_valid(raise_exception=True)
        value["execute_config"]["template_detail"] = detail_slz.validated_data
        return value

    def validate_general_template_detail(self, value):
        plugin_instance = ActionPlugin.objects.get(id=value["plugin_id"])
        execute_config = value["execute_config"]
        template_id = execute_config.get("template_id")
        if not template_id:
            raise ValidationError(_("选取的周边系统模板ID不能为空"))
        try:
            template_params = plugin_instance.perform_resource_request(
                "detail", **{"template_id": template_id, "bk_biz_id": value["bk_biz_id"]}
            )
        except BKAPIError as error:
            raise ValidationError(
                _("套餐类型为{plugin_name}, 请求对应第三方平台资源({template_id})校验错误{error}").format(
                    plugin_name=plugin_instance.name, template_id=template_id, error=str(error)
                )
            )

        params_keys = {item["key"] for item in template_params}
        value["execute_config"]["template_detail"] = {
            k: v for k, v in value["execute_config"]["template_detail"].items() if k in params_keys
        }
        return value

    def get_detail_slz_class(self, plugin_id):
        """获取详细执行参数的序列化类"""
        plugin_serializers = {"notice": NotifyActionConfigSlz, "webhook": HttpCallBackConfigSlz}
        return plugin_serializers.get(self.all_plugins.get(str(plugin_id), {}).get("plugin_type"))


class ActionConfigDetailSlz(ActionConfigBaseInfoSlz):
    name = serializers.CharField(required=True)
    bk_biz_id = serializers.IntegerField(required=True)

    def validate_name(self, value):
        query_result = ActionConfig.objects.filter(name=value, bk_biz_id__in=[self.initial_data["bk_biz_id"], 0])
        if self.instance:
            query_result = query_result.exclude(id=self.instance.id)
        if query_result.exists():
            raise ValidationError(detail=_("当前套餐名称已经存在，请重新确认"))
        return value

    def validate(self, attrs):
        attrs["hash"] = ""
        attrs["snippet"] = ""
        return attrs


class ActionConfigListSlz(ActionConfigDetailSlz):
    class Meta:
        model = ActionConfig
        fields = (
            "id",
            "plugin_id",
            "desc",
            "name",
            "bk_biz_id",
            "update_user",
            "update_time",
            "is_enabled",
            "app",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["plugin_type"] = self.all_plugins.get(str(data["plugin_id"]), {}).get("plugin_key")
        return data


class ActionConfigPatchSlz(ActionConfigDetailSlz):
    """
    patch 方法更新不需要每个字段进行强制需要
    """

    name = serializers.CharField(required=False)
    plugin_id = serializers.IntegerField(required=False)
    bk_biz_id = serializers.IntegerField(required=False)
    execute_config = serializers.JSONField(required=False)

    def validate(self, attrs):
        # 如果是默认套餐且尝试修改bk_biz_id，则忽略bk_biz_id字段
        if self.instance and int(self.instance.bk_biz_id) == GLOBAL_BIZ_ID and "bk_biz_id" in attrs:
            attrs.pop("bk_biz_id")

        return super().validate(attrs)


class ActionPluginSlz(serializers.ModelSerializer):
    name = serializers.CharField(required=True)
    config_schema = serializers.JSONField(required=False)
    backend_config = serializers.JSONField(required=False)

    class Meta:
        model = ActionPlugin
        fields = (
            "id",
            "name",
            "plugin_type",
            "plugin_key",
            "update_user",
            "update_time",
            "is_enabled",
            "config_schema",
            "backend_config",
        )


class CreateManualActionDataSlz(ActionConfigBaseInfoSlz):
    config_id = serializers.IntegerField(required=True)


class CreateActionDataSerializer(serializers.Serializer):
    """操作请求参数"""

    alert_ids = serializers.ListField(required=True, child=serializers.CharField(), label="告警id列表")
    action_configs = serializers.ListField(required=True, child=CreateManualActionDataSlz(), label="执行的动作信息")


class BatchCreateDataSerializer(serializers.Serializer):
    """
    批量手动创建任务
    """

    operate_data_list = serializers.ListField(required=True, child=CreateActionDataSerializer())
    bk_biz_id = serializers.CharField(required=True, label="业务ID")


class GetCreateParamsSerializer(serializers.Serializer):
    config_ids = serializers.ListField(required=False, child=serializers.IntegerField(), label="套餐ID")
    action_configs = serializers.ListField(required=False, child=serializers.DictField(), label="套餐ID")
    action_id = serializers.IntegerField(required=False, label="事件ID", default=0)
    alert_ids = serializers.ListField(required=True, child=serializers.CharField(), label="告警ID")
    bk_biz_id = serializers.CharField(required=True, label="业务ID")


class CreateDemoActionSlz(ActionConfigBaseInfoSlz):
    name = serializers.CharField(required=False, allow_blank=True)
