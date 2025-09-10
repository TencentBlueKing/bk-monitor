"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.models.strategy import AlgorithmModel
from bkmonitor.strategy.serializers import allowed_threshold_method

from . import constants


class DetectSerializer(serializers.Serializer):
    """判断条件"""

    recovery_check_window = serializers.IntegerField(label=_("恢复检查窗口"), min_value=1)
    trigger_check_window = serializers.IntegerField(label=_("触发检查窗口"), min_value=1)
    trigger_count = serializers.IntegerField(label=_("触发次数"), min_value=1)


class UserGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("用户组 ID"), min_value=1)
    name = serializers.CharField(label=_("用户组名称"))


class AlgorithmSerializer(serializers.Serializer):
    """检测算法"""

    level = serializers.ChoiceField(label=_("级别"), choices=constants.ThresholdLevel.choices())
    method = serializers.ChoiceField(label=_("检测方法"), choices=allowed_threshold_method)
    threshold = serializers.FloatField(label=_("阈值"))
    type = serializers.ChoiceField(
        label=_("检测算法类型"),
        choices=AlgorithmModel.ALGORITHM_CHOICES,
        default=AlgorithmModel.AlgorithmChoices.Threshold,
    )


class BaseAppStrategyTemplateRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名称"), max_length=50)
    is_mock = serializers.BooleanField(label=_("是否为 mock 数据"), default=True)


class BaseServiceStrategyTemplateRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    service_name = serializers.CharField(label=_("服务名称"))


class StrategyTemplatePreviewRequestSerializer(BaseServiceStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateDetailRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateApplyRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    """策略模板下发"""

    class GlobalSerializer(serializers.Serializer):
        detect = DetectSerializer(required=False)
        user_group_ids = serializers.ListField(
            label=_("用户组 ID 列表"), child=serializers.IntegerField(min_value=1), required=False
        )

    class ExtraSerializer(GlobalSerializer):
        strategy_template_id = serializers.IntegerField(label=_("策略模板 ID"), min_value=1)
        service_name = serializers.CharField(label=_("服务名称"))
        context = serializers.DictField(label=_("查询模板的变量上下文"), required=False)
        algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer(), required=False)

    service_names = serializers.ListField(label=_("服务名称列表"), child=serializers.CharField())
    strategy_template_ids = serializers.ListField(
        label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1)
    )
    extra = serializers.ListField(label=_("额外编辑的参数"), child=ExtraSerializer(), default=[], allow_empty=True)
    _global = GlobalSerializer(label=_("批量修改的参数"), source="global", default={})


class StrategyTemplateCheckRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    service_names = serializers.ListField(
        label=_("服务名称列表"), child=serializers.CharField(), default=[], allow_empty=True
    )
    strategy_template_ids = serializers.ListField(
        label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1), default=[], allow_empty=True
    )


class StrategyTemplateListRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(label=_("策略模板名称"))
    algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer())
    detect = DetectSerializer(label=_("判断条件"))
    user_group_list = serializers.ListField(label=_("用户组列表"), child=UserGroupSerializer())
    context = serializers.DictField(label=_("查询模板的变量上下文"), default={})
    is_enabled = serializers.BooleanField(label=_("是否启用"))
    is_auto_apply = serializers.BooleanField(label=_("是否自动下发"))


class StrategyTemplateUpdateRequestSerializer(
    StrategyTemplateUpdateSerializer, BaseAppStrategyTemplateRequestSerializer
):
    pass


class StrategyTemplateCloneRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    edit_data = StrategyTemplateUpdateSerializer(label=_("克隆模板编辑数据"))


class StrategyTemplateBatchPartialUpdateRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    class EditDataSerializer(serializers.Serializer):
        user_group_list = serializers.ListField(label=_("用户组列表"), child=UserGroupSerializer(), required=False)
        algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer(), required=False)
        is_enabled = serializers.BooleanField(label=_("是否启用"), required=False)
        is_auto_apply = serializers.BooleanField(label=_("是否自动下发"), required=False)

    ids = serializers.ListField(label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1))
    edit_data = EditDataSerializer(label=_("批量编辑数据"))


class StrategyTemplateCompareRequestSerializer(BaseServiceStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateAlertsRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    ids = serializers.ListField(label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1))
    need_strategies = serializers.BooleanField(label=_("是否需要策略列表"), default=False)


class StrategyTemplateDeleteRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    pass
