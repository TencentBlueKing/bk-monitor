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

from apm_web.strategy.serializers import AlgorithmSerializer, DetectSerializer, BaseAppStrategyTemplateRequestSerializer
from apm_web.strategy.constants import StrategyTemplateCategory, StrategyTemplateMonitorType, StrategyTemplateType


class BuiltinStrategyTemplateSerializer(BaseAppStrategyTemplateRequestSerializer):
    class QueryTemplateSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        name = serializers.CharField(label=_("查询模板名称"))

    code = serializers.CharField(label=_("策略模板代号"), max_length=128)
    name = serializers.CharField(label=_("策略模板名称"), max_length=128)
    type = serializers.ChoiceField(
        label=_("策略模板类型"),
        choices=StrategyTemplateType.choices(),
        default=StrategyTemplateType.BUILTIN_TEMPLATE.value,
    )
    system = serializers.CharField(label=_("模板类型"), max_length=64)
    category = serializers.ChoiceField(
        label=_("策略模板分类"),
        choices=StrategyTemplateCategory.choices(),
        default=StrategyTemplateCategory.DEFAULT.value,
    )
    monitor_type = serializers.ChoiceField(
        label=_("监控类型"),
        choices=StrategyTemplateMonitorType.choices(),
        default=StrategyTemplateMonitorType.DEFAULT.value,
    )
    detect = DetectSerializer(label=_("判断条件"))
    algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer())
    user_group_ids = serializers.ListField(
        label=_("告警用户组 ID 列表"), child=serializers.IntegerField(min_value=1), min_length=1
    )

    query_template = QueryTemplateSerializer(label=_("查询模板"))
    context = serializers.DictField(label=_("查询模板的变量上下文"), default={})

    create_user = serializers.CharField(label=_("创建人"), max_length=32, default="system")
    update_user = serializers.CharField(label=_("最后修改人"), max_length=32, default="system")
