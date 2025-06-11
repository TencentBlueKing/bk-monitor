import os

from apps.log_commons.job import JobHelper
from apps.log_databus.constants import GSE_PATH, IPC_PATH
from apps.log_databus.handlers.check_collector.checker.agent_checker import AgentChecker
from apps.log_databus.models import CollectorConfig
from apps.log_databus.handlers.check_collector.base import CheckCollectorRecord
from apps.log_databus.handlers.check_collector.checker.path_check import LogPathChecker
from apps.log_databus.handlers.check_collector.handler import async_atomic_check
from apps.log_databus.handlers.check_collector.checker.bkunifylogbeat_checker import BkunifylogbeatChecker

collector_config_id = 1021
hosts = [{"bk_cloud_id": 0, "bk_host_id": 127, "ip": "10.0.6.33"}]
collector_config = CollectorConfig.objects.get(pk=collector_config_id)
key = CheckCollectorRecord.generate_check_record_id(
    collector_config_id=collector_config.collector_config_id,
    hosts=hosts
)
print(key)
record = CheckCollectorRecord(check_record_id=key)
record.append_init()
target_server = JobHelper.adapt_hosts_target_server(
    bk_biz_id=collector_config.bk_biz_id,
    hosts=hosts
)
path_check = LogPathChecker(
    collector_config_id=collector_config.collector_config_id,
    check_collector_record=record
)
checker = AgentChecker(
    target_server=target_server,
    bk_biz_id=collector_config.bk_biz_id,
    subscription_id=collector_config.subscription_id or 0,
    gse_path=os.environ.get("GSE_ROOT_PATH", GSE_PATH),
    ipc_path=os.environ.get("GSE_IPC_PATH", IPC_PATH),
    check_collector_record=record,
    collector_config_id=collector_config_id
)
checker.run()
path_check.run()
print(record.get_infos())
