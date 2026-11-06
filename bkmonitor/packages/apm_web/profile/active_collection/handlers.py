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

from apm.models import ProfileDataSource
from apm_web.profile.active_collection.constants import BUILTIN_PROFILE_SERVICE_NAME, RUNNING_EXECUTION_WINDOW_MS
from apm_web.profile.constants import NORMAL_SERVICE_MAX_QUERY_SIZE
from apm_web.profile.doris.querier import APIType
from constants.apm import BUILTIN_PROFILING_APP_NAME


class ActiveProfilingResultMixin:
    """查看与导出 Profiling 结果共用：定位键与起止时间由前端从主机执行行传入，取数复用现有 Profiling 检索"""

    def _locate_samples(self, validated_request_data):
        """单次采集的样本按 scheduled_at + bk_host_id 定位，计划任务再匹配 task_id，返回 Profiling 检索的查询参数"""
        bk_biz_id = validated_request_data["bk_biz_id"]
        filter_labels = {
            "scheduled_at": str(validated_request_data["scheduled_at"]),
            "bk_host_id": str(validated_request_data["bk_host_id"]),
        }
        if "task_id" in validated_request_data:
            filter_labels["task_id"] = str(validated_request_data["task_id"])
        # 查询窗取该主机的实际起止，两端各放宽一个运行窗口容忍上报端时钟偏差
        return {
            "bk_biz_id": bk_biz_id,
            "app_name": BUILTIN_PROFILING_APP_NAME,
            "service_name": BUILTIN_PROFILE_SERVICE_NAME,
            "start": validated_request_data["started_at"] - RUNNING_EXECUTION_WINDOW_MS,
            "end": validated_request_data["finished_at"] + RUNNING_EXECUTION_WINDOW_MS,
            "result_table_id": self._get_profile_datasource(bk_biz_id).result_table_id,
            "filter_labels": filter_labels,
        }

    def _convert_samples(self, validated_request_data, converter):
        """按单次采集定位样本，用调用方的转换器转换；没有样本时返回 None"""
        from apm_web.profile.views import ProfileQueryViewSet

        query_params = self._locate_samples(validated_request_data)
        samples = ProfileQueryViewSet.query(
            **query_params,
            sample_type=validated_request_data["data_type"],
            # 多取一行判断是否超限，超限时报错而不是截断
            extra_params={"limit": {"offset": 0, "rows": NORMAL_SERVICE_MAX_QUERY_SIZE + 1}},
        )

        if not samples or not samples.get("list"):
            return None
        if len(samples["list"]) > NORMAL_SERVICE_MAX_QUERY_SIZE:
            raise ValueError(_("该次采集的调用栈超过 {} 条，无法完整查看或导出").format(NORMAL_SERVICE_MAX_QUERY_SIZE))
        converter.convert(
            samples, agg_interval=ProfileQueryViewSet.get_agg_interval(query_params["start"], query_params["end"])
        )
        return converter

    def _query_sample_types(self, validated_request_data):
        """按单次采集定位样本，返回其中出现过的 sample_type，按名称排序"""
        from apm_web.profile.views import ProfileQueryViewSet

        rows = ProfileQueryViewSet.query(
            **self._locate_samples(validated_request_data),
            api_type=APIType.SELECT_COUNT,
            dimension_fields="sample_type",
            extra_params={"metric_fields": "count(*)"},
        ).get("list", [])
        return sorted(rows, key=lambda row: row["sample_type"])

    def _get_profile_datasource(self, bk_biz_id):
        """enable 开通的 Profiling 数据源，bk_data_id 仍为 -1 说明链路没建成"""
        profile_datasource = ProfileDataSource.objects.filter(
            bk_biz_id=bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME
        ).first()
        if not profile_datasource or profile_datasource.bk_data_id == -1:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return profile_datasource
