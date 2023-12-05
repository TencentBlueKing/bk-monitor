import copy
import logging
import math
import time
from typing import List

from celery.task import task
from django.conf import settings
from django.utils.translation import ugettext as _

from alarm_backends.constants import CONST_SECOND
from alarm_backends.core.alert import Alert, AlertCache
from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.key import ACTION_POLL_KEY_LOCK
from alarm_backends.core.cluster import get_cluster_bk_biz_ids
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.converge.shield.shielder import AlertShieldConfigShielder
from alarm_backends.service.fta_action.double_check import DoubleCheckHandler
from alarm_backends.service.fta_action.tasks.alert_assign import AlertAssigneeManager
from alarm_backends.service.fta_action.tasks.noise_reduce import (
    NoiseReduceRecordProcessor,
)
from alarm_backends.service.fta_action.utils import PushActionProcessor, need_poll
from bkmonitor.action.serializers import ActionPluginSlz
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models import ActionInstance, ActionPlugin
from bkmonitor.utils import extended_json
from bkmonitor.utils.common_utils import count_md5
from constants.action import (
    DEFAULT_NOTICE_ACTION,
    ActionNoticeType,
    ActionPluginType,
    ActionSignal,
    IntervalNotifyMode,
)
from constants.alert import EventSeverity, EventStatus, HandleStage
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("fta_action.run")


@task(ignore_result=True, queue="celery_action")
def create_actions(
    strategy_id,
    signal,
    alert_ids=None,
    alerts: List[AlertDocument] = None,
    severity=None,
    dimensions=None,
    dimension_hash="",
    relation_id=None,
    execute_times=0,
    is_unshielded=False,
    notice_type=ActionNoticeType.NORMAL,
):
    """
    根据策略产生任务
    :param notice_type: 通知类型
    :param is_unshielded: 是否为解屏蔽
    :param execute_times: 执行次数
    :param strategy_id:策略ID
    :param signal:产生信号
    :param alert_ids:告警ID列表
    :param alerts: 告警列表
    :param severity: 告警级别，如果为None, 则默认用告警级别最严重的alert填充
    :param dimensions: 策略匹配维度, 默认为列表，包含key， value, display_key, display_value
    :param dimension_hash: 维度hash
    :param relation_id: 关联的ID
    :return:
    """
    exc = None
    actions = []
    if is_unshielded:
        notice_type = ActionNoticeType.UNSHILEDED

    public_labels = {"strategy_id": metrics.TOTAL_TAG, "signal": signal, "run_type": "once", "notice_type": notice_type}

    alert_id = alerts[0].id if alerts else alert_ids[0]
    logger.info("do create actions(%s) for alert(%s)", notice_type, alert_id)

    try:
        with metrics.ACTION_CREATE_PROCESS_TIME.labels(**public_labels).time():
            actions = CreateActionProcessor(
                strategy_id,
                signal,
                alert_ids,
                alerts,
                severity,
                dimensions,
                dimension_hash,
                relation_id,
                execute_times,
                is_unshielded,
                notice_type,
            ).do_create_actions()
        logger.info("do create actions(%s) end for alert(%s), action count(%s)", notice_type, alert_id, len(actions))
    except BaseException as e:
        exc = e
        logger.exception("create actions for alert(%s) failed: %s", alert_id, e)

    metrics.ACTION_CREATE_PROCESS_COUNT.labels(
        status=metrics.StatusEnum.from_exc(exc), exception=exc, **public_labels
    ).inc()
    metrics.ACTION_CREATE_PUSH_COUNT.labels(**public_labels).inc(len(actions))
    metrics.report_all()

    return actions


@task(ignore_result=True, queue="celery_interval_action")
def create_interval_actions(
    strategy_id,
    signal,
    alert_ids=None,
    alerts: List[AlertDocument] = None,
    severity=None,
    dimensions=None,
    dimension_hash="",
    relation_id=None,
    execute_times=0,
):
    exc = None
    actions = []

    public_labels = {
        "strategy_id": strategy_id,
        "signal": signal,
        "run_type": "interval",
        "notice_type": ActionNoticeType.NORMAL,
    }

    alert_id = alerts[0].id if alerts else alert_ids[0]
    logger.info("do create polled actions for alert(%s), relation_id(%s)", alert_id, relation_id)

    try:
        with metrics.ACTION_CREATE_PROCESS_TIME.labels(**public_labels).time():
            actions = CreateActionProcessor(
                strategy_id, signal, alert_ids, alerts, severity, dimensions, dimension_hash, relation_id, execute_times
            ).do_create_actions()
        logger.info("create polled actions(%s) for alert(%s)", len(actions), alert_id)
    except BaseException as e:
        exc = e
        logger.info("create polled actions for alert(%s) failed: %s", alert_id, e)

    metrics.ACTION_CREATE_PROCESS_COUNT.labels(
        status=metrics.StatusEnum.from_exc(exc), exception=exc, **public_labels
    ).inc()
    metrics.ACTION_CREATE_PUSH_COUNT.labels(**public_labels).inc(len(actions))
    metrics.report_all()

    return actions


def check_create_poll_action():
    """
    周期创建循环通知任务
    :return:
    """
    try:
        polled_action_interval = int(getattr(settings, "POLLED_ACTION_INTERVAL", CONST_SECOND * 30))
    except BaseException as error:  # NOCC:broad-except(设计如此:)
        logger.info("get polled_action_interval from settings failed(), use default interval", str(error))
        polled_action_interval = CONST_SECOND * 30
    for interval in range(0, 60, polled_action_interval):
        check_create_poll_action_10_secs.apply_async(countdown=interval, expires=120)


@task(ignore_result=True, queue="celery_action_cron")
def check_create_poll_action_10_secs():
    """
    每10s进行一次数据查询
    :return:
    """
    try:
        with service_lock(ACTION_POLL_KEY_LOCK):
            CreateIntervalActionProcessor().process()
    except LockError:
        # 加锁失败
        logger.info("[get service lock fail] check_create_poll_action. will process later")
        return
    except BaseException as e:  # NOCC:broad-except(设计如此:)
        logger.exception("[process error] check_create_poll_action, reason：{msg}".format(msg=str(e)))
        return


class CreateIntervalActionProcessor:
    def __init__(self):
        self.polled_actions = []
        self.finished_actions = []
        self.polled_alerts = []
        self.need_polled_actions = {}

    def process(self):
        # 检查需要创建周期任务的内容
        self.check_polled_actions()
        # 创建周期任务
        self.create_interval_action()

        logger.info(
            "check_create_poll_action need_polled_actions({}), polled_actions({}) finished_actions({})".format(
                len(self.need_polled_actions.keys()), len(self.polled_actions), len(self.finished_actions)
            )
        )

    def check_polled_actions(self):
        """
        检查所有需要轮询的任务
        :return:
        """
        bk_biz_ids = set(get_cluster_bk_biz_ids())
        action_instances = ActionInstance.objects.filter(need_poll=True, is_polled=False).only(
            "id",
            "need_poll",
            "is_polled",
            "inputs",
            "action_config_id",
            "execute_times",
            "strategy_id",
            "signal",
            "alerts",
            "alert_level",
            "dimensions",
            "dimension_hash",
            "strategy_relation_id",
            "end_time",
            "is_parent_action",
        )
        checked_alerts = []
        for action_instance in action_instances:
            # 仅处理集群内的业务
            if action_instance.bk_biz_id not in bk_biz_ids:
                continue
            action_config = ActionConfigCacheManager.get_action_config_by_id(config_id=action_instance.action_config_id)
            action_instance.action_config = action_config
            self.check_finished_actions(checked_alerts, action_instance)
            self.check_interval_matched_actions(action_instance, action_config)

    def create_interval_action(self):
        """
        创建周期任务
        :return:
        """
        polled_alert_docs = {alert.id: alert for alert in AlertDocument.mget(ids=self.polled_alerts)}
        for action_id, action_instance in self.need_polled_actions.items():
            # 当上一次任务结束时间已经满足了轮转，则需要创建任务
            alert = polled_alert_docs.get(action_instance.alerts[0], None)
            alert_latest_time = alert.latest_time if alert else 0

            if (
                action_instance.inputs.get("alert_latest_time", 0) < alert_latest_time
                and alert.status_detail == EventStatus.ABNORMAL
            ):
                # 当前周期通知的最近异常点一定要大于历史异常点
                # 当前告警的具体状态一定， 存在恢复中状态的周期通知不需要发送
                create_interval_actions.delay(
                    action_instance.strategy_id,
                    action_instance.signal,
                    action_instance.alerts,
                    severity=action_instance.alert_level,
                    dimensions=action_instance.dimensions,
                    dimension_hash=action_instance.dimension_hash,
                    relation_id=action_instance.strategy_relation_id,
                    execute_times=action_instance.execute_times,
                )
                self.polled_actions.append(action_id)

        # 更新DB的数据，已经轮询的，设置为已经轮询，不需要轮询的，直接取消
        ActionInstance.objects.filter(id__in=self.polled_actions).update(is_polled=True)
        ActionInstance.objects.filter(id__in=self.finished_actions).update(need_poll=False)

    def check_finished_actions(self, checked_alerts: list, action_instance):
        check_key = "{}_{}".format(action_instance.alerts[0], action_instance.action_config_id)
        if check_key in checked_alerts:
            # 增加检测机制，每个alert对应的action类型仅保留一个同类型的周期任务
            self.finished_actions.append(action_instance.id)
            return
        checked_alerts.append(check_key)
        if not need_poll(action_instance):
            # 不需要轮询的时候，直接设置为结束
            self.finished_actions.append(action_instance.id)

    def check_interval_matched_actions(self, action_instance, action_config):
        """
        判断周期间隔是否已经达到
        """
        if action_instance.id in self.finished_actions:
            return
        try:
            execute_config = action_config["execute_config"]["template_detail"]
        except KeyError as error:
            logger.error("No execute_config params in action_config %s error %s", action_config, str(error))
            return
        except TypeError as error:
            logger.error("type error execute_config params in action_config %s error %s", action_config, str(error))
            return
        notify_interval = self.calc_action_interval(execute_config, action_instance)
        if notify_interval <= 0 or int(action_instance.end_time.timestamp()) + notify_interval > int(time.time()):
            # 不满足创建周期任务条件的时候，直接返回
            return

        self.need_polled_actions.update({action_instance.id: action_instance})
        self.polled_alerts.extend(action_instance.alerts)

    @staticmethod
    def calc_action_interval(execute_config, action_instance: ActionInstance):
        """
        计算周期任务间隔
        :param execute_config: 执行参数
        :param action_instance: 当前的主任务动作
        :return:
        """
        if execute_config.get("need_poll", True) is False:
            return 0

        try:
            notify_interval = int(execute_config.get("notify_interval", 0))
        except TypeError:
            notify_interval = 0

        interval_notify_mode = execute_config.get("interval_notify_mode", IntervalNotifyMode.STANDARD)
        if interval_notify_mode == IntervalNotifyMode.INCREASING:
            # 按照指数级别进行处理
            notify_interval = int(notify_interval * math.pow(2, action_instance.execute_times - 1))
        return notify_interval


class CreateActionProcessor:
    def __init__(
        self,
        strategy_id,
        signal,
        alert_ids=None,
        alerts: List[AlertDocument] = None,
        severity=None,
        dimensions=None,
        dimension_hash="",
        relation_id=None,
        execute_times=0,
        is_unshielded=False,
        notice_type=ActionNoticeType.NORMAL,
    ):
        self.strategy_id = strategy_id
        self.signal = signal
        alert_ids = alert_ids or [alert.id for alert in alerts]
        alert_keys = [AlertKey(alert_id=alert_id, strategy_id=self.strategy_id) for alert_id in alert_ids]
        self.alert_objs = {alert.id: alert for alert in Alert.mget(alert_keys)}
        self.alerts = [
            AlertDocument(**alert.data)
            for alert in self.alert_objs.values()
            if alert.is_valid_handle(execute_times, relation_id)
        ]
        self.is_alert_shielded = False
        self.shield_detail = ""
        self.alert_ids = alert_ids
        self.severity = severity or self.alerts[0].severity
        self.dimensions = dimensions
        self.dimension_hash = dimension_hash
        self.relation_id = relation_id
        self.execute_times = execute_times
        self.is_unshielded = is_unshielded
        self.strategy = Strategy(strategy_id).config or self.alerts[0].strategy or {}
        self.generate_uuid = self.get_generate_uuid()
        self.noise_reduce_result = False
        self.notice = {}
        self.notice_type = notice_type

    def get_generate_uuid(self):
        md5_elements = [self.strategy_id, self.signal, self.alert_ids, int(time.time())]
        if self.relation_id:
            # 当带有特定的套餐关系， 也需要特别记录
            md5_elements.append(self.relation_id)

        return count_md5(md5_elements)

    def get_action_relations(self):
        if self.strategy:
            actions = copy.deepcopy(self.strategy.get("actions", []))
            self.notice = copy.deepcopy(self.strategy.get("notice", {}))
        else:
            # 没有策略的，按默认规则发送通知
            self.notice = copy.deepcopy(DEFAULT_NOTICE_ACTION)
            actions = [self.notice]

        if self.notice.get("config_id"):
            # 增加通知操作，并进行降噪处理
            actions.append(self.notice)
            if self.notice_type != ActionNoticeType.UPGRADE:
                # 升级的通知不做降噪处理
                self.noise_reduce_result = NoiseReduceRecordProcessor(
                    self.notice, self.signal, self.strategy_id, self.alerts[0], self.generate_uuid
                ).process()

        if self.relation_id:
            # 指定了关联关系，默认用指定的关联关系
            actions = [action for action in actions if action["id"] == self.relation_id]

        # 根据信号过滤处理动作
        actions = [action for action in actions if self.signal in action["signal"]]
        return actions

    def get_alert_shield_result(self):
        """
        获取告警的屏蔽状态
        :return:
        """
        for alert in self.alerts:
            # 关联多告警的内容，只要有其中一个不满足条件，直接就屏蔽
            try:
                shielder = AlertShieldConfigShielder(alert)
                if shielder.is_matched():
                    self.shield_detail = extended_json.loads(shielder.detail).get("message", "")
                    return True, shielder.list_shield_ids()
            except Exception as error:
                logger.exception("check alert(%s) shield status failed ,error is %s", alert.id, str(error))
        return False, []

    def is_alert_status_valid(self, alert):
        """
        判断当前告警是否需要执行
        :param alert:
        :return:
        """
        if self.signal == ActionSignal.ACK:
            if not alert.is_ack_noticed:
                # 如果当前信息为确认通知并且没有发送过，则一定执行
                return True
            return False

        compared_status = EventStatus.ABNORMAL if self.signal == ActionSignal.NO_DATA else self.signal.upper()
        if alert.is_ack or (alert.status != compared_status):
            # 告警已经确认
            desc = _("用户已确认当前告警，系统自动忽略所有的通知和处理套餐的执行")
            current_timestamp = int(time.time())
            if not alert.is_ack:
                desc = _("当前告警状态发生变化，系统自动忽略{}的所有通知和处理套餐的执行").format(ActionSignal.ACTION_SIGNAL_DICT.get(self.signal))
            action_log = dict(
                op_type=AlertLog.OpType.ACTION,
                alert_id=[alert.id],
                description=desc,
                time=current_timestamp,
                create_time=current_timestamp,
                event_id=current_timestamp,
            )
            AlertLog.bulk_create([AlertLog(**action_log)])
            return False
        return True

    def alert_assign_handle(self, alert, action_configs, origin_actions, itsm_actions):
        """
        分派操作
        :param alert:
        :param action_configs:
        :param origin_actions:
        :param itsm_actions:
        :return:
        """
        # 注： 指定了处理动作的情况下， 不需要进行分派，主要是webhook回调
        assign_mode = self.notice["options"].get("assign_mode")
        assign_labels = {
            "bk_biz_id": alert.event.bk_biz_id,
            "assign_type": "action",
            "notice_type": self.notice_type,
            "alert_source": getattr(alert.event, "plugin_id", ""),
        }
        with metrics.ALERT_ASSIGN_PROCESS_TIME.labels(**assign_labels).time():
            exc = None
            try:
                assignee_manager = AlertAssigneeManager(
                    alert,
                    self.notice["user_groups"],
                    assign_mode,
                    self.notice["options"].get("upgrade_config", {}),
                    notice_type=self.notice_type,
                )
                assign_labels.update({"rule_group_id": assignee_manager.matched_group})
            except BaseException as error:
                assign_labels.update({"rule_group_id": None})
                exc = error
                logger.exception("[alert assign] alert(%s) assign failed, error info %s", alert.id, str(error))
            assign_labels["status"] = metrics.StatusEnum.from_exc(exc)

        metrics.ALERT_ASSIGN_PROCESS_COUNT.labels(**assign_labels).inc()
        if self.execute_times == 0 and self.notice_type != ActionNoticeType.UPGRADE:
            # 创建流程单据，仅第一次分派的时候进行操作
            for itsm_action_id in assignee_manager.itsm_actions.keys():
                if str(itsm_action_id) not in action_configs:
                    action_configs[str(itsm_action_id)] = ActionConfigCacheManager.get_action_config_by_id(
                        itsm_action_id
                    )
                if str(itsm_action_id) not in origin_actions:
                    # 不在告警处理中，直接添加
                    itsm_actions.append({"config_id": itsm_action_id, "id": 0, "options": {}})
        return assignee_manager

    @classmethod
    def is_action_config_valid(cls, alert, action_config):
        """
        当前处理套餐是否有效
        :param alert:
        :param action_config:
        :return:
        """
        if action_config and action_config["is_enabled"]:
            return True
        current_timestamp = int(time.time())
        action_log = dict(
            op_type=AlertLog.OpType.ACTION,
            alert_id=[alert.id],
            description=_("处理套餐【{}】已经被删除或禁用，系统自动忽略该处理").format(
                action_config.get("name") or action_config.get("config_id")
            ),
            time=current_timestamp,
            create_time=current_timestamp,
            event_id=current_timestamp,
        )
        AlertLog.bulk_create([AlertLog(**action_log)])
        return False

    def do_create_actions(self):
        if not self.alerts:
            logger.info(
                "create actions failed: empty alerts(%s), strategy_id(%s), signal(%s)",
                self.alert_ids,
                self.strategy_id,
                self.signal,
            )
            return []

        logger.info(
            "Ready to create actions strategy_id(%s), signal(%s), alert_ids(%s), severity(%s),"
            " execute_times(%s), relation_id(%s)",
            self.strategy_id,
            self.signal,
            self.alert_ids,
            self.severity,
            self.execute_times,
            self.relation_id,
        )
        actions = self.get_action_relations()
        new_actions = []
        self.is_alert_shielded, shield_ids = self.get_alert_shield_result()
        # 创建推送队列的人员信息
        self.create_message_queue_action(new_actions)

        if not actions:
            logger.info(
                "create actions error: empty config, strategy_id %s, alerts %s, signal %s",
                self.strategy_id,
                self.alert_ids,
                self.signal,
            )
            return new_actions

        action_configs = {
            str(action["config_id"]): ActionConfigCacheManager.get_action_config_by_id(action["config_id"])
            for action in actions
        }
        origin_actions = list(action_configs.keys())

        # 插件不会有很多项，直接拉全量的数据即可
        action_plugins = {
            str(plugin["id"]): plugin for plugin in ActionPluginSlz(instance=ActionPlugin.objects.all(), many=True).data
        }

        action_instances = []
        alerts_assignee = {alert.id: alert.to_dict().get("assignee") or [] for alert in self.alerts}
        alerts_appointee = {alert.id: alert.to_dict().get("appointee") or [] for alert in self.alerts}
        alerts_supervisor = {alert.id: alert.to_dict().get("supervisor") or [] for alert in self.alerts}
        # 根据用户组信息获取人员
        alert_logs = []
        qos_alerts = []
        current_qos_count = 0
        for alert in self.alerts:
            if not self.is_alert_status_valid(alert):
                # 所有的通知，需要判断信号是否为有效状态
                continue
            itsm_actions = []
            assignee_manager = self.alert_assign_handle(alert, action_configs, origin_actions, itsm_actions)
            # 自动分派负责人只能追加
            # 手动分派的情况下直接覆盖
            supervisors = []
            assignees = []
            appointees = []
            if not assignee_manager.is_matched and not self.strategy_id:
                # 第三方告警如果没有适配到的规则，直接忽略
                continue
            if self.notice_type == ActionNoticeType.UPGRADE:
                supervisors = assignee_manager.get_supervisors()
                if not supervisors:
                    logger.info("ignore to send supervise notice for alert(%s) due to empty supervisor", alert.id)
                    continue
                is_qos, current_qos_count = self.alert_objs[alert.id].qos_calc(self.signal)
                if is_qos:
                    qos_alerts.append(alert.id)
                    logger.info("ignore to send supervise notice for alert(%s) due to notice qos", alert.id)
                    continue
            else:
                assignees = assignee_manager.get_assignees()
                appointees = assignee_manager.get_appointees()

            alerts_assignee[alert.id].extend(assignees)
            alerts_appointee[alert.id].extend(appointees)
            alerts_supervisor[alert.id].extend(supervisors)

            for action in actions + itsm_actions:
                action_config = action_configs.get(str(action["config_id"]))
                if not self.is_action_config_valid(alert, action_config):
                    continue
                action_plugin = action_plugins.get(str(action_config["plugin_id"]))
                action_instances.append(
                    self.do_create_action(
                        action_config,
                        action_plugin,
                        alert,
                        action_relation=action,
                        assignee_manager=assignee_manager,
                        shield_ids=shield_ids,
                    )
                )
            if assignee_manager.match_manager:
                alert_log = assignee_manager.match_manager.get_alert_log()
                if alert_log:
                    alert_logs.append(AlertLog(**alert_log))
        if action_instances:
            ActionInstance.objects.bulk_create(action_instances)
            new_actions.extend(
                PushActionProcessor.push_actions_to_queue(
                    self.generate_uuid,
                    alerts=self.alerts,
                    is_shielded=self.is_alert_shielded,
                    need_noise_reduce=self.noise_reduce_result,
                    notice_config=self.notice,
                )
            )

        logger.info(
            "create actions finished, strategy_id %s, alerts %s, signal %s, created actions(%s) %s",
            self.strategy_id,
            self.alert_ids,
            self.signal,
            len(new_actions),
            new_actions,
        )
        # 更新是否已经处理的状态至告警
        # 当前告警如果是降噪处理，也认为是已经处理，不需要创建任务出来
        is_handled = True if self.noise_reduce_result else bool(new_actions)
        self.update_alert_documents(alerts_assignee, shield_ids, is_handled, alerts_appointee, alerts_supervisor)
        if qos_alerts:
            # 有qos处理记录， 这里只有可能是通知处理的
            alert_logs.append(Alert.create_qos_log(qos_alerts, current_qos_count, len(qos_alerts)))
        if alert_logs:
            AlertLog.bulk_create(alert_logs)
        return new_actions

    def update_alert_documents(self, alerts_assignee, shield_ids, is_handled, alerts_appointee, alerts_supervisor):
        """
        更新告警内容
        :param alert_appointee: 告警负责人
        :param alerts_assignee: 告警通知人
        :param shield_ids:
        :param is_handled:
        :return:
        """
        handled_alerts = [
            AlertDocument(
                id=alert.id,
                is_handled=is_handled,
                is_ack_noticed=True if self.signal == ActionSignal.ACK else alert.is_ack_noticed,
                handle_stage=[HandleStage.HANDLE] if not self.noise_reduce_result else [HandleStage.NOISE_REDUCE],
                is_shielded=self.is_alert_shielded,
                shield_id=shield_ids,
                severity=alert.severity,
                assignee=list(set(alerts_assignee[alert.id])),
                appointee=list(set(alerts_appointee[alert.id])),
                supervisor=list(set(alerts_supervisor[alert.id])),
                extra_info=alert.extra_info,
                assign_tags=alert.assign_tags,
            )
            for alert in self.alerts
        ]
        cached_alerts = [Alert(data=alert.to_dict()) for alert in self.alerts]
        AlertCache.save_alert_to_cache(cached_alerts)
        AlertCache.save_alert_snapshot(cached_alerts)
        AlertDocument.bulk_create(handled_alerts, action=BulkActionType.UPDATE)

    def create_message_queue_action(self, new_actions: list):
        """
        创建推送k队列的处理记录
        :param new_actions: 新的任务列表
        :return:
        """
        need_message_queue = settings.ENABLE_MESSAGE_QUEUE and settings.MESSAGE_QUEUE_DSN
        if not need_message_queue:
            return

        if self.is_alert_shielded and not settings.ENABLE_PUSH_SHIELDED_ALERT:
            # 当前告警处于屏蔽状态并且不允许推送屏蔽告警，直接忽略
            logger.info(
                "Ignore to create message queue action for shielded alert(%s)"
                " because config[ENABLE_PUSH_SHIELDED_ALERT] is %s",
                self.alert_ids,
                settings.ENABLE_PUSH_SHIELDED_ALERT,
            )
            return

        plugin_type = ActionPluginType.MESSAGE_QUEUE
        action_instance = ActionInstance.objects.create(
            alerts=self.alert_ids,
            signal=self.signal,
            strategy_id=0,
            alert_level=self.severity,
            bk_biz_id=self.alerts[0].event.bk_biz_id,
            dimensions=self.dimensions or [],
            action_plugin={"plugin_type": plugin_type},
        )
        PushActionProcessor.push_action_to_execute_queue(action_instance, self.alerts)
        new_actions.append(action_instance.id)

    def do_create_action(
        self,
        action_config: dict,
        action_plugin: dict,
        alert: AlertDocument,
        action_relation=None,
        assignee_manager=None,
        shield_ids=None,
    ):
        """
        根据套餐配置创建处理记录
        :param assignee_manager: 告警负责人对象
        :param alert: 处理的告警对象
        :param shield_ids: 屏蔽ID
        :param action_relation：关联处理套餐关系
        :param action_config: 套餐配置快照
        :param action_plugin: 套餐类型快照
        :param assignee: 处理人员
        :return:
        """
        action_relation = action_relation or {}
        inputs = {
            "alert_latest_time": alert.latest_time,
            "is_alert_shielded": self.is_alert_shielded,
            "shield_ids": shield_ids,
            "shield_detail": self.shield_detail,
            "is_unshielded": self.is_unshielded,
            "notice_type": self.notice_type,
            "exclude_notice_ways": action_relation["options"].get("exclude_notice_ways", {}).get(self.signal, []),
            "time_range": "--".join(
                [
                    action_relation["options"].get("start_time", "00:00:00"),
                    action_relation["options"].get("end_time", "23:59:59"),
                ]
            ),
        }
        is_parent_action = False
        alert_level = EventSeverity.REMIND
        try:
            alert_level = alert.severity or int(self.severity)
        except ValueError as error:
            logger.error("Get alert level failed: %s, alerts: %s", str(error), alert.alert_name)
        if action_plugin["plugin_type"] == ActionPluginType.NOTICE:
            is_parent_action = True
            if self.notice_type == ActionNoticeType.UPGRADE:
                notify_info = assignee_manager.get_upgrade_notify_info()
            else:
                notify_info = assignee_manager.get_notify_info()
            inputs["notify_info"] = notify_info
        try:
            # TODO: 如果有更多的处理场景，需要将二次确认的处理提到更前端
            DoubleCheckHandler(alert).handle(inputs)
        except Exception:  # pylint: disable=broad-except
            logger.exception("二次确认发生错误，跳过处理 Alert<%s>", alert)
            # 当二次确认发生任意异常时，不影响原来的处理逻辑
        relation_id = action_relation.get("id") or 0
        if self.signal in ActionSignal.ABNORMAL_SIGNAL and alert.extra_info:
            # 如果处理的时候，记录第一次一次通知时间和通知次数，用来作为记录当前告警是否已经产生通知
            handle_record = {
                "last_time": int(time.time()),
                "is_shielded": self.is_alert_shielded,
                "latest_anomaly_time": alert.latest_time,
                "execute_times": self.execute_times + 1,
            }
            if alert.cycle_handle_record:
                history_record = alert.cycle_handle_record.get(str(relation_id))
                if not history_record or (
                    history_record and history_record["execute_times"] < handle_record["execute_times"]
                ):
                    # 如果曾经没有对应的周期记录，则直接赋值
                    # 如果曾经有周期记录，并且当前记录的执行次数小于当前执行次数，则更新
                    alert.extra_info["cycle_handle_record"][str(relation_id)] = handle_record
            else:
                alert.extra_info["cycle_handle_record"] = {str(relation_id): handle_record}

        return ActionInstance(
            alerts=[alert.id],
            signal=self.signal,
            strategy_id=self.strategy_id or alert.strategy_id or 0,
            inputs=inputs,
            alert_level=alert_level,
            is_parent_action=is_parent_action,
            action_config=action_config,
            action_config_id=action_config["id"],
            action_plugin=action_plugin,
            bk_biz_id=alert.event.bk_biz_id or action_config["bk_biz_id"],
            assignee=assignee_manager.get_appointees(action_id=action_config["id"])
            or assignee_manager.get_origin_notice_receivers(),
            generate_uuid=self.generate_uuid,
            dimensions=self.dimensions or [],
            dimension_hash=self.dimension_hash,
            strategy=self.strategy,
            strategy_relation_id=relation_id,
            execute_times=self.execute_times,
        )
