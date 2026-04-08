"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from alarm_backends.core.context import ActionContext
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionInstance
from bkmonitor.utils.send import Sender
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.action import ActionSignal, NoticeType

logger = logging.getLogger("fta_action.run")


class Command(BaseCommand):
    """
    告警通知预览命令

    功能：预览告警发送出去的标准通知内容（标题和正文）

    使用方法：
        python manage.py notice_preview <alert_id> [--notice-way <notice_way>] [--action-id <action_id>]

    参数说明：
        alert_id: 告警 ID（必需，用于查找动作实例）
        --notice-way: 通知方式（可选，如：mail、sms、weixin、wxwork-bot 等）
                     如果不指定，将预览策略中配置的所有通知渠道（去重）
        --action-id: 动作实例 ID（可选，如果不指定则使用第一个通知动作）
                    如果指定了 action_id，将使用该动作实例中的告警信息

    示例：
        # 1. 预览所有通知渠道（自动查找告警对应的动作实例，按渠道去重）
        python manage.py notice_preview 12345

        # 2. 只预览邮件通知
        python manage.py notice_preview 12345 --notice-way mail

        # 3. 通过动作实例 ID 预览（使用动作实例中的告警信息）
        python manage.py notice_preview 12345 --action-id 67890

    相关命令：
        # 查看可用的上下文变量（用于编写自定义模板）
        python manage.py context_preview 12345
    """

    def add_arguments(self, parser):
        parser.add_argument("alert_id", type=int, help="告警 ID")
        parser.add_argument("--notice-way", type=str, help="通知方式（如：mail、sms、weixin、wxwork-bot）")
        parser.add_argument("--action-id", type=int, help="动作实例 ID（可选）")

    def handle(self, alert_id, *args, **options):
        notice_way = options.get("notice_way")
        action_id = options.get("action_id")

        try:
            # 1. 获取动作实例列表
            if action_id:
                # 如果指定了 action_id，只获取该动作实例
                action_instances = self._get_action_instances_by_id(action_id)
            else:
                # 如果没有指定，获取告警关联的所有通知动作实例
                action_instances = self._get_action_instances_by_alert(alert_id)

            if not action_instances:
                self.stdout.write(self.style.ERROR(f"告警 ID {alert_id} 没有关联的通知动作"))
                return

            # 2. 按渠道分组，去重并选择每个渠道对应的动作实例
            notice_way_to_action = self._group_actions_by_notice_way(action_instances, notice_way)

            if not notice_way_to_action:
                self.stdout.write(self.style.WARNING("没有可预览的通知"))
                return

            # 3. 遍历每个唯一的通知渠道，预览通知
            total_previews = 0
            for nw, action_instance in notice_way_to_action.items():
                # 获取告警文档列表（从 action_instance.alerts 获取）
                alert_docs = self._get_alert_documents(action_instance, alert_id)
                if not alert_docs:
                    self.stdout.write(
                        self.style.WARNING(f"通知方式 {nw} (动作实例 {action_instance.id}) 无法获取告警文档，跳过")
                    )
                    continue

                # 创建 ActionContext
                context = self._create_action_context(action_instance, alert_docs)

                # 渲染并输出预览结果
                total_previews += 1
                preview_result = self._render_notice_preview(context, nw, action_instance)
                if preview_result.get("error"):
                    self.stdout.write(
                        self.style.ERROR(
                            f"\n预览通知方式 {nw} (动作实例 {action_instance.id}) 失败: {preview_result['error']}\n"
                        )
                    )
                else:
                    self._output_preview_result(preview_result, nw, action_instance)

            if total_previews == 0:
                self.stdout.write(self.style.WARNING("没有可预览的通知"))
            else:
                self.stdout.write(self.style.SUCCESS(f"\n总计预览了 {total_previews} 个唯一通知渠道"))

        except Exception as e:
            logger.exception(f"预览告警通知失败: alert_id={alert_id}, error={str(e)}")
            self.stdout.write(self.style.ERROR(f"预览失败: {str(e)}"))

    def _get_action_instances_by_id(self, action_id):
        """
        通过 action_id 获取动作实例列表

        :param action_id: 动作实例 ID
        :return: ActionInstance 对象列表
        """
        try:
            action_instance = ActionInstance.objects.get(id=action_id)
            # 检查是否为通知类型的动作
            if action_instance.action_plugin.get("plugin_type") != "notice":
                self.stdout.write(self.style.WARNING(f"动作实例 {action_id} 不是通知类型的动作"))
                return []
            return [action_instance]
        except ActionInstance.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"动作实例 {action_id} 不存在"))
            return []

    def _get_action_instances_by_alert(self, alert_id):
        """
        通过 alert_id 获取所有通知动作实例列表

        :param alert_id: 告警 ID
        :return: ActionInstance 对象列表
        """
        # 从 ES 查找所有通知动作
        action_docs = ActionInstanceDocument.mget_by_alert(
            alert_ids=[alert_id],
            include={"action_plugin_type": "notice"},
            ordering=["-create_time"],
        )

        if not action_docs:
            return []

        # 获取所有动作实例的完整对象
        action_instances = []
        for action_doc in action_docs:
            try:
                action_instance = ActionInstance.objects.get(id=action_doc.raw_id)
                action_instances.append(action_instance)
            except ActionInstance.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"动作实例 {action_doc.raw_id} 不存在"))
                continue

        return action_instances

    def _get_alert_documents(self, action_instance, fallback_alert_id):
        """
        从 ActionInstance 获取告警文档列表

        :param action_instance: ActionInstance 对象
        :param fallback_alert_id: 备用的告警 ID（如果 ActionInstance.alerts 为空）
        :return: AlertDocument 对象列表
        """
        alert_ids = []

        # 从 ActionInstance.alerts 获取告警 ID 列表
        if action_instance.alerts:
            try:
                if isinstance(action_instance.alerts, list):
                    # 处理列表，安全转换为整数
                    for aid in action_instance.alerts:
                        try:
                            alert_ids.append(int(aid) if isinstance(aid, str) else aid)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"无法转换告警 ID: {aid}, error={str(e)}")
                else:
                    # 处理单个值
                    try:
                        alert_ids = [
                            int(action_instance.alerts)
                            if isinstance(action_instance.alerts, str)
                            else action_instance.alerts
                        ]
                    except (ValueError, TypeError) as e:
                        logger.warning(f"无法转换告警 ID: {action_instance.alerts}, error={str(e)}")
            except Exception as e:
                logger.exception(f"解析 ActionInstance.alerts 失败: {str(e)}")

        # 如果没有，使用 fallback_alert_id
        if not alert_ids:
            alert_ids = [fallback_alert_id]

        # 获取所有告警文档
        alert_docs = []
        for alert_id in alert_ids:
            try:
                alert_doc = AlertDocument.get(id=alert_id)
                if alert_doc:
                    alert_docs.append(alert_doc)
                else:
                    self.stdout.write(self.style.WARNING(f"告警 ID {alert_id} 不存在"))
            except Exception as e:
                logger.exception(f"获取告警文档失败: alert_id={alert_id}, error={str(e)}")
                self.stdout.write(self.style.WARNING(f"获取告警 ID {alert_id} 失败: {str(e)}"))

        return alert_docs

    def _group_actions_by_notice_way(self, action_instances, specified_notice_way=None):
        """
        按通知渠道分组动作实例，每个渠道只保留一个动作实例（去重）

        :param action_instances: ActionInstance 对象列表
        :param specified_notice_way: 指定的通知方式（可选），如果指定则只处理该方式
        :return: 字典 {notice_way: action_instance}，每个 notice_way 对应一个动作实例
        """
        notice_way_to_action = {}

        for action_instance in action_instances:
            # 获取该动作实例的所有通知方式
            notice_ways = self._get_all_notice_ways_from_action(action_instance)

            # 如果指定了 notice_way，只保留匹配的
            if specified_notice_way:
                notice_ways = [nw for nw in notice_ways if nw == specified_notice_way]

            # 对每个 notice_way，如果还没有对应的动作实例，则记录
            for nw in notice_ways:
                if nw not in notice_way_to_action:
                    notice_way_to_action[nw] = action_instance
                    self.stdout.write(self.style.SUCCESS(f"通知方式 {nw} 使用动作实例 {action_instance.id}"))
                else:
                    # 已经存在，跳过（去重）
                    self.stdout.write(
                        self.style.WARNING(
                            f"通知方式 {nw} 已存在（动作实例 {notice_way_to_action[nw].id}），跳过动作实例 {action_instance.id}"
                        )
                    )

        return notice_way_to_action

    def _get_all_notice_ways_from_action(self, action_instance):
        """
        从动作实例获取所有通知方式

        :param action_instance: ActionInstance 对象
        :return: 通知方式列表
        """
        notice_ways = []

        # 1. 从 action_instance.inputs 中获取通知方式
        notice_way = action_instance.inputs.get("notice_way")
        if notice_way:
            if isinstance(notice_way, list):
                notice_ways.extend(notice_way)
            else:
                notice_ways.append(notice_way)

        # 2. 从 execute_config 中获取（优先级更高，会覆盖 inputs 中的配置）
        execute_config = action_instance.action_config.get("execute_config", {})
        template_detail = execute_config.get("template_detail", {})
        config_notice_ways = template_detail.get("notice_way", [])
        if config_notice_ways:
            if isinstance(config_notice_ways, list):
                notice_ways = config_notice_ways
            else:
                notice_ways = [config_notice_ways]

        # 去重并保持顺序
        seen = set()
        result = []
        for nw in notice_ways:
            if nw and nw not in seen:
                seen.add(nw)
                result.append(nw)

        return result

    def _create_action_context(self, action_instance, alert_docs):
        """
        创建 ActionContext

        :param action_instance: ActionInstance 对象
        :param alert_docs: AlertDocument 对象列表
        :return: ActionContext 对象
        """
        # 创建 ActionContext
        context = ActionContext(
            action=action_instance,
            alerts=alert_docs,
            use_alert_snap=False,
        )

        return context

    def _render_notice_preview(self, context, notice_way, action_instance):
        """
        渲染通知预览

        :param context: ActionContext 对象
        :param notice_way: 通知方式
        :param action_instance: ActionInstance 对象
        :return: 预览结果字典，包含 title 和 content
        """
        # 确定 action_signal
        action_signal = (
            action_instance.signal
            if action_instance.signal not in [ActionSignal.MANUAL, ActionSignal.NO_DATA]
            else ActionSignal.ABNORMAL
        )

        # 确定 msg_type
        msg_type = "markdown" if notice_way in settings.MD_SUPPORTED_NOTICE_WAYS else notice_way

        # 构建模板路径
        title_template_path = f"notice/{action_signal}/action/{notice_way}_title.jinja"
        content_template_path = f"notice/{action_signal}/action/{msg_type}_content.jinja"

        # 获取 context 字典（每次调用都生成新的字典，避免修改影响其他通知方式）
        context_dict = context.get_dictionary()
        # 设置当前通知方式
        context_dict["notice_way"] = notice_way

        # 添加用户自定义内容（从 execute_config 获取）
        execute_config = action_instance.action_config.get("execute_config", {})
        template_detail = execute_config.get("template_detail", {})
        if "user_content" in template_detail:
            context_dict["user_content"] = template_detail["user_content"]

        # 创建 Sender 实例（不实际发送）
        try:
            # 从 bk_biz_id 转换为 bk_tenant_id
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(action_instance.bk_biz_id)

            sender = Sender(
                context=context_dict,
                title_template_path=title_template_path,
                content_template_path=content_template_path,
                notice_type=NoticeType.ALERT_NOTICE,
                bk_tenant_id=bk_tenant_id,
            )

            return {
                "title": sender.title,
                "content": sender.content,
                "notice_way": notice_way,
                "action_signal": action_signal,
                "msg_type": msg_type,
                "error": None,
            }
        except Exception as e:
            logger.exception(f"渲染通知预览失败: notice_way={notice_way}, error={str(e)}")
            return {
                "title": "",
                "content": "",
                "notice_way": notice_way,
                "action_signal": action_signal,
                "msg_type": msg_type,
                "error": str(e),
            }

    def _output_preview_result(self, preview_result, notice_way, action_instance):
        """
        输出预览结果

        :param preview_result: 预览结果字典
        :param notice_way: 通知方式
        :param action_instance: ActionInstance 对象
        """
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("告警通知预览结果"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        self.stdout.write(f"动作实例 ID: {action_instance.id}")
        self.stdout.write(f"告警信号: {preview_result['action_signal']}")
        self.stdout.write(f"通知方式: {notice_way}")
        self.stdout.write(f"消息类型: {preview_result['msg_type']}")
        self.stdout.write("\n" + "-" * 80 + "\n")

        self.stdout.write(self.style.SUCCESS("通知标题:"))
        self.stdout.write(preview_result["title"])
        self.stdout.write("\n" + "-" * 80 + "\n")

        self.stdout.write(self.style.SUCCESS("通知内容:"))
        self.stdout.write(preview_result["content"])
        self.stdout.write("\n" + "=" * 80 + "\n")
