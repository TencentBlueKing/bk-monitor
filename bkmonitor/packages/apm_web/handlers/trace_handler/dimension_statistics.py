from core.drf_resource import api


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
                exclude_property=params.get("exclude_property", []),
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
