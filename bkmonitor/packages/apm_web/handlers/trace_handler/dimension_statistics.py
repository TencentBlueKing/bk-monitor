import math

from core.drf_resource import api


class HistogramNiceNumberGenerator:
    """nice number生成器"""

    # fmt: off
    HistogramBucketSizes = [
        1e-9,  2e-9,  2.5e-9,  4e-9,  5e-9,
        1e-8,  2e-8,  2.5e-8,  4e-8,  5e-8,
        1e-7,  2e-7,  2.5e-7,  4e-7,  5e-7,
        1e-6,  2e-6,  2.5e-6,  4e-6,  5e-6,
        1e-5,  2e-5,  2.5e-5,  4e-5,  5e-5,
        1e-4,  2e-4,  2.5e-4,  4e-4,  5e-4,
        1e-3,  2e-3,  2.5e-3,  4e-3,  5e-3,
        1e-2,  2e-2,  2.5e-2,  4e-2,  5e-2,
        1e-1,  2e-1,  2.5e-1,  4e-1,  5e-1,
        1,     2,     2.5,     4,     5,
        1e+1,  2e+1,  2.5e+1,  4e+1,  5e+1,
        1e+2,  2e+2,  2.5e+2,  4e+2,  5e+2,
        1e+3,  2e+3,  2.5e+3,  4e+3,  5e+3,
        1e+4,  2e+4,  2.5e+4,  4e+4,  5e+4,
        1e+5,  2e+5,  2.5e+5,  4e+5,  5e+5,
        1e+6,  2e+6,  2.5e+6,  4e+6,  5e+6,
        1e+7,  2e+7,  2.5e+7,  4e+7,  5e+7,
        1e+8,  2e+8,  2.5e+8,  4e+8,  5e+8,
        1e+9,  2e+9,  2.5e+9,  4e+9,  5e+9,
    ]
    # fmt: on
    @classmethod
    def calculate_bucket_size(
        cls, min_value: float | int, max_value: float | int, num_buckets: int
    ) -> tuple[float | int, float | int, float | int]:
        """计算bucket size"""
        target_size = (max_value - min_value) / num_buckets
        for bucket_size in cls.HistogramBucketSizes:
            if bucket_size >= target_size:
                min_x = min_value // bucket_size * bucket_size
                max_x = math.ceil(max_value / bucket_size) * bucket_size
                return min_x, max_x, bucket_size
        return min_value, max_value, target_size


class DimensionStatisticsAPIHandler:
    """trace 检索页面维度统计功能支持"""

    @classmethod
    def get_api_topk_data(cls, params: dict) -> dict:
        """获取topk数据"""

        return api.apm_api.query_fields_topk(
            dict(
                bk_biz_id=params["bk_biz_id"],
                app_name=params["app_name"],
                mode=params["mode"],
                start_time=params["start_time"],
                end_time=params["end_time"],
                fields=params["fields"],
                limit=params.get("limit", 5),
                filters=params.get("filters", []),
                query_string=params.get("query_string", ""),
            )
        )

    @classmethod
    def get_api_statistics_info_data(cls, params: dict) -> dict:
        """获取info数据"""

        return api.apm_api.query_field_statistics_info(
            dict(
                bk_biz_id=params["bk_biz_id"],
                app_name=params["app_name"],
                mode=params["mode"],
                start_time=params["start_time"],
                end_time=params["end_time"],
                field=params["field"],
                limit=params.get("limit", 5),
                filters=params.get("filters", []),
                query_string=params.get("query_string", ""),
            )
        )

    @classmethod
    def get_api_statistics_graph_data(cls, params: dict) -> dict:
        """获取graph数据"""

        return api.apm_api.query_field_statistics_graph(
            dict(
                bk_biz_id=params["bk_biz_id"],
                app_name=params["app_name"],
                mode=params["mode"],
                start_time=params["start_time"],
                end_time=params["end_time"],
                field=params["field"],
                limit=params.get("limit", 5),
                filters=params.get("filters", []),
                query_string=params.get("query_string", ""),
            )
        )
