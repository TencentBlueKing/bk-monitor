# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkm_ipchooser.serializers import base


class ExecuteDynamicGroupSer(base.ScopeSelectorBaseSer, base.PaginationSer):
    meta = base.ScopeSer(help_text=_("Meta元数据"), required=False)
    id = serializers.CharField(label=_("动态分组ID"), required=True)


class DynamicGroupSer(serializers.Serializer):
    meta = base.ScopeSer(help_text=_("Meta元数据"), required=False)
    id = serializers.CharField(label=_("动态分组ID"), required=True)


class ListDynamicGroupSer(base.ScopeSelectorBaseSer):
    dynamic_group_list = serializers.ListField(child=DynamicGroupSer(), required=False, default=[])


class AgentStatistiscSer(base.ScopeSelectorBaseSer):
    dynamic_group_list = serializers.ListField(child=DynamicGroupSer(), required=True)
