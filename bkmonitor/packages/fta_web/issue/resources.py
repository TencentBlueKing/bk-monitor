from rest_framework import serializers

from core.drf_resource import Resource
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.utils import slice_time_interval
from fta_web.issue.handlers.issue import IssueQueryHandler
from fta_web.issue.serializers import IssueSearchSerializer


class SearchIssueResource(Resource):
    """查询 Issue 列表"""

    class RequestSerializer(IssueSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=500, default=10)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="返回ES DSL查询语句", default=False)

    def perform_request(self, validated_request_data):
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        handler = IssueQueryHandler(**validated_request_data)
        result = handler.search(show_aggs=show_aggs, show_dsl=show_dsl)

        return result


class IssueAlertDateHistogramResultResource(Resource):
    """查询 Issue 关联的告警趋势图（支持 group_by 分组维度）"""

    def perform_request(self, validated_request_data):
        interval = validated_request_data.pop("interval", "auto")
        group_by = validated_request_data.pop("group_by", None)
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")

        handler = AlertQueryHandler(**validated_request_data)
        results = handler.date_histogram(interval=interval, group_by=group_by)

        if not results:
            return {"default_time_series": {"start_time": start_time, "end_time": end_time, "interval": interval}}

        # 未指定 group_by 时保持与 AlertDateHistogramResultResource 一致的返回格式
        if not group_by:
            return list(results.values())[0]

        return results

    @staticmethod
    def sliced_date_histogram(
        start_time: int,
        end_time: int,
        interval: int | str = "auto",
        handler_kwargs: dict = None,
        group_by: list[str] | None = None,
    ) -> dict:
        """
        按时间分片并行查询告警趋势图，合并各分片结果。

        通过 bulk_request 调用自身 perform_request 实现并行，
        根据是否指定 group_by 采用不同的合并策略。

        参数:
            start_time: 起始时间戳（秒）
            end_time: 结束时间戳（秒）
            interval: 聚合间隔，"auto" 表示自动计算
            handler_kwargs: 构造 AlertQueryHandler 的额外参数（如 conditions、bk_biz_ids 等）
            group_by: 分组维度列表，默认 None 表示按 status 分组

        返回值示例:

        1) 无 group_by（默认按 status 分组）—— 两层结构 {状态: {时间戳: 数量}}:
           sliced_date_histogram(start_time=1741334400, end_time=1741348800, ...)
           {
               "ABNORMAL":  {1741334400000: 5, 1741338000000: 8, ...},
               "RECOVERED": {1741334400000: 0, 1741338000000: 2, ...},
               "CLOSED":    {1741334400000: 0, 1741338000000: 1, ...},
           }

        2) 有 group_by —— 三层结构 {维度元组: {状态: {时间戳: 数量}}}:
           sliced_date_histogram(..., group_by=["issue_id"])
           {
               ("issue-abc",): {
                   "ABNORMAL":  {1741334400000: 3, 1741338000000: 5, ...},
                   "RECOVERED": {1741334400000: 0, 1741338000000: 1, ...},
                   "CLOSED":    {1741334400000: 0, 1741338000000: 0, ...},
               },
               ("issue-def",): {
                   "ABNORMAL":  {1741334400000: 2, 1741338000000: 3, ...},
                   "RECOVERED": {1741334400000: 0, 1741338000000: 1, ...},
                   "CLOSED":    {1741334400000: 0, 1741338000000: 1, ...},
               },
           }
        """
        handler_kwargs = handler_kwargs or {}

        # 构造分片请求列表，通过 bulk_request 并行执行
        results = IssueAlertDateHistogramResultResource().bulk_request(
            [
                {
                    "start_time": sliced_start,
                    "end_time": sliced_end,
                    "interval": interval,
                    "group_by": group_by,
                    **handler_kwargs,
                }
                for sliced_start, sliced_end in slice_time_interval(start_time, end_time)
            ]
        )

        if group_by:
            # 有 group_by：三层结构 {维度元组: {状态: {时间戳: 数量}}}
            merged = {}
            for result in results:
                if isinstance(result, dict) and "default_time_series" in result:
                    continue
                for dimension_tuple, status_series in result.items():
                    if dimension_tuple not in merged:
                        merged[dimension_tuple] = {}
                    for status_key, ts_map in status_series.items():
                        if status_key not in merged[dimension_tuple]:
                            merged[dimension_tuple][status_key] = {}
                        merged[dimension_tuple][status_key].update(ts_map)
            return merged
        else:
            # 无 group_by：两层结构 {状态: {时间戳: 数量}}
            merged = {}
            for result in results:
                for status, series in result.items():
                    if status == "default_time_series":
                        continue
                    if status not in merged:
                        merged[status] = {}
                    merged[status].update(series)
            return merged
