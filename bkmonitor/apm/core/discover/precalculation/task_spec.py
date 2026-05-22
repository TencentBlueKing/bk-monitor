"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import Q

from apm.models import ApmApplication, TraceDataSource


@dataclass(frozen=True)
class PreCalculateTaskSpec:
    """一个 trace data_id 对应一个预计算任务。"""

    data_id: str
    trace_result_table_id: str
    apps: tuple[ApmApplication, ...]
    is_shared: bool

    @property
    def primary_app(self) -> ApmApplication:
        return self.apps[0]

    @property
    def display_name(self) -> str:
        apps = ",".join([f"{app.bk_biz_id}:{app.app_name}" for app in self.apps])
        return f"data_id={self.data_id} shared={self.is_shared} apps=[{apps}]"


class PreCalculateTaskSpecProvider:
    """从 APM 应用集合构造预计算任务，屏蔽 App 与 data_id 的一对多关系。"""

    @classmethod
    def list_task_specs(
        cls,
        enabled_only: bool = True,
        require_trace_enabled: bool = True,
        require_metric_enabled: bool = True,
        data_ids: Iterable[int | str] | None = None,
    ) -> list[PreCalculateTaskSpec]:
        if data_ids is not None and not data_ids:
            return []

        q: Q = Q()
        if enabled_only:
            q &= Q(is_enabled=True)
        if require_trace_enabled:
            q &= Q(is_enabled_trace=True)
        if require_metric_enabled:
            q &= Q(is_enabled_metric=True)

        trace_datasources: list[TraceDataSource]
        if data_ids is not None:
            trace_datasources = list(
                TraceDataSource.objects.filter(bk_data_id__in={int(data_id) for data_id in data_ids})
            )

            app_names: set[str] = {trace_datasource.app_name for trace_datasource in trace_datasources}
            bk_biz_ids: set[int] = {trace_datasource.bk_biz_id for trace_datasource in trace_datasources}
            q &= Q(app_name__in=app_names) & Q(bk_biz_id__in=bk_biz_ids)
        else:
            trace_datasources = list(TraceDataSource.objects.all())

        trace_datasource_mapping: dict[tuple[int, str], TraceDataSource] = {
            (trace_datasource.bk_biz_id, trace_datasource.app_name): trace_datasource
            for trace_datasource in trace_datasources
        }
        if not trace_datasource_mapping:
            return []

        apps: list[ApmApplication] = []
        for app in ApmApplication.objects.filter(q):
            # data_ids 精准过滤场景可能过滤出不同业务，相同应用名的数据，此处需要根据实际查询出的 TraceDataSource 进行过滤，
            # 避免误将不相关的应用数据纳入预计算范围。
            if (app.bk_biz_id, app.app_name) not in trace_datasource_mapping:
                continue
            apps.append(app)

        grouped_apps: dict[str, list[ApmApplication]] = defaultdict(list)
        for app in apps:
            trace_datasource = trace_datasource_mapping.get((app.bk_biz_id, app.app_name))
            if not (trace_datasource and trace_datasource.is_ready()):
                continue

            data_id = str(trace_datasource.bk_data_id)
            grouped_apps[data_id].append(app)

        task_specs: list[PreCalculateTaskSpec] = []
        for data_id, apps in grouped_apps.items():
            apps.sort(key=lambda item: (item.bk_biz_id, item.app_name, item.id))
            trace_datasource = trace_datasource_mapping[(apps[0].bk_biz_id, apps[0].app_name)]
            task_specs.append(
                PreCalculateTaskSpec(
                    data_id=data_id,
                    trace_result_table_id=trace_datasource.result_table_id,
                    apps=tuple(apps),
                    is_shared=trace_datasource.is_shared,
                )
            )

        task_specs.sort(key=lambda item: item.data_id)
        return task_specs

    @classmethod
    def get_task_spec(cls, data_id: int | str) -> PreCalculateTaskSpec:
        task_spec_data_id = str(data_id)
        task_specs = cls.list_task_specs(
            enabled_only=False, require_trace_enabled=False, require_metric_enabled=False, data_ids=[task_spec_data_id]
        )
        for task_spec in task_specs:
            if task_spec.data_id == task_spec_data_id:
                return task_spec
        raise ValueError(f"data_id: {data_id} 未找到有效预计算任务")
