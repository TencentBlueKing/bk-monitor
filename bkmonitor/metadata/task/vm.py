"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time

from alarm_backends.core.lock.service_lock import share_lock
from core.prometheus import metrics
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.db import filter_model_by_in_page

logger = logging.getLogger("metadata")


@share_lock(ttl=3600, identify="metadata_check_access_vm_task")
def check_access_vm_task(only_v4=True):
    """检测遗漏或者失败的接入 vm 的结果表

    NOTE: 因为需要调用vm的接口，建议是需要单个单个执行

    Args:
        only_v4: 是否只重新接入V4（BKDATA）的数据源，默认为False，即V3和V4都接入
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="check_access_vm_task", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()  # 记录开始时间
    logger.info("check_access_vm_task:start to check result table and access vm")
    # 获取有关联数据源的结果表
    rt_ds_dict = {
        obj["table_id"]: obj["bk_data_id"]
        for obj in models.DataSourceResultTable.objects.values("table_id", "bk_data_id")
    }

    # 过滤启用的结果表
    rt_info = filter_model_by_in_page(
        model=models.ResultTable,
        field_op="table_id__in",
        filter_data=list(rt_ds_dict.keys()),
        value_field_list=["table_id"],
        value_func="values",
        other_filter={"is_deleted": False, "is_enable": True, "default_storage": "influxdb"},
    )
    # 过滤出没有接入 vm 的结果表
    rt_list = [rt["table_id"] for rt in rt_info]
    accessed_vm_rt_list = filter_model_by_in_page(
        model=models.AccessVMRecord,
        field_op="result_table_id__in",
        filter_data=list(rt_list),
        value_field_list=["result_table_id"],
        value_func="values_list",
    )
    need_access_vm_rt_list = []
    # 移除 agentmetrix 对应的结果表，因为这部分结果表后续会废弃
    for rt in set(rt_list) - set(accessed_vm_rt_list):
        if rt.startswith("agentmetrix."):
            continue
        need_access_vm_rt_list.append(rt)

    logger.info("check_access_vm_task:need add vm result table_id list: %s", json.dumps(need_access_vm_rt_list))

    # 如果检查没有需要创建的，直接返回
    if not need_access_vm_rt_list:
        end_time = time.time()  # 记录结束时间
        logger.info("check_access_vm_task:no need to add fix access vm, total use %.2f seconds", end_time - start_time)
        return

    # 逐个 ResultTable 同步下发 DataLink。
    for rt in need_access_vm_rt_list:
        bk_data_id = rt_ds_dict.get(rt)
        if bk_data_id is None:
            logger.warning("table_id: %s not found data_id", rt)
            continue
        # 开始接入
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
            # 如果指定了 only_v4，则跳过 V3 的接入。
            if only_v4 and ds.created_from == DataIdCreatedFromSystem.BKGSE.value:
                logger.info(
                    "check_access_vm_task: skip v3 datalink due to only_v4=True, table_id->[%s],data_id->[%s]",
                    rt,
                    bk_data_id,
                )
                continue

            result_table = models.ResultTable.objects.get(table_id=rt, bk_tenant_id=ds.bk_tenant_id)
            logger.info(
                "check_access_vm_task: try to apply result table datalink,table_id->[%s],data_id->[%s]",
                rt,
                bk_data_id,
            )
            result_table.apply_datalink(delay=False)
        except Exception as e:
            logger.error("apply result table datalink error, table_id: %s, error: %s", rt, e)

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="check_access_vm_task", process_target=None).observe(
        cost_time
    )
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="check_access_vm_task", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.report_all()
    logger.info("check_access_vm_task: check successfully，use %.2f seconds", cost_time)
