# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import sys

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def migrate_apm_metric_dimension(sender, **kwargs):
    from apm.models import ApmMetricDimension

    ApmMetricDimension.init_builtin_config()


class ApmApiConfig(AppConfig):
    name = "apm"
    verbose_name = "apm"
    label = "apm"

    def ready(self):
        # 注册APM发现器
        from apm.core.discover.base import DiscoverBase
        from apm.core.discover.endpoint import EndpointDiscover
        from apm.core.discover.host import HostDiscover
        from apm.core.discover.instance import InstanceDiscover
        from apm.core.discover.node import NodeDiscover
        from apm.core.discover.relation import RelationDiscover
        from apm.core.discover.remote_service_relation import (
            RemoteServiceRelationDiscover,
        )
        from apm.core.discover.root_endpoint import RootEndpointDiscover

        DiscoverBase.register(EndpointDiscover)
        DiscoverBase.register(HostDiscover)
        DiscoverBase.register(InstanceDiscover)
        DiscoverBase.register(NodeDiscover)
        DiscoverBase.register(RelationDiscover)
        DiscoverBase.register(RemoteServiceRelationDiscover)
        DiscoverBase.register(RootEndpointDiscover)

        # 注册Profile发现器
        from apm.core.discover.profile.base import DiscoverContainers
        from apm.core.discover.profile.service import ServiceDiscover

        DiscoverContainers.register(ServiceDiscover)

        if "migrate" in sys.argv:
            post_migrate.connect(migrate_apm_metric_dimension, sender=self)
