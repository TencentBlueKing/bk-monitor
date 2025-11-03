"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import datetime
import logging
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.utils.translation import gettext as _
from rest_framework import serializers

from bkmonitor.action.serializers.report import (
    FrequencySerializer,
    ReceiverSerializer,
    ReportChannelSerializer,
    ReportContentSerializer,
    StaffSerializer,
)
from bkmonitor.models import Strategy
from bkmonitor.models.base import ReportContents, ReportItems, ReportStatus
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.grafana import fetch_biz_panels, fetch_panel_title_ids
from bkmonitor.utils.request import get_request, get_request_tenant_id
from constants.report import GRAPH_ID_REGEX, GroupId, StaffChoice
from core.drf_resource import CacheResource, api, resource
from core.drf_resource.base import Resource
from core.drf_resource.exceptions import CustomException

logger = logging.getLogger(__name__)
GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")


class ReportListResource(Resource):
    """
    已订阅列表接口
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False, allow_null=True)

    @staticmethod
    def get_request_user():
        return get_request().user

    def perform_request(self, params: dict):
        bk_tenant_id = get_request_tenant_id()
        # 提取用户有权限读取的订阅
        target_groups = []

        groups_data = {group_data["id"]: group_data["children"] for group_data in resource.report.group_list()}
        request_user = self.get_request_user()
        username = request_user.username
        is_superuser = request_user.is_superuser
        if params.get("id"):
            report_queryset = ReportItems.objects.filter(id=params["id"], bk_tenant_id=bk_tenant_id).order_by(
                "-update_time"
            )
        else:
            report_queryset = ReportItems.objects.filter(bk_tenant_id=bk_tenant_id).order_by("-update_time")

        if not is_superuser:
            # 找到用户所属的组别
            for group, usernames in groups_data.items():
                if username in usernames:
                    target_groups.append(group)

            # 针对用户所有所属组别生成Q
            total_Q_query = Q()
            Q_receivers_list = [
                Q(receivers__contains=[{"id": group, "type": StaffChoice.group}]) for group in target_groups
            ]

            Q_managers_list = [
                Q(managers__contains=[{"id": group, "type": StaffChoice.group}]) for group in target_groups
            ]

            Q_user_list = [
                Q(receivers__contains=[{"id": username, "type": StaffChoice.user, "is_enabled": True}]),
                Q(managers__contains=[{"id": username, "type": StaffChoice.user}]),
            ]

            for Q_item in Q_receivers_list + Q_managers_list + Q_user_list:
                total_Q_query |= Q_item

            # 筛选出对应的items
            report_queryset = report_queryset.filter(total_Q_query)

        result = list(report_queryset.values())
        # 补充用户最后一次发送时间
        # 取最近1000条发送状态数据
        user_last_send_time = defaultdict(dict)
        for status in ReportStatus.objects.filter(bk_tenant_id=bk_tenant_id).order_by("-create_time").values()[:1000]:
            for receiver in status["details"]["receivers"]:
                if receiver not in user_last_send_time[status["report_item"]]:
                    user_last_send_time[status["report_item"]][receiver] = status["create_time"]

        for report in result:
            for receiver in report["receivers"]:
                if user_last_send_time.get(report["id"], {}).get(receiver["id"]):
                    receiver["last_send_time"] = user_last_send_time[report["id"]].get(receiver["id"])
            report["channels"] = report["channels"] or []
            report["channels"].append(
                {"channel_name": "user", "is_enabled": bool(report["receivers"]), "subscribers": report["receivers"]}
            )

        return result


class ReportContentResource(Resource):
    """
    订阅内容获取接口
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=True)

    def perform_request(self, params: dict):
        bk_tenant_id = get_request_tenant_id()
        username = get_request().user.username
        is_superuser = get_request().user.is_superuser

        report_item = ReportItems.objects.get(id=params["report_item_id"], bk_tenant_id=bk_tenant_id)
        # 检查用户是否有权限
        if not is_superuser:
            managers = report_item.format_managers
            if username not in managers:
                raise PermissionError(_("您无权限访问此页面"))

        ret_data = model_to_dict(report_item)
        ret_data["contents"] = list(
            ReportContents.objects.filter(report_item=params["report_item_id"], bk_tenant_id=bk_tenant_id).values()
        )

        # 补充图表名称
        panel_names: dict[tuple[int, str], dict[str, str]] = {}
        for content in ret_data["contents"]:
            content["graph_name"] = []
            for graph in content["graphs"]:
                # 解析图表id
                match = GRAPH_ID_REGEX.match(graph)
                if not match:
                    continue
                bk_biz_ids, dashboard_uid, panel_id = match.group(1, 4, 5)
                bk_biz_ids = bk_biz_ids.split(",")
                # 获取实际业务id
                if len(bk_biz_ids) > 1:
                    # 说明是内置图表，只取订阅报表默认业务
                    bk_biz_id = int(settings.MAIL_REPORT_BIZ)
                else:
                    try:
                        bk_biz_id = int(bk_biz_ids[0])
                    except ValueError:
                        # 业务id不是数字，说明是内置业务，只取订阅报表默认业务
                        bk_biz_id = int(settings.MAIL_REPORT_BIZ)

                # 如果没有获取过此仪表盘的图表名称，则获取
                if (bk_biz_id, dashboard_uid) not in panel_names:
                    panel_names[(bk_biz_id, dashboard_uid)] = {}
                    for panel in fetch_panel_title_ids(bk_biz_id, dashboard_uid):
                        panel_names[(bk_biz_id, dashboard_uid)][str(panel["id"])] = panel["title"]
                dashboard_panel_names = panel_names[(bk_biz_id, dashboard_uid)]

                # 补充图表名称
                content["graph_name"].append({"graph_id": graph, "graph_name": dashboard_panel_names.get(panel_id)})
        return ret_data


class ReportCloneResource(Resource):
    """
    订阅报表克隆接口
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=True)

    def perform_request(self, params: dict):
        bk_tenant_id = get_request_tenant_id()
        report_item = ReportItems.objects.filter(id=params["report_item_id"], bk_tenant_id=bk_tenant_id).values()
        if not report_item:
            raise CustomException(f"[mail_report] item id: {params['report_item_id']} not exists.")
        report_item = report_item[0]
        new_mail_title = f"{report_item['mail_title']}_copy"

        # 判断重名
        i = 1
        while ReportItems.objects.filter(mail_title=new_mail_title, bk_tenant_id=bk_tenant_id):
            new_mail_title = f"{new_mail_title}({i})"  # noqa
            i += 1

        report_item.pop("id")
        report_item["mail_title"] = new_mail_title
        # 从report_item中移除bk_tenant_id字段，避免解包的时候无法覆盖bk_tenant_id字段导致报错
        report_item.pop("bk_tenant_id", None)
        report_content_to_create = []
        report_contents = list(
            ReportContents.objects.filter(report_item=params["report_item_id"], bk_tenant_id=bk_tenant_id).values()
        )

        with transaction.atomic():
            created_item = ReportItems.objects.create(**report_item, bk_tenant_id=bk_tenant_id)
            for content in report_contents:
                content.pop("id")
                content["report_item"] = created_item.id
                content["bk_tenant_id"] = bk_tenant_id
                report_content_to_create.append(ReportContents(**content))
            ReportContents.objects.bulk_create(report_content_to_create)
        return True


class StatusListResource(Resource):
    """
    已发送列表接口
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False, allow_null=True)

    def perform_request(self, params: dict):
        bk_tenant_id = get_request_tenant_id()
        # 提取用户有权限读取的订阅
        if params.get("id"):
            report_items = resource.report.report_list(id=params["id"])
        else:
            report_items = resource.report.report_list()

        items = {item["id"]: item for item in report_items}
        # 当前日期格式
        cur_date = datetime.datetime.now().date()
        # 近2周
        two_weeks_ago = cur_date - datetime.timedelta(weeks=2)
        status_queryset = ReportStatus.objects.filter(
            report_item__in=list(items.keys()), create_time__gte=two_weeks_ago, bk_tenant_id=bk_tenant_id
        ).order_by("-create_time")
        statuses = status_queryset.values()
        for status in statuses:
            status.update({"receivers": status["details"].get("receivers", [])})
            status.update({"username": items.get(status["report_item"]).get("create_user")})
        return list(statuses)


class GraphsListByBizResource(Resource):
    """
    每个业务下的图表列表接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        user_bizs = resource.space.get_bk_biz_ids_by_user(get_request().user)
        if validated_request_data["bk_biz_id"] not in user_bizs:
            raise PermissionError(_("您无权限访问此业务的图表列表接口"))
        return {validated_request_data["bk_biz_id"]: fetch_biz_panels(validated_request_data["bk_biz_id"])}


class GetPanelsByDashboardResource(Resource):
    """
    获取仪表盘下的图表列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        uid = serializers.CharField(required=True)

    def perform_request(self, params: dict):
        return fetch_panel_title_ids(params["bk_biz_id"], params["uid"])


class BuildInMetricResource(Resource):
    """
    内置指标
    """

    def perform_request(self, validated_request_data):
        # 获取运营数据内置仪表盘的数据
        dashboard_data = []
        report_dashboards = fetch_biz_panels(int(settings.MAIL_REPORT_BIZ))
        for dashboard in report_dashboards:
            if settings.REPORT_DASHBOARD_UID == dashboard["uid"]:
                dashboard_data.append(dashboard)
        return dashboard_data


class ReportCreateOrUpdateResource(Resource):
    """
    创建/编辑订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=False)
        mail_title = serializers.CharField(required=False, max_length=512)
        receivers = ReceiverSerializer(many=True, required=False)
        channels = ReportChannelSerializer(many=True, required=False)
        managers = StaffSerializer(many=True, required=False)
        frequency = FrequencySerializer(required=False)
        report_contents = ReportContentSerializer(many=True, required=False)
        is_enabled = serializers.BooleanField(required=False)
        # 是否发送链接，敏感原因，默认关闭
        is_link_enabled = serializers.BooleanField(required=False, default=True)

    def fetch_group_members(self, staff_list, staff_type):
        """
        获取组别内的所有人员，并充填回去
        :param staff_list: 人员列表
        :param staff_type: 人员类型, 可选：[manager, receiver]
        :return: 充填完组内人员的列表
        """
        group_list = {group_data["id"]: group_data["children"] for group_data in resource.report.group_list()}
        exists_groups = [staff["id"] for staff in staff_list if staff["type"] == StaffChoice.group]

        # 如果是已去除的组别里的人员，删除掉此数据
        staff_list = [staff for staff in staff_list if not staff.get("group") or staff["group"] in exists_groups]

        staff_list_members = [staff["id"] for staff in staff_list if staff["type"] == StaffChoice.user]
        new_staff_list = staff_list
        for staff in staff_list:
            # 只有组类型的数据才需要填充人员
            if not staff.get("type"):
                continue
            members = group_list.get(staff["id"], [])
            for member in members:
                if member in staff_list_members:
                    # 已存在相关用户记录，跳过
                    continue
                data = {"id": member, "name": member, "group": staff["id"], "type": StaffChoice.user}
                if staff_type == "receiver":
                    data["is_enabled"] = True
                new_staff_list.append(data)
        return new_staff_list

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        current_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if validated_request_data.get("report_item_id"):
            # 编辑则提取订阅项
            report_item = ReportItems.objects.filter(
                id=validated_request_data["report_item_id"], bk_tenant_id=bk_tenant_id
            )
            if not report_item:
                raise CustomException(_("此订阅不存在"))

            # 更新参数
            update_args = copy.deepcopy(validated_request_data)

            # 如果更改了接收者和管理者
            if validated_request_data.get("receivers"):
                receivers = self.fetch_group_members(validated_request_data["receivers"], "receiver")
                # 补充用户被添加进来的时间
                for receiver in receivers:
                    if "create_time" not in receiver:
                        receiver["create_time"] = current_time
                update_args["receivers"] = receivers

            if validated_request_data.get("managers"):
                update_args["managers"] = self.fetch_group_members(validated_request_data["managers"], "manager")

            update_args.pop("report_item_id")
            if validated_request_data.get("report_contents"):
                update_args.pop("report_contents")

            update_args["last_send_time"] = None
            report_item.update(**update_args)
            report_item = report_item.first()
        else:
            # 创建
            report_item = ReportItems(bk_tenant_id=bk_tenant_id)
            create_info = {"create_time": current_time, "last_send_time": ""}
            # 人员信息补充
            receivers = self.fetch_group_members(validated_request_data["receivers"], "receiver")
            for receiver in receivers:
                receiver.update(create_info)
            for channel in validated_request_data["channels"]:
                for subscribe in channel["subscribers"]:
                    subscribe.update(create_info)
            report_item.mail_title = validated_request_data["mail_title"]
            report_item.receivers = receivers
            report_item.managers = self.fetch_group_members(validated_request_data["managers"], "manager")
            report_item.frequency = validated_request_data["frequency"]
            report_item.channels = validated_request_data["channels"]
            if validated_request_data.get("is_enabled") is not None:
                report_item.is_enabled = validated_request_data["is_enabled"]
            report_item.is_link_enabled = validated_request_data["is_link_enabled"]
            report_item.save()
        with transaction.atomic():
            # 如果需要修改子内容
            if validated_request_data.get("report_contents"):
                ReportContents.objects.filter(report_item=report_item.id, bk_tenant_id=bk_tenant_id).delete()
                report_contents = []
                for content in validated_request_data["report_contents"]:
                    report_contents.append(
                        ReportContents(
                            report_item=report_item.id,
                            content_title=content["content_title"],
                            content_details=content["content_details"],
                            row_pictures_num=content["row_pictures_num"],
                            graphs=content["graphs"],
                            width=content["width"],
                            height=content["height"],
                            bk_tenant_id=bk_tenant_id,
                        )
                    )
                ReportContents.objects.bulk_create(report_contents)
        return "success"


class ReportDeleteResource(Resource):
    """
    删除订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=True)

    def perform_request(self, params: dict):
        bk_tenant_id = get_request_tenant_id()
        try:
            ReportItems.objects.filter(id=params["report_item_id"], bk_tenant_id=bk_tenant_id).delete()
            ReportContents.objects.filter(report_item=params["report_item_id"], bk_tenant_id=bk_tenant_id).delete()
            return "success"
        except Exception as e:
            logger.error(e)
            raise CustomException(e)


class ReportTestResource(Resource):
    """
    测试订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        mail_title = serializers.CharField(required=True, max_length=512)
        receivers = ReceiverSerializer(many=True)
        channels = ReportChannelSerializer(many=True, required=False)
        report_contents = ReportContentSerializer(many=True)
        frequency = FrequencySerializer(required=False)
        is_link_enabled = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data):
        validated_request_data["creator"] = str(get_request().user)
        return api.monitor.test_report_mail(**validated_request_data)


class GroupListResource(CacheResource):
    """
    订阅报表用户组列表接口
    """

    # 缓存类型
    cache_type = CacheType.BIZ

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False)

    def format_data(self, group_type, children):
        """
        格式化数据
        :param group_type: 组类型
        :param children: 组下的人员
        :return: 格式化后的数据
        """
        notify_groups = resource.cc.get_notify_roles()
        notify_groups[GroupId.bk_biz_controller] = _("配置管理人员")
        notify_groups[GroupId.bk_biz_notify_receiver] = _("告警接收人员")
        if "admin" in children:
            children.remove("admin")
        if "system" in children:
            children.remove("system")

        return {
            "id": group_type,
            "display_name": notify_groups[group_type],
            "logo": "",
            "type": "group",
            "children": list(filter(None, set(children))),
        }

    def fetch_strategy_bizs(self):
        """
        通过策略配置开关获取已接入的业务列表
        :return: biz_list: 已接入的业务列表
        """
        return list(set(Strategy.origin_objects.filter(is_enabled=True).values_list("bk_biz_id", flat=True)))

    def perform_request(self, validated_request_data):
        bk_biz_ids = self.fetch_strategy_bizs()
        if validated_request_data.get("bk_biz_id"):
            bk_biz_ids = [validated_request_data["bk_biz_id"]]
        all_business = api.cmdb.get_business(bk_biz_ids=bk_biz_ids)
        maintainers = []
        productors = []
        developers = []
        testers = []

        for biz in all_business:
            maintainers.extend(biz.bk_biz_maintainer)
            productors.extend(biz.bk_biz_productor)
            developers.extend(biz.bk_biz_developer)
            testers.extend(biz.bk_biz_tester)

        # 配置人员列表、告警接收人员列表
        setting_notify_group_data = api.monitor.get_setting_and_notify_group()

        result = [
            self.format_data(GroupId.bk_biz_maintainer, maintainers),
            self.format_data(GroupId.bk_biz_productor, productors),
            self.format_data(GroupId.bk_biz_tester, testers),
            self.format_data(GroupId.bk_biz_developer, developers),
            self.format_data(GroupId.bk_biz_controller, setting_notify_group_data["controller_group"]["users"]),
            self.format_data(GroupId.bk_biz_notify_receiver, setting_notify_group_data["alert_group"]["users"]),
        ]

        return result
