#!/usr/bin/env python
"""
蓝鲸监控告警动作重试脚本
用于重试执行失败的 FTA Action

使用方法：
1. 通过 Django shell:
   python manage.py shell
   >>> from scripts.retry_action_script import retry_action, retry_multiple_actions
   >>> retry_action(12345)
   >>> retry_multiple_actions([12345, 67890])

2. 直接在shell中执行:
   python manage.py shell -c "from scripts.retry_action_script import retry_action; retry_action(12345)"
"""

import logging
import importlib


from bkmonitor.models import ActionInstance
from bkmonitor.documents import AlertDocument
from alarm_backends.core.i18n import i18n
from constants.action import ActionStatus


def setup_logger():
    """设置日志配置"""
    logger = logging.getLogger("fta_action_retry")

    # 避免重复添加handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    return logger


logger = setup_logger()


def get_action_instance(action_id: int):
    """获取Action实例"""
    try:
        return ActionInstance.objects.get(id=action_id)
    except ActionInstance.DoesNotExist:
        logger.error(f"Action with ID {action_id} not found")
        return None


def get_related_alerts(action) -> list:
    """获取与Action相关的Alert"""
    if not action.alerts:
        logger.warning(f"Action {action.id} has no related alerts")
        return []

    alert_ids: list = action.alerts
    # 从es中获取关联的alerts
    alerts = AlertDocument.mget(ids=alert_ids)

    # 过滤None值
    valid_alerts = [alert for alert in alerts if alert is not None]

    logger.info(f"Found {len(valid_alerts)} valid alerts out of {len(alerts)} for action {action.id}")
    return valid_alerts


def get_processor_class(action):
    """根据action配置获取对应的处理器类"""
    plugin_type = action.action_plugin.get("plugin_type")

    if not plugin_type:
        logger.error(f"Cannot determine plugin type for action {action.id}")
        return None
    # 使用绝对路径导入
    module_name = f"alarm_backends.service.fta_action.{plugin_type}.processor"

    try:
        module = importlib.import_module(module_name)
        logger.info(f"Successfully imported module {module_name}")
        return module.ActionProcessor
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing processor module for plugin type {plugin_type}: {str(e)}")
        return None


def retry_action(action_id: int) -> bool:
    """
    使用适配的processor重试指定的Action

    Args:
        action_id (int): 要重试的动作ID

    Returns:
        bool: 重试是否成功
    """
    logger.info(f"Starting retry for action {action_id}")

    # 获取action实例
    action = get_action_instance(action_id)
    if not action:
        return False

    # 检查Action状态
    if action.status == ActionStatus.SUCCESS:
        logger.warning(f"Action {action_id} is already successful, skipping retry")
        return True
    elif action.status == ActionStatus.RUNNING:
        logger.warning(f"Action {action_id} is currently running, skipping retry")
        return False

    logger.info(f"Processing action {action_id} with plugin type {action.action_plugin.get('plugin_type')}")

    # 设置业务 ID 的 i18n 上下文
    i18n.set_biz(action.bk_biz_id)

    # 获取关联的告警
    alerts = get_related_alerts(action)

    # 获取处理器类
    processor_class = get_processor_class(action)
    if not processor_class:
        return False

    try:
        # 实例化处理器
        processor = processor_class(action_id=action_id, alerts=alerts)

        # 判断要执行的方法 - 检查是否有指定的重试函数
        func_name = "execute"  # 默认执行方法
        kwargs = {}

        if hasattr(processor, "action") and hasattr(processor.action, "outputs"):
            retry_func = processor.action.outputs.get("retry_func")
            if retry_func and hasattr(processor, retry_func):
                func_name = retry_func
                logger.info(f"Using retry function: {retry_func}")

                # 获取重试参数
                retry_kwargs = processor.action.outputs.get("retry_kwargs", {})
                if retry_kwargs:
                    kwargs.update(retry_kwargs)

        # 获取执行函数
        func = getattr(processor, func_name)

        # 执行
        logger.info(f"Executing {func_name} for action {action_id}")
        func(**kwargs)

        logger.info(f"Action {action_id} retry completed successfully")
        return True

    except ActionInstance.DoesNotExist:
        logger.error(f"Action {action_id} was deleted during retry")
        return False
    except AttributeError as e:
        logger.error(f"Processor method error for action {action_id}: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error retrying action {action_id}: {str(e)}")
        return False


def retry_multiple_actions(action_ids: list[int] | tuple[int]) -> dict[str, int]:
    """
    批量重试多个Action

    Args:
        action_ids (list): 要重试的动作ID列表

    Returns:
        dict: 包含成功和失败统计的字典
    """
    if not isinstance(action_ids, list | tuple):
        logger.error("action_ids must be a list or tuple")
        return {"success": 0, "failed": 0, "total": 0}

    success_count = 0
    failed_count = 0

    logger.info(f"Starting batch retry for {len(action_ids)} actions")

    # 遍历所有action_id去执行重试操作
    for action_id in action_ids:
        try:
            action_id = int(action_id)
            logger.info(f"Processing action ID: {action_id}")
            success = retry_action(action_id)
            if success:
                success_count += 1
                logger.info(f"✓ Action {action_id} processed successfully")
            else:
                failed_count += 1
                logger.error(f"✗ Action {action_id} processing failed")
        except ValueError:
            failed_count += 1
            logger.error(f"✗ Invalid action ID: {action_id}. Must be an integer.")

    total = len(action_ids)
    logger.info(
        f"Batch retry completed. {success_count}/{total} actions processed successfully, {failed_count} failed."
    )

    return {"success": success_count, "failed": failed_count, "total": total}


def get_action_info(action_id: int) -> dict:
    """
    获取Action的详细信息，便于调试

    Args:
        action_id (int): 动作ID

    Returns:
        dict: Action的详细信息
    """
    action = get_action_instance(action_id)
    if not action:
        return None

    info = {
        "id": action.id,
        "status": action.status,
        "plugin_type": action.action_plugin.get("plugin_type"),
        "bk_biz_id": action.bk_biz_id,
        "alerts_count": len(action.alerts) if action.alerts else 0,
        "create_time": action.create_time,
        "update_time": action.update_time,
    }

    if hasattr(action, "outputs") and action.outputs:
        info["outputs"] = action.outputs

    return info


# 如果直接运行脚本，显示使用说明
if __name__ == "__main__":
    print(
        """
        蓝鲸监控告警动作重试脚本
        
        推荐使用方式：
        1. 启动 Django shell:
           python manage.py shell
        
        2. 导入脚本:
           from scripts.retry_action_script import retry_action, retry_multiple_actions, get_action_info
        
        3. 使用示例:
           # 重试单个action
           retry_action(12345)
        
           # 批量重试多个action
           retry_multiple_actions([12345, 67890, 13579])
        
           # 查看动作信息
           get_action_info(12345)
        
        4. 一行命令执行:
           python manage.py shell -c "from scripts.retry_action_script import retry_action; retry_action(12345)"
        """
    )
