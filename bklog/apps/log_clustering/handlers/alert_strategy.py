import arrow

from apps.api import MonitorApi
from apps.log_clustering.constants import AlertStatusEnum


class AlertStrategyHandler(object):
    def __init__(self, index_set_id):
        self.index_set_id = index_set_id

    def get_alert_records(
        self,
        bk_biz_id,
        status,
        page,
        page_size,
    ):
        """
        :param bk_biz_id: 业务id
        :param status: 状态
        :param page:  页数
        :param page_size:  每页条数
        """
        alert_status = []
        if status != AlertStatusEnum.ALL.value:
            alert_status = [status]
        current_time = arrow.now()
        start_time = int(current_time.shift(days=-7).timestamp())
        end_time = int(current_time.timestamp())
        request_params = {
            "bk_biz_ids": [bk_biz_id],
            "status": alert_status,
            "conditions": [{"key": "metric", "value": [f"bk_log_search.index_set.{self.index_set_id}"]}],
            "start_time": start_time,
            "end_time": end_time,
            "page": page,
            "page_size": page_size,
            "show_overview": False,
            "show_aggs": False,
        }
        alert_result = MonitorApi.search_alert(request_params)
        result_list = []
        for alert_config in alert_result["alerts"]:
            result_list.append(
                {
                    "id": alert_config["id"],
                    "strategy_id": alert_config["strategy_id"],
                    "alert_name": alert_config["alert_name"],
                    "first_anomaly_time": alert_config["first_anomaly_time"],
                    "duration": alert_config["duration"],
                    "status": alert_config["status"],
                    "severity": alert_config["severity"],
                }
            )
        return result_list

    def get_strategy_records(
        self,
        bk_biz_id,
        page,
        page_size,
    ):
        """
        :param bk_biz_id: 业务id
        :param page: 页数
        :param page_size: 每页条数
        """
        current_time = arrow.now()
        start_time = int(current_time.shift(days=-7).timestamp())
        end_time = int(current_time.timestamp())

        # 获取最近告警时间
        request_params = {
            "bk_biz_ids": [bk_biz_id],
            "conditions": [{"key": "metric", "value": [f"bk_log_search.index_set.{self.index_set_id}"]}],
            "start_time": start_time,
            "end_time": end_time,
            "show_overview": False,
            "show_aggs": False,
        }
        alert_result = MonitorApi.search_alert(request_params)
        alert_config_dict = {}
        for alert_config in alert_result["alerts"]:
            id = alert_config["id"]
            strategy_id = alert_config["strategy_id"]
            latest_time = alert_config["latest_time"]
            if strategy_id not in alert_config_dict or id > alert_config_dict[strategy_id]["id"]:
                alert_config_dict[strategy_id] = {"id": id, "latest_time": latest_time}
        # 获取策略信息
        strategy_result = MonitorApi.search_alarm_strategy_v3(
            {
                "page": page,
                "page_size": page_size,
                "conditions": [{"key": "metric_id", "value": [f"bk_log_search.index_set.{self.index_set_id}"]}],
                "bk_biz_id": bk_biz_id,
                "with_notice_group": False,
                "with_notice_group_detail": False,
            }
        )

        strategy_config_list = []
        for strategy_config in strategy_result["strategy_config_list"]:
            strategy_id = strategy_config["id"]
            strategy_config_list.append(
                {
                    "alart_name": strategy_config["name"],
                    "latest_time": alert_config_dict.get(strategy_id, {}).get("latest_time"),
                }
            )
        return strategy_config_list
