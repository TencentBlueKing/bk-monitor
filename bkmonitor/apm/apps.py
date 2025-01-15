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

import settings


def migrate_apm_metric_dimension(sender, **kwargs):
    from apm.models import ApmMetricDimension

    ApmMetricDimension.init_builtin_config()


class ApmApiConfig(AppConfig):
    name = "apm"
    verbose_name = "apm"
    label = "apm"

    def ready(self):
        from apm.core.discover.base import DiscoverContainer

        # Trace 数据拓扑发现器 ↓
        from apm.core.discover.endpoint import EndpointDiscover
        from apm.core.discover.host import HostDiscover
        from apm.core.discover.instance import InstanceDiscover
        from apm.core.discover.node import NodeDiscover
        from apm.core.discover.relation import RelationDiscover
        from apm.core.discover.remote_service_relation import (
            RemoteServiceRelationDiscover,
        )
        from apm.core.discover.root_endpoint import RootEndpointDiscover
        from constants.apm import TelemetryDataType

        DiscoverContainer.register(TelemetryDataType.TRACE.value, EndpointDiscover)
        DiscoverContainer.register(TelemetryDataType.TRACE.value, HostDiscover)
        DiscoverContainer.register(TelemetryDataType.TRACE.value, InstanceDiscover)
        DiscoverContainer.register(TelemetryDataType.TRACE.value, NodeDiscover)
        DiscoverContainer.register(TelemetryDataType.TRACE.value, RelationDiscover)
        DiscoverContainer.register(TelemetryDataType.TRACE.value, RemoteServiceRelationDiscover)
        DiscoverContainer.register(TelemetryDataType.TRACE.value, RootEndpointDiscover)

        # Metric 数据拓扑发现器 ↓
        from apm.core.discover.metric.service import (
            ServiceDiscover as MetricServiceDiscover,
        )

        DiscoverContainer.register(TelemetryDataType.METRIC.value, MetricServiceDiscover)

        # Profile 数据拓扑发现器 ↓
        from apm.core.discover.profile.service import (
            ServiceDiscover as ProfileServiceDiscover,
        )

        DiscoverContainer.register(TelemetryDataType.PROFILING.value, ProfileServiceDiscover)

        if "migrate" in sys.argv and settings.ENVIRONMENT != "development":
            post_migrate.connect(migrate_apm_metric_dimension, sender=self)
