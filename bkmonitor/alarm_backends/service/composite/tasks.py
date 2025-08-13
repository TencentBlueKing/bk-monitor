import logging

from alarm_backends.core.alert import Alert
from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.service.composite.processor import CompositeProcessor
from alarm_backends.service.scheduler.app import app
from constants.action import ActionSignal
from core.errors.alert import AlertNotFoundError
from core.prometheus import metrics

logger = logging.getLogger("composite")


@app.task(ignore_result=True, queue="celery_composite")
def check_action_and_composite(
    alert_key: AlertKey, alert_status: str, composite_strategy_ids: list = None, retry_times: int = 0
):
    """
    :param alert_key: 告警标识
    :param alert_status: 告警状态
    :param composite_strategy_ids: 待检测关联策略ID列表
    :param retry_times: 重试次数，最大为2
    :return:
    """
    if retry_times > 2:
        logger.info(
            "[composite] alert(%s) strategy(%s) retry times exceed 2, skip it",
            alert_key.alert_id,
            alert_key.strategy_id,
        )
        return

    logger.info(
        "[composite] alert(%s) strategy(%s) begin: alert_key(%s)", alert_key.alert_id, alert_key.strategy_id, alert_key
    )
    try:
        alert = Alert.get(alert_key)
    except AlertNotFoundError:
        # 如果从redis和ES都找不到告警，可以推迟一分钟之后再次检测
        logger.info("[composite] alert(%s) not found, retry in 5s", alert_key.alert_id)
        if retry_times <= 2:
            # 异常情况下最多重试2次
            check_action_and_composite.apply_async(
                kwargs={
                    "alert_key": alert_key,
                    "alert_status": alert_status,
                    "composite_strategy_ids": composite_strategy_ids,
                    "retry_times": retry_times + 1,
                },
                countdown=5,
            )
        return

    if not alert:
        logger.info("[composite] alert(%s) not found, skip it", alert_key.alert_id)
        return

    if not alert.bk_biz_id:
        logger.info("[composite] alert(%s) bk_biz_id is empty, skip it", alert.id)
        return

    exc = None

    try:
        with metrics.COMPOSITE_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).time():
            processor = CompositeProcessor(
                alert=alert,
                alert_status=alert_status,
                composite_strategy_ids=composite_strategy_ids,
                retry_times=retry_times,
            )
            processor.process()
    except Exception as e:
        exc = e
        logger.exception("[composite ERROR] alert(%s) strategy(%s) detail: %s", alert.id, alert.strategy_id, e)

    metrics.COMPOSITE_PROCESS_COUNT.labels(
        strategy_id=metrics.TOTAL_TAG, status=metrics.StatusEnum.from_exc(exc), exception=exc
    ).inc()
    metrics.report_all()


@app.task(ignore_result=True, queue="celery_composite")
def check_incident_action_and_composite(incident_id: int, incident_stage: str, incident_actions: list = None, **kwargs):
    """
    :param incident_id: 故障id
    :param incident_stage: 故障阶段
    :param incident_actions: 故障关联动作
    :return:
    """
    logger.info("[incident composite] incident(%s) stage(%s) begin", incident_id, incident_stage)

    exc = None

    try:
        # 每个故障动作关联着和一批故障先关的告警, 每个动作单独触发
        for action in incident_actions:
            related_alerts = action.pop("related_alerts")
            if not related_alerts or str(action.get("signal")).lower() != ActionSignal.INCIDENT.lower():
                continue
            top_alert = Alert(data=related_alerts[0])
            operate_actions = {
                "strategy_id": action["strategy_id"],
                "signal": action["signal"],
                "alert_ids": [top_alert.id],
                "dimensions": top_alert.dimensions,
                "severity": action["severity"],
            }
            with metrics.COMPOSITE_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).time():
                processor = CompositeProcessor(alert=top_alert, alert_status=top_alert.status)
                processor.add_action(**operate_actions)
                processor.push_actions()
    except Exception as e:
        exc = e
        logger.exception("[incident composite ERROR] incident(%s) stage(%s) detail: %s", incident_id, incident_stage, e)

    metrics.COMPOSITE_PROCESS_COUNT.labels(
        strategy_id=metrics.TOTAL_TAG, status=metrics.StatusEnum.from_exc(exc), exception=exc
    ).inc()
    metrics.report_all()
