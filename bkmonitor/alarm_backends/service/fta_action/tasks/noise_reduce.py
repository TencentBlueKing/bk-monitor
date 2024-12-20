import logging
import time
from collections import defaultdict

from django.conf import settings
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from alarm_backends.core.alert import Alert
from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.core.cache import key
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.fta_action.utils import PushActionProcessor
from alarm_backends.service.scheduler.app import app
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models import ActionInstance
from bkmonitor.utils.common_utils import count_md5
from constants.action import ActionSignal
from constants.alert import HandleStage
from core.errors.alarm_backends import LockError

logger = logging.getLogger("fta_action.run")


@app.task(ignore_result=True, queue="celery_action")
def run_noise_reduce_task(processor):
    processor.process()


class NoiseReduceRecordProcessor:
    def __init__(self, notice_config, signal, strategy_id, alert: AlertDocument, generate_uuid):
        self.noise_reduce_config = notice_config.get("options", {}).get("noise_reduce_config", {})
        self.signal = signal
        self.strategy_id = strategy_id
        self.redis_client = key.NOISE_REDUCE_ABNORMAL_KEY.client
        self.alert = alert
        self.generate_uuid = generate_uuid
        self.noise_dimension_hash = count_md5(self.noise_reduce_config.get("dimensions", []))
        self.abnormal_record_key = key.NOISE_REDUCE_ABNORMAL_KEY.get_key(
            strategy_id=self.strategy_id, noise_dimension_hash=self.noise_dimension_hash, severity=self.alert.severity
        )
        self.alert_record_key = key.NOISE_REDUCE_ALERT_KEY.get_key(
            strategy_id=self.strategy_id, noise_dimension_hash=self.noise_dimension_hash, severity=self.alert.severity
        )

    @cached_property
    def need_noise_reduce(self):
        """
        是否需要在新建任务的时候进行通知降噪
        :param notice_config: 通知配置
        :param signal: 通知信号
        :param execute_times:执行次数
        :return:
        """
        return self.signal == ActionSignal.ABNORMAL and self.noise_reduce_config.get("is_enabled")

    def process(self):
        if not self.need_noise_reduce:
            return False

        logger.info(
            "start to record dimension values of strategy(%s), start alert(%s)", self.strategy_id, self.alert.id
        )
        current_timestamp = int(time.time())

        alert_dimensions = {dimension.key: dimension.value for dimension in self.alert.dimensions}

        dimensions = self.alert.origin_alarm["data"]["dimensions"] if self.alert.origin_alarm else alert_dimensions

        dimension_value = {
            dimension_key: dimensions.get(dimension_key) for dimension_key in self.noise_reduce_config["dimensions"]
        }
        dimension_value_hash = count_md5(dimension_value)
        try:
            with service_lock(
                key.NOISE_REDUCE_INIT_LOCK_KEY,
                strategy_id=self.strategy_id,
                noise_dimension_hash=self.noise_dimension_hash,
            ):
                # 获取到锁之后，检测是否已有降噪窗口
                if not self.redis_client.zrangebyscore(
                    self.abnormal_record_key,
                    (current_timestamp - settings.NOISE_REDUCE_TIMEDELTA * 60),
                    current_timestamp,
                ):
                    execute_processor = NoiseReduceExecuteProcessor(
                        self.noise_reduce_config, self.strategy_id, self.alert.latest_time, self.alert.severity
                    )
                    task_id = run_noise_reduce_task.apply_async(
                        (execute_processor,),
                        expires=(settings.NOISE_REDUCE_TIMEDELTA + 2) * 60,
                        countdown=settings.NOISE_REDUCE_TIMEDELTA * 60,
                    )
                    logger.info(
                        "start noise reduce window for strategy(%s), new task(%s), start alert(%s)",
                        self.strategy_id,
                        task_id,
                        self.alert.id,
                    )
        except LockError:
            # 获取锁错误表示窗口当前策略有告警在并发处理，可以忽略
            logger.info(
                "noise reduce window of strategy(%s) already exist, current alert(%s)", self.strategy_id, self.alert.id
            )

        # 记录信息
        self.redis_client.zadd(self.abnormal_record_key, {dimension_value_hash: current_timestamp})
        self.redis_client.zadd(
            self.alert_record_key, {"{}--{}".format(self.alert.id, self.generate_uuid): current_timestamp}
        )

        # 插入日志
        action_log = dict(
            op_type=AlertLog.OpType.ACTION,
            alert_id=[self.alert.id],
            description=_("当前告警策略正在进行降噪处理中，通知被抑制，满足降噪条件之后将会重新发出"),
            time=current_timestamp,
            create_time=current_timestamp,
            event_id=current_timestamp,
        )
        AlertLog.bulk_create([AlertLog(**action_log)])

        logger.info("end to record dimension values of strategy(%s), start alert(%s)", self.strategy_id, self.alert.id)
        return True


class NoiseReduceExecuteProcessor:
    def __init__(self, noise_reduce_config, strategy_id, latest_time, severity):
        self.noise_reduce_config = noise_reduce_config
        self.count = self.noise_reduce_config.get("count")
        self.strategy_id = strategy_id
        self.begin_time = latest_time
        self.end_time = None
        self.noise_dimension_hash = count_md5(self.noise_reduce_config["dimensions"])
        self.redis_client = None
        self.need_notice = False
        self.total_record_key = key.NOISE_REDUCE_TOTAL_KEY.get_key(
            strategy_id=self.strategy_id, noise_dimension_hash=self.noise_dimension_hash
        )
        self.abnormal_record_key = key.NOISE_REDUCE_ABNORMAL_KEY.get_key(
            strategy_id=self.strategy_id, noise_dimension_hash=self.noise_dimension_hash, severity=severity
        )
        self.alert_record_key = key.NOISE_REDUCE_ALERT_KEY.get_key(
            strategy_id=self.strategy_id, noise_dimension_hash=self.noise_dimension_hash, severity=severity
        )

    def process(self):
        # 插入日志

        self.end_time = int(time.time())
        self.redis_client = key.NOISE_REDUCE_TOTAL_KEY.client
        dimensions = ",".join(self.noise_reduce_config["dimensions"])
        logger.info(
            "begin execute noise reduce task of strategy(%s) dimension_hash(%s) dimensions(%s)",
            self.strategy_id,
            self.noise_dimension_hash,
            dimensions,
        )
        try:
            with service_lock(
                key.NOISE_REDUCE_OPERATE_LOCK_KEY,
                strategy_id=self.strategy_id,
                noise_dimension_hash=self.noise_dimension_hash,
            ):
                dimension_hash_keys = self.redis_client.zrangebyscore(
                    self.abnormal_record_key, self.begin_time, self.end_time
                )
                total_dimension_hash_keys = self.redis_client.zrangebyscore(
                    self.total_record_key, self.begin_time, self.end_time
                )
                alert_keys = self.redis_client.zrangebyscore(self.alert_record_key, self.begin_time, self.end_time)
                alert_info = [alert_key.split("--") for alert_key in alert_keys]
                alert_ids = [item[0] for item in alert_info]
                generate_uuids = [item[1] for item in alert_info]
                self.clear_cache()

                noise_percent = (
                    len(dimension_hash_keys) * 100 // len(total_dimension_hash_keys)
                    if len(total_dimension_hash_keys)
                    else 0
                )

                if len(dimension_hash_keys) * 100 // len(total_dimension_hash_keys) < self.count:
                    action_log = dict(
                        op_type=AlertLog.OpType.ACTION,
                        alert_id=alert_ids,
                        description=_("在一个降噪收敛窗口（{}min）内, 未达到设置的阈值{}%, 告警通知已被抑制, 当前比值为{}%").format(
                            settings.NOISE_REDUCE_TIMEDELTA, self.count, noise_percent
                        ),
                        time=self.end_time,
                        create_time=self.end_time,
                        event_id=self.end_time,
                    )
                    AlertLog.bulk_create([AlertLog(**action_log)])

                    logger.info(
                        "count(%s) of noise reduce task of strategy(%s) dimension_hash(%s) is less than settings(%s), "
                        "notice would be canceled",
                        noise_percent,
                        self.strategy_id,
                        self.noise_dimension_hash,
                        self.count,
                    )
                else:
                    self.need_notice = True
                    logger.info(
                        "count(%s) of noise reduce task of strategy(%s) dimension_hash(%s) is more than settings(%s), "
                        "ready to create notice action",
                        noise_percent,
                        self.strategy_id,
                        self.noise_dimension_hash,
                        self.count,
                    )

                self.create_noise_reduce_actions(generate_uuids, alert_ids)
        except LockError:
            # 获取锁错误表示窗口当前策略有告警在并发处理，可以忽略
            logger.info(
                "noise reduce task of strategy(%s) dimension_hash(%s) already exist",
                self.strategy_id,
                self.noise_dimension_hash,
            )

        logger.info(
            "end execute noise reduce task of strategy(%s) dimension_hash(%s) dimensions(%s)",
            self.strategy_id,
            self.noise_dimension_hash,
            dimensions,
        )

    def clear_cache(self):
        """
        清理掉过期的内容
        :return:
        """
        self.redis_client.delete(self.abnormal_record_key)
        self.redis_client.zremrangebyscore(self.total_record_key, 0, self.begin_time)
        self.redis_client.delete(self.alert_record_key)

    def create_noise_reduce_actions(self, generate_uuids, alert_ids):
        """
        :param alert_ids:
        :param generate_uuids:对应的主任务标识
        :return:
        """
        # 满足的情况下， 创建对应的任务
        logger.info(
            "begin to create noise reduce action for strategy(%s) dimension_hash(%s)",
            self.strategy_id,
            self.noise_dimension_hash,
        )
        all_sub_actions = []
        parent_action_ids = list(
            ActionInstance.objects.filter(is_parent_action=True, generate_uuid__in=generate_uuids).values_list(
                "id", flat=True
            )
        )
        alert_keys = [AlertKey(alert_id=alert_id, strategy_id=self.strategy_id) for alert_id in alert_ids]
        alerts = {alert.id: AlertDocument(**alert.data) for alert in Alert.mget(alert_keys)}
        action_alert_relation = defaultdict(list)
        if self.need_notice:
            for parent_action in ActionInstance.objects.filter(is_parent_action=True, generate_uuid__in=generate_uuids):
                all_sub_actions.extend(parent_action.create_sub_actions(need_create=False))
                action_alert_relation[parent_action.generate_uuid].append(alerts.get(parent_action.alerts[0], None))

            if all_sub_actions:
                ActionInstance.objects.bulk_create(all_sub_actions, batch_size=100)
        else:
            # 被抑制的时候，更新抑制的状态
            reduced_alerts = [
                AlertDocument(id=alert_id, handle_stage=[HandleStage.NOISE_REDUCE]) for alert_id in alerts
            ]
            AlertDocument.bulk_create(reduced_alerts, action=BulkActionType.UPDATE)

        PushActionProcessor.push_actions_to_converge_queue(
            list(
                ActionInstance.objects.filter(generate_uuid__in=generate_uuids).filter(
                    Q(parent_action_id__in=parent_action_ids) | Q(id__in=parent_action_ids)
                )
            ),
            action_alert_relation,
        )
