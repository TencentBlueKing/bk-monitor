import arrow

from apps.api import MonitorApi
from apps.log_search.constants import MAX_WORKERS, AlertStatusEnum
from apps.log_search.exceptions import IndexSetDoseNotExistException
from apps.log_search.models import LogIndexSet
from apps.utils.local import get_request_username
from apps.utils.thread import MultiExecuteFunc
from bkm_space.utils import space_uid_to_bk_biz_id


class AlertStrategyHandler(object):
    DAYS = 7

    def __init__(self, index_set_id):
        self.index_set_id = index_set_id

        try:
            self.log_index_set_obj = LogIndexSet.objects.get(index_set_id=self.index_set_id)
        except LogIndexSet.DoesNotExist:
            raise IndexSetDoseNotExistException()

    def get_alert_records(
        self,
        status=AlertStatusEnum.ALL.value,
        page=1,
        page_size=10,
    ):
        """
        :param status: 状态
        :param page:  页数
        :param page_size:  每页条数
        """
        bk_biz_id = space_uid_to_bk_biz_id(self.log_index_set_obj.space_uid)
        alert_status = []
        conditions = [{"key": "metric", "value": [f"bk_log_search.index_set.{self.index_set_id}"]}]
        username = get_request_username()
        if status == AlertStatusEnum.NOT_SHIELDED_ABNORMAL.value:
            alert_status = [status]
        elif status == AlertStatusEnum.MY_ASSIGNEE.value:
            conditions.append({"key": "assignee", "value": [username]})

        current_time = arrow.now()
        start_time = int(current_time.shift(days=-self.DAYS).timestamp())
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
        # 按照latest_time降序
        sorted_alerts = sorted(alert_result["alerts"], key=lambda alert: alert["latest_time"], reverse=True)
        result_list = []
        for alert_config in sorted_alerts:
            result_list.append(
                {
                    "id": alert_config["id"],
                    "strategy_id": alert_config["strategy_id"],
                    "alert_name": alert_config["alert_name"],
                    "first_anomaly_time": alert_config["first_anomaly_time"],
                    "duration": alert_config["duration"],
                    "status": alert_config["status"],
                    "severity": alert_config["severity"],
                    "assignee": alert_config["assignee"],
                    "appointee": alert_config["appointee"],
                    "end_time": alert_config["end_time"],
                }
            )
        return result_list

    def get_strategy_records(
        self,
        page=1,
        page_size=10,
    ):
        """
        :param page: 页数
        :param page_size: 每页条数
        """
        bk_biz_id = space_uid_to_bk_biz_id(self.log_index_set_obj.space_uid)
        start_time = int(arrow.now().shift(days=-self.DAYS).timestamp())
        end_time = int(arrow.now().timestamp())

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
        # 按策略更新时间降序
        sorted_strategy_result = sorted(
            strategy_result["strategy_config_list"], key=lambda alert: alert["update_time"], reverse=True
        )
        strategy_id_list = []
        strategy_config_list = []
        for strategy_config in sorted_strategy_result:
            strategy_id = strategy_config["id"]
            strategy_id_list.append(strategy_id)
            strategy_config_list.append(
                {
                    "strategy_id": strategy_id,
                    "name": strategy_config["name"],
                    "query_string": strategy_config.get("items", [{}])[0]
                    .get("query_configs", [{}])[0]
                    .get("query_string", "*"),
                }
            )
        multi_execute_func = MultiExecuteFunc(max_workers=MAX_WORKERS)
        for strategy_id in strategy_id_list:
            # 获取最近告警时间
            request_params = {
                "bk_biz_ids": [bk_biz_id],
                "conditions": [{"key": "strategy_id", "value": [strategy_id]}],
                "start_time": start_time,
                "end_time": end_time,
                "ordering": ["-latest_time"],
                "page": 1,
                "page_size": 1,
                "show_overview": False,
                "show_aggs": False,
            }
            multi_execute_func.append(
                result_key=strategy_id,
                func=MonitorApi.search_alert,
                params=request_params,
            )
        multi_result = multi_execute_func.run()
        for strategy_config in strategy_config_list:
            strategy_id = strategy_config["strategy_id"]
            alerts = multi_result.get(strategy_id, {}).get("alerts")
            strategy_config.update({"latest_time": alerts[0].get("latest_time") if alerts else None})
        return strategy_config_list
