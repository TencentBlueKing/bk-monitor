"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import copy
import hashlib
import json
import logging
from os import path

import requests
from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.translation import gettext as _

from bkmonitor.models import GlobalConfig
from bkmonitor.utils.template import AlarmNoticeTemplate, AlarmOperateNoticeTemplate
from bkmonitor.utils.text import (
    cut_line_str_by_max_bytes,
    cut_str_by_max_bytes,
    get_content_length,
)
from common.context_processors import Platform
from constants.action import ActionPluginType, NoticeType, NoticeWay
from core.drf_resource import api
from core.prometheus import metrics

try:
    from alarm_backends.core.i18n import i18n
except Exception:
    i18n = None

logger = logging.getLogger("fta_action.run")


class BaseSender:
    """
    通知发送器
    """

    LengthLimit = {
        "sms": 140,
    }

    NoticeTemplate = {
        NoticeType.ALERT_NOTICE: AlarmNoticeTemplate,
        NoticeType.ACTION_NOTICE: AlarmOperateNoticeTemplate,
    }

    NoEncoding = [NoticeWay.SMS]
    Utf8Encoding = "utf-8"

    def __init__(
        self, context=None, title_template_path="", content_template_path="", notice_type=NoticeType.ALERT_NOTICE
    ):
        """
        :param context: EventContext or dict
        :param title_template_path: 通知title的模板路径
        :param content_template_path: 通知content的模板路径
        """
        self.context = context
        try:
            self.bk_biz_id = int(self.context.get("target").business.bk_biz_id)
        except Exception as error:
            logger.debug("failed to get notice business id: %s", str(error))
            self.bk_biz_id = self.context.get("bk_biz_id", 0)

        # todo: 这里是公共模块，不应该依赖alarm_backends
        if i18n:
            i18n.set_biz(self.bk_biz_id)
            language = i18n.get_locale()
            if not language == settings.DEFAULT_LOCALE:
                title_template_path = self.get_language_template_path(title_template_path, language)
                content_template_path = self.get_language_template_path(content_template_path, language)

        notice_template_class = self.NoticeTemplate.get(notice_type, AlarmNoticeTemplate)
        # 此处的模板已经在没有的情况下获取到了默认模板，所以不需要带语言后缀渲染
        title_template = notice_template_class(title_template_path)
        content_template = notice_template_class(content_template_path)
        context_dict = self.get_context_dict()
        self.notice_way = context_dict.get("notice_way", None)
        self.mentioned_users = context_dict.get("mentioned_users", None)
        self.encoding = None if self.notice_way in self.NoEncoding else self.Utf8Encoding
        self.context["encoding"] = self.encoding
        self.title = title_template.render(context_dict)
        try:
            self.content = content_template.render(context_dict)
        except Exception as e:
            logger.exception(e)
            self.content = str(e)
            return
        self.msg_type = "markdown" if self.notice_way in settings.MD_SUPPORTED_NOTICE_WAYS else "text"
        self.handle_content_length(content_template, context_dict)

    def handle_content_length(self, content_template, context_dict):
        content_limit = self.get_content_limit(self.notice_way)
        # 渲染后的总提长度: self.content（这里做了特殊字符的replace, 一个特殊字符占1个长度)
        content_length = get_content_length(self.content, self.encoding)
        if not content_limit or content_limit >= content_length:
            # 不需要限制长度
            return
        # 计算扣除 user_content 后剩余模板内容的长度（这里user_content的特殊字符 占2个长度）
        template_content_length = content_length - get_content_length(
            context_dict.get("user_content", ""), self.encoding
        )
        self.context["limit"] = True
        # content_length 基于self.content 计算（经过了\\n, \\t的转换， 因此实际长度比context_dict["user_content"]中的原始长度小
        # template_content_length 这里长度计算少了
        # 重新渲染的长度，要减去特殊字符的个数。
        self.context["user_content_length"] = (
            content_limit - template_content_length - 1 - self.content.count("\n") - self.content.count("\t")
        )
        self.content = content_template.render(self.get_context_dict())

    @staticmethod
    def get_language_template_path(template_path, language):
        """
        获取对应语言的模板文件
        :param template_path: 原模板
        :param language: 对应语言
        :return:
        """
        dir_path, filename = path.split(template_path)
        name, ext = path.splitext(filename)
        name = f"{name}_{language}{ext}"
        lang_template_path = path.join(dir_path, name)
        try:
            get_template(lang_template_path)
        except TemplateDoesNotExist:
            logger.info(f"use default template because language template file {lang_template_path} load fail")
            return template_path
        logger.info(f"use special language template {lang_template_path} for notice")
        return lang_template_path

    def get_context_dict(self):
        """
        获取上下文字典
        """
        context_dict = {"notice_title": GlobalConfig.get("NOTICE_TITLE")}
        if self.context is None:
            return context_dict
        if not isinstance(self.context, dict):
            context_dict.update(self.context.get_dictionary())
        else:
            context_dict.update(self.context)
        return context_dict

    def handle_api_result(self, api_result, notice_receivers):
        """
        处理接口返回结果
        """
        notice_result = {}
        message: str = api_result.get("message", "")
        msg_id = api_result.get("data", {}).get("msg_id")
        message_details: dict[str, str] = api_result.get("message_detail", {})
        if msg_id:
            # 记录msg_id信息
            message = f"{message} msg_id: {msg_id}"

        for notice_receiver in notice_receivers:
            if notice_receiver in api_result["username_check"]["invalid"]:
                notice_result[notice_receiver] = {"message": message, "result": False, "msg_id": msg_id}
            else:
                notice_result[notice_receiver] = {"message": message, "result": True, "msg_id": msg_id}

        # 针对有具体详情的用户更新其内容
        if message_details:
            for notice_receiver, message_detail in message_details.items():
                notice_result[notice_receiver]["message"] = message_detail
                notice_result[notice_receiver]["result"] = False
        return notice_result

    @classmethod
    def get_content_limit(cls, notice_way):
        content_limit = settings.NOTICE_MESSAGE_MAX_LENGTH.get(notice_way, 0)
        if notice_way == NoticeWay.SMS and settings.SMS_CONTENT_LENGTH:
            # 短信以页面的配置为主
            content_limit = settings.SMS_CONTENT_LENGTH
        return content_limit

    @classmethod
    def get_notice_content(cls, notice_way, content, encoding="utf-8"):
        """
        获取通知实际发送内容
        :param encoding: 编码方式
        :param notice_way: 通知方法
        :param content:原内容
        :return:
        """
        if notice_way in cls.NoEncoding:
            encoding = None
        content_limit = cls.get_content_limit(notice_way)
        content_length = get_content_length(content, encoding)
        if content_limit and content_length > content_limit:
            content = cut_str_by_max_bytes(content, content_limit, encoding=encoding)
            content = f"{content[: len(content) - 3]}..."
            logger.info(
                f"send.{notice_way}: \n actual content: {content} \norigin content length({content_length}) is bigger than ({content_limit})  "
            )
        return content

    @staticmethod
    def split_layout_content(msgtype, content, mentioned_users, encoding="utf-8"):
        """
        获取通知实际发送内容
        :param msgtype: 通知格式
        :param content:原内容
         :param encoding: 编码方式
        :return:
        """
        content_limit = 2046
        content_length = get_content_length(content, encoding)
        contents = [content]
        if content_limit and content_length > content_limit:
            contents = cut_line_str_by_max_bytes(content, content_limit, encoding=encoding)
        msg_layout = {"type": "column_layout", "components": []}
        for block_msg in contents:
            msg_layout["components"].append({"type": msgtype, "text": block_msg, "style": "sub_text"})

        if mentioned_users:
            # 进行数据检测截断， 默认用markdown的格式推送
            mentioned_users = cut_str_by_max_bytes(mentioned_users, content_limit, encoding=encoding)
            msg_layout["components"].append({"type": "markdown", "text": mentioned_users, "style": "sub_text"})

        msg_layout["components"].append({"type": "divider"})
        return msg_layout

    def send(self, notice_way: str, notice_receivers: list, action_plugin=ActionPluginType.NOTICE):
        """
        统一发送通知
        :return: :return: {
            "user1": {"result": true, "message": "OK"},
            "user2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        if notice_way != self.notice_way:
            # 需要判断真正通知的方式是否与默认的一致，不一致的话要重置msg_type
            self.msg_type = "markdown" if notice_way in settings.MD_SUPPORTED_NOTICE_WAYS else "text"
            self.encoding = None if notice_way in self.NoEncoding else self.Utf8Encoding
        if isinstance(self.content, Exception):
            return {
                notice_receiver: {"message": str(self.content), "result": False} for notice_receiver in notice_receivers
            }
        self.content = self.get_notice_content(notice_way, self.content)
        method = getattr(self, "send_{}".format(notice_way.replace("-", "_")), None)
        if method:
            notice_results = method(notice_receivers, action_plugin=action_plugin)
        else:
            notice_results = self.send_default(notice_way, notice_receivers)

        if notice_results:
            failed_count = 0
            succeed_count = 0
            for result in notice_results.values():
                if result["result"]:
                    succeed_count += 1
                else:
                    failed_count += 1
            if failed_count:
                metrics.ACTION_NOTICE_API_CALL_COUNT.labels(
                    notice_way=notice_way, status=metrics.StatusEnum.FAILED
                ).inc(failed_count)
            if succeed_count:
                metrics.ACTION_NOTICE_API_CALL_COUNT.labels(
                    notice_way=notice_way, status=metrics.StatusEnum.SUCCESS
                ).inc(succeed_count)

        return notice_results

    def send_default(self, notice_way, notice_receivers, sender=None):
        raise NotImplementedError


class Sender(BaseSender):
    def send_weixin(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        发送微信通知
        :return: {
            "user1": {"result": true, "message": "OK"},
            "user2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        sender_name = settings.WECOM_APP_ACCOUNT.get(str(self.context.get("alert_level")))

        if (
            settings.IS_WECOM_ROBOT_ENABLED
            and Platform.te
            and sender_name
            and (not settings.WECOM_ROBOT_BIZ_WHITE_LIST or self.bk_biz_id in settings.WECOM_ROBOT_BIZ_WHITE_LIST)
        ):
            logger.info(
                "send.webot_app({}): \ntitle: {}\ncontent: {} \naction_plugin {}".format(
                    ",".join(notice_receivers), self.title, self.content, action_plugin
                )
            )
            # 复用企业微信机器人的配置
            # 如果启用了并且是te环境，可以使用
            # 用白名单控制
            # 需要判断是否有通知人员，才进行通知发送
            api_result = api.cmsi.send_wecom_app(
                # 这里receiver 也是用户名
                receiver=notice_receivers,
                sender=sender_name,
                content=self.content,
                type=self.msg_type,
            )
        else:
            logger.info(
                "send.weixin({}): \ntitle: {}\ncontent: {} \naction_plugin {}".format(
                    ",".join(notice_receivers), self.title, self.content, action_plugin
                )
            )
            api_result = api.cmsi.send_weixin(
                # 用户名
                receiver__username=",".join(notice_receivers),
                heading=self.title,
                message=self.content,
                is_message_base64=True,
            )
        return self.handle_api_result(api_result, notice_receivers)

    def send_mail(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        发送邮件通知
        :return: {
            "user1": {"result": true, "message": "OK"},
            "user2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        params = {
            "title": self.title,
            # 发送执行通知的邮件，默认将内容换行
            "content": self.content,
            "is_content_base64": True,
        }
        # external_email: 邮件订阅支持直接外部邮件发送
        # receiver 对应邮箱地址
        # receiver__username 对应用户名, 使用这个字段，不需要关注用户敏感信息, 邮箱地址由邮件发送网关处理(esb[cmsi]/apigw[bk-cmsi])
        if self.context.get("external_email"):
            params["receiver"] = ",".join(notice_receivers)
            params["receiver__username"] = ""
        else:
            params["receiver__username"] = ",".join(notice_receivers)
            params["receiver"] = ""

        # 添加附件参数
        if self.context.get("attachments"):
            params["attachments"] = self.context.get("attachments")
        elif self.context.get("alarm") and action_plugin == ActionPluginType.NOTICE:
            params["attachments"] = self.context["alarm"].attachments

        logger.info("send.mail({}): \ntitle: {}".format(",".join(notice_receivers), self.title))

        api_result = api.cmsi.send_mail(**params)
        return self.handle_api_result(api_result, notice_receivers)

    def send_sms(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        发送短信通知
        :return: {
            "user1": {"result": true, "message": "OK"},
            "user2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        logger.info(
            "send.sms({}): \ncontent: {} \naction_plugin {}".format(
                ",".join(notice_receivers), self.content, action_plugin
            )
        )
        self.content = self.get_notice_content(NoticeWay.SMS, self.content)
        api_result = api.cmsi.send_sms(
            receiver__username=",".join(notice_receivers),
            content=self.content,
            is_content_base64=True,
        )
        return self.handle_api_result(api_result, notice_receivers)

    def send_voice(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        发送语音通知
        :return: {
            "user1,user2": {"result": true, "message": "发送成功"},
            "user1,user2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        notice_result = {}
        result = True
        message = _("发送成功")
        notice_receivers = ",".join(notice_receivers)

        logger.info(f"send.voice({notice_receivers}): \ncontent: {self.content}, \n action_plugin {action_plugin}")

        try:
            msg_result = api.cmsi.send_voice(
                receiver__username=notice_receivers,
                auto_read_message=self.content,
            )
            msg_id = msg_result.get("msg_id", "")
            if msg_id:
                message = _("发送成功, 消息ID为{}").format(msg_id)

        except Exception as e:
            result = False
            message = str(e)
            logger.exception(f"send.voice failed, {e}")

        notice_result[notice_receivers] = {"message": message, "result": result}
        return notice_result

    @staticmethod
    def send_wxwork_image(image, chat_ids):
        md5 = hashlib.md5(base64.decodebytes(image.encode(encoding="UTF-8"))).hexdigest()
        params = {
            "chatid": "|".join(chat_ids),
            "msgtype": "image",
            "image": {"base64": image, "md5": md5},
        }
        r = requests.post(settings.WXWORK_BOT_WEBHOOK_URL, json=params)
        return r.json()

    @staticmethod
    def send_wxwork_content(msgtype, content, chat_ids, mentioned_users=None, mentioned_title=None):
        """
        发送文本类的内容
        """
        if not mentioned_users:
            # 如果没有提醒人员，直接调用一次接口
            content = Sender.get_notice_content(NoticeWay.WX_BOT, content, Sender.Utf8Encoding)
            params = {
                "msgtype": msgtype,
                "chatid": "|".join(chat_ids),
                msgtype: {"content": content},
            }
            r = requests.post(settings.WXWORK_BOT_WEBHOOK_URL, json=params)
            return r.json()

        send_result = {"errcode": 0, "errmsg": []}
        for chat_id in chat_ids:
            params = {"msgtype": msgtype, "chatid": chat_id}
            chat_mentioned_users = mentioned_users.get(chat_id, [])
            msg_content = {}
            send_content = content.rstrip("\n")
            if chat_mentioned_users:
                if msgtype == "markdown":
                    # 如果是markdown格式，组装markdown的内容
                    mentioned_users_string = "".join([f"<@{user}>" for user in chat_mentioned_users])
                    mentioned_users_string = f"**{mentioned_title or _('告警关注者')}: **{mentioned_users_string}\n"
                    logger.info("send wxwork to %s, mentioned_users_string %s", chat_id, mentioned_users_string)
                    if "--mention-users--" in content:
                        # 如果有提醒占位符位置，需要做替换，一般异常告警提醒人的位置在中间，需要做替换
                        send_content = content.replace("--mention-users--\n", mentioned_users_string)
                    else:
                        # 没有的话，直接做拼接
                        send_content = "\n".join([content, mentioned_users_string])
                else:
                    msg_content["mentioned_list"] = chat_mentioned_users
            else:
                send_content = content.replace("--mention-users--\n", "")
            send_content = Sender.get_notice_content(NoticeWay.WX_BOT, send_content, Sender.Utf8Encoding)
            msg_content["content"] = send_content
            params[msgtype] = msg_content
            try:
                response = requests.post(settings.WXWORK_BOT_WEBHOOK_URL, json=params).json()
                if response["errcode"] != 0:
                    send_result["errcode"] = -1
                    send_result["errmsg"].append(f"send to {chat_id} failed: {response['errmsg']}")
            except Exception as error:
                send_result["errcode"] = -1
                send_result["errmsg"].append(f"send to {chat_id} failed: {str(error)}")
        return send_result

    @staticmethod
    def send_wxwork_layouts(msgtype, content, chat_ids, layouts: list, mentioned_users=None, mentioned_title=None):
        """
        模块化消息推送(未启用)
        """
        send_result = {"errcode": 0, "errmsg": []}
        for chat_id in chat_ids:
            # 每个chatid的通知人员可能不一样，需要根据不同的chatid进行拆分
            chat_mentioned_users = mentioned_users.get(chat_id, [])
            mentioned_users_string = ""
            if chat_mentioned_users:
                mentioned_users_string = "".join([f"<@{user}>" for user in chat_mentioned_users])
                mentioned_users_string = f"**{mentioned_title or _('告警关注者')}: **{mentioned_users_string}"
            chat_layouts = copy.deepcopy(layouts)
            chat_layouts.insert(0, Sender.split_layout_content(msgtype, content, mentioned_users_string))
            params = {
                "msgtype": "message",
                "chatid": chat_id,
                "layouts": chat_layouts,
            }
            try:
                response = requests.post(settings.WXWORK_BOT_WEBHOOK_URL, json=params).json()
                if response["errcode"] != 0:
                    send_result["errmsg"].append(f"send to {chat_id} failed: {response['errmsg']}")
            except Exception as error:
                send_result["errcode"] = -1
                send_result["errmsg"].append(f"send to {chat_id} failed: {str(error)}")
        send_result["errmsg"] = ",".join(send_result["errmsg"])
        return send_result

    def send_wxwork_bot(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        发送企业微信群通知
        """

        def finish_send_wxork_bot(msg, ret):
            notice_result = {}
            for notice_receiver in notice_receivers:
                notice_result[notice_receiver] = {"message": msg, "result": ret}
            return notice_result

        message = _("发送成功")
        logger.info(
            "send.wxwork_group({}): \ncontent: {} \n action_plugin {}".format(
                ",".join(notice_receivers), self.content, action_plugin
            )
        )

        result = True

        alarm = self.context.get("alarm", None)
        if not settings.WXWORK_BOT_WEBHOOK_URL:
            return finish_send_wxork_bot(_("未配置蓝鲸监控群机器人回调地址，请联系管理员"), False)

        if not notice_receivers:
            return finish_send_wxork_bot(_("未配置企业微信群id，请联系管理员"), False)

        try:
            # 如果不是，保留以前的发送格式
            response = self.send_wxwork_content(self.msg_type, self.content, notice_receivers, self.mentioned_users)
            if response["errcode"] != 0:
                result = False
                message = response["errmsg"]
        except Exception as e:
            result = False
            message = str(e)
            logger.exception(f"send.wxwork_group failed, {e}")

        if action_plugin == ActionPluginType.NOTICE and settings.WXWORK_BOT_SEND_IMAGE:
            # 只有告警通知才发送图片，执行不做图片发送
            try:
                image = alarm.chart_image if alarm else None
                if image:
                    response = self.send_wxwork_image(image, notice_receivers)
                    if response["errcode"] != 0:
                        logger.error("send.wxwork_group image failed, {}".format(response["errmsg"]))
                else:
                    logger.info(
                        "ignore sending chart image to chat_id({}) for action({})".format(
                            "|".join(notice_receivers),
                            self.context["action"].id if self.context.get("action") else "NULL",
                        )
                    )
            except Exception as e:
                logger.exception(f"send.wxwork_group image failed, {e}")

        return finish_send_wxork_bot(message, result)

    def send_rtx(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        :param notice_receivers:
        :param action_plugin:
        :return:
        """
        sender = None
        notice_way = "rtx"
        if settings.IS_WECOM_ROBOT_ENABLED and Platform.te:
            # 允许进行通知方式切换，才进行通知发送
            sender = settings.WECOM_ROBOT_ACCOUNT.get(str(self.context.get("alert_level")))
            if sender:
                notice_way = "wecom_robot"
        return self.send_default(notice_way, notice_receivers, sender)

    def send_default(self, notice_way, notice_receivers, sender=None):
        """
        发送默认通知
        :return: {
            "user1": {"result": true, "message": "OK"},
            "user2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        logger.info(
            "send.{}({}): \ntitle: {}\ncontent: {}".format(
                notice_way, ",".join(notice_receivers), self.title, self.content
            )
        )
        if notice_way == "wecom_robot":
            # 企业微信robot发送的内容需要json格式支持
            self.content = json.dumps({"type": self.msg_type, self.msg_type: {"content": self.content}})

        msg_data = dict(
            msg_type=notice_way, receiver__username=",".join(notice_receivers), title=self.title, content=self.content
        )
        if sender:
            msg_data.update({"sender": sender})

        api_result = api.cmsi.send_msg(**msg_data)
        return self.handle_api_result(api_result, notice_receivers)


class NoneTemplateSender(Sender):
    def __init__(self, title="", content="", context=None):
        self.context = context or {}
        self.title = title
        self.content = content
        self.msg_type = "text"
        self.notice_way = None
        self.encoding = self.Utf8Encoding
        self.bk_biz_id = None


class ChannelBkchatSender(BaseSender):
    def send_default(self, notice_way, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        蓝鲸信息流通知发送
        :param notice_receivers:
        :param action_plugin:
        :return:
        """
        notice_params = {
            "notice_group_id_list": notice_receivers,
            "msg_type": self.msg_type,
            "msg_content": self.content,
        }

        logger.info("send.bkchat_{}({}): image md5 is {}".format(notice_way, ",".join(notice_receivers), self.content))

        api_result = api.bkchat.send_notice_group_msg(**notice_params)
        return self.handle_api_result(api_result, notice_receivers)

    def send_mail(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        通过 bkchat 发送邮件通知
        :return: {
            "1": {"result": true, "message": "OK"},
            "2": {"result": false, "message": "发送失败"}
        }
        :rtype: dict
        """
        msg_params = {
            "title": self.title,
            "content": self.content,
            "is_content_base64": True,
        }
        # 添加附件参数
        if self.context.get("attachments"):
            msg_params["attachments"] = self.context.get("attachments")
        elif self.context.get("alarm") and action_plugin == ActionPluginType.NOTICE:
            msg_params["attachments"] = self.context["alarm"].attachments

        logger.info("send.bkchat_mail({}): \ntitle: {}".format(",".join(notice_receivers), self.title))

        notice_params = {"notice_group_id_list": notice_receivers, "msg_type": self.msg_type, "msg_param": msg_params}
        api_result = api.bkchat.send_notice_group_msg(**notice_params)
        return self.handle_api_result(api_result, notice_receivers)

    def send_wxwork_bot(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        """
        发送企业微信机器人通知
        """
        alarm = self.context.get("alarm")
        msg_param = {"content": self.content}
        notice_params = {"notice_group_id_list": notice_receivers, "msg_type": self.msg_type, "msg_param": msg_param}
        api_result = api.bkchat.send_notice_group_msg(**notice_params)
        logger.info("send.bkchat_wxwork_bot({}): \ncontent: {}".format(",".join(notice_receivers), self.content))
        image = alarm.chart_image if alarm else None
        if not image:
            # 没有图片的，根据图片的内容发送结果解析
            return self.handle_api_result(api_result, notice_receivers)

        md5 = hashlib.md5(base64.decodebytes(image.encode(encoding="UTF-8"))).hexdigest()
        logger.info("send.bkchat_wxwork_bot_image({}): image md5 is {}".format(",".join(notice_receivers), md5))
        notice_params = {
            "notice_group_id_list": notice_receivers,
            "msg_type": "image",
            "msg_param": {"base64": image, "md5": md5},
        }
        api_result = api.bkchat.send_notice_group_msg(**notice_params)
        # 有图片需要发送的，以发送出图片的结果为准
        return self.handle_api_result(api_result, notice_receivers)

    def send_mini_program(self, notice_receivers, action_plugin=ActionPluginType.NOTICE):
        alarm = self.context.get("alarm")
        if action_plugin != ActionPluginType.NOTICE or (alarm and not alarm.is_abnormal):
            # 仅支持异常告警的通知推送， 非异常类的告警，直接忽略
            return {
                notice_receiver: {"message": _("微信公众号仅支持告警异常通知推送"), "result": False}
                for notice_receiver in notice_receivers
            }

        msg_param = {
            "keyword1": {
                "value": f"{_(alarm.level_name)}({alarm.id})",
                "color": "#7092ed",
            },
            "keyword2": {"value": alarm.description, "color": "#173177"},
            "keyword3": {"value": alarm.begin_time.strftime(settings.DATETIME_FORMAT), "color": "#7092ed"},
        }

        notice_params = {"notice_group_id_list": notice_receivers, "msg_type": "mini", "msg_param": msg_param}
        api_result = api.bkchat.send_notice_group_msg(**notice_params)
        return self.handle_api_result(api_result, notice_receivers)
