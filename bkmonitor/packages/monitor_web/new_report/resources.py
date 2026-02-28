# -*- coding: utf-8 -*-
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
import logging
from collections import defaultdict
from urllib.parse import urljoin

import arrow
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from api.itsm.default import TokenVerifyResource
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.models import Report, ReportApplyRecord, ReportChannel, ReportSendRecord
from bkmonitor.report.serializers import (
    ChannelSerializer,
    ContentConfigSerializer,
    FrequencySerializer,
    ScenarioConfigSerializer,
)
from bkmonitor.report.utils import get_last_send_record_map
from bkmonitor.utils.itsm import ApprovalStatusEnum
from bkmonitor.utils.request import get_request, get_request_username
from bkmonitor.utils.user import get_local_username
from constants.new_report import (
    SUBSCRIPTION_VARIABLES_MAP,
    ApplyRecordQueryTypeEnum,
    ChannelEnum,
    ReportCreateTypeEnum,
    ReportQueryTypeEnum,
    SendModeEnum,
    SendStatusEnum,
    StaffEnum,
)
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.drf_resource.exceptions import CustomException

logger = logging.getLogger(__name__)
GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")


def get_send_status(send_records):
    if not send_records:
        return SendStatusEnum.NO_STATUS.value
    for record in send_records:
        if record["send_status"] == SendStatusEnum.FAILED.value:
            return SendStatusEnum.FAILED.value
        if record["send_status"] == SendStatusEnum.NO_STATUS.value:
            return SendStatusEnum.NO_STATUS.value
    return SendStatusEnum.SUCCESS.value


def get_send_mode(frequency):
    if frequency["type"] != 1:
        return SendModeEnum.PERIODIC.value
    return SendModeEnum.ONE_TIME.value


class GetReportListResource(Resource):
    """
    获取订阅列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id", required=True)
        search_key = serializers.CharField(required=False, label="搜索关键字", default="", allow_null=True, allow_blank=True)
        query_type = serializers.CharField(required=False, label="查询类型", default=ReportQueryTypeEnum.ALL.value)
        create_type = serializers.CharField(required=False, label="创建类型", default=ReportCreateTypeEnum.SELF.value)
        conditions = serializers.ListField(required=False, child=serializers.DictField(), default=[], label="查询条件")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        page_size = serializers.IntegerField(required=False, default=10, label="每页数量")
        order = serializers.CharField(required=False, label="排序", default="", allow_null=True, allow_blank=True)

    @staticmethod
    def check_permission(bk_biz_id, raise_exception=False):
        permission_obj = Permission()
        permission_obj.skip_check = False
        return permission_obj.is_allowed(
            ActionEnum.MANAGE_REPORT,
            [ResourceEnum.BUSINESS.create_instance(bk_biz_id)],
            raise_exception=raise_exception,
        )

    @staticmethod
    def filter_by_search_key(qs, search_key):
        origin_report_ids = set(qs.values_list("id", flat=True))
        # 搜索订阅名称
        filter_report_ids = set(qs.filter(name__contains=search_key).values_list("id", flat=True))
        # 搜索订阅人
        filter_report_ids |= set(
            ReportChannel.objects.filter(
                subscribers__contains={"id": search_key}, report_id__in=origin_report_ids
            ).values_list("report_id", flat=True)
        )

        return qs.filter(id__in=filter_report_ids)

    @staticmethod
    def filter_by_query_type(qs, query_type):
        invalid_report_ids = set()
        report_ids = set(qs.values_list("id", flat=True))
        username = get_request_username()
        # 已失效订阅列表
        for report in qs:
            if Report.is_invalid(report.end_time, report.frequency):
                invalid_report_ids.add(report.id)
        # 已取消订阅列表
        cancelled_report_ids = set(
            ReportChannel.objects.filter(
                subscribers__contains=[{"id": username, "type": StaffEnum.USER.value, "is_enabled": False}],
                report_id__in=report_ids,
            ).values_list("report_id", flat=True)
        )
        available_report_ids = report_ids - cancelled_report_ids - invalid_report_ids
        query_type_map = {
            ReportQueryTypeEnum.INVALID.value: invalid_report_ids,
            ReportQueryTypeEnum.CANCELLED.value: cancelled_report_ids,
            ReportQueryTypeEnum.AVAILABLE.value: available_report_ids,
            ReportQueryTypeEnum.ALL.value: report_ids,
        }
        return qs.filter(id__in=query_type_map[query_type])

    @staticmethod
    def filter_by_create_type(create_type: str, report_qs):
        if create_type == ReportCreateTypeEnum.SELF.value:
            # 当前用户的订阅
            report_qs = GetReportListResource.filter_by_user(report_qs)
        elif create_type == ReportCreateTypeEnum.MANAGER.value:
            # 管理员创建的订阅
            report_qs = report_qs.filter(is_manager_created=True)

        return report_qs

    @staticmethod
    def filter_by_user(report_qs):
        target_groups = []
        groups_data = {group_data["id"]: group_data["children"] for group_data in resource.report.group_list()}
        username = get_request_username()
        # 找到用户所属的组别
        for group, usernames in groups_data.items():
            if username in usernames:
                target_groups.append(group)

        # 针对用户所有所属组别生成Q
        total_Q_query = Q()
        Q_receivers_list = [
            Q(subscribers__contains=[{"id": group, "type": StaffEnum.GROUP.value}]) for group in target_groups
        ]

        Q_user_list = [
            Q(subscribers__contains={"id": username}),
        ]

        for Q_item in Q_receivers_list + Q_user_list:
            total_Q_query |= Q_item

        # 筛选出对应的items
        report_ids = list(report_qs.values_list("id", flat=True))
        filter_report_ids = list(
            ReportChannel.objects.filter(total_Q_query & Q(report_id__in=report_ids)).values_list(
                "report_id", flat=True
            )
        )
        return report_qs.filter(id__in=filter_report_ids)

    def get_filter_dict_by_conditions(self, conditions: list) -> (dict, dict):
        db_fields = ["send_mode", "scenario"]
        db_filter_dict = defaultdict(list)
        external_filter_dict = defaultdict(list)
        for condition in conditions:
            key = condition["key"].lower()
            value = condition["value"]
            if not isinstance(value, list):
                value = [value]
            if key in db_fields:
                query_key = f"{key}__in"
                db_filter_dict[query_key] = value
            else:
                external_filter_dict[key] = value
        return db_filter_dict, external_filter_dict

    def sort_reports(self, reports: list, order: str) -> list:
        reverse_order = False
        if order.startswith('-'):
            reverse_order = True
            order = order[1:]  # 去掉负号

        sorted_reports = sorted(reports, key=lambda x: arrow.get(x[order]).timestamp or 0, reverse=reverse_order)
        return sorted_reports

    def fill_external_info(self, reports, external_filter_dict, report_channels_map, last_send_record_map):
        new_reports = []
        current_user = get_request_username()
        for report in reports:
            report["channels"] = report_channels_map.get(report["id"], [])
            report["is_invalid"] = Report.is_invalid(report["end_time"], report["frequency"])
            report["is_self_subscribed"] = report["create_user"] == current_user
            record_info = last_send_record_map[report["id"]]
            if record_info:
                report["last_send_time"] = record_info["send_time"]
                report["send_status"] = get_send_status(record_info["records"])
            else:
                report["last_send_time"] = None
                report["send_status"] = SendStatusEnum.NO_STATUS.value

            # 过滤conditions中额外字段
            need_filter = False
            for key, value in external_filter_dict.items():
                if not report[key] in value:
                    need_filter = True
                    break
            if not need_filter:
                new_reports.append(report)

        return new_reports

    def perform_request(self, validated_request_data):
        report_qs = Report.objects.all().order_by("-update_time")

        # 根据角色过滤
        if validated_request_data["create_type"]:
            # 管理员视角需校验当前用户的订阅管理权限
            if validated_request_data["create_type"] == ReportCreateTypeEnum.MANAGER.value:
                self.check_permission(validated_request_data["bk_biz_id"], raise_exception=True)
            # 用户视角获取全业务下的订阅
            if validated_request_data["create_type"] != ReportCreateTypeEnum.SELF.value:
                report_qs = report_qs.filter(bk_biz_id=validated_request_data["bk_biz_id"])
            report_qs = self.filter_by_create_type(validated_request_data["create_type"], report_qs)

        # 根据搜索关键字过滤
        if validated_request_data["search_key"]:
            report_qs = self.filter_by_search_key(report_qs, validated_request_data["search_key"])

        # 根据查询类型过滤
        if validated_request_data["query_type"]:
            report_qs = self.filter_by_query_type(report_qs, validated_request_data["query_type"])

        # 获取订阅最后一次发送记录
        last_send_record_map = get_last_send_record_map(report_qs)

        db_filter_dict, external_filter_dict = self.get_filter_dict_by_conditions(validated_request_data["conditions"])

        if db_filter_dict:
            report_qs = report_qs.filter(Q(**db_filter_dict))

        reports = list(report_qs.values())
        report_ids = list(report_qs.values_list("id", flat=True))

        # 获取订阅渠道列表
        report_channels_map = defaultdict(list)
        for channel in list(ReportChannel.objects.filter(report_id__in=report_ids).values()):
            channel.pop("id")
            report_id = channel.pop("report_id")
            report_channels_map[report_id].append(channel)

        # 补充订阅信息
        reports = self.fill_external_info(reports, external_filter_dict, report_channels_map, last_send_record_map)

        # 分页
        total = len(reports)
        reports = reports[
            (validated_request_data["page"] - 1)
            * validated_request_data["page_size"] : validated_request_data["page"]
            * validated_request_data["page_size"]
        ]

        # 根据排序字段进行排序
        if validated_request_data["order"]:
            reports = self.sort_reports(reports, validated_request_data["order"])

        return {"report_list": reports, "total": total}


class GetReportResource(Resource):
    """
    获取订阅
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        report = Report.objects.values().get(id=validated_request_data["report_id"])
        report["channels"] = list(
            ReportChannel.objects.filter(report_id=report["id"]).values(
                "channel_name", "is_enabled", "subscribers", "send_text"
            )
        )
        report["is_self_subscribed"] = get_request().user.username == report["create_user"]
        return report


class CloneReportResource(Resource):
    """
    订阅报表克隆接口
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        report_qs = Report.objects.filter(id=validated_request_data["report_id"])
        if not report_qs.exists():
            raise CustomException(f"[report] report id: {validated_request_data['report_id']} not exists.")
        report = report_qs.values()[0]
        new_name = f'{report["name"]}_clone'

        i = 1
        while Report.objects.filter(name=new_name):
            new_name = f"{report['name']}_clone({i})"  # noqa
            i += 1

        report.pop("id")
        report["name"] = new_name
        report_channels = list(ReportChannel.objects.filter(report_id=validated_request_data["report_id"]).values())
        report_channels_to_create = []
        with transaction.atomic():
            new_report_obj = Report.objects.create(**report)
            for channel in report_channels:
                channel.pop("id")
                channel["report_id"] = new_report_obj.id
                report_channels_to_create.append(ReportChannel(**channel))
            ReportChannel.objects.bulk_create(report_channels_to_create)
        return new_report_obj.id


class CreateOrUpdateReportResource(Resource):
    """
    创建/编辑订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        scenario = serializers.CharField(label="订阅场景", required=True)
        subscriber_type = serializers.CharField(label="订阅人类型", required=True)
        channels = ChannelSerializer(many=True, required=True)
        frequency = FrequencySerializer(required=True)
        content_config = ContentConfigSerializer(required=True)
        scenario_config = ScenarioConfigSerializer(required=True)
        start_time = serializers.IntegerField(label="开始时间", required=False, default=None, allow_null=True)
        end_time = serializers.IntegerField(label="结束时间", required=False, default=None, allow_null=True)
        is_manager_created = serializers.BooleanField(required=False, default=False)
        is_enabled = serializers.BooleanField(required=False, default=True)

    def get_bk_biz_maintainer(self, bk_biz_id):
        """
        获取业务运维人员列表
        """
        business = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
        return getattr(business[0], "bk_biz_maintainer", []) if business else []

    def create_approval_ticket(self, params, bk_biz_maintainer):
        """
        创建ITSM审批单据并创建审批记录
        """
        subscribers = []
        for channel in params["channels"]:
            subscribers.extend(channel["subscribers"])
        subscriber_ids = [subscriber["id"] for subscriber in subscribers]
        ticket_data = {
            "creator": get_request_username() or get_local_username(),
            "fields": [
                {"key": "bk_biz_id", "value": params["bk_biz_id"]},
                {"key": "subscribers", "value": ", ".join(subscriber_ids)},
                {"key": "title", "value": "邮件订阅创建审批"},
                {"key": "report_name", "value": params["name"]},
                {"key": "scenario", "value": params["scenario"]},
                {"key": "approver", "value": ",".join(bk_biz_maintainer)},
            ],
            "service_id": settings.REPORT_APPROVAL_SERVICE_ID,
            "fast_approval": False,
            "meta": {"callback_url": urljoin(settings.BK_ITSM_CALLBACK_HOST, "/report_callback/")},
        }
        try:
            return api.itsm.create_fast_approval_ticket(ticket_data)
        except Exception as e:
            logger.error(f"审批创建异常: {e}")
            raise e

    def create_apply_reocrd(self, report, approval_data, bk_biz_maintainer):
        current_step = [{"tag": "DEFAULT", "name": "提交审批"}]
        record = ReportApplyRecord(
            report_id=report.id,
            bk_biz_id=report.bk_biz_id,
            approval_url=approval_data.get("ticket_url", ""),
            approval_sn=approval_data.get("sn", ""),
            approval_step=current_step,
            approvers=bk_biz_maintainer,
            status=ApprovalStatusEnum.RUNNING.value,
        )
        record.save()

    def perform_request(self, validated_request_data):
        params = copy.deepcopy(validated_request_data)
        is_manager_created = GetReportListResource.check_permission(validated_request_data["bk_biz_id"])
        params["is_manager_created"] = is_manager_created
        report_channels = params.pop("channels", [])
        params["send_mode"] = get_send_mode(params["frequency"])
        if params.get("id"):
            # 编辑
            try:
                report = Report.objects.get(id=params["id"])
            except Report.DoesNotExist:
                raise Exception("report_id: %s not found", params["id"])
            report.__dict__.update(params)
            report.save()
        else:
            # 创建
            # 判断是否需要审批
            need_apply = False
            approval_data = None
            bk_biz_maintainer = []
            if params["subscriber_type"] == "others" and not params["is_manager_created"]:
                # 创建订阅itsm审批单据
                need_apply = True
                bk_biz_maintainer = self.get_bk_biz_maintainer(params["bk_biz_id"])
                approval_data = self.create_approval_ticket(validated_request_data, bk_biz_maintainer)
            if need_apply:
                params["is_deleted"] = True
            report = Report(**params)
            report.save()
            # 创建审批记录
            if approval_data:
                self.create_apply_reocrd(report, approval_data, bk_biz_maintainer)
        with transaction.atomic():
            # 更新订阅渠道
            ReportChannel.objects.filter(report_id=report.id).delete()
            report_channels_to_create = []
            for channel in report_channels:
                channel["report_id"] = report.id
                report_channels_to_create.append(ReportChannel(**channel))
            ReportChannel.objects.bulk_create(report_channels_to_create)
        return report.id


class DeleteReportResource(Resource):
    """
    删除订阅
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        try:
            Report.objects.filter(id=validated_request_data["report_id"]).delete()
            ReportChannel.objects.filter(report_id=validated_request_data["report_id"]).delete()
            ReportApplyRecord.objects.filter(report_id=validated_request_data["report_id"]).delete()
            ReportSendRecord.objects.filter(report_id=validated_request_data["report_id"]).delete()
            return "success"
        except Exception as e:
            logger.exception(e)
            raise CustomException(e)


class SendReportResource(Resource):
    """
    发送订阅：测试发送/重新发送
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=False)
        bk_biz_id = serializers.IntegerField(required=False)
        scenario = serializers.CharField(label="订阅场景", required=False)
        channels = ChannelSerializer(many=True, required=False)
        frequency = FrequencySerializer(required=False)
        content_config = ContentConfigSerializer(required=False)
        scenario_config = ScenarioConfigSerializer(required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False, default=None, allow_null=True)
        end_time = serializers.IntegerField(label="结束时间", required=False, default=None, allow_null=True)
        is_manager_created = serializers.BooleanField(required=False, default=False)
        is_enabled = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data):
        try:
            api.monitor.send_report(**validated_request_data)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("send report error:{}".format(e))
        return "success"


class CancelOrResubscribeReportResource(Resource):
    """
    取消/重新订阅
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=True)
        is_enabled = serializers.BooleanField(required=True)

    def perform_request(self, validated_request_data):
        username = get_request().user.username
        is_enabled = validated_request_data["is_enabled"]
        try:
            channel = ReportChannel.objects.get(
                report_id=validated_request_data["report_id"], channel_name=ChannelEnum.USER.value
            )
        except ReportChannel.DoesNotExist:
            raise CustomException(
                f"[report] report id: " f"{validated_request_data['report_id']} user channel not exists."
            )

        for subscriber in channel.subscribers:
            if subscriber["id"] == username and subscriber["type"] == "user":
                subscriber["is_enabled"] = is_enabled
                channel.save()
                return "success"
        channel.subscribers.append({"id": username, "type": StaffEnum.USER.value, "is_enabled": is_enabled})
        channel.save()
        return "success"


class GetSendRecordsResource(Resource):
    """
    获取订阅发送记录
    """

    class RequestSerializer(serializers.Serializer):
        report_id = serializers.IntegerField(required=True)
        channel_name = serializers.CharField(required=False)

    def perform_request(self, validated_request_data):
        qs = ReportSendRecord.objects.filter(report_id=validated_request_data["report_id"]).exclude(
            send_status=SendStatusEnum.NO_STATUS.value
        )
        if validated_request_data.get("channel_name"):
            qs = qs.filter(channel_name=validated_request_data["channel_name"])
        return list(qs.order_by("-send_time").values())[:100]


class GetApplyRecordsResource(Resource):
    """
    获取订阅申请记录
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        query_type = serializers.CharField(required=False, label="查询类型", default=ApplyRecordQueryTypeEnum.USER.value)
        status = serializers.ChoiceField(required=False, label="审批状态", choices=ApprovalStatusEnum.get_choices())

    def perform_request(self, validated_request_data):
        qs = ReportApplyRecord.objects.all()
        if validated_request_data["query_type"] == ApplyRecordQueryTypeEnum.USER.value:
            # 根据用户获取
            username = get_request().user.username
            qs = qs.filter(create_user=username)
        else:
            # 根据业务获取
            qs = qs.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        if validated_request_data.get("status"):
            qs = qs.filter(status=validated_request_data["status"])
        qs = qs.order_by("-create_time")
        report_ids = qs.values_list("report_id", flat=True)
        apply_records = list(qs.values())
        report_infos = list(Report.origin_objects.filter(id__in=report_ids).values())

        # 获取订阅渠道列表
        report_channels_map = defaultdict(list)
        for channel in list(ReportChannel.objects.filter(report_id__in=report_ids).values()):
            channel.pop("id")
            report_id = channel.pop("report_id")
            report_channels_map[report_id].append(channel)

        id_to_report = {}
        for report_info in report_infos:
            id_to_report[report_info["id"]] = report_info
        for apply_record in apply_records:
            report_id = apply_record["report_id"]
            report_info = id_to_report[report_id]
            status_info = api.itsm.get_ticket_status(sn=apply_record["approval_sn"])
            if status_info["current_steps"]:
                apply_record["approval_step"] = status_info["current_steps"]
            apply_record["content_title"] = report_info["name"]
            apply_record["channels"] = report_channels_map.get(report_id, [])
            apply_record["scenario"] = report_info["scenario"]
            apply_record["frequency"] = report_info["frequency"]
            apply_record["send_mode"] = report_info["send_mode"]
        return apply_records


class GetVariablesResource(Resource):
    """
    根据订阅场景获取标题变量列表
    """

    class RequestSerializer(serializers.Serializer):
        scenario = serializers.CharField(label="订阅场景", required=True)

    def perform_request(self, validated_request_data):
        return SUBSCRIPTION_VARIABLES_MAP[validated_request_data["scenario"]]


class GetExistReportsResource(Resource):
    """
    根据条件获取已存在的订阅
    """

    class RequestSerializer(serializers.Serializer):
        scenario = serializers.CharField(label="订阅场景", required=True)
        query_type = serializers.CharField(required=False, label="查询类型")
        bk_biz_id = serializers.IntegerField(required=True)
        # CLUSTERING ONLY
        index_set_id = serializers.IntegerField(required=False)

    def perform_request(self, validated_request_data):
        qs = Report.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], scenario=validated_request_data["scenario"]
        )
        if validated_request_data.get("create_type"):
            qs = GetReportListResource.filter_by_create_type(validated_request_data["create_type"], qs)
        reports = list(qs.values())
        exist_report_list = []
        for report in reports:
            # 目前仅支持日志聚类模块检索条件
            if validated_request_data["index_set_id"]:
                if report["scenario_config"].get("index_set_id", None) == validated_request_data["index_set_id"]:
                    exist_report_list.append(report)

        return exist_report_list


class ReportCallbackResource(Resource):
    """
    获取审批结果
    """

    class RequestSerializer(serializers.Serializer):
        sn = serializers.CharField(required=True, label="工单号")
        title = serializers.CharField(required=True, label="工单标题")
        updated_by = serializers.CharField(required=True, label="更新人")
        approve_result = serializers.BooleanField(required=True, label="审批结果")
        token = serializers.CharField(required=False, label="校验token")

    def perform_request(self, validated_request_data):
        if validated_request_data.get("token"):
            verify_data = TokenVerifyResource().request({"token": validated_request_data["token"]})
            if not verify_data.get("is_passed", False):
                return {"message": "Error Token", "result": False}
        try:
            apply_record = ReportApplyRecord.objects.get(approval_sn=validated_request_data["sn"])
        except ReportApplyRecord.DoesNotExist:
            raise Exception("approval_sn: %s apply record not found", validated_request_data["sn"])
        # 审批
        if not validated_request_data["approve_result"]:
            apply_record.status = ApprovalStatusEnum.FAILED.value
            apply_record.save()
            return dict(result=True, message=f"approval failed by {validated_request_data['updated_by']}")
        # 审批通过则订阅生效
        apply_record.status = ApprovalStatusEnum.SUCCESS.value
        apply_record.save()
        report_id = apply_record.report_id
        Report.origin_objects.filter(id=report_id).update(is_deleted=False)
        return dict(result=True, message="approval success")
