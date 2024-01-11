"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import hashlib
import logging

from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apm_web.models import Application, ProfileUploadRecord, UploadedFileStatus
from apm_web.profile.constants import (
    PROFILE_UPLOAD_RECORD_NEW_FILE_NAME,
    CallGraphResponseDataMode,
)
from apm_web.profile.converter import generate_profile_id
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.doris.converter import DorisConverter
from apm_web.profile.doris.querier import APIParams, APIType, Query
from apm_web.profile.file_handler import ProfilingFileHandler
from apm_web.profile.resources import QueryServicesDetailResource
from apm_web.profile.serializers import (
    ProfileListFileSerializer,
    ProfileQuerySerializer,
    ProfileUploadRecordSLZ,
    ProfileUploadSerializer,
)
from apm_web.tasks import profile_file_upload_and_parse
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource import api
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

logger = logging.getLogger("root")


class ProfileViewSet(ViewSet):
    """Profile viewSet"""

    INSTANCE_ID = "app_name"

    def get_permissions(self):
        # put auth here, but left empty for debugging
        if self.action in []:
            return [
                InstanceActionForDataPermission(
                    self.INSTANCE_ID,
                    [ActionEnum.VIEW_APM_APPLICATION],
                    ResourceEnum.APM_APPLICATION,
                    get_instance_id=Application.get_application_id_by_app_name,
                )
            ]
        return []

    @action(methods=["POST"], detail=False, url_path="upload")
    def upload(self, request: Request):
        """上传 profiling 文件"""
        uploaded = request.FILES.get("file")
        if not uploaded:
            raise ValueError(_("上传文件为空"))

        serializer = ProfileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        try:
            application = Application.objects.get(
                bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
            )
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}) 不存在").format(validated_data["app_name"]))

        data = uploaded.read()
        md5 = hashlib.md5(data).hexdigest()
        if ProfileUploadRecord.objects.filter(file_md5=md5).exists():
            raise ValueError(_("相同文件已上传"))

        # 上传文件到 bkrepo, 上传文件失败，不记录，不执行异步任务
        try:
            ProfilingFileHandler().bk_repo_storage.client.upload_fileobj(uploaded, key=uploaded.name)
        except Exception:
            logger.exception("failed to upload file to bkrepo")
            raise Exception(_("上传文件失败"))

        profile_id = generate_profile_id()

        # record it if everything is ok
        record = ProfileUploadRecord.objects.create(
            bk_biz_id=validated_data["bk_biz_id"],
            app_name=application.app_name,
            file_md5=md5,
            file_type=validated_data["file_type"],
            profile_id=profile_id,
            operator=request.user.username,
            origin_file_name=uploaded.name,
            file_size=uploaded.size,  # 单位Bytes
            file_name=PROFILE_UPLOAD_RECORD_NEW_FILE_NAME.format(timezone.now().strftime("%Y-%m-%d-%H-%M-%S")),
            status=UploadedFileStatus.UPLOADED,
            service_name=validated_data.get("service_name", "default"),
        )

        # 异步任务： 文件解析及存储
        profile_file_upload_and_parse.delay(
            uploaded.name,
            validated_data["file_type"],
            profile_id,
            validated_data["bk_biz_id"],
            application.app_name,
        )

        return Response(data=ProfileUploadRecordSLZ(record).data)

    @action(methods=["GET"], detail=False, url_path="list_profile_upload_records")
    def list_profile_upload_records(self, request: Request):
        serializer = ProfileListFileSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        filter_params = {}
        if validated_data.get("bk_biz_id"):
            filter_params["bk_biz_id"] = validated_data.get("bk_biz_id")
        if validated_data.get("app_name"):
            filter_params["app_name"] = validated_data.get("app_name")
        if validated_data.get("origin_file_name"):
            filter_params["origin_file_name"] = validated_data.get("origin_file_name")
        if validated_data.get("service_name "):
            filter_params["service_name"] = validated_data.get("service_name")
        queryset = ProfileUploadRecord.objects.filter(**filter_params)
        return Response(data=ProfileUploadRecordSLZ(queryset, many=True).data)

    @classmethod
    def build_extra_params(cls, profile_id: str, label: dict) -> dict:
        extra_params = {}
        if profile_id:
            extra_params["label_filter"] = {"profile_id": profile_id}
        if label and isinstance(extra_params.get("label_filter"), dict):
            extra_params["label_filter"].update(label)
        else:
            extra_params["label_filter"] = label
        return extra_params

    @classmethod
    def get_profile_data(
        cls, validated_data, app_name: str, start: int, end: int, application_info: dict
    ) -> DorisConverter:
        """
        获取 profile 数据
        """
        bk_biz_id = validated_data["bk_biz_id"]
        profile_type = validated_data["profile_type"]
        profile_id = validated_data.get("profile_id", "")
        filter_label = validated_data.get("filter_label", {})
        diff_profile_id = validated_data.get("diff_profile_id", "")
        diff_filter_label = validated_data.get("diff_filter_label", {})
        if profile_id or filter_label:
            extra_params = cls.build_extra_params(profile_id, filter_label)
        elif diff_profile_id or diff_filter_label:
            extra_params = cls.build_extra_params(diff_profile_id, diff_filter_label)
        else:
            extra_params = {}

        q = Query(
            api_type=APIType.QUERY_SAMPLE,
            api_params=APIParams(
                biz_id=bk_biz_id,
                app=app_name,
                type=profile_type,
                start=start,
                end=end,
                **extra_params,
            ),
            result_table_id=application_info["profiling_config"]["result_table_id"],
        )

        r = q.execute()

        if r is None:
            raise ValueError(_("未查询到有效数据"))
        c = DorisConverter()
        p = c.convert(r)
        if p is None:
            raise ValueError(_("无法转换 profiling 数据"))
        return c

    @action(methods=["POST"], detail=False, url_path="query")
    def query(self, request: Request):
        """查询 profiling 数据"""
        serializer = ProfileQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        bk_biz_id = validated_data["bk_biz_id"]
        app_name = validated_data["app_name"]
        try:
            application_id = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id).pk
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}) 不存在").format(app_name))

        try:
            application_info = api.apm_api.detail_application({"application_id": application_id})
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}) 不存在").format(application_id))

        if "app_name" not in application_info:
            raise ValueError(_("应用({}) 不存在").format(application_id))
        app_name = application_info["app_name"]
        if "profiling_config" not in application_info:
            raise ValueError(_("应用({}) 未开启性能分析").format(application_id))

        offset = validated_data["offset"]
        start = validated_data["start"]
        end = validated_data["end"]
        # 由于 doris 入库可能存在延迟，所以需要稍微加大查询时间范围
        # profile_id 对于数据有较强的过滤效果，不会引起数据量过大问题
        # doris 存储默认按自然天划分，默认查找从当天最早的数据开始

        # start & end all in microsecond, so we need to convert it to millisecond
        start = int(
            datetime.datetime.combine(
                datetime.datetime.fromtimestamp(start / (1000 * 1000)), datetime.time.min
            ).timestamp()
            * 1000
        )
        end = int(end / 1000 + offset * 1000)

        doris_converter = self.get_profile_data(
            validated_data=validated_data, app_name=app_name, start=start, end=end, application_info=application_info
        )
        diagram_types = validated_data["diagram_types"]
        if validated_data.get("is_compared"):
            diff_doris_converter = self.get_profile_data(
                validated_data=validated_data,
                app_name=app_name,
                start=start,
                end=end,
                application_info=application_info,
            )
            diff_diagram_dicts = (
                get_diagrammer(d_type).diff(doris_converter, diff_doris_converter) for d_type in diagram_types
            )
            return Response(data={k: v for diagram_dict in diff_diagram_dicts for k, v in diagram_dict.items()})

        options = {"sort": validated_data.get("sort"), "data_mode": CallGraphResponseDataMode.IMAGE_DATA_MODE}
        diagram_dicts = (get_diagrammer(d_type).draw(doris_converter, **options) for d_type in diagram_types)
        return Response(data={k: v for diagram_dict in diagram_dicts for k, v in diagram_dict.items()})


class QueryViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self):
        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute("GET", QueryServicesDetailResource, endpoint="services_detail"),
    ]
