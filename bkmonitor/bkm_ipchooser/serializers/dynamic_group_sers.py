# -*- coding: utf-8 -*-
from rest_framework import serializers

from bkm_ipchooser.serializers import base


class ExecuteDynamicGroupSer(base.ScopeSelectorBaseSer, base.PaginationSer):
    meta = base.ScopeSer(help_text="Meta元数据", required=False)
    id = serializers.CharField(label="动态分组ID", required=True)


class DynamicGroupSer(serializers.Serializer):
    meta = base.ScopeSer(help_text="Meta元数据", required=False)
    id = serializers.CharField(label="动态分组ID", required=True)


class ListDynamicGroupSer(base.ScopeSelectorBaseSer):
    dynamic_group_list = serializers.ListField(child=DynamicGroupSer(), required=False, default=[])


class AgentStatisticsSer(base.ScopeSelectorBaseSer):
    dynamic_group_list = serializers.ListField(child=DynamicGroupSer(), required=True)
