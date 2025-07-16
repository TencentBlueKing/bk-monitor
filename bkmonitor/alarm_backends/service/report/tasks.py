"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import logging
from collections import defaultdict

import arrow
from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q

from alarm_backends.service.report.render.dashboard import (
    RenderDashboardConfig,
    render_dashboard_panel,
)
from alarm_backends.service.scheduler.app import app
from alarm_backends.service.selfmonitor.collect.redis import RedisMetricCollectReport
from alarm_backends.service.selfmonitor.collect.transfer import TransferMetricHelper
from bkmonitor.browser import get_or_create_eventloop
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models import (
    RenderImageTask,
    ReportContents,
    ReportItems,
    ReportStatus,
    StatisticsMetric,
)
from bkmonitor.utils.custom_report_tools import custom_report_tool
from bkmonitor.utils.range import TIME_MATCH_CLASS_MAP
from bkmonitor.utils.range.period import TimeMatch, TimeMatchBySingle
from bkmonitor.utils.time_tools import localtime
from core.prometheus import metrics
from core.statistics.metric import Metric
from metadata.models import DataSource

GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")
logger = logging.getLogger("bkmonitor.cron_report")


def operation_data_custom_report_v2():
    """
    新运营数据自定义上报
    """
    all_data = []
    try:
        bk_data_id = int(GlobalConfig.objects.get(key="STATISTICS_REPORT_DATA_ID").value)
    except GlobalConfig.DoesNotExist:
        bk_data_id = settings.STATISTICS_REPORT_DATA_ID

    report_tool = custom_report_tool(bk_data_id)

    timestamp = arrow.now().timestamp
    # 获取运营数据，更新时间大于1天前的直接忽略
    statistics = StatisticsMetric.objects.filter(update_time__gte=timestamp - 24 * 60 * 60)
    for stat in statistics:
        metrics = Metric.loads(stat.data)
        for metric in metrics.export_json():
            data = {
                # 指标，必需项
                "metrics": {metric["name"]: metric["value"]},
                # 来源标识
                "target": settings.BK_PAAS_INNER_HOST,
                # 数据时间，精确到毫秒，非必需项
                "timestamp": timestamp * 1000,
            }

            # 补充维度
            if metric["labels"]:
                dimensions = metric["labels"]
                if "target_biz_id" in dimensions:
                    dimensions["bk_biz_id"] = dimensions["target_biz_id"]
                data["dimension"] = dimensions

            all_data.append(data)

    # 数据上报
    report_tool.send_data_by_http(all_data, DataSource.objects.get(bk_data_id=bk_data_id).token)
    logger.info("[operation_data_custom_report_v2] success, dataid: %d, data_len: %d", bk_data_id, len(all_data))


def report_mail_detect():
    """
    检测是否有邮件需要发送
    """
    from alarm_backends.service.report.handler import ReportHandler

    today = datetime.datetime.today().strftime("%Y-%m-%d")
    now_time = arrow.now()
    ten_minute_ago = TimeMatch.convert_datetime_to_arrow(datetime.datetime.now() - datetime.timedelta(minutes=10))
    report_items = list(
        ReportItems.objects.filter(
            Q(is_enabled=True) & (Q(last_send_time=None) | Q(last_send_time__lt=today) | Q(frequency__type=5))
        )
    )
    # 当频率为5的时候，需要按小时发送，所以要拿出来比较

    # 汇总所有订阅的content信息
    report_items_contents = defaultdict(list)
    for report_content in list(ReportContents.objects.filter(id__in=[item.id for item in report_items]).values()):
        report_items_contents[report_content["report_item"]] += report_content

    # 处理订阅
    for item in report_items:
        shield_type = int(item.frequency.get("type", "-1"))
        time_match_class = TIME_MATCH_CLASS_MAP.get(shield_type, TimeMatchBySingle)
        # 最后发送时间进行本地化
        last_send_time = localtime(item.last_send_time) if item.last_send_time else None
        # 补充begin_time和end_time
        item.frequency["begin_time"] = ten_minute_ago.format("HH:mm:ss")
        item.frequency["end_time"] = now_time.format("HH:mm:ss")
        time_check = time_match_class(item.frequency, ten_minute_ago, now_time)
        run_time_strings = []
        if item.frequency["type"] == 1:
            run_time_strings = [item.frequency["run_time"]]
        elif item.frequency["type"] == 5:
            current_hour = datetime.datetime.today().strftime("%H")
            run_time_config = ReportItems.HourFrequencyTime.TIME_CONFIG.get(str(item.frequency["hour"]))
            if run_time_config:
                hours = run_time_config.get("hours", [current_hour])
                minutes = run_time_config.get("minutes", ["00"])
                for hour in hours:
                    if hour != current_hour:
                        # 发送小时非当前时间，直接返回
                        continue
                    for minute in minutes:
                        if last_send_time:
                            last_send_hour = last_send_time.strftime("%H")
                            last_send_min = last_send_time.strftime("%M")
                            if last_send_hour == current_hour and last_send_min >= minute:
                                # 当前这个小时，且在检测的这个分钟已经发送过，则不再检测发送
                                # 因为有一分钟裕量，否则有可能前后一分钟都会命中
                                continue
                        run_time_strings.append(f"{today} {hour}:{minute}:00")
        else:
            run_time_strings = [f"{datetime.datetime.today().strftime('%Y-%m-%d')} {item.frequency['run_time']}"]
        for time_str in run_time_strings:
            run_time = TimeMatch.convert_datetime_to_arrow(datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S"))
            if time_check.is_match(run_time):
                # 更新发送时间
                item.last_send_time = datetime.datetime.now()
                item.save()
                # 发送邮件
                logger.info("[mail_report] start process and render mails on run time(%s)...", run_time)
                ReportHandler(bk_tenant_id=item.bk_tenant_id, item_id=item.id).process_and_render_mails()
                logger.info("[mail_report] end process and render mails...")
                # 满足一次条件直接终止
                break


@app.task(ignore_result=True, queue="celery_report_cron")
def render_mails(
    mail_handler,
    report_item: ReportItems,
    report_item_contents,
    receivers,
    is_superuser,
    channel_name=ReportItems.Channel.USER,
):
    """
    渲染并发送邮件
    :param channel_name: 订阅渠道名称
    :param is_superuser: 创建者是否超级管理员
    :param mail_handler: 报表处理器
    :param report_item: 订阅报表
    :param report_item_contents: 报表内容
    :param receivers: 接收者
    """
    if not receivers:
        # 没有订阅者的情况下，直接返回
        logger.info(f"[mail_report] ignore send mail({report_item.mail_title}) due to no receivers")
        return
    logger.info(f"[mail_report] report_item({report_item.id}) start...")
    status = {
        "bk_tenant_id": report_item.bk_tenant_id,
        "report_item": mail_handler.item_id,
        "mail_title": report_item.mail_title,
        "create_time": datetime.datetime.now(tz=datetime.timezone.utc),
        "details": {
            "receivers": receivers,
            "report_item_contents": report_item_contents,
            "error_message": {},
            "channel_name": channel_name,
        },
        "is_success": True,
    }
    exc = None
    # 接收人
    receivers_string = ", ".join([str(receiver) for receiver in receivers])
    bk_biz_ids = []
    if channel_name == ReportItems.Channel.USER:
        # 只有通知渠道是用户的情况下，才考虑获取权限信息
        try:
            # 获取订阅者的业务列表
            perm_client = Permission(username=receivers[0], bk_tenant_id=report_item.bk_tenant_id)
            perm_client.skip_check = False
            spaces = perm_client.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
            bk_biz_ids = [s["bk_biz_id"] for s in spaces]
        except Exception as error:
            logger.exception(
                "[mail_report] get business info of report_item(%s) failed: %s", report_item.id, str(error)
            )
            bk_biz_ids = []

    try:
        render_args, err_msg = mail_handler.render_images_to_html(
            report_item.bk_tenant_id,
            report_item.mail_title,
            report_item_contents,
            bk_biz_ids,
            receivers,
            report_item.frequency,
            is_superuser,
            is_link_enabled=report_item.is_link_enabled,
            channel_name=channel_name,
        )
        status["mail_title"] = f"{report_item.mail_title} {render_args['mail_title_time']}"
        if err_msg:
            status["details"]["error_message"][receivers_string] = err_msg
        if channel_name == ReportItems.Channel.WXBOT:
            # 订阅渠道是wxbot的情况
            result = mail_handler.send_wxbots(render_args, receivers)
        else:
            result = mail_handler.send_mails(render_args, receivers)
        if isinstance(result, str):
            failed_list = []
        else:
            failed_list = [msg for msg in result if msg]

        if not failed_list:
            ReportStatus.objects.create(**status)
        else:
            # 将错误信息写入error_message
            status["details"]["error_message"][receivers_string] = failed_list
            status["is_success"] = False
            ReportStatus.objects.create(**status)
    except Exception as e:
        exc = e
        # 有用户发送失败了也得继续，不能影响其他用户的发送流程
        logger.exception(f"[mail_report] Send mail failed: {e}")
        status["details"]["error_message"][receivers_string] = str(e)
        status["is_success"] = False
        ReportStatus.objects.create(**status)

    if report_item.last_send_time:
        latency = datetime.datetime.now().timestamp() - report_item.last_send_time.timestamp()
        metrics.MAIL_REPORT_SEND_LATENCY.labels(item_id=report_item.id).observe(latency)

    metrics.MAIL_REPORT_SEND_COUNT.labels(
        item_id=report_item.id, status=metrics.StatusEnum.from_exc(exc), exception=exc
    ).inc()
    metrics.report_all()


def report_transfer_operation_data():
    """上报 transfer 运营数据"""
    h = TransferMetricHelper()
    h.fetch()
    h.report()


# 采集周期（小于1min）
collector_interval = 30


def collect_redis_metric():
    # 这次采完后， 1min内还剩seq次，通过异步任务发送
    seq = 60 / collector_interval - 1
    if seq > 0:
        run_collect_redis_metric.apply_async(kwargs={"seq": seq}, countdown=collector_interval)
    RedisMetricCollectReport().collect_redis_metric_data()


@app.task(ignore_result=True, queue="celery_report_cron")
def run_collect_redis_metric(seq):
    # 采集一次后判断是否要继续采集
    seq -= 1
    if seq > 0:
        run_collect_redis_metric.apply_async(kwargs={"seq": seq}, countdown=collector_interval)
    RedisMetricCollectReport().collect_redis_metric_data()


@app.task(ignore_result=True, queue="celery_report_cron")
def render_image_task(task: RenderImageTask):
    """
    渲染图片任务

    :param task: 渲染图片任务
    """
    # 更新任务状态为渲染中
    task.start_time = datetime.datetime.now()
    task.status = RenderImageTask.Status.RENDERING
    task.error = ""
    task.save()

    event_loop = get_or_create_eventloop()

    # 根据任务类型，定义渲染函数及配置
    func, config = None, None
    if task.type == RenderImageTask.Type.DASHBOARD:
        config = RenderDashboardConfig(**task.options, bk_tenant_id=task.bk_tenant_id)
        func = render_dashboard_panel
    else:
        raise ValueError(f"Invalid task type: {task.type}")

    image: bytes = None
    if func:
        # 执行渲染
        try:
            image = event_loop.run_until_complete(func(config))
        except Exception as e:
            task.error = str(e)
    else:
        task.error = f"Invalid task type: {task.type}"

    # 完成时间
    task.finish_time = datetime.datetime.now()

    # 如果错误，则状态为失败
    if task.error:
        task.status = RenderImageTask.Status.FAILED
    else:
        task.status = RenderImageTask.Status.SUCCESS
        task.image = ContentFile(image, name=f"{task.type}/{str(task.task_id)}.{config.image_format}")

    task.save()
