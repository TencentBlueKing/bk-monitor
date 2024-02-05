# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import datetime
import logging
import math
import shutil
import time
import traceback
from typing import Any, Dict

import arrow
from celery.task import task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.utils.translation import ugettext as _

from bkm_space.api import SpaceApi
from bkm_space.define import Space, SpaceTypeEnum
from bkmonitor.dataflow.constant import (
    FLINK_KEY_WORDS,
    METRIC_RECOMMENDATION_SCENE_NAME,
    AccessStatus,
    VisualType,
    get_plan_id_by_algorithm,
    get_scene_id_by_algorithm,
)
from bkmonitor.dataflow.flow import DataFlow
from bkmonitor.dataflow.task.intelligent_detect import (
    MetricRecommendTask,
    MultivariateAnomalyIntelligentModelDetectTask,
    StrategyIntelligentModelDetectTask,
)
from bkmonitor.models import ActionConfig
from bkmonitor.models.external_iam import ExternalPermissionApplyRecord
from bkmonitor.strategy.new_strategy import QueryConfig, get_metric_id
from bkmonitor.strategy.serializers import MultivariateAnomalyDetectionSerializer
from bkmonitor.utils.common_utils import to_bk_data_rt_id
from bkmonitor.utils.local import local
from bkmonitor.utils.sql import sql_format_params
from bkmonitor.utils.user import set_local_username
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.dataflow import ConsumingMode
from core.drf_resource import api, resource
from core.errors.api import BKAPIError
from core.errors.bkmonitor.dataflow import DataFlowNotExists
from fta_web.tasks import run_init_builtin_action_config
from monitor_web.commons.cc.utils import CmdbUtil
from monitor_web.constants import (
    AIOPS_ACCESS_MAX_RETRIES,
    AIOPS_ACCESS_RETRY_INTERVAL,
    MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD,
    MULTIVARIATE_ANOMALY_DETECTION_SCENE_PARAMS_MAP,
)
from monitor_web.export_import.constant import ImportDetailStatus, ImportHistoryStatus
from monitor_web.extend_account.models import UserAccessRecord
from monitor_web.models.custom_report import CustomEventGroup, CustomTSTable
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.strategies.built_in import run_build_in
from utils import business, count_md5

logger = logging.getLogger("monitor_web")


User = get_user_model()


def set_client_user():
    biz_set = business.get_all_activate_business()
    local.username = business.maintainer(biz_set[0])


@task(ignore_result=True)
def record_login_user(username: str, source: str, last_login: float, space_info: Dict[str, Any]):
    logger.info(
        "[record_login_user] task start: username -> %s, source -> %s, last_login -> %s, space_info -> %s",
        username,
        last_login,
        source,
        last_login,
    )

    try:
        user = User.objects.get(username=username)
        user.last_login = datetime.datetime.now()
        user.save()

        UserAccessRecord.objects.update_or_create_by_space(username, source, space_info)
    except Exception:  # noqa
        logger.exception(
            "[record_login_user] failed to record: username -> %s, source -> %s, last_login -> %s, space_info -> %s",
            username,
            last_login,
            source,
            last_login,
        )


@task(ignore_result=True)
def active_business(username: str, space_info: Dict[str, Any]):
    logger.info("[active_business] task start: username -> %s, space_info -> %s", username, space_info)
    try:
        business.activate(int(space_info["bk_biz_id"]), username)
    except Exception:  # noqa
        logger.exception(
            "[active_business] activate error: biz_id -> %s, username -> %s", space_info["bk_biz_id"], username
        )


@task(ignore_result=True)
def cache_space_data(username: str, space_info: Dict[str, Any]):
    logger.info("[cache_space_data] task start: username -> %s", username)
    try:
        resource.cc.fetch_allow_biz_ids_by_user.refresh(username)
    except Exception:  # noqa
        logger.exception("[cache_space_data] error: username -> %s, space_info -> %s", username, space_info)


@task(ignore_result=True)
def run_init_builtin(bk_biz_id):
    if bk_biz_id and settings.ENVIRONMENT != "development":
        logger.info("[run_init_builtin] enter with bk_biz_id -> %s", bk_biz_id)
        # 创建默认内置策略
        run_build_in(int(bk_biz_id))

        # 创建k8s内置策略
        run_build_in(int(bk_biz_id), mode="k8s")

        if (
            settings.ENABLE_DEFAULT_STRATEGY
            and int(bk_biz_id) > 0
            and not ActionConfig.origin_objects.filter(bk_biz_id=bk_biz_id, is_builtin=True).exists()
        ):
            logger.warning("[run_init_builtin] home run_init_builtin_action_config: bk_biz_id -> %s", bk_biz_id)
            # 如果当前页面没有出现内置套餐，则会进行快捷套餐的初始化
            try:
                run_init_builtin_action_config.delay(bk_biz_id)
            except Exception as error:
                # 直接忽略
                logger.exception(
                    "[run_init_builtin] run_init_builtin_action_config failed: bk_biz_id -> %s, error -> %s",
                    bk_biz_id,
                    str(error),
                )
        # TODO 先关闭，后面稳定了直接打开
        # if not AlertAssignGroup.origin_objects.filter(bk_biz_id=cc_biz_id, is_builtin=True).exists():
        #     # 如果当前页面没有出现内置的规则组
        #     run_init_builtin_assign_group(cc_biz_id)
    else:
        logger.info("[run_init_builtin] skipped with bk_biz_id -> %s", bk_biz_id)


@task(ignore_result=True)
def update_config_status():
    """
    周期性查询节点管理任务状态，更新执行中的采集配置的状态
    """
    resource.collecting.update_config_status()


@task(ignore_result=True)
def update_config_instance_count():
    """
    周期性查询节点管理任务状态，更新启用中的采集配置的主机数和异常数
    """
    resource.collecting.update_config_instance_count()


@task(ignore_result=True)
def update_external_approval_status():
    """
    周期性查询外部版权限审批单据状态，更新审批结果
    """
    for record in ExternalPermissionApplyRecord.objects.filter(status="approval").exclude(approval_sn=""):
        approve_result = api.itsm.ticket_approve_result({"sn": [record.approval_sn]})[0]
        current_status = approve_result.pop("current_status", "")
        if current_status and current_status == "FINISHED":
            logger.info(f"[{approve_result['sn']}] approve_result is FINISHED, url: {approve_result['ticket_url']}")
            resource.iam.callback(approve_result)


@task(ignore_result=True, queue="celery_resource")
def update_metric_list():
    """
    定时刷新指标列表结果表
    :return:
    """
    from monitor.models import GlobalConfig
    from monitor_web.strategies.metric_list_cache import SOURCE_TYPE

    def update_metric(_source_type, bk_biz_id=None):
        try:
            if bk_biz_id is not None:
                SOURCE_TYPE[_source_type](bk_biz_id).run(delay=True)
            else:
                SOURCE_TYPE[_source_type]().run(delay=True)
        except BaseException as e:
            logger.exception("Failed to update metric list(%s) for (%s)", f"{bk_biz_id}_{_source_type}", e)

    set_local_username(settings.COMMON_USERNAME)

    # 获取上次执行分发任务时间戳
    metric_cache_task_last_timestamp, _ = GlobalConfig.objects.get_or_create(
        key="METRIC_CACHE_TASK_LAST_TIMESTAMP", defaults={"value": 0}
    )
    # 如果当前分发任务距离上次更新时间不超过周期1min，则不执行本次任务，避免短时间重复下发
    now_timestamp = arrow.get(datetime.datetime.now()).timestamp
    if metric_cache_task_last_timestamp.value and now_timestamp - metric_cache_task_last_timestamp.value < 60:
        return

    # 指标缓存类型: 全业务、单业务、业务0
    source_type_use_biz = ["BKDATA", "LOGTIMESERIES", "BKMONITORALERT"]
    source_type_all_biz = ["BASEALARM", "BKMONITORLOG"]
    source_type_add_biz_0 = ["BKMONITOR", "CUSTOMEVENT", "CUSTOMTIMESERIES", "BKFTAALERT", "BKMONITORK8S"]
    # 非业务空间不需要执行
    source_type_gt_0 = ["BKDATA"]
    # 不再全局周期任务重执行，引导用户通过主动刷新进行触发
    extr_source_type_gt_0 = ["LOGTIMESERIES", "BKFTAALERT", "BKMONITORALERT", "BKMONITOR"]
    businesses = SpaceApi.list_spaces()

    # 记录分发任务轮次
    metric_cache_task_round, is_created = GlobalConfig.objects.get_or_create(key="METRIC_CACHE_TASK_ROUND")
    if is_created:
        metric_cache_task_round.value = 0
    offset = metric_cache_task_round.value
    # 分发任务周期，默认为分钟
    period = settings.METRIC_CACHE_TASK_PERIOD

    # 更新分发任务轮次
    if period <= 1 or offset == period - 1:
        metric_cache_task_round.value = 0
    else:
        metric_cache_task_round.value = offset + 1
    metric_cache_task_round.save()

    # 更新此轮分发任务时间戳
    metric_cache_task_last_timestamp.value = now_timestamp
    metric_cache_task_last_timestamp.save()

    # 计算每轮任务更新业务数
    biz_num = math.ceil(len(businesses) / period)
    biz_count = 0

    start = time.time()
    logger.info("^update metric list(round %s)" % offset)

    # 最后一轮进行全业务和0业务更新
    if offset == 0:
        biz_count += 1
        for source_type in source_type_add_biz_0:
            update_metric(source_type, 0)
        for source_type in source_type_all_biz:
            update_metric(source_type)

    # 记录有容器集群的cmdb业务列表
    k8s_biz_set = set()
    for biz in businesses[offset * biz_num : (offset + 1) * biz_num]:
        biz_count += 1
        for source_type in source_type_use_biz + source_type_add_biz_0:
            # 非容器平台项目，不需要缓存容器指标：
            if not biz.space_code and source_type == "BKMONITORK8S":
                continue
            else:
                # 记录容器平台项目空间关联的业务id
                try:
                    k8s_biz: Space = SpaceApi.get_related_space(biz.space_uid, SpaceTypeEnum.BKCC.value)
                    if k8s_biz:
                        k8s_biz_set.add(k8s_biz.bk_biz_id)
                except BKAPIError:
                    pass
            # 部分环境可用禁用数据平台指标缓存
            if not settings.ENABLE_BKDATA_METRIC_CACHE and source_type == "BKDATA":
                continue
            # 数据平台指标缓存仅支持更新大于0业务
            if source_type in (source_type_gt_0 + extr_source_type_gt_0) and biz.bk_biz_id <= 0:
                continue
            update_metric(source_type, biz.bk_biz_id)

    # 关联容器平台的业务，批量跑容器指标
    for k8s_biz_id in k8s_biz_set:
        update_metric("BKMONITORK8S", k8s_biz_id)

    logger.info("$update metric list(round {}), biz count: {}, cost: {}".format(offset, biz_count, time.time() - start))


@task(queue="celery_resource")
def update_metric_list_by_biz(bk_biz_id):
    from monitor.models import ApplicationConfig
    from monitor_web.strategies.metric_list_cache import SOURCE_TYPE

    source_type_use_biz = [
        "BKDATA",
        "LOGTIMESERIES",
        "BKMONITOR",
        "CUSTOMEVENT",
        "CUSTOMTIMESERIES",
        "BKMONITORALERT",
        "BKFTAALERT",
        "BKMONITORK8S",
    ]
    source_type_gt_0 = ["BKDATA"]

    for source_type, source in list(SOURCE_TYPE.items()):
        # 部分环境可用禁用数据平台指标缓存
        if not settings.ENABLE_BKDATA_METRIC_CACHE and source_type == "BKDATA":
            continue

        try:
            if source_type in source_type_use_biz:
                if source_type in source_type_gt_0 and bk_biz_id <= 0:
                    continue
                start = time.time()
                logger.info("update metric list({}) by biz({})".format(source_type, bk_biz_id))
                source(bk_biz_id).run(delay=False)
                logger.info("update metric list({}) succeed in {}".format(source_type, time.time() - start))

        except BaseException as e:
            logger.exception("Failed to update metric list(%s) for (%s)", source_type, e)

    ApplicationConfig.objects.filter(cc_biz_id=bk_biz_id, key=f"{bk_biz_id}_update_metric_cache").delete()


@task(ignore_result=True)
def run_metric_manager_async(manager):
    """
    异步执行更新任务
    """
    manager._run()


@task(ignore_result=True)
def update_cmdb_util_info():
    """
    更新cc util的缓存数据
    :return:
    """
    CmdbUtil.refresh()


@task(ignore_result=True)
def append_metric_list_cache(result_table_id_list):
    """
    追加或更新新增的采集插件标列表
    """
    from bkmonitor.models.metric_list_cache import MetricListCache
    from monitor_web.strategies.metric_list_cache import BkmonitorMetricCacheManager

    def update_or_create_metric_list_cache(metric_list):
        # 这里可以考虑 删除 + 创建逻辑
        for metric in metric_list:
            metric["metric_md5"] = count_md5(metric)
            MetricListCache.objects.update_or_create(
                metric_field=metric["metric_field"],
                result_table_id=metric["result_table_id"],
                related_id=metric.get("related_id"),
                data_type_label=metric.get("data_type_label"),
                data_source_label=metric.get("data_source_label"),
                defaults=metric,
            )

    if settings.ROLE == "api":
        # api 调用不做指标实时更新。
        return

    set_local_username(settings.COMMON_USERNAME)
    if not result_table_id_list:
        return
    one_result_table_id = result_table_id_list[0]
    db_name = one_result_table_id.split(".")[0]
    group_list = api.metadata.query_time_series_group.request.refresh(time_series_group_name=db_name)
    plugin = None
    if group_list:
        # 单指标单表模式, 指标会被打散成group list 返回
        # -> metadata.models.custom_report.time_series.TimeSeriesGroup.to_split_json
        new_metric_list = []
        if plugin is None:
            plugin_type, plugin_id = db_name.split("_", 1)
            plugin = CollectorPluginMeta.objects.filter(plugin_type=plugin_type, plugin_id=plugin_id).first()
        for result in group_list:
            result["bk_biz_id"] = plugin.bk_biz_id
            create_msg = BkmonitorMetricCacheManager().get_plugin_ts_metric(result)
            new_metric_list.extend(list(create_msg))
        update_or_create_metric_list_cache(new_metric_list)
    else:
        for result_table_id in result_table_id_list:
            result_table_msg = api.metadata.get_result_table(table_id=result_table_id)
            data_id_info = api.metadata.get_data_id(bk_data_id=result_table_msg["bk_data_id"], with_rt_info=False)
            for k in ["source_label", "type_label"]:
                result_table_msg[k] = data_id_info[k]

            create_msg = BkmonitorMetricCacheManager().get_metrics_by_table(result_table_msg)
            update_or_create_metric_list_cache(create_msg)


@task(ignore_result=True)
def update_failure_shield_content():
    """
    更新失效的屏蔽策略的内容信息
    """
    resource.shield.update_failure_shield_content()


@task(ignore_result=True, queue="celery_resource")
def import_config(
    username,
    bk_biz_id,
    history_instance,
    collect_config_list,
    strategy_config_list,
    view_config_list,
    is_overwrite_mode=False,
):
    """
    批量导入采集配置、策略配置、视图配置
    :param username:
    :param bk_biz_id:
    :param history_instance:
    :param collect_config_list:
    :param strategy_config_list:
    :param view_config_list:
    :param is_overwrite_mode: 是否覆盖原配置
    :return:
    """
    from monitor_web.export_import.import_config import (
        import_collect,
        import_strategy,
        import_view,
    )
    from monitor_web.models import ImportDetail

    set_local_username(username)
    import_collect(bk_biz_id, history_instance, collect_config_list)
    import_strategy(bk_biz_id, history_instance, strategy_config_list, is_overwrite_mode)
    import_view(bk_biz_id, view_config_list, is_overwrite_mode)
    if (
        ImportDetail.objects.filter(history_id=history_instance.id, import_status=ImportDetailStatus.IMPORTING).count()
        == 0
    ):
        history_instance.status = ImportHistoryStatus.IMPORTED
        history_instance.save()


@task(ignore_result=True)
def remove_file(file_path):
    """
    定时删除指定文件夹
    :param file_path:
    :return:
    """
    shutil.rmtree(file_path)
    if settings.USE_CEPH:
        default_storage.delete(file_path.replace(settings.MEDIA_ROOT, ""))


@task(ignore_result=True)
def append_event_metric_list_cache(bk_event_group_id):
    """
    追加或更新新增的自定义事件入缓存表
    :param bk_event_group_id:
    :return:
    """
    from bkmonitor.models.metric_list_cache import MetricListCache
    from monitor_web.strategies.metric_list_cache import (
        BkMonitorLogCacheManager,
        CustomEventCacheManager,
    )

    set_local_username(settings.COMMON_USERNAME)
    event_group_id = int(bk_event_group_id)
    event_type = CustomEventGroup.objects.get(bk_event_group_id=event_group_id).type
    if event_type == "custom_event":
        result_table_msg = api.metadata.get_event_group.request.refresh(event_group_id=event_group_id)
        create_msg = CustomEventCacheManager().get_metrics_by_table(result_table_msg)
        for metric_msg in create_msg:
            MetricListCache.objects.update_or_create(
                metric_field=metric_msg["metric_field"],
                result_table_id=metric_msg["result_table_id"],
                related_id=metric_msg.get("related_id", ""),
                data_type_label=metric_msg.get("data_type_label"),
                data_source_label=metric_msg.get("data_source_label"),
                defaults=metric_msg,
            )
    else:
        BkMonitorLogCacheManager().run()


@task(ignore_result=True, queue="celery_resource")
def update_task_running_status(task_id):
    """
    异步查询拨测任务启动状态，更新拨测任务列表中的运行状态
    """
    set_local_username(settings.COMMON_USERNAME)
    resource.uptime_check.update_task_running_status(task_id)


@task(ignore_result=True)
def append_custom_ts_metric_list_cache(time_series_group_id):
    from bkmonitor.models.metric_list_cache import MetricListCache
    from monitor_web.strategies.metric_list_cache import CustomMetricCacheManager

    try:
        params = {
            "time_series_group_id": time_series_group_id,
        }
        results = api.metadata.get_time_series_group(params)
        for result in results:
            result["custom_ts"] = CustomTSTable.objects.get(time_series_group_id=time_series_group_id)
            create_msg = CustomMetricCacheManager().get_metrics_by_table(result)
            for metric_msg in create_msg:
                MetricListCache.objects.update_or_create(
                    metric_field=metric_msg["metric_field"],
                    result_table_id=metric_msg["result_table_id"],
                    related_id=metric_msg.get("related_id", ""),
                    data_type_label=metric_msg.get("data_type_label"),
                    data_source_label=metric_msg.get("data_source_label"),
                    defaults=metric_msg,
                )
    except BaseException as err:
        logger.error("[update_custom_ts_metric] failed, msg is {}".format(err))


@task(ignore_result=True, queue="celery_resource")
def access_aiops_by_strategy_id(strategy_id):
    from bkmonitor.data_source.handler import DataQueryHandler
    from bkmonitor.models import (
        AlgorithmModel,
        ItemModel,
        QueryConfigModel,
        StrategyModel,
    )

    strategy = StrategyModel.objects.get(id=strategy_id, is_enabled=True)
    item = ItemModel.objects.filter(strategy_id=strategy_id).first()
    detect_algorithm = AlgorithmModel.objects.filter(
        strategy_id=strategy_id,
        item_id=item.id,
        type__in=AlgorithmModel.AIOPS_ALGORITHMS,
    ).first()
    if not detect_algorithm:
        logger.info("strategy_id({}) does not config intelligent detect, skipped", strategy_id)
        return
    plan_id = detect_algorithm.config.get("plan_id")

    if not plan_id:
        logger.info("strategy_id({}) intelligent detect plan_id not exist, skipped", strategy_id)
        return

    plan_args = detect_algorithm.config.get("args")

    rt_query_config = QueryConfig.from_models(
        QueryConfigModel.objects.filter(strategy_id=strategy_id, item_id=item.id)
    )[0]

    rt_query_config.intelligent_detect["status"] = AccessStatus.CREATED
    rt_query_config.save()

    if rt_query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
        # 1. 接入
        try:
            api.metadata.access_bk_data_by_result_table(table_id=rt_query_config.result_table_id, is_access_now=True)
        except Exception as e:  # noqa
            err_msg = "access({}) to bkdata failed: {}".format(rt_query_config.result_table_id, e)
            logger.exception(err_msg)
        else:
            logger.info("access({}) to bkdata success.".format(rt_query_config.result_table_id))

        rt_scope = {"bk_biz_id": str(strategy.bk_biz_id)}
        bk_data_result_table_id = to_bk_data_rt_id(rt_query_config.result_table_id, settings.BK_DATA_RAW_TABLE_SUFFIX)
    elif rt_query_config.data_source_label == DataSourceLabel.BK_DATA:
        rt_scope = {}
        bk_data_result_table_id = rt_query_config.result_table_id
    else:
        err_msg = (
            "time series data of other platforms does not support intelligent anomaly detection algorithms, "
            "pending development"
        )
        rt_query_config.intelligent_detect["status"] = AccessStatus.FAILED
        rt_query_config.intelligent_detect["message"] = err_msg
        rt_query_config.save()
        raise Exception(err_msg)

    rt_query_config.intelligent_detect["status"] = AccessStatus.RUNNING
    rt_query_config.save()

    # 3. 创建智能检测dataflow
    metric_field = rt_query_config.metric_field
    value_fields = ["`{}`".format(f) for f in rt_query_config.agg_dimension[:]]
    group_by_fields = []
    for field in rt_query_config.agg_dimension:
        if field.upper() in FLINK_KEY_WORDS:
            group_by_fields.append(f"`{field}`")
            continue
        group_by_fields.append(field)
    value_fields.append(
        "%(method)s(`%(field)s`) as `%(field)s`" % dict(field=metric_field, method=rt_query_config.agg_method)
    )

    sql, params = (
        DataQueryHandler(rt_query_config.data_source_label, rt_query_config.data_type_label)
        .table(bk_data_result_table_id)
        .filter(**rt_scope)
        .group_by(*group_by_fields)
        .agg_condition(rt_query_config.agg_condition)
        .values(*value_fields)
        .query.sql_with_params()
    )

    strategy_sql = sql_format_params(sql=sql, params=params)

    agg_dimension = copy.deepcopy(rt_query_config.agg_dimension)
    agg_condition = []
    agg_method = "SUM" if rt_query_config.agg_method == "COUNT" else rt_query_config.agg_method
    if detect_algorithm.type == AlgorithmModel.AlgorithmChoices.AbnormalCluster:
        group = detect_algorithm.config.get("group", list())
        plan_args["$cluster"] = ",".join(list(set(agg_dimension) - set(group)))
        agg_dimension = group
        agg_condition.append({"key": "is_anomaly", "method": "eq", "value": [1]})
        agg_method = "COUNT"
    try:
        detect_data_flow = StrategyIntelligentModelDetectTask(
            strategy_id=strategy.id,
            rt_id=bk_data_result_table_id,
            metric_field=rt_query_config.metric_field,
            agg_interval=rt_query_config.agg_interval,
            agg_dimensions=agg_dimension,
            strategy_sql=strategy_sql,
            scene_id=get_scene_id_by_algorithm(detect_algorithm.type),
            plan_id=plan_id,
            plan_args=plan_args,
        )
        detect_data_flow.create_flow()
        detect_data_flow.start_flow(consuming_mode=ConsumingMode.Current)
        output_table_name = detect_data_flow.output_table_name

        if detect_data_flow.flow_status != DataFlow.Status.Running:
            raise Exception(f"flow status is not running, current flow status:({detect_data_flow.flow_status})")

    except BaseException as e:  # noqa
        retries = rt_query_config.intelligent_detect.get("retries", 0)
        if retries < AIOPS_ACCESS_MAX_RETRIES:
            err_msg = "create intelligent detect by strategy_id({}) failed: {}, retrying: {}/{}".format(
                strategy.id,
                e,
                retries,
                AIOPS_ACCESS_MAX_RETRIES,
            )
            logger.exception(err_msg)
            # 失败之后继续尝试
            access_aiops_by_strategy_id.apply_async(args=(strategy_id,), countdown=AIOPS_ACCESS_RETRY_INTERVAL)
            rt_query_config.intelligent_detect["status"] = AccessStatus.RUNNING
            rt_query_config.intelligent_detect["retries"] = retries + 1
            rt_query_config.intelligent_detect["message"] = err_msg
            rt_query_config.save()
        else:
            # 超过最大重试次数后直接失败
            err_msg = "create intelligent detect by strategy_id({}) failed: {}".format(strategy.id, e)
            logger.exception(err_msg)
            rt_query_config.intelligent_detect["status"] = AccessStatus.FAILED
            rt_query_config.intelligent_detect["message"] = err_msg
            rt_query_config.save()

            # 发邮件
            params = {
                "receiver__username": settings.BK_DATA_PROJECT_MAINTAINER,
                "title": _("{}创建异常检测").format(strategy_id),
                "content": traceback.format_exc().replace("\n", "<br>"),
                "is_content_base64": True,
            }
            try:
                api.cmsi.send_mail(**params)
            except BaseException:  # noqa
                logger.exception(
                    "send.mail({}) failed, content:({})".format(settings.BK_DATA_PROJECT_MAINTAINER, params)
                )

        # 只要失败就直接退出
        return

    # 根据 visual_type 不同，查询不同的字段
    if detect_algorithm.config.get("visual_type") == VisualType.BOUNDARY:
        extend_fields = ["is_anomaly", "lower_bound", "upper_bound", "extra_info"]
    elif detect_algorithm.config.get("visual_type") == VisualType.SCORE:
        extend_fields = ["is_anomaly", "anomaly_score", "extra_info"]
    elif detect_algorithm.config.get("visual_type") == VisualType.FORECASTING:
        extend_fields = ["predict", "lower_bound", "upper_bound"]
    elif detect_algorithm.type == AlgorithmModel.AlgorithmChoices.AbnormalCluster:
        extend_fields = ["cluster"]
    else:
        extend_fields = ["is_anomaly", "extra_info"]

    # 将配置好的模型生成的rt_id放到extend_fields中，前端会根据这张表来查询数据
    rt_query_config.intelligent_detect = {
        "data_flow_id": detect_data_flow.data_flow.flow_id,
        "data_source_label": DataSourceLabel.BK_DATA,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "result_table_id": output_table_name,
        "metric_field": "value",
        "extend_fields": {"values": extend_fields},
        "agg_condition": agg_condition,
        "agg_dimension": agg_dimension,
        "plan_id": plan_id,
        "agg_method": agg_method,
        "status": AccessStatus.SUCCESS,
        "message": "create dataflow success",
    }
    rt_query_config.save()


@task(ignore_result=True)
def access_pending_aiops_strategy():
    """
    找到状态为 PENDING 的 AIOps 策略，并尝试接入
    适用于通过 kernel API 创建的策略，由于缺少异步 Worker 未能及时触发接入的场景
    """
    from bkmonitor.models import AlgorithmModel, QueryConfigModel, StrategyModel

    # 找出包含智能算法的策略
    algorithms = set(
        AlgorithmModel.objects.filter(type__in=AlgorithmModel.AIOPS_ALGORITHMS).values_list("strategy_id", flat=True)
    )
    # 找出接入状态为PENDING的策略
    query_configs = set(
        QueryConfigModel.objects.filter(config__intelligent_detect__status=AccessStatus.PENDING).values_list(
            "strategy_id", flat=True
        )
    )

    # 两者做交集
    strategy_ids = algorithms & query_configs

    # 过滤出启用的策略
    enabled_strategy_ids = set(
        StrategyModel.objects.filter(id__in=strategy_ids, is_enabled=True).values_list("id", flat=True)
    )

    for strategy_id in enabled_strategy_ids:
        access_aiops_by_strategy_id.delay(strategy_id)

    logger.info(
        "[access_pending_aiops_strategy] send %d strategies: %s", len(enabled_strategy_ids), enabled_strategy_ids
    )


@task(ignore_result=True)
def update_aiops_dataflow_status():
    """
    aiops的状态维护
    增加：
        - 新建dataflow
    删除：
        - 延时删除dataflow
    修改：
        - 如果表未变更，只修改部分查询条件等，则直接更新dataflow
        - 如果表发生了切换，那么需要重建dataflow(停用已有的dataflow，新建一个)

    注意：
    这里没有发多个任务运行，是因为同时操作多个任务，计算平台会出错
    后续策略配置多了后，需要拆解这里的任务
    """
    if not settings.IS_ACCESS_BK_DATA:
        return

    from bkmonitor.dataflow.task.intelligent_detect import (
        StrategyIntelligentModelDetectTask,
    )
    from bkmonitor.models import AlgorithmModel, QueryConfigModel, StrategyModel

    result = api.bkdata.get_data_flow_list(project_id=settings.BK_DATA_PROJECT_ID)
    if not result:
        logger.info("no dataflow exists in project({})".format(settings.BK_DATA_PROJECT_ID))

    # 找到当前计算平台已有的模型应用dataflow
    strategy_to_data_flow = {}
    for flow in result:
        # 去掉没在运行的dataflow
        flow_status = flow["status"]
        if flow_status != DataFlow.Status.Running:
            continue

        # 从名称判断是否为智能异常检测的dataflow
        flow_name = flow.get("flow_name", "")
        if StrategyIntelligentModelDetectTask.FLOW_NAME_KEY not in flow_name:
            continue

        groups = flow_name.split(StrategyIntelligentModelDetectTask.FLOW_NAME_KEY)
        groups = [i.strip() for i in groups if i.strip()]
        if len(groups) != 2:
            continue

        strategy_id, rt_id = groups
        if not strategy_id.isdigit():
            continue

        strategy_to_data_flow.setdefault(int(strategy_id), []).append({"rt_id": rt_id, "flow": flow})

    # 找到监控平台配置了智能异常检测的所有策略
    qs = AlgorithmModel.objects.filter(type__in=AlgorithmModel.AIOPS_ALGORITHMS).values_list("strategy_id", flat=True)
    strategy_ids = list(qs)

    strategy_ids = list(StrategyModel.objects.filter(id__in=strategy_ids, is_enabled=True).values_list("id", flat=True))
    query_configs = QueryConfig.from_models(QueryConfigModel.objects.filter(strategy_id__in=strategy_ids))
    strategy_to_query_config = {query_config.strategy_id: query_config for query_config in query_configs}

    # 停用掉策略已停用或删除，但是计算平台仍然在运行的dataflow
    for strategy_id in set(strategy_to_data_flow.keys()) - set(strategy_to_query_config.keys()):
        flow_list = strategy_to_data_flow.get(strategy_id)
        for f in flow_list:
            flow_id, flow_status = f["flow"]["flow_id"], f["flow"]["status"]
            try:
                logger.info("stop dataflow(%s) because strategy(%s) is disabled or deleted", flow_id, strategy_id)
                api.bkdata.stop_data_flow(flow_id=flow_id)
            except BaseException:  # noqa
                logger.exception("stop dataflow({}) error".format(flow_id))

    # 创建新的dataflow
    for strategy_id in set(strategy_to_query_config.keys()) - set(strategy_to_data_flow.keys()):
        try:
            logger.info("create dataflow because strategy(%s) not create yet", strategy_id)
            access_aiops_by_strategy_id(strategy_id=strategy_id)
        except BaseException:  # noqa
            logger.exception("create strategy({}) dataflow status error".format(strategy_id))

    # 修改正在运行的dataflow，保持和监控平台的策略配置一致
    for strategy_id in set(strategy_to_query_config.keys()) & set(strategy_to_data_flow.keys()):
        try:
            rt_query_config = strategy_to_query_config.get(strategy_id)
            if rt_query_config.data_source_label == DataSourceLabel.BK_DATA:
                bk_data_result_table_id = rt_query_config.result_table_id
            else:
                bk_data_result_table_id = to_bk_data_rt_id(
                    rt_query_config.result_table_id, settings.BK_DATA_RAW_TABLE_SUFFIX
                )

            # 去掉多余的dataflow
            flow_list = strategy_to_data_flow.get(strategy_id)
            for f in flow_list:
                rt_id = f["rt_id"]
                flow_id = f["flow"]["flow_id"]
                if rt_id != bk_data_result_table_id:
                    try:
                        logger.info(
                            "stop dataflow because strategy(%s) rt is changed (%s -> %s)",
                            strategy_id,
                            rt_id,
                            bk_data_result_table_id,
                        )
                        api.bkdata.stop_data_flow(flow_id=flow_id)
                    except BaseException:  # noqa
                        logger.exception("stop dataflow({}) error".format(flow_id))

            access_aiops_by_strategy_id(strategy_id=strategy_id)
        except BaseException:  # noqa
            logger.exception("update strategy({}) dataflow status error".format(strategy_id))


@task(ignore_result=True)
def update_report_receivers():
    """
    更新订阅报表接收组人员
    """
    from bkmonitor.models import ReportItems
    from monitor_web.report.resources import ReportCreateOrUpdateResource

    report_items = ReportItems.objects.all()
    for report_item in report_items:
        receivers = ReportCreateOrUpdateResource().fetch_group_members(report_item.receivers, "receiver")
        # 补充用户被添加进来的时间
        for receiver in receivers:
            if "create_time" not in receiver:
                receiver["create_time"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        report_item.receivers = receivers
        report_item.save()


@task(ignore_result=True)
def keep_alive():
    """
    低频队列Worker保活任务
    """
    print("alive")


@task(ignore_result=True)
def collect_metric(collect):
    """
    异步执行采集任务
    """
    try:
        from bkmonitor.utils.request import set_request_username

        set_request_username("admin")
        start_time = time.time()
        collect.collect()
        end_time = time.time()
        logger.info(
            "[collect_metric_data] Collection task execution success; Collector: %s; Cost: %.6f",
            collect.__class__.__name__,
            end_time - start_time,
        )
    except BaseException as error:
        logger.exception(
            "[collect_metric_data] Collection task execution failed; Collector: %s; Error: %s",
            collect.__class__.__name__,
            error,
        )


@task(ignore_result=True)
def update_statistics_data():
    """
    定时更新运营指标数据
    """
    from monitor_web.statistics.v2.factory import INSTALLED_COLLECTORS

    for collector in INSTALLED_COLLECTORS:
        collect_metric.apply_async(args=(collector(),))


def get_multivariate_anomaly_strategy(bk_biz_id, scene_id):
    """
    获取多指标异常策略
    """
    from bkmonitor.models import AlgorithmModel, StrategyModel

    strategy_objs = StrategyModel.objects.filter(bk_biz_id=bk_biz_id)
    strategy_ids = [s.id for s in strategy_objs]
    return AlgorithmModel.objects.filter(
        strategy_id__in=strategy_ids,
        type=AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection,
        config__contains={"scene_id": scene_id},
    )


def parse_scene_metrics(plan_args):
    """
    解析host场景的指标数据
    """
    from monitor_web.aiops.host_monitor.resources import query_metric_info

    metric_list_str = plan_args["$metric_list"] if "$metric_list" in plan_args else ""
    # 格式化metric label
    metric_list = metric_list_str.replace("__", ".").split(",")
    metrics_info = query_metric_info(metric_list)
    # 转化数据格式
    return [
        {
            "metric_id": get_metric_id(
                data_source_label=metric.data_source_label,
                data_type_label=metric.data_type_label,
                result_table_id=metric.result_table_id,
                metric_field=metric.metric_field,
            ),
            "name": _(metric.metric_field_name),
            "unit": metric.unit,
            "metric_name": metric.bkmonitor_metric_fullname,
        }
        for metric in metrics_info
    ]


@task(ignore_result=True)
def access_aiops_multivariate_anomaly_detection_by_bk_biz_id(bk_biz_id, need_access_scenes):
    """
    根据业务ID创建多指标异常检测flow
    @param bk_biz_id: 业务ID
    @param need_access_scenes: 需要接入的场景
    @return:
    """

    from bkmonitor.aiops.utils import AiSetting
    from bkmonitor.data_source.handler import DataQueryHandler

    # 查询该业务是否配置有ai设置
    ai_setting = AiSetting(bk_biz_id=bk_biz_id)

    multivariate_anomaly_detection = ai_setting.multivariate_anomaly_detection
    # 查询该业务下的每个场景是否开启多指标异常检测
    for scene in need_access_scenes:
        scene_config = getattr(multivariate_anomaly_detection, scene)
        if not scene_config.is_enabled:
            continue

        # 如果没有对应场景的dataclass则跳过
        scene_params_dataclass = MULTIVARIATE_ANOMALY_DETECTION_SCENE_PARAMS_MAP.get(scene, None)
        if not scene_params_dataclass:
            continue

        intelligent_detect = scene_config.intelligent_detect

        intelligent_detect["status"] = AccessStatus.RUNNING
        ai_setting.save(multivariate_anomaly_detection=multivariate_anomaly_detection.to_dict())

        # 刷新策略中的算法指标配置
        algorithm_objs = get_multivariate_anomaly_strategy(bk_biz_id, scene)
        metrics_config = parse_scene_metrics(scene_config.plan_args)
        # 批了更新config
        for obj in algorithm_objs:
            obj_config = obj.config
            obj_config["metrics"] = metrics_config
            # 验证数据格式是否正确，避免格式没有同步
            serializer = MultivariateAnomalyDetectionSerializer(data=obj_config)
            serializer.is_valid(raise_exception=True)
            obj.config = serializer.validated_data
            obj.save()

        # 获取对应场景的参数开始构建flow
        scene_params = scene_params_dataclass()

        # 构建实时计算节点的sql
        sql_build_params = scene_params.sql_build_params
        agg_condition = sql_build_params["agg_condition"]

        sql, params = (
            DataQueryHandler(sql_build_params["data_source_label"], sql_build_params["data_type_label"])
            .table(sql_build_params["result_table_id"])
            .filter(**{"bk_biz_id": str(bk_biz_id)})
            .agg_condition(agg_condition)
            .values(*sql_build_params["value_fields"])
            .query.sql_with_params()
        )

        scene_sql = sql_format_params(sql=sql, params=params)

        # flow创建
        try:
            business_host_flow = MultivariateAnomalyIntelligentModelDetectTask(
                access_bk_biz_id=bk_biz_id,
                bk_biz_id=settings.BK_DATA_BK_BIZ_ID,
                scene_name=scene,
                rt_id=sql_build_params["result_table_id"],
                metric_field=MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD,
                agg_dimensions=scene_params.agg_dimensions,
                strategy_sql=scene_sql,
                scene_id=settings.BK_DATA_SCENE_ID_MULTIVARIATE_ANOMALY_DETECTION,
                plan_id=scene_config.default_plan_id,
                plan_args=scene_config.plan_args,
            )
            business_host_flow.create_flow()
            business_host_flow.start_flow(consuming_mode=ConsumingMode.Current)
            output_table_name = business_host_flow.output_table_name

            intelligent_detect = {
                "data_flow_id": business_host_flow.data_flow.flow_id,
                "data_source_label": DataSourceLabel.BK_DATA,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "result_table_id": output_table_name,
                "metric_field": "metrics_json",
                "extend_fields": {},
                "agg_condition": agg_condition,
                "agg_dimension": scene_params.agg_dimensions,
                "plan_id": scene_config.default_plan_id,
                "agg_method": "",
                "status": AccessStatus.SUCCESS,
                "message": "create dataflow success",
            }

            scene_config.intelligent_detect = intelligent_detect
            ai_setting.save(multivariate_anomaly_detection=multivariate_anomaly_detection.to_dict())
        except BaseException as e:  # noqa
            err_msg = "create intelligent detect by bk_biz_id({}), scene({}) failed: {}".format(bk_biz_id, scene, e)
            intelligent_detect["status"] = AccessStatus.FAILED
            intelligent_detect["message"] = err_msg
            ai_setting.save(multivariate_anomaly_detection=multivariate_anomaly_detection.to_dict())
            logger.exception(err_msg)
            params = {
                "receiver__username": settings.BK_DATA_PROJECT_MAINTAINER,
                "title": _("{} {}创建异常检测").format(bk_biz_id, scene),
                "content": traceback.format_exc().replace("\n", "<br>"),
                "is_content_base64": True,
            }
            try:
                api.cmsi.send_mail(**params)
            except BaseException:  # noqa
                logger.exception(
                    "send.mail({}) failed, content:({})".format(settings.BK_DATA_PROJECT_MAINTAINER, params)
                )
            return


@task(ignore_result=True)
def stop_aiops_multivariate_anomaly_detection_flow(access_bk_biz_id, need_stop_scenes):
    """
    停止对应业务ai设置下的场景
    @param access_bk_biz_id:
    @param need_stop_scenes: 需要关闭的场景列表
    @return:
    """
    scene_name_mapping = MultivariateAnomalyIntelligentModelDetectTask.SCENE_NAME_MAPPING
    for need_stop_scene in need_stop_scenes:
        flow_name = MultivariateAnomalyIntelligentModelDetectTask.build_flow_name(
            access_bk_biz_id, scene_name_mapping[need_stop_scene]
        )
        try:
            data_flow = DataFlow.from_bkdata_by_flow_name(flow_name)
            if data_flow.flow_info.get("status") == DataFlow.Status.Running:
                data_flow.stop()
        except DataFlowNotExists:
            logger.exception(
                "biz({}) need close scene({}) flow {} not exists".format(access_bk_biz_id, need_stop_scene, flow_name)
            )
            continue


@task(ignore_result=True)
def access_biz_metric_recommend_flow(access_bk_biz_id):
    """接入业务指标推荐flow

    :param access_bk_biz_id: 待接入的业务id
    """
    from bkmonitor.aiops.utils import AiSetting

    # 查询该业务是否配置有ai设置
    ai_setting = AiSetting(bk_biz_id=access_bk_biz_id)
    metric_recommend = ai_setting.metric_recommend

    # 构建flow
    try:
        metric_recommend_task = MetricRecommendTask(
            access_bk_biz_id=access_bk_biz_id,
            scene_id=get_scene_id_by_algorithm(METRIC_RECOMMENDATION_SCENE_NAME),
            plan_id=get_plan_id_by_algorithm(METRIC_RECOMMENDATION_SCENE_NAME),
        )

        metric_recommend_task.create_flow()
        metric_recommend_task.start_flow(consuming_mode=ConsumingMode.Current)
        metric_recommend.is_enabled = True
        metric_recommend.result_table_id = metric_recommend_task.node_list[-1].output_table_name
        ai_setting.save()
        # 此处记得从继续启动
    except Exception as e:  # noqa
        err_msg = "create metric recommend by bk_biz_id({}) failed: {}".format(access_bk_biz_id, e)
        logger.exception(err_msg)
