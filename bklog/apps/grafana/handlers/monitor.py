from apps.api import MonitorApi
from apps.grafana.constants import LOG_GRAFANA_DATA_SOURCE_IN_MONITOR, LOG_DATA_SOURCE_LABEL_IN_MONITOR
from apps.log_search.constants import GlobalCategoriesEnum
from apps.log_search.models import LogIndexSet


class MonitorGrafanaHandler:
    @staticmethod
    def save_to_dashboard(params: dict):
        index_set_obj = LogIndexSet.objects.filter(index_set_id=params["index_set_id"]).first()
        log_index_set_param = {
            "id": [index_set_obj.category_id, index_set_obj.index_set_id],
            "labels": [str(GlobalCategoriesEnum.get_display(index_set_obj.category_id)), index_set_obj.index_set_name],
        }

        request_params = {
            "bk_biz_id": params["bk_biz_id"],
            "dashboard_uids": params["dashboard_uids"],
            "panels": [
                {
                    "name": params["panel_name"],
                    "datasource": LOG_GRAFANA_DATA_SOURCE_IN_MONITOR,
                    "queries": [
                        {
                            "expression": "",
                            "query_configs": [
                                {
                                    "query_string": params["query_string"],
                                    "data_source_label": LOG_DATA_SOURCE_LABEL_IN_MONITOR,
                                    "index": log_index_set_param,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        return MonitorApi.save_to_dashboard(request_params)
