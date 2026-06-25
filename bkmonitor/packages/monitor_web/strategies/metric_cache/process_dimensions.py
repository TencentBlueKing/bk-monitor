"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

logger = logging.getLogger(__name__)

# 进程采集结果表 -> 对应的自定义时序分组名（metadata TimeSeriesGroup）
PROCESS_RT_TO_TS_GROUP = {"process.perf": "process_perf", "process.port": "process_port"}
# 补全进程维度时需要过滤掉的内部维度（与 metric_list_cache.FILTER_DIMENSION_LIST 对齐）
PROCESS_EXTRA_DIMENSION_FILTER = {"time", "bk_supplier_id", "bk_cmdb_level", "timestamp"}


def get_process_extra_dimensions(bk_tenant_id: str, bk_biz_id: int, result_table_ids: set) -> dict:
    """进程采集：用业务真实上报的自定义时序分组维度，补全指标缓存里缺失的维度。

    process.perf / process.port 在指标缓存（MetricListCache）里的维度是写死的静态清单
    (PROCESS_METRIC_DIMENSIONS)，不含用户「维度提取」(extract_pattern 正则从进程启动命令提取)
    出来的维度（如 process），也不含其它逐配置各异的提取维度。这些维度只存在于业务真实上报的
    TimeSeriesGroup(process_perf / process_port).tag_list 里，故按真实上报动态补齐，避免静态清单漂移。

    仅在请求涉及进程表且业务确有进程采集时才查询 metadata，常规业务零额外开销。
    返回 {result_table_id: [{"id", "name"}, ...]}；调用方自行与静态维度按 id 去重合并。
    """
    process_tables = {rt for rt in result_table_ids if rt in PROCESS_RT_TO_TS_GROUP}
    if not process_tables:
        return {}

    from core.drf_resource import api
    from monitor_web.models.collecting import CollectConfigMeta

    if not CollectConfigMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id="bkprocessbeat"
    ).exists():
        return {}

    extra: dict[str, list[dict]] = {}
    for table_id in process_tables:
        group_name = PROCESS_RT_TO_TS_GROUP[table_id]
        try:
            groups = api.metadata.query_time_series_group(
                bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, time_series_group_name=group_name
            )
        except Exception:  # noqa
            # 数据未上报或 metadata 异常时静默降级为静态维度，不阻断接口
            logger.exception("augment process dimensions failed: biz=%s, table=%s", bk_biz_id, table_id)
            continue
        seen: set = set()
        dims: list = []
        for group in groups or []:
            for metric in group.get("metric_info_list") or []:
                for tag in metric.get("tag_list") or []:
                    field = tag.get("field_name")
                    if not field or field in PROCESS_EXTRA_DIMENSION_FILTER or field in seen:
                        continue
                    seen.add(field)
                    dims.append({"id": field, "name": tag.get("description") or field})
        if dims:
            extra[table_id] = dims
    return extra
