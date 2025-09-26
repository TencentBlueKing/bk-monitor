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
import datetime
import logging
from collections import defaultdict

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.core.cache.mail_report import MailReportCacheManager
from alarm_backends.service.report.render.dashboard import (
    RenderDashboardConfig,
    generate_dashboard_url,
    render_dashboard_panel,
)
from alarm_backends.service.report.tasks import render_mails
from bkmonitor.browser import get_or_create_eventloop
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models import ReportContents, ReportItems
from bkmonitor.utils.grafana import fetch_panel_title_ids
from bkmonitor.utils.send import Sender
from constants.report import GRAPH_ID_REGEX, LOGO, BuildInBizType, StaffChoice
from core.drf_resource import api
from core.drf_resource.exceptions import CustomException

logger = logging.getLogger("bkmonitor.cron_report")


def split_graph_id(graph_id: str) -> tuple[str, str, str]:
    """
    分割图表ID
    分为三段，由减号分隔
    第一段是逗号分隔的业务ID，或是内置业务类型。业务ID是数字可以是负数，内置业务类型是非数字字符串
    第二段是仪表盘UID，可能包含减号
    第三段是图表ID，图表ID应该是数字，有一种特殊情况是*，表示整个仪表盘
    """
    if not graph_id:
        return "", "", ""

    result = GRAPH_ID_REGEX.match(graph_id)
    if not result:
        return "", "", ""

    return result.group(1, 4, 5)


def chunk_list(items: list, chunk_size: int):
    """
    对数组进行指定长度的分页
    :param items: 带分页数组
    :param chunk_size: 指定每组长度
    :return: 分页后的数组
    """
    groups = [[]]
    j_index = 0
    for index, value in enumerate(items):
        if index != 0 and index % chunk_size == 0:
            groups.append([])
            j_index += 1
        groups[j_index].append(value)
    return groups


async def start_tasks(elements):
    """
    启动浏览器并执行截图任务
    :param elements: panel信息
    {
        "bk_biz_id": 2,
        "dashboard_uid": "xxx",
        "panel_id": "xxx",
        "image_size":{
            "width": width,
            "height": height
        },
        "variables": {"bk_biz_id": ["1", "2", "3"]},
        "start_time": 1612766359450,
        "end_time": 1612766359450,
        "with_panel_title": False,
    }
    :return: [(element, err_msg)]
    """
    result = []
    for element in elements:
        err_msg = None
        config = RenderDashboardConfig(
            bk_tenant_id=element["bk_tenant_id"],
            bk_biz_id=element["bk_biz_id"],
            dashboard_uid=element["dashboard_uid"],
            panel_id=element["panel_id"],
            with_panel_title=element["with_panel_title"],
            width=element["width"],
            height=element["height"],
            scale=element["scale"],
            variables=element["variables"],
            start_time=element["start_time"] // 1000,
            end_time=element["end_time"] // 1000,
        )
        try:
            img = await render_dashboard_panel(config)
        except Exception as e:
            err_msg = {"tag": element["tag"], "exception_msg": str(e)}
            continue

        element["base64"] = base64.b64encode(img).decode("utf-8")
        element["url"] = generate_dashboard_url(config, external=True)
        logger.info(f"fetch_images_by_puppeteer: render img length({len(img)})")

        result.append((element, err_msg))

    return result


def screenshot_by_uid_panel_id(bk_tenant_id, graph_info, need_title=False):
    """
    根据所需图表信息进行截图
    :param graph_info: 图表信息
    [{
        "bk_biz_id": 2,
        "uid": uid,
        "panel_id": panel_id,
        "image_size":{
            "width": width,
            "height": height
        },
        "var_bk_biz_ids": ["2", "3", "4"],
        "from_time": 1612766359450,
        "to_time": 1612766359450,
        "is_superuser": False
    }]
    :return: {bk_biz_id-uid-panel_id: {base64: base64, url: url}}
    """

    elements = []
    for graph in graph_info:
        element = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": graph["bk_biz_id"],
            "dashboard_uid": graph["uid"],
            "panel_id": graph["panel_id"] if graph["panel_id"] != "*" else None,
            "start_time": graph.get("from_time", ""),
            "end_time": graph.get("to_time", ""),
            "variables": graph.get("variables", {}),
            "with_panel_title": need_title,
            "width": graph["image_size"]["width"],
            "height": graph["image_size"]["height"],
            "scale": graph.get("image_size", {}).get("deviceScaleFactor", 2),
            "tag": graph["tag"],
        }
        elements.append(element)

    # 异步启动任务, 生成结果
    logger.info("[mail_report] start asyncio tasks.")
    loop = get_or_create_eventloop()
    result = loop.run_until_complete(start_tasks(elements))

    graph_filename_maps = {
        graph["tag"]: {"base64": graph["base64"], "url": graph["url"]}
        for graph in [item[0] for item in result]
        if graph.get("base64")
    }

    # 处理错误信息
    error_messages = {}
    for item in result:
        tag = item[0]["tag"]
        if item[1]:
            error_messages[tag] = item[1]

    # 返回图表信息和错误信息
    return graph_filename_maps, error_messages


class ReportHandler:
    """
    报表处理器
    """

    def __init__(self, bk_tenant_id: str, item_id=None):
        self.image_size_mapper = {
            1: {"width": 800, "height": 270, "deviceScaleFactor": 2},
            2: {"width": 620, "height": 300, "deviceScaleFactor": 2},
        }
        self.item_id = item_id
        self.bk_tenant_id = bk_tenant_id

    def fetch_receivers(self, item_receivers: list[dict] | None = None) -> list[str]:
        """
        获取所有需要接收邮件的人
        :return: 接收邮件的名单
        """
        receivers = []
        if not item_receivers:
            item_receivers = ReportItems.objects.get(pk=self.item_id, bk_tenant_id=self.bk_tenant_id).receivers
        groups_data = api.monitor.group_list()
        # 先解析组，再解析人，去掉is_enabled=False的人员
        # 只有开启了订阅的人才需要接收邮件
        for receiver in item_receivers:
            if receiver["is_enabled"] and receiver["type"] == StaffChoice.group:
                for group in groups_data:
                    if receiver.get("id") == group["id"]:
                        receivers.extend(group["children"])
        for receiver in item_receivers:
            if receiver["type"] == StaffChoice.user and receiver.get("id"):
                if receiver["is_enabled"]:
                    receivers.append(receiver["id"])
                elif receiver["id"] in receivers and not receiver["is_enabled"]:
                    # 如果 is_enabled=False 删除该接收者
                    receivers.remove(receiver["id"])
        receivers = list(set(receivers))
        if "admin" in receivers:
            receivers.remove("admin")
        if "system" in receivers:
            receivers.remove("system")
        return receivers

    def fetch_images_time(self, frequency):
        """
        解析frequency成起始时间和结束时间
        :param frequency: 频率
        :return: 起始时间和结束时间
        """
        now_time = datetime.datetime.now()
        # 如果没有频率参数，默认取最近一天的数据
        if not frequency:
            from_time = now_time + datetime.timedelta(hours=-24)
            return int(from_time.timestamp() * 1000), int(now_time.timestamp() * 1000), from_time, now_time
        # 如果存在用户自定义的数据范围，取用户自定义的数据范围
        if frequency.get("data_range"):
            time_level = frequency["data_range"]["time_level"]
            number = frequency["data_range"]["number"]
            kwargs = {time_level: -int(number)}
            from_time = now_time + datetime.timedelta(**kwargs)
        # 如果用户没有自定义的数据范围，取发送频率对应的数据范围
        else:
            if frequency["type"] == 3:
                from_time = now_time + datetime.timedelta(hours=-24 * 7)
            elif frequency["type"] == 4:
                from_time = now_time + datetime.timedelta(hours=-24 * 30)
            elif frequency["type"] == 5:
                now_time = datetime.datetime.strptime(now_time.strftime("%Y-%m-%d %H:%M:00"), "%Y-%m-%d %H:%M:%S")
                from_time = now_time - datetime.timedelta(minutes=frequency["hour"] * 60)
            else:
                from_time = now_time + datetime.timedelta(hours=-24)
        return int(from_time.timestamp() * 1000), int(now_time.timestamp() * 1000), from_time, now_time

    def parse_graph_info(self, graph_info, is_superuser, user_bizs, receivers):
        """
        解析业务列表
        :param graph_info: ["all-uid-panel_id"] / ["2,3,4-uid-penel_id"]
        :param is_superuser: 超管
        :param user_bizs: 用户有权限的业务列表
        :return: bk_biz_id, var_bk_biz_ids
        """

        def handle_superuser(user_bizs):
            """
            处理超管权限和有权限的业务
            :param user_bizs: 用户的业务列表
            :return: var_bk_biz_ids
            """
            if is_superuser:
                # 如果是超管，默认取全部业务
                var_bk_biz_ids = ["All"]
            else:
                # 否则只取用户对应业务权限的前20个
                var_bk_biz_ids = list(user_bizs)[:20]
                if not var_bk_biz_ids:
                    var_bk_biz_ids = ["none"]
            return var_bk_biz_ids

        var_bk_biz_ids = graph_info[0].split(",")
        setting_notify_group_data = MailReportCacheManager().fetch_groups_and_user_bizs()

        if len(var_bk_biz_ids) > 1:
            # 如果是多选业务的内置指标
            bk_biz_id = int(settings.MAIL_REPORT_BIZ)
        elif BuildInBizType.ALL in var_bk_biz_ids:
            # 内置指标-有权限的业务
            bk_biz_id = int(settings.MAIL_REPORT_BIZ)
            var_bk_biz_ids = handle_superuser(user_bizs)
        elif BuildInBizType.SETTINGS in var_bk_biz_ids:
            # 内置指标-配置管理员组
            bk_biz_id = int(settings.MAIL_REPORT_BIZ)
            var_bk_biz_ids = handle_superuser(
                setting_notify_group_data["controller_group"]["users_biz"].get(receivers[0], [])
            )
        elif BuildInBizType.NOTIFY in var_bk_biz_ids:
            # 内置指标-告警接收组
            bk_biz_id = int(settings.MAIL_REPORT_BIZ)
            var_bk_biz_ids = handle_superuser(
                setting_notify_group_data["alert_group"]["users_biz"].get(receivers[0], [])
            )
        else:
            # 普通情况，直接走原来的逻辑即可
            bk_biz_id = graph_info[0]
        return bk_biz_id, var_bk_biz_ids

    def render_images_to_html(
        self,
        bk_tenant_id,
        mail_title,
        contents,
        user_bizs,
        receivers,
        frequency=None,
        is_superuser=False,
        is_link_enabled=True,
        channel_name=ReportItems.Channel.USER,
    ):
        """
        将图像渲染到HTML中
        :param mail_title: 邮件标题
        :param contents: 发送内容
        :param frequency: 发送频率
        :return: True/False
        """
        total_graphs = []
        from_time_stamp, to_time_stamp, from_time, to_time = self.fetch_images_time(frequency)
        for content in contents:
            graphs = content["graphs"]
            for graph in graphs:
                graph_info = split_graph_id(graph)
                bk_biz_id, var_bk_biz_ids = self.parse_graph_info(graph_info, is_superuser, user_bizs, receivers)

                variables = {}
                if graph_info[2] != "*":
                    variables = {"bk_biz_id": var_bk_biz_ids}

                # 获取默认宽度高度
                if graph_info[2] == "*":
                    default_width = 1600
                    default_height = None
                else:
                    default_width = self.image_size_mapper.get(content["row_pictures_num"], {}).get("width", 620)
                    default_height = self.image_size_mapper.get(content["row_pictures_num"], {}).get("height", 300)

                total_graphs.append(
                    {
                        "bk_biz_id": bk_biz_id,
                        "uid": graph_info[1],
                        "panel_id": graph_info[2],
                        "image_size": {
                            "width": content["width"] or default_width,
                            "height": content["height"] or default_height,
                            "deviceScaleFactor": 2,
                        },
                        "variables": variables,
                        "tag": graph,
                        "from_time": from_time_stamp,
                        "to_time": to_time_stamp,
                    }
                )

        # 截图
        logger.info(f"[mail_report] prepare for screenshot {mail_title}...")
        images_files, err_msg = screenshot_by_uid_panel_id(
            bk_tenant_id, total_graphs, need_title=bool(channel_name == ReportItems.Channel.WXBOT)
        )
        logger.info(f"[mail_report] got screenshot {mail_title}...")

        # 渲染邮件模板
        render_args = {}
        render_args["is_link_enabled"] = is_link_enabled
        # 是否是外部邮件
        render_args["external_email"] = bool(channel_name == ReportItems.Channel.EMAIL)
        render_args["sensitive_message"] = _("请遵守公司规范，切勿泄露敏感信息，后果自负!")
        render_args["redirect_url"] = settings.MAIL_REPORT_URL if is_link_enabled else ""
        render_args["mail_title"] = mail_title

        # 邮件范围
        render_args["from_time"] = from_time.strftime("%Y-%m-%d %H:%M:%S")
        render_args["to_time"] = to_time.strftime("%Y-%m-%d %H:%M:%S")

        # 邮件标题后补
        render_args["mail_title_time"] = f"({from_time.strftime('%Y-%m-%d')} ~ {to_time.strftime('%Y-%m-%d')})"
        render_args["time_range"] = f"({render_args['from_time']} ~ {render_args['to_time']})"

        render_args["contents"] = []
        render_args["attachments"] = [
            {
                "filename": "__INLINE__logo.png",
                "content_id": "<___INLINE__logo.png>",
                "disposition": "inline",
                "type": "png",
                "content": LOGO,
            }
        ]

        # 记录图表标题的中间变量
        panel_names: dict[tuple[int, str], dict[str, str]] = {}

        for content in contents:
            graphs = []
            for graph in content["graphs"]:
                graph_biz_id, graph_uid, graph_panel_id = split_graph_id(graph)
                var_bk_biz_ids = graph_biz_id.split(",")
                if len(var_bk_biz_ids) > 1:
                    source = ",".join(var_bk_biz_ids)
                elif BuildInBizType.ALL in var_bk_biz_ids:
                    source = _("有权限的业务")
                elif BuildInBizType.NOTIFY in var_bk_biz_ids:
                    source = _("告警接收业务")
                elif BuildInBizType.SETTINGS in var_bk_biz_ids:
                    source = _("配置管理业务")
                else:
                    source = graph_biz_id
                if images_files.get(graph):
                    render_args["attachments"].append(
                        {
                            "filename": f"__INLINE__{graph}.jpeg",
                            "content_id": f"<__INLINE__{graph}.jpeg>",
                            "disposition": "inline",
                            "type": "jpeg",
                            "content": images_files[graph].get("base64"),
                        }
                    )
                image_url = images_files.get(graph, {}).get("url", "")

                # 获取实际业务ID
                if len(var_bk_biz_ids) > 1:
                    # 说明是内置图表，只取订阅报表默认业务
                    bk_biz_id = int(settings.MAIL_REPORT_BIZ)
                else:
                    try:
                        bk_biz_id = int(graph_biz_id)
                    except ValueError:
                        # 业务id不是数字，说明是内置业务，只取订阅报表默认业务
                        bk_biz_id = int(settings.MAIL_REPORT_BIZ)

                # 获取图表标题
                if (bk_biz_id, graph_uid) not in panel_names:
                    panel_names[(bk_biz_id, graph_uid)] = {}
                    for panel in fetch_panel_title_ids(bk_biz_id, graph_uid):
                        panel_names[(bk_biz_id, graph_uid)][str(panel["id"])] = panel["title"]
                panel_name = panel_names[(bk_biz_id, graph_uid)].get(graph_panel_id, "")

                graph_url = ""
                if is_link_enabled and settings.REPORT_DASHBOARD_UID not in image_url:
                    graph_url = image_url
                graphs.append(
                    {
                        "graph_tag": graph,
                        "url": graph_url,
                        "cid_tag": f"{graph}.jpeg",
                        "title": panel_name,
                        "source": source,
                        "content": images_files.get(graph, {}).get("base64"),
                    }
                )

            # 根据每行几幅图填充为 [[1],[2]] 或者 [[1,2], ...]等
            render_grphs = chunk_list(graphs, content["row_pictures_num"])

            render_args["contents"].append(
                {
                    "title": content["content_title"],
                    "content": content["content_details"],
                    "two_graph": True if content["row_pictures_num"] == 2 else False,
                    "graphs": render_grphs,
                    # 所有的图片列表
                    "origin_graphs": graphs,
                }
            )

        return render_args, err_msg

    def send_mails(self, render_args, receivers):
        """
        发送邮件
        :param render_args: 渲染参数
        :param receivers: 接收者
        :return: success or raise failed
        """
        try:
            content_template_path = "report/report_content.jinja"
            if render_args["contents"]:
                if "*" in render_args["contents"][0]["graphs"][0][0]["graph_tag"]:
                    content_template_path = "report/report_full.jinja"
            sender = Sender(
                title_template_path="report/report_title.jinja",
                content_template_path=content_template_path,
                context=render_args,
            )
            result = sender.send_mail(receivers)
            failed_list = []
            succeed_list = []
            for receiver in result:
                if not result[receiver]["result"]:
                    failed_list.append(result[receiver])
                else:
                    succeed_list.append(result[receiver])
            logger.info(
                f"[mail_report] send_mail finished: {render_args['mail_title']}, "
                f"failed_list({len(failed_list)}), succeed_list({len(succeed_list)})"
            )
            return "success" if not failed_list else failed_list
        except Exception as e:
            raise CustomException(f"[mail_report] send_mail failed: {e}")

    def send_wxbots(self, render_args, receivers):
        """
        发送企业微信
        :param render_args: 渲染参数
        :param receivers: 接收者
        :return: success or raise failed
        """
        try:
            if not settings.WXWORK_BOT_WEBHOOK_URL:
                return []

            success_count = 0
            failed = []
            is_link_enabled = render_args["is_link_enabled"]
            for content in render_args["contents"]:
                try:
                    content_template = _(
                        "**{title}{time_range}**\n**内容标题: **{sub_title}\n**内容说明: **{content}\n"
                        "**图片列表: **\n>{graph_names}\n"
                    )
                    graph_names = [
                        f"[{graph['title']}]({graph['url']})" if is_link_enabled else graph["title"]
                        for graph in content["origin_graphs"]
                    ]
                    send_content = content_template.format(
                        title=render_args["mail_title"],
                        time_range=render_args["time_range"],
                        sub_title=f"[{content['title']}]({render_args['redirect_url']})"
                        if is_link_enabled
                        else content["title"],
                        content=content["content"],
                        graph_names="\n>".join(graph_names),
                    )
                    response = Sender.send_wxwork_content("markdown", send_content, receivers)
                    if response["errcode"] != 0:
                        logger.error("[mail_report] send.wxwork_group content failed, {}".format(response["errmsg"]))
                        failed.append(response["errmsg"])
                except Exception as error:
                    logger.error(f"[mail_report] send.wxwork_group content failed, {error}")

                for graph in content["origin_graphs"]:
                    try:
                        response = Sender.send_wxwork_image(graph["content"], receivers)
                        if response["errcode"] != 0:
                            logger.error("[mail_report] send.wxwork_group image failed, {}".format(response["errmsg"]))
                            failed.append(response["errmsg"])
                        else:
                            success_count += 1
                    except Exception as error:
                        logger.error(f"[mail_report] send.wxwork_group image failed, {error}")

            logger.info(
                f"[mail_report] send_wxbot finished: {render_args['mail_title']},"
                f" succeed({success_count}), failed({len(failed)})"
            )
            return "success" if not failed else failed
        except Exception as e:
            raise CustomException(f"[mail_report] send_wxbot failed: {e}")

    def parse_users_group(self, bk_tenant_id: str, all_user_different_graph, receivers, superusers):
        """
        发送分组逻辑
        :param all_user_different_graph: 内置图表类型
        :param receivers: 用户列表
        :param superusers: 超管用户名单
        :return: 分组结果 {"ALL-bk_biz_id1,bk_biz_id2-SETTINGS-bk_biz_id1": {user1, user2}}
        """
        send_groups = defaultdict(set)
        setting_notify_group_data = api.monitor.get_setting_and_notify_group()
        for receiver in receivers:
            tag_string = ""  # 用户各类业务串的唯一标志
            if not receiver or len(receiver) == 32 or "webhook(" in receiver:
                # 过滤空接收人、机器人及webhook
                continue
            user_is_superuser = receiver in superusers
            if all_user_different_graph[BuildInBizType.ALL]:
                perm_client = Permission(username=receiver, bk_tenant_id=bk_tenant_id)
                perm_client.skip_check = False
                business_list = [
                    biz["bk_biz_id"] for biz in perm_client.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
                ]
                business_list.sort()
                biz_list = "superuser" if user_is_superuser else ",".join([str(biz) for biz in business_list])
                tag_string += f"{BuildInBizType.ALL}-{biz_list},"

            if all_user_different_graph[BuildInBizType.SETTINGS]:
                users_biz = [
                    int(biz)
                    for biz in list(setting_notify_group_data["controller_group"]["users_biz"].get(receiver, set()))
                ]
                users_biz.sort()
                biz_list = "superuser" if user_is_superuser else ",".join([str(biz) for biz in users_biz])
                tag_string += f"{BuildInBizType.SETTINGS}-{biz_list},"

            if all_user_different_graph[BuildInBizType.NOTIFY]:
                users_biz = [
                    int(biz) for biz in list(setting_notify_group_data["alert_group"]["users_biz"].get(receiver, set()))
                ]
                users_biz.sort()
                biz_list = "superuser" if user_is_superuser else ",".join([str(biz) for biz in users_biz])
                tag_string += f"{BuildInBizType.NOTIFY}-{biz_list}"

            send_groups[tag_string].add(receiver)
        return send_groups

    def process_and_render_mails(self):
        """
        渲染HTML并发送邮件入库
        """
        report_item = ReportItems.objects.get(bk_tenant_id=self.bk_tenant_id, pk=self.item_id)
        report_item_contents = list(
            ReportContents.objects.filter(bk_tenant_id=self.bk_tenant_id, report_item=self.item_id).values()
        )

        # 如果选择图表时选了'有权限的业务'
        all_user_different_graph = {
            BuildInBizType.ALL: False,
            BuildInBizType.NOTIFY: False,
            BuildInBizType.SETTINGS: False,
        }
        for content in report_item_contents:
            for graph in content["graphs"]:
                if BuildInBizType.ALL in graph:
                    all_user_different_graph[BuildInBizType.ALL] = True
                elif BuildInBizType.NOTIFY in graph:
                    all_user_different_graph[BuildInBizType.NOTIFY] = True
                elif BuildInBizType.SETTINGS in graph:
                    all_user_different_graph[BuildInBizType.SETTINGS] = True

        receivers = self.fetch_receivers(report_item.receivers)
        logger.info(
            f"[mail_report] mail_title: {report_item.mail_title};"
            f"receivers: {receivers};"
            f"channels: {report_item.channels};"
            f"different_graph: {all_user_different_graph}"
        )

        superusers = set(settings.MAIL_REPORT_ALL_BIZ_USERNAMES)
        if receivers:
            # 普通订阅如果有用户的时候，才做原有的用户逻辑处理
            if any(all_user_different_graph.values()):
                # 如果每个用户的图表都不一样
                # 获取用户的业务列表并分组渲染发送
                send_groups = self.parse_users_group(
                    bk_tenant_id=report_item.bk_tenant_id,
                    all_user_different_graph=all_user_different_graph,
                    receivers=receivers,
                    superusers=superusers,
                )
                logger.info(f"[mail_report] groups count: {len(send_groups)}")
                # 分组渲染发送
                for biz in send_groups:
                    render_mails.apply_async(
                        args=(
                            self,
                            report_item,
                            report_item_contents,
                            list(send_groups[biz]),
                            list(send_groups[biz])[0] in superusers,
                        )
                    )
            else:
                # 如果每个用户的图表都一样，一次性解决
                render_mails.apply_async(
                    args=(
                        self,
                        report_item,
                        report_item_contents,
                        receivers,
                        report_item.create_user in superusers,
                    )
                )

        for channel in report_item.channels:
            if channel.get("is_enabled"):
                # 所有的channel, 无法校验权限，只要满足条件，默认全部接口
                subscribers = [subscriber["username"] for subscriber in channel["subscribers"]]
                render_mails.apply_async(
                    args=(self, report_item, report_item_contents, subscribers, True),
                    kwargs={"channel_name": channel["channel_name"]},
                )
