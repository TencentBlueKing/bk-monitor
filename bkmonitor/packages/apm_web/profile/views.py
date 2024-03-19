"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import gzip
import hashlib
import itertools
import json
import logging
from typing import Optional, Tuple, Union

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apm_web.models import Application, ProfileUploadRecord, UploadedFileStatus
from apm_web.profile.constants import (
    BUILTIN_APP_NAME,
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_SERVICE_NAME,
    EXPORT_FORMAT_MAP,
    PROFILE_EXPORT_FILE_NAME,
    PROFILE_UPLOAD_RECORD_NEW_FILE_NAME,
    CallGraphResponseDataMode,
)
from apm_web.profile.converter import generate_profile_id
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.doris.converter import DorisConverter
from apm_web.profile.doris.querier import APIParams, APIType, Query
from apm_web.profile.file_handler import ProfilingFileHandler
from apm_web.profile.resources import (
    ListApplicationServicesResource,
    QueryProfileBarGraphResource,
    QueryServicesDetailResource,
)
from apm_web.profile.serializers import (
    ProfileListFileSerializer,
    ProfileQueryExportSerializer,
    ProfileQueryLabelsSerializer,
    ProfileQueryLabelValuesSerializer,
    ProfileQuerySerializer,
    ProfileUploadRecordSLZ,
    ProfileUploadSerializer,
)
from apm_web.tasks import profile_file_upload_and_parse
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission
from core.drf_resource import api
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

logger = logging.getLogger("root")


class ProfileBaseViewSet(ViewSet):
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


class ProfileUploadViewSet(ProfileBaseViewSet):
    @action(methods=["POST"], detail=False, url_path="upload")
    def upload(self, request: Request):
        """上传 profiling 文件"""
        uploaded = request.FILES.get("file")
        if not uploaded:
            raise ValueError(_("上传文件为空"))

        serializer = ProfileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        data = uploaded.read()
        md5 = hashlib.md5(data).hexdigest()
        exist_record = ProfileUploadRecord.objects.filter(bk_biz_id=validated_data["bk_biz_id"], file_md5=md5).first()
        if exist_record:
            raise ValueError(_(f"已上传过相同文件，名称：{exist_record.file_name}({exist_record.origin_file_name})"))

        # 上传文件到 bkrepo, 上传文件失败，不记录，不执行异步任务
        try:
            # 文件 key: {bk_biz_id}_{uploaded.name}
            key = f"{validated_data['bk_biz_id']}_{uploaded.name}"
            ProfilingFileHandler().bk_repo_storage.client.upload_fileobj(data, key=key)
        except Exception as e:
            logger.exception("failed to upload file to bkrepo")
            raise Exception(_("上传文件失败， 失败原因: {}").format(e))

        profile_id = generate_profile_id()
        app_name = validated_data.get("app_name", BUILTIN_APP_NAME)
        service_name = validated_data.get("service_name", app_name)

        # record it if everything is ok
        record = ProfileUploadRecord.objects.create(
            bk_biz_id=validated_data["bk_biz_id"],
            app_name=app_name,
            file_key=key,
            file_md5=md5,
            profile_id=profile_id,
            operator=request.user.username,
            origin_file_name=uploaded.name,
            file_size=uploaded.size,  # 单位Bytes
            file_name=PROFILE_UPLOAD_RECORD_NEW_FILE_NAME.format(timezone.now().strftime("%Y-%m-%d-%H-%M-%S")),
            status=UploadedFileStatus.UPLOADED,
            service_name=service_name,
        )

        # 异步任务：文件解析及存储
        profile_file_upload_and_parse.delay(
            key,
            profile_id,
            validated_data["bk_biz_id"],
            service_name,
        )

        return Response(data=ProfileUploadRecordSLZ(record).data)

    @action(methods=["GET"], detail=False, url_path="records")
    def records(self, request: Request):
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


class ProfileQueryViewSet(ProfileBaseViewSet):
    """Profile Query viewSet"""

    @staticmethod
    def _query(
        bk_biz_id: int,
        data_type: str,
        app_name: str,
        service_name: str,
        start: int,
        end: int,
        result_table_id: str,
        extra_params: Optional[dict] = None,
        api_type: APIType = APIType.QUERY_SAMPLE_BY_JSON,
        profile_id: Optional[str] = None,
        filter_labels: Optional[dict] = None,
        converted: bool = True,
    ) -> Union[DorisConverter, dict]:
        """
        获取 profile 数据
        """
        if api_type.value == APIType.LABEL_VALUES and "label_key" not in extra_params:
            raise ValueError(_("查询 label values 时 label_key 不能为空"))

        filter_labels = filter_labels or {}
        extra_params = extra_params or {}
        for k, v in filter_labels.items():
            if "label_filter" not in extra_params:
                extra_params["label_filter"] = {k: v}
            else:
                extra_params["label_filter"][k] = v

        if profile_id:
            if "label_filter" not in extra_params:
                extra_params["label_filter"] = {"profile_id": profile_id}
            else:
                extra_params["label_filter"]["profile_id"] = profile_id

        if api_type.value == APIType.LABEL_VALUES:
            extra_params["label_key"] = label_key  # noqa

        q = Query(
            api_type=api_type,
            api_params=APIParams(
                biz_id=str(bk_biz_id),
                app=app_name,
                service_name=service_name,
                type=data_type,
                start=start,
                end=end,
                **extra_params,
            ),
            result_table_id=result_table_id,
        )

        r = q.execute()
        if r is None:
            raise ValueError(_("未查询到有效数据"))

        if not converted or not r.get("list"):
            return r

        c = DorisConverter()
        p = c.convert(r)
        if p is None:
            raise ValueError(_("无法转换 profiling 数据"))
        return c

    def _get_essentials(self, validated_data: dict) -> dict:
        """获取 app_name,service_name,bk_biz_id,result_table_id"""

        # storing data in 2 ways:
        # - global storage, bk_biz_id/space_id level
        # - application storage, application level
        if validated_data["global_query"]:
            app_name = BUILTIN_APP_NAME
            service_name = app_name
            # TODO: fetch from apm api in the future
            # we keep the same rule for now
            bk_biz_id = api.cmdb.get_blueking_biz()
            result_table_id = f"{bk_biz_id}_profile_{BUILTIN_APP_NAME}"
        else:
            bk_biz_id = validated_data["bk_biz_id"]
            app_name = validated_data["app_name"]
            service_name = validated_data.get("service_name", DEFAULT_SERVICE_NAME)
            application_info = self._examine_application(bk_biz_id, app_name)
            result_table_id = application_info["profiling_config"]["result_table_id"]

        return {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
            "result_table_id": result_table_id,
        }

    @action(methods=["POST", "GET"], detail=False, url_path="samples")
    def samples(self, request: Request):
        """查询 profiling samples 数据"""
        serializer = ProfileQuerySerializer(data=request.data or request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        start, end = self._enlarge_duration(
            validated_data["start"], validated_data["end"], offset=validated_data["offset"]
        )
        essentials = self._get_essentials(validated_data)

        doris_converter = self._query(
            bk_biz_id=essentials["bk_biz_id"],
            app_name=essentials["app_name"],
            service_name=essentials["service_name"],
            data_type=validated_data["data_type"],
            start=start,
            end=end,
            profile_id=validated_data.get("profile_id"),
            filter_labels=validated_data.get("filter_labels"),
            result_table_id=essentials["result_table_id"],
            extra_params={"order": {"expr": "dtEventTimeStamp", "sort": "desc"}},
        )

        if (
            validated_data.get("global_query", False)
            and isinstance(DorisConverter, dict)
            and not doris_converter.get("list")
            and validated_data.get("profile_id")
        ):
            # 全局查询并且无数据时 查询文件上传记录的异常信息并展示
            record = ProfileUploadRecord.objects.filter(profile_id=validated_data["profile_id"]).first()
            if record:
                raise ValueError(
                    f"文件解析失败，状态：{dict(UploadedFileStatus.choices).get(record.status)}，异常信息：{record.content}",
                )

        if isinstance(doris_converter, dict) and not doris_converter.get("list"):
            raise ValueError(_("未查询到有效数据"))

        diagram_types = validated_data["diagram_types"]
        options = {"sort": validated_data.get("sort"), "data_mode": CallGraphResponseDataMode.IMAGE_DATA_MODE}
        if validated_data.get("is_compared"):
            diff_doris_converter = self._query(
                bk_biz_id=essentials['bk_biz_id'],
                app_name=essentials["app_name"],
                service_name=essentials["service_name"],
                data_type=validated_data["data_type"],
                start=start,
                end=end,
                profile_id=validated_data.get("diff_profile_id"),
                filter_labels=validated_data.get("diff_filter_labels"),
                result_table_id=essentials["result_table_id"],
                extra_params={"order": {"expr": "dtEventTimeStamp", "sort": "desc"}},
            )
            diff_diagram_dicts = (
                get_diagrammer(d_type).diff(doris_converter, diff_doris_converter, **options)
                for d_type in diagram_types
            )
            data = {k: v for diagram_dict in diff_diagram_dicts for k, v in diagram_dict.items()}
            data.update(doris_converter.get_sample_type())
            return Response(data=data)

        diagram_dicts = (get_diagrammer(d_type).draw(doris_converter, **options) for d_type in diagram_types)
        data = {k: v for diagram_dict in diagram_dicts for k, v in diagram_dict.items()}
        data.update(doris_converter.get_sample_type())
        return Response(data=data)

    @staticmethod
    def _enlarge_duration(start: int, end: int, offset: int) -> Tuple[int, int]:
        # start & end all in microsecond, so we need to convert it to millisecond
        start = int(start / 1000 + offset * 1000)
        end = int(end / 1000 + offset * 1000)

        return start, end

    @staticmethod
    def _examine_application(bk_biz_id: int, app_name: str) -> dict:
        """
        检查应用的 Profiling 功能是否可用
        """
        try:
            application = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id)
            application_id = application.pk
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}) 不存在").format(app_name))

        try:
            application_info = api.apm_api.detail_application({"application_id": application_id})
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}) 不存在").format(application_id))

        if "app_name" not in application_info:
            raise ValueError(_("应用({}) 不存在").format(application_id))
        if "profiling_config" not in application_info:
            raise ValueError(_("应用({}) 未开启性能分析").format(application_id))

        return application_info

    @action(methods=["GET"], detail=False, url_path="labels")
    def labels(self, request: Request):
        """获取 profiling 数据的 label_key 列表"""
        limit = 1000

        serializer = ProfileQueryLabelsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        essentials = self._get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = self._enlarge_duration(validated_data["start"], validated_data["end"], offset=300)

        # 因为 bkbase label 接口已经改为返回原始格式的所以这里改成取前 5000条 label 进行提取 key 列表
        results = self._query(
            api_type=APIType.LABELS,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            data_type=validated_data["data_type"],
            converted=False,
            result_table_id=result_table_id,
            start=start,
            end=end,
            extra_params={"limit": {"rows": limit}},
        )

        label_keys = set(
            itertools.chain(*[list(json.loads(i["labels"]).keys()) for i in results["list"] if i.get("labels")])
        )

        return Response(data={"label_keys": label_keys})

    @action(methods=["GET"], detail=False, url_path="label_values")
    def label_values(self, request: Request):
        """获取 profiling 数据的 label_values 列表"""
        serializer = ProfileQueryLabelValuesSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        offset, rows = validated_data["offset"], validated_data["rows"]
        essentials = self._get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = self._enlarge_duration(validated_data["start"], validated_data["end"], offset=300)
        results = self._query(
            api_type=APIType.LABEL_VALUES,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            data_type=validated_data["data_type"],
            extra_params={
                "label_key": validated_data["label_key"],
                "limit": {"offset": offset, "rows": rows},
            },
            result_table_id=result_table_id,
            start=start,
            end=end,
            converted=False,
        )

        return Response(data={"label_values": [i["label_value"] for i in results["list"] if i.get("label_value")]})

    @action(methods=["GET"], detail=False, url_path="export")
    def export(self, request: Request):
        serializer = ProfileQueryExportSerializer(data=request.data or request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        essentials = self._get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = self._enlarge_duration(
            validated_data["start"], validated_data["end"], offset=validated_data["offset"]
        )
        doris_converter = self._query(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            service_name=service_name,
            data_type=validated_data["data_type"],
            start=start,
            end=end,
            profile_id=validated_data.get("profile_id"),
            filter_labels=validated_data.get("filter_labels"),
            result_table_id=result_table_id,
        )

        # transfer data
        export_format = validated_data.get("export_format", DEFAULT_EXPORT_FORMAT)
        if export_format not in EXPORT_FORMAT_MAP:
            raise ValueError(f"({export_format}) format is currently not supported")
        now_str = timezone.now().strftime("%Y-%m-%d-%H-%M-%S")
        file_name = PROFILE_EXPORT_FILE_NAME.format(
            app_name=app_name, data_type=validated_data["data_type"], time=now_str, format=export_format
        )
        serialized_data = doris_converter.profile.SerializeToString()
        compressed_data = gzip.compress(serialized_data)

        response = HttpResponse(compressed_data, content_type="application/octet-stream")
        response["Content-Encoding"] = "gzip"
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'

        return response


class ResourceQueryViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self):
        if self.action in ["services"]:
            return [ViewBusinessPermission()]

        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute("GET", ListApplicationServicesResource, endpoint="services"),
        ResourceRoute("POST", QueryProfileBarGraphResource, endpoint="services_trace_bar"),
        ResourceRoute("GET", QueryServicesDetailResource, endpoint="services_detail"),
    ]
