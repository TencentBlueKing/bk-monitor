"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.documents.incident import IncidentDocument
import logging
import time
from typing import Any

from django.conf import settings
from constants.incident import IncidentStatus
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.incident import IncidentOperationDocument
from bkmonitor.utils.request import get_request_username
from constants.incident import (
    INCIDENT_ATTRIBUTE_ALIAS_MAPPINGS,
    INCIDENT_ATTRIBUTE_VALUE_ENUMS,
    IncidentOperationClass,
    IncidentOperationType,
)

logger = logging.getLogger("incident.operation")


class IncidentOperationManager:
    # 需要触发通知的操作类型
    NOTICE_TRIGGER_OPERATIONS = [
        IncidentOperationType.CREATE,
        IncidentOperationType.OBSERVE,
        IncidentOperationType.RECOVER,
        IncidentOperationType.REOPEN,
        IncidentOperationType.UPDATE,
        IncidentOperationType.MERGE,
        IncidentOperationType.MERGE_TO,
    ]

    @classmethod
    def _get_incident_document_with_retry(
        cls, incident_id: int, max_retries: int = 3, retry_delay: float = 0.5, sleep_time=0.5
    ):
        """
        通过 incident_id 查询故障文档，带重试机制

        由于 ES 的 Near Real-Time 特性，文档写入后需要等待 refresh（默认1秒）才能被搜索到。
        此方法添加重试机制以应对查询延迟问题。

        :param incident_id: 故障ID
        :param max_retries: 最大重试次数，默认3次
        :param retry_delay: 每次重试间隔（秒），默认0.5秒
        :param sleep_time: 首次前置等待时间（秒），默认0.5秒
        :return: IncidentDocument 对象，如果未找到则返回 None
        """

        if sleep_time > 0:
            time.sleep(sleep_time)
        for retry in range(max_retries):
            try:
                search = IncidentDocument.search()
                search = search.filter("term", incident_id=incident_id)
                results = search.execute()

                if results:
                    logger.debug(f"Found incident document for incident_id {incident_id} on retry {retry + 1}")
                    return results[0]

                if retry < max_retries - 1:
                    logger.debug(
                        f"Incident document not found for incident_id {incident_id}, "
                        f"retry {retry + 1}/{max_retries} after {retry_delay}s"
                    )
                    time.sleep(retry_delay)
            except Exception as e:
                logger.error(
                    f"Error querying incident document for incident_id {incident_id} on retry {retry + 1}: {e}"
                )
                if retry < max_retries - 1:
                    time.sleep(retry_delay)

        logger.warning(f"Incident document not found for incident_id {incident_id} after {max_retries} retries")
        return None

    @classmethod
    def record_operation(
        cls, incident_id: int, operation_type: IncidentOperationType, operate_time=None, send_notice=False, **kwargs
    ) -> IncidentOperationDocument:
        if operation_type.operation_class == IncidentOperationClass.USER:
            operator = get_request_username()
        else:
            operator = None

        # 从 kwargs 中提取 incident_document（不存入 extra_info）
        incident_document = kwargs.pop("incident_document", None)

        IncidentOperationDocument.bulk_create(
            [
                IncidentOperationDocument(
                    incident_id=incident_id,
                    operator=operator,
                    operation_type=operation_type.value,
                    create_time=operate_time if operate_time else int(time.time()),
                    extra_info=kwargs,
                )
            ],
            action=BulkActionType.CREATE,
        )

        # 根据操作类型决定是否发送通知
        notice_enabled = getattr(settings, "ENABLE_BK_INCIDENT_NOTICE", False)
        if notice_enabled and send_notice:
            if operation_type in cls.NOTICE_TRIGGER_OPERATIONS:
                cls._send_incident_notice(incident_id, operation_type, incident_document=incident_document, **kwargs)

    @classmethod
    def _send_incident_notice(
        cls,
        incident_id: int,
        operation_type: IncidentOperationType,
        incident_document: IncidentDocument = None,
        **kwargs,
    ) -> None:
        """发送故障通知（支持多种通知方式）

        :param incident_id: 故障ID
        :param operation_type: 操作类型
        :param incident_document: 故障文档对象（可选，如果传入则直接使用，避免 ES 查询延迟）
        :param kwargs: 额外参数
        """
        try:
            # 获取配置的通知接收人（字典格式：{bk_biz_id: [ids]}）
            builtin_config = getattr(settings, "BK_INCIDENT_BUILTIN_CONFIG", {})
            builtin_chat_ids_dict = builtin_config.get("builtin_chat_ids", {})
            builtin_user_ids_dict = builtin_config.get("builtin_user_ids", {})

            if not builtin_chat_ids_dict and not builtin_user_ids_dict:
                logger.debug(f"No receivers configured for incident {incident_id}, skip sending notice")
                return

            # 优先使用传入的 incident_document，避免 ES 索引延迟导致查询失败
            # 这对于 CREATE 事件尤为重要，因为文档刚写入 ES 时可能还未被索引
            if not incident_document:
                incident_document = cls._get_incident_document_with_retry(incident_id, sleep_time=0.5)
                if not incident_document:
                    logger.warning(f"Failed to get incident document for incident {incident_id}, skip sending notice")
                    return

            # 根据故障的业务ID从字典中获取对应的接收人
            # 注意：配置中的 key 是字符串，需要转换类型
            bk_biz_id = str(incident_document.bk_biz_id)
            chat_ids = builtin_chat_ids_dict.get(bk_biz_id, [])
            user_ids = builtin_user_ids_dict.get(bk_biz_id, [])
            # 接收人，使用内置的admin接收人，管理员组
            admin_ids = builtin_chat_ids_dict.get("admin", [])
            if admin_ids:
                chat_ids.extend(admin_ids)

            if not chat_ids and not user_ids:
                logger.debug(
                    f"No receivers configured for incident {incident_id} (bk_biz_id={bk_biz_id}), skip sending notice"
                )
                return

            # 延迟导入避免循环依赖
            from bkmonitor.aiops.incident.notice import IncidentNoticeHelper

            # 发送通知（支持多种方式）
            all_results = IncidentNoticeHelper.send_incident_notice(
                incident=incident_document,
                chat_ids=chat_ids,
                user_ids=user_ids,
                title=None,
                operation_type=operation_type,
                **kwargs,
            )

            # 记录通知操作
            if all_results:
                # 收集所有成功的接收人
                all_receivers = []
                for notice_way, results in all_results.items():
                    for receiver, res in results.items():
                        if res.get("result"):
                            all_receivers.append(f"{notice_way}:{receiver}")

                if all_receivers:
                    # 直接记录通知操作，不再触发通知（避免递归）
                    cls._record_notice_without_trigger(
                        incident_id=incident_id,
                        operate_time=int(time.time()),
                        receivers=all_receivers,
                    )
                    logger.info(
                        f"Sent incident notice for incident {incident_id} (operation: {operation_type.value}) "
                        f"to {len(all_receivers)} receiver(s) via {len(all_results)} channel(s)"
                    )
        except Exception as e:
            logger.exception(f"Failed to send incident notice for incident {incident_id}: {e}")

    @classmethod
    def _record_notice_without_trigger(
        cls, incident_id: int, operate_time: int, receivers: list[str]
    ) -> IncidentOperationDocument:
        """记录通知发送流水（不触发通知发送，仅记录）

        使用 SEND_MESSAGE 类型，该类型为内部操作类型，不在故障流转记录查询中展示

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param receivers: 接收人
        :return: 故障流转记录
        """
        operator = None
        IncidentOperationDocument.bulk_create(
            [
                IncidentOperationDocument(
                    incident_id=incident_id,
                    operator=operator,
                    operation_type=IncidentOperationType.SEND_MESSAGE.value,
                    create_time=operate_time,
                    extra_info={"receivers": receivers},
                )
            ],
            action=BulkActionType.CREATE,
        )

    @classmethod
    def record_create_incident(
        cls,
        incident_id: int,
        operate_time: int,
        alert_count: int,
        assignees: list[str],
        incident_document: IncidentDocument = None,
        incident_name: str = None,
    ) -> IncidentOperationDocument:
        """记录生成故障
        文案: 生成故障，包含{alert_count}个告警，负责人为{handlers}

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_count: 告警数量
        :param assignees: 故障负责人
        :param incident_document: 故障文档对象（可选，传入后可直接用于发送通知，避免 ES 查询延迟）
        :param incident_name: 故障名称（用于判断是否为匿名故障）
        :return: 故障流转记录
        """
        # 匿名故障不发送通知
        is_anonymous = cls.is_anonymous_incident(incident_name) if incident_name else False

        return cls.record_operation(
            incident_id,
            IncidentOperationType.CREATE,
            operate_time,
            send_notice=not is_anonymous,
            alert_count=alert_count,
            assignees=assignees,
            incident_document=incident_document,
        )

    @classmethod
    def record_observe_incident(cls, incident_id: int, operate_time: int) -> IncidentOperationDocument:
        """记录故障状态转为观察中
        文案: 故障观察中

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :return: 故障流转记录
        """
        return cls.record_operation(incident_id, IncidentOperationType.OBSERVE, operate_time, send_notice=True)

    @classmethod
    def record_recover_incident(cls, incident_id: int, operate_time: int) -> IncidentOperationDocument:
        """记录故障状态转为恢复
        文案: 故障已恢复

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :return: 故障流转记录
        """
        return cls.record_operation(incident_id, IncidentOperationType.RECOVER, operate_time, send_notice=True)

    @classmethod
    def record_reopen_incident(cls, incident_id: int, operate_time: int) -> IncidentOperationDocument:
        """记录故障重新打开
        文案: 故障在观察期间重新打开

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :return: 故障流转记录
        """
        return cls.record_operation(incident_id, IncidentOperationType.REOPEN, operate_time, send_notice=True)

    @classmethod
    def record_notice_incident(
        cls, incident_id: int, operate_time: int, receivers: list[str]
    ) -> IncidentOperationDocument:
        """记录故障通知
        文案: 故障通知已发送（接收人：{receivers}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param receivers: 接收人
        :return: 故障流转记录
        """
        return cls.record_operation(incident_id, IncidentOperationType.NOTICE, operate_time, receivers=receivers)

    @classmethod
    def record_update_incident(
        cls, incident_id: int, operate_time: int, incident_key: str, from_value: Any, to_value: Any, **kwargs
    ):
        """记录故障修改属性
        文案: 故障属性{incident_key}: 从{from_value}被修改为{to_value}

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param incident_key: 故障属性Key
        :param from_value: 属性原来的值
        :param to_value: 属性修改后的值
        :return: 故障流转记录
        """
        # status 变更属于高频、强语义事件：若存在对应的专用事件类型，则优先写入专用事件
        # 以避免同一次变更重复产生 UPDATE(status) 与专用事件两条通知。
        if incident_key == "status":
            if to_value == IncidentStatus.MERGED.value:
                merge_info = kwargs.get("merge_info")
                return cls.record_merge_incident(operate_time, merge_info=merge_info)
            if to_value == IncidentStatus.RECOVERED.value:
                return cls.record_recover_incident(incident_id=incident_id, operate_time=operate_time)
            if to_value == IncidentStatus.RECOVERING.value:
                # 观察中事件：观察时长由 notice.py 中的 _format_observe_duration 从 end_time 实时计算
                return cls.record_observe_incident(incident_id=incident_id, operate_time=operate_time)
            # 故障重新打开：从观察中（RECOVERING）变为异常（ABNORMAL）
            if to_value == IncidentStatus.ABNORMAL.value and from_value == IncidentStatus.RECOVERING.value:
                return cls.record_reopen_incident(incident_id=incident_id, operate_time=operate_time)

        enum_class = INCIDENT_ATTRIBUTE_VALUE_ENUMS.get(incident_key)
        return cls.record_operation(
            incident_id,
            IncidentOperationType.UPDATE,
            operate_time,
            incident_key=incident_key,
            from_value=str(enum_class(from_value).alias) if enum_class else from_value,
            to_value=str(enum_class(to_value).alias) if enum_class else to_value,
            incident_key_alias=INCIDENT_ATTRIBUTE_ALIAS_MAPPINGS.get(incident_key, incident_key),
        )

    @classmethod
    def is_anonymous_incident(cls, incident_name: str) -> bool:
        """判断是否为匿名故障（后台默认生成的临时故障名称）

        :param incident_name: 故障名称
        :return: 是否为匿名故障
        """
        return bool(incident_name and incident_name.startswith("new_incident_"))

    @classmethod
    def record_merge_incident(cls, operate_time: int, merge_info: dict = None, alert_count: int = None):
        """记录故障合并
        文案:
        - MERGE_TO: 故障被合并到{target_incident_name}
        - MERGE: 故障{origin_incident_name}被合并入当前故障

        :param operate_time: 流转生成时间
        :param merge_info: 故障合并的信息
            "origin_incident_id": 被合并的故障id,
            "origin_incident_name": 被合并的故障name
            "origin_created_at": 被合并的故障create_time
            "target_incident_id": 合并到的目标故障id,
            "target_incident_name": 合并到的目标故障name
            "target_created_at": 合并到的目标故障create_time
        :param alert_count: 被合并故障的告警数量（用于匿名故障的通知展示）
        :return: 故障流转记录
        """
        merge_info = merge_info if isinstance(merge_info, dict) else {}
        origin_incident_id = merge_info.get("origin_incident_id")
        target_incident_id = merge_info.get("target_incident_id")
        origin_incident_name = merge_info.get("origin_incident_name", "")
        target_incident_name = merge_info.get("target_incident_name", "")
        origin_created_at = merge_info.get("origin_created_at")
        target_created_at = merge_info.get("target_created_at")

        if not all([origin_incident_id, target_incident_id]) or origin_incident_id == target_incident_id:
            logger.warning(
                f"Invalid merge info: origin_incident_id={origin_incident_id}, target_incident_id={target_incident_id}"
            )
            return False

        origin_incident_id = int(origin_incident_id)
        target_incident_id = int(target_incident_id)

        # 构建故障文档ID，用于链接跳转
        # IncidentDocument的id格式为: {create_time}{incident_id}
        origin_incident_doc_id = f"{origin_created_at}{origin_incident_id}" if origin_created_at else None
        target_incident_doc_id = f"{target_created_at}{target_incident_id}" if target_created_at else None

        # 判断源故障是否为匿名故障（new_incident_xxx 格式）
        is_anonymous = cls.is_anonymous_incident(origin_incident_name)

        # 给被合并故障，记录 incident_merge_to 记录
        # 匿名故障不发送通知
        cls.record_operation(
            origin_incident_id,
            IncidentOperationType.MERGE_TO,
            operate_time,
            send_notice=not is_anonymous,  # 匿名故障不发送通知
            link_incident_name=target_incident_name,
            link_incident_id=target_incident_id,
            link_incident_doc_id=target_incident_doc_id,
            action={"type": "link", "target": "incident", "params": ["link_incident_doc_id"]},
        )

        # 给合并目标故障，记录 incident_merge 记录
        cls.record_operation(
            target_incident_id,
            IncidentOperationType.MERGE,
            operate_time,
            send_notice=True,
            link_incident_name=origin_incident_name,
            link_incident_id=origin_incident_id,
            link_incident_doc_id=origin_incident_doc_id,
            is_anonymous_source=is_anonymous,  # 标记源故障是否为匿名故障
            alert_count=alert_count,  # 传递告警数量
            action={"type": "link", "target": "incident", "params": ["link_incident_doc_id"]},
        )

        return True

    @classmethod
    def record_incident_alert_trigger(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障检测到新告警
        文案: 检测到新告警（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 新告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id, IncidentOperationType.ALERT_TRIGGER, operate_time, alert_name=alert_name, alert_id=alert_id
        )

    @classmethod
    def record_incident_alert_recover(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障告警恢复
        文案: 告警已恢复（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 新告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id, IncidentOperationType.ALERT_RECOVER, operate_time, alert_name=alert_name, alert_id=alert_id
        )

    @classmethod
    def record_incident_alert_invalid(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障告警失效
        文案: 告警已失效（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 新告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.ALERT_INVALID,
            operate_time,
            alert_name=alert_name,
            alert_id=alert_id,
        )

    @classmethod
    def record_incident_alert_notice(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int, receivers: list[str]
    ) -> IncidentOperationDocument:
        """记录故障告警通知
        文案: 告警通知已发送（{alert_name}；接收人：{recievers}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 新告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.ALERT_NOTICE,
            operate_time,
            alert_name=alert_name,
            receivers=receivers,
            alert_id=alert_id,
        )

    @classmethod
    def record_incident_alert_convergence(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id, converged_count: int
    ) -> IncidentOperationDocument:
        """记录故障告警收敛
        文案: 告警已收敛（{alert_name}，共包含{converged_count}个关联的告警事件）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 新告警名称
        :param alert_id: 告警ID
        :param converged_count: 被收敛的告警事件个数
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.ALERT_CONVERGENCE,
            operate_time,
            alert_name=alert_name,
            alert_id=alert_id,
            converged_count=converged_count,
        )

    @classmethod
    def record_user_update_incident(
        cls, incident_id: int, operate_time: int, incident_key: str, from_value: Any, to_value: Any
    ) -> IncidentOperationDocument:
        """记录用户修改故障属性
        文案: 故障属性{incident_key}: 从{from_value}被修改为{to_value}

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param incident_key: 故障属性Key
        :param from_value: 属性原来的值
        :param to_value: 属性修改后的值
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.MANUAL_UPDATE,
            operate_time,
            incident_key=incident_key,
            from_value=from_value,
            to_value=to_value,
            incident_key_alias=INCIDENT_ATTRIBUTE_ALIAS_MAPPINGS.get(incident_key, incident_key),
        )

    @classmethod
    def record_feedback_incident(
        cls, incident_id: int, operate_time: int, feedback_incident_root: str, content: str, is_cancel: bool = False
    ) -> IncidentOperationDocument:
        """记录用户反馈/取消反馈故障根因
        文案: 反馈根因：{feedback_incident_root}

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param feedback_incident_root: 反馈的故障根因
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.FEEDBACK,
            operate_time,
            feedback_incident_root=feedback_incident_root,
            content=content,
            is_cancel=is_cancel,
        )

    @classmethod
    def record_close_incident(cls, incident_id: int, operate_time: int) -> IncidentOperationDocument:
        """记录用户关闭故障
        文案: 故障已关闭

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :return: 故障流转记录
        """
        return cls.record_operation(incident_id, IncidentOperationType.CLOSE, operate_time)

    @classmethod
    def record_incident_gather_group(
        cls, incident_id: int, operate_time: int, group_name: str
    ) -> IncidentOperationDocument:
        """记录故障一键拉群
        文案: 一键拉群（{group_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param group_name: 群名称
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.GROUP_GATHER,
            operate_time,
            group_name=group_name,
        )

    @classmethod
    def record_incident_alert_confirm(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障告警确认
        文案: 告警已确认（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id, IncidentOperationType.ALERT_CONFIRM, operate_time, alert_name=alert_name, alert_id=alert_id
        )

    @classmethod
    def record_incident_alert_shield(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障告警屏蔽
        文案: 告警已屏蔽（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id, IncidentOperationType.ALERT_SHIELD, operate_time, alert_name=alert_name, alert_id=alert_id
        )

    @classmethod
    def record_incident_alert_handle(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障告警手动处理
        文案: 告警已被手动处理（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id, IncidentOperationType.ALERT_HANDLE, operate_time, alert_name=alert_name, alert_id=alert_id
        )

    @classmethod
    def record_incident_alert_dispatch(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int, handlers: list[str]
    ) -> IncidentOperationDocument:
        """记录故障告警分派
        文案: 告警已分派（{alert_name}；处理人：{handlers}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 告警名称
        :param alert_id: 告警ID
        :param handlers: 处理人
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.ALERT_DISPATCH,
            operate_time,
            alert_name=alert_name,
            alert_id=alert_id,
            handlers=handlers,
        )

    @classmethod
    def record_incident_alert_close(
        cls, incident_id: int, operate_time: int, alert_name: str, alert_id: int
    ) -> IncidentOperationDocument:
        """记录故障告警关闭
        文案: 告警已被关闭（{alert_name}）

        :param incident_id: 故障ID
        :param operate_time: 流转生成时间
        :param alert_name: 告警名称
        :param alert_id: 告警ID
        :return: 故障流转记录
        """
        return cls.record_operation(
            incident_id,
            IncidentOperationType.ALERT_CLOSE,
            operate_time,
            alert_name=alert_name,
            alert_id=alert_id,
        )
