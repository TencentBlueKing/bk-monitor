"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import functools
import gzip
import hashlib
import itertools
import json
import logging

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from rest_framework.viewsets import ViewSet

from apm_web.decorators import user_visit_record
from apm_web.models import Application, ProfileUploadRecord, UploadedFileStatus
from apm_web.profile.constants import (
    BUILTIN_APP_NAME,
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_SERVICE_NAME,
    EBPF_PROFILING_APP_PREFIX,
    EXPORT_FORMAT_MAP,
    LARGE_SERVICE_MAX_QUERY_SIZE,
    NORMAL_SERVICE_MAX_QUERY_SIZE,
    PROFILE_EXPORT_FILE_NAME,
    PROFILE_UPLOAD_RECORD_NEW_FILE_NAME,
    CallGraphResponseDataMode,
)
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.diagrams.ebpf_converter import EbpfConverter
from apm_web.profile.diagrams.tree_converter import TreeConverter
from apm_web.profile.doris.converter import DorisProfileConverter
from apm_web.profile.doris.querier import APIParams, APIType, ConverterType, Query
from apm_web.profile.file_handler import ProfilingFileHandler
from apm_web.profile.profileconverter import generate_profile_id
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
from bkmonitor.utils.cache import CacheType, using_cache
from core.drf_resource import api
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.errors.api import BKAPIError

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
    @user_visit_record
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
    @user_visit_record
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
        if validated_data.get("service_name"):
            filter_params["service_name"] = validated_data.get("service_name")

        # 过滤掉过期的文件 (过期文件在 bkbase 中已查不到不需要显示)
        datasource = api.apm_api.query_builtin_profile_datasource()
        last_retention = datetime.datetime.now() - datetime.timedelta(days=datasource["retention"])
        queryset = ProfileUploadRecord.objects.filter(**filter_params, uploaded_time__gte=last_retention).order_by(
            "-uploaded_time"
        )
        return Response(data=ProfileUploadRecordSLZ(queryset, many=True).data)


class ProfileQueryViewSet(ProfileBaseViewSet):
    """Profile Query viewSet"""

    @staticmethod
    def ebpf_query(
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        start: int,
        end: int,
        sample_type: str,
        converter: ConverterType | None = None,
    ) -> TreeConverter:
        """
        获取 ebpf profile 数据
        """
        profile_data = api.apm_api.query_ebpf_profile(
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            start=start,
            data_type=sample_type,
            end=end,
        )
        ebpf_converter = EbpfConverter()
        ebpf_converter.convert(raw=profile_data, data_type=sample_type)
        return ebpf_converter

    @staticmethod
    def query(
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        start: int,
        end: int,
        result_table_id: str,
        extra_params: dict | None = None,
        api_type: APIType = APIType.QUERY_SAMPLE_BY_JSON,
        profile_id: str | None = None,
        filter_labels: dict | None = None,
        dimension_fields: str = None,
        data_type: str = None,
        sample_type: str = None,
        order: str = None,
        agg_method: str | None = None,
        agg_interval: int = 60,
        converter: ConverterType | None = None,
    ) -> DorisProfileConverter | TreeConverter | dict:
        """
        获取 profile 数据
        """
        retry_handler = None

        def update_profile_id(api_params, key, replace_key, query_profile_id):
            api_params.label_filter.pop(key)
            api_params.label_filter[replace_key] = query_profile_id

        extra_params = extra_params or {}
        if api_type in [APIType.QUERY_SAMPLE_BY_JSON, APIType.SELECT_COUNT]:
            # query_sample / select_count 接口需要传递 dimension_fields 参数
            if not dimension_fields:
                dimension_fields = ",".join(
                    ["dtEventTimeStamp", "type", "service_name", "period_type", "period", "sample_type"]
                )
            extra_params["dimension_fields"] = dimension_fields

        if filter_labels:
            extra_params.setdefault("label_filter", {})
            extra_params["label_filter"].update(filter_labels)

        if sample_type:
            filters = extra_params.setdefault("general_filters", {})
            filters["sample_type"] = f"op_eq|{sample_type}"

        if profile_id:
            extra_params.setdefault("label_filter", {})
            extra_params["label_filter"].update({"profile_id": profile_id})

        if "order" not in extra_params:
            if order:
                extra_params.setdefault("order", {})
                sort = "desc" if order.startswith("-") else "asc"
                extra_params["order"] = {"expr": order.replace("-", ""), "sort": sort}
            else:
                if api_type == APIType.QUERY_SAMPLE_BY_JSON:
                    # 如果没有排序并且为 query_sample_by_json 类型 那么增加排序字段 dtEventTimeStamp,t1.stacktrace_id 保持接口返回数据一致
                    extra_params.setdefault("order", {})
                    extra_params["order"] = {"expr": "dtEventTimeStamp,t1.stacktrace_id", "sort": "desc"}

        if "profile_id" in extra_params.get("label_filter", {}):
            retry_handler = functools.partial(
                update_profile_id,
                key="profile_id",
                replace_key="span_id",
                query_profile_id=extra_params["label_filter"]["profile_id"],
            )
        if "span_id" in extra_params.get("label_filter", {}):
            retry_handler = functools.partial(
                update_profile_id,
                key="span_id",
                replace_key="profile_id",
                query_profile_id=extra_params["label_filter"]["span_id"],
            )

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
        r = q.execute(retry_if_empty_handler=retry_handler)
        if r is None:
            return {}

        if not converter:
            return r

        # 注意: 不同转换器有不同的返回结果
        try:
            if converter == ConverterType.Profile:
                c = DorisProfileConverter()
                c.convert(r, agg_method, agg_interval)
            elif converter == ConverterType.Tree:
                c = TreeConverter()
                c.convert(r, agg_method, agg_interval)
            else:
                raise ValueError(f"不支持的 Profiling 转换器: {converter}")
        except Exception as e:  # noqa
            raise ValueError(f"无法使用 {converter} 转换 Profiling 数据，异常信息: {e}")

        return c

    @classmethod
    def get_essentials(cls, validated_data: dict) -> dict:
        """获取 app_name,service_name,bk_biz_id,result_table_id"""
        is_ebpf = False
        result_table_id = ""
        # storing data in 2 ways:
        # - global storage, bk_biz_id/space_id level
        # - application storage, application level
        if validated_data["global_query"]:
            builtin_datasource = api.apm_api.query_builtin_profile_datasource()
            app_name = BUILTIN_APP_NAME
            service_name = app_name
            bk_biz_id = builtin_datasource["bk_biz_id"]
            result_table_id = builtin_datasource["result_table_id"]
        else:
            app_name = validated_data["app_name"]
            if validated_data["app_name"].startswith(EBPF_PROFILING_APP_PREFIX):
                # 如果以 app_name 以 ebpf- 开头，则认为是 ebpf 采集数据 请求参数伪装成 application 格式 并在返回 essential 时增加标识位
                app_name = validated_data["app_name"][len(EBPF_PROFILING_APP_PREFIX) :]
                is_ebpf = True
            bk_biz_id = validated_data["bk_biz_id"]
            service_name = validated_data.get("service_name", DEFAULT_SERVICE_NAME)
            if not is_ebpf:
                application_info = cls._examine_application(bk_biz_id, app_name)
                result_table_id = application_info["profiling_config"]["result_table_id"]

        return {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
            "result_table_id": result_table_id,
            "is_ebpf": is_ebpf,
        }

    @classmethod
    def get_query_params(cls, request_data):
        serializer = ProfileQuerySerializer(data=request_data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        essentials = cls.get_essentials(data)
        # 根据是否是大应用调整获取的消息条数 避免接口耗时过长
        if not essentials["is_ebpf"] and cls.is_large_service(
            essentials["bk_biz_id"], essentials["app_name"], essentials["service_name"], data["data_type"]
        ):
            extra_params = {"limit": {"offset": 0, "rows": LARGE_SERVICE_MAX_QUERY_SIZE}}
        else:
            extra_params = {"limit": {"offset": 0, "rows": NORMAL_SERVICE_MAX_QUERY_SIZE}}

        return data, essentials, extra_params

    @classmethod
    def calculate_timerange(cls, validate_data):
        offset = validate_data.get("offset", 0)
        start, end = cls.enlarge_duration(validate_data["start"], validate_data["end"], offset=offset)
        return start, end, offset

    @classmethod
    def converter_query(cls, essentials, validate_data, extra_params):
        offset = validate_data.get("offset", 0)

        start_time, end_time = validate_data["start"], validate_data["end"]
        filter_start_time = validate_data["filter_labels"].get("start")
        filter_end_time = validate_data["filter_labels"].get("end")
        if filter_start_time and filter_end_time:
            # 时间对比使用对比中的时间
            start_time, end_time = cls.enlarge_duration(filter_start_time, filter_end_time, offset)
            del validate_data["filter_labels"]["start"]
            del validate_data["filter_labels"]["end"]
        else:
            start_time, end_time = cls.enlarge_duration(start_time, end_time, offset)
        if essentials["is_ebpf"]:
            return cls.ebpf_query(
                bk_biz_id=essentials["bk_biz_id"],
                app_name=essentials["app_name"],
                service_name=essentials["service_name"],
                start=start_time,
                end=end_time,
                sample_type=validate_data["data_type"],
            )
        else:
            return cls.query(
                bk_biz_id=essentials["bk_biz_id"],
                app_name=essentials["app_name"],
                service_name=essentials["service_name"],
                start=start_time,
                end=end_time,
                profile_id=validate_data.get("profile_id"),
                filter_labels=validate_data.get("filter_labels"),
                result_table_id=essentials["result_table_id"],
                sample_type=validate_data["data_type"],
                agg_method=validate_data["agg_method"],
                agg_interval=cls.get_agg_interval(start_time, end_time),
                converter=ConverterType.Tree,
                extra_params=extra_params,
            )

    @classmethod
    def get_services_language(cls, validate_data):
        from apm_web.handlers.service_handler import ServiceHandler

        options = {
            "app_name": validate_data.get("app_name"),
            "bk_biz_id": validate_data.get("bk_biz_id"),
            "service_name": validate_data.get("service_name"),
        }
        try:
            node_data = ServiceHandler.get_node(**options)
            service_language = node_data.get("extra_data", {}).get("service_language", "")
            return service_language
        except Exception:
            logger.exception(f"【ProfileQueryViewSet】Failed to query service_language using the parameter {options}.")
            return ""

    @classmethod
    def get_converter_options(cls, validate_data):
        service_language = cls.get_services_language(validate_data)
        return {
            "sort": validate_data.get("sort"),
            "data_mode": CallGraphResponseDataMode.IMAGE_DATA_MODE,
            "service_language": service_language,
        }

    @classmethod
    def converter_to_data(cls, validate_data, tree_converter):
        if isinstance(tree_converter, dict) and not tree_converter:
            return {}

        if not tree_converter.tree:
            return {}

        diagram_dicts = (
            get_diagrammer(d_type).draw(tree_converter, **cls.get_converter_options(validate_data))
            for d_type in validate_data["diagram_types"]
        )
        data = {k: v for diagram_dict in diagram_dicts for k, v in diagram_dict.items()}
        data.update(tree_converter.get_sample_type())
        return data

    @classmethod
    def get_agg_interval(cls, start, end):
        """
        获取聚合周期（规则：5分钟内取秒级聚合，5分钟以上分钟级别聚合）
        params: start , end  (单位: 毫秒)
        return: 返回聚合周期(单位：秒)
        """
        return 1 if end - start <= 5 * 60 * 1000 else 60

    @action(methods=["POST", "GET"], detail=False, url_path="samples")
    @user_visit_record
    def samples(self, request: Request):
        """查询 profiling samples 数据"""

        validate_data, essentials, extra_params = self.get_query_params(request.data)

        if "tendency" in validate_data["diagram_types"]:
            start, end, _offset = self.calculate_timerange(validate_data)
            validate_data["diagram_types"].remove("tendency")
            tendency_result, compare_tendency_result = self._get_tendency_data(
                essentials=essentials,
                start=start,
                end=end,
                profile_id=validate_data.get("profile_id"),
                filter_labels=validate_data.get("filter_labels"),
                is_compared=validate_data.get("is_compared"),
                diff_profile_id=validate_data.get("diff_profile_id"),
                diff_filter_labels=validate_data.get("diff_filter_labels"),
                sample_type=validate_data["data_type"],
                agg_interval=self.get_agg_interval(start, end),
            )

            if len(validate_data["diagram_types"]) == 0:
                if validate_data.get("is_compared"):
                    return Response(data=compare_tendency_result)
                return Response(data=tendency_result)

        tree_converter = self.converter_query(essentials, validate_data, extra_params)

        if validate_data["global_query"] and not tree_converter:
            # 如果是全局搜索并且无返回结果 说明文件上传可能发生了异常
            # 文件查询时，如果搜索不到数，将会用文件上传记录的异常信息进行提示
            if validate_data.get("profile_id"):
                record = ProfileUploadRecord.objects.filter(profile_id=validate_data["profile_id"]).first()
                if record and record.status != UploadedFileStatus.STORE_SUCCEED.value:
                    raise ValueError(
                        f"上传文件解析为 Profile 数据失败，"
                        f"解析状态：{dict(UploadedFileStatus.choices).get(record.status)}，"
                        f"异常信息：{record.content}"
                    )

        if not tree_converter or tree_converter.empty():
            return Response(_("未查询到有效数据"), status=HTTP_200_OK)

        if validate_data.get("is_compared"):
            diff_start_time = validate_data["diff_filter_labels"].pop("start", validate_data["start"])
            diff_end_time = validate_data["diff_filter_labels"].pop("end", validate_data["end"])
            diff_start_time, diff_end_time = self.enlarge_duration(
                diff_start_time, diff_end_time, offset=validate_data.get("offset", 0)
            )
            diff_tree_converter = self.query(
                bk_biz_id=essentials["bk_biz_id"],
                app_name=essentials["app_name"],
                service_name=essentials["service_name"],
                start=diff_start_time,
                end=diff_end_time,
                profile_id=validate_data.get("diff_profile_id"),
                filter_labels=validate_data.get("diff_filter_labels"),
                result_table_id=essentials["result_table_id"],
                sample_type=validate_data["data_type"],
                agg_method=validate_data["agg_method"],
                agg_interval=self.get_agg_interval(diff_start_time, diff_end_time),
                converter=ConverterType.Tree,
                extra_params=extra_params,
            )
            if not diff_tree_converter or diff_tree_converter.empty():
                return Response(_("当前对比项的查询条件未查询到有效数据，请调整后再试"), status=HTTP_200_OK)

            diff_diagram_dicts = (
                get_diagrammer(d_type).diff(
                    tree_converter, diff_tree_converter, **self.get_converter_options(validate_data)
                )
                for d_type in validate_data["diagram_types"]
            )
            data = {k: v for diagram_dict in diff_diagram_dicts for k, v in diagram_dict.items()}
            data.update(tree_converter.get_sample_type())
            return Response(data=data)

        return Response(data=self.converter_to_data(validate_data, tree_converter))

    @classmethod
    @using_cache(CacheType.APM(60 * 60))
    def is_large_service(cls, bk_biz_id, app_name, service, sample_type):
        """判断此 profile 服务是否是大应用"""

        try:
            response = api.apm_api.query_profile_services_detail(
                **{
                    "bk_biz_id": bk_biz_id,
                    "app_name": app_name,
                    "service_name": service,
                    "sample_type": sample_type,
                    "is_large": True,
                }
            )
            return bool(response)
        except BKAPIError as e:
            logger.exception(
                f"[ProfileIsLargeService] "
                f"request ({bk_biz_id}){app_name}[{service}]({sample_type})service detail failed, error: {e}",
            )
            return False

    def _get_tendency_data(
        self,
        sample_type,
        essentials,
        start,
        end,
        profile_id=None,
        filter_labels=None,
        is_compared=False,
        diff_profile_id=None,
        diff_filter_labels=None,
        agg_interval=60,
    ):
        """获取时序表数据"""
        interval = agg_interval * 1000
        dimension = f"FLOOR(dtEventTimeStamp / {interval}) * {interval}"

        tendency_data = self.query(
            api_type=APIType.SELECT_COUNT,
            bk_biz_id=essentials["bk_biz_id"],
            app_name=essentials["app_name"],
            service_name=essentials["service_name"],
            sample_type=sample_type,
            start=start,
            end=end,
            profile_id=profile_id,
            filter_labels=filter_labels,
            result_table_id=essentials["result_table_id"],
            dimension_fields=f"{dimension} AS time",
            extra_params={
                "metric_fields": "sum(value)",
                "order": {"expr": f"({dimension})", "sort": "asc"},
            },
        )

        compare_tendency_result = {}
        if is_compared:
            compare_tendency_data = self.query(
                api_type=APIType.SELECT_COUNT,
                bk_biz_id=essentials["bk_biz_id"],
                app_name=essentials["app_name"],
                service_name=essentials["service_name"],
                sample_type=sample_type,
                start=start,
                end=end,
                profile_id=diff_profile_id,
                filter_labels=diff_filter_labels,
                result_table_id=essentials["result_table_id"],
                dimension_fields=f"{dimension} AS time",
                extra_params={
                    "metric_fields": "sum(value)",
                    "order": {"expr": f"({dimension})", "sort": "asc"},
                },
            )
            compare_tendency_result = get_diagrammer("tendency").diff(
                tendency_data,
                compare_tendency_data,
                sample_type=sample_type,
            )

        tendency_data = get_diagrammer("tendency").draw(tendency_data, sample_type=sample_type)
        return tendency_data, compare_tendency_result

    @staticmethod
    def enlarge_duration(start: int, end: int, offset: int, min_range: int = 0) -> tuple[int, int]:
        """
        params:
            - start, end: unit microseconds
            - offset, min_range: unit seconds

        return: unit milliseconds
        """
        # start & end all in microsecond, so we need to convert it to millisecond
        start = int(int(start) / 1000 + offset * 1000)
        end = int(int(end) / 1000 + offset * 1000)

        min_range_milli_seconds = min_range * 1000
        if min_range_milli_seconds > 0 and end - start < min_range_milli_seconds:
            # 如果起止时间小于最小范围 min_range，则将整个起止时间各往外延展一半，整体时长增长一个 min_range
            half_min_range_milli_seconds = int(min_range_milli_seconds / 2)
            start = start - half_min_range_milli_seconds
            end = end + half_min_range_milli_seconds

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
            application_info = api.apm_api.detail_application({"bk_biz_id": bk_biz_id, "app_name": app_name})
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

        essentials = self.get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = self.enlarge_duration(validated_data["start"], validated_data["end"], offset=0, min_range=3600)

        # 因为 bkbase label 接口已经改为返回原始格式的所以这里改成取前 5000条 label 进行提取 key 列表
        results = self.query(
            api_type=APIType.LABELS,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            result_table_id=result_table_id,
            start=start,
            end=end,
            extra_params={"limit": {"rows": limit}},
        )

        label_keys = set(
            itertools.chain(*[list(json.loads(i["labels"]).keys()) for i in results.get("list", {}) if i.get("labels")])
        )

        return Response(data={"label_keys": label_keys})

    @action(methods=["GET"], detail=False, url_path="label_values")
    def label_values(self, request: Request):
        """获取 profiling 数据的 label_values 列表"""
        serializer = ProfileQueryLabelValuesSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        offset, rows = validated_data["offset"], validated_data["rows"]
        essentials = self.get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = self.enlarge_duration(validated_data["start"], validated_data["end"], offset=0, min_range=3600)
        results = self.query(
            api_type=APIType.LABEL_VALUES,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            extra_params={
                "label_key": validated_data["label_key"],
                "limit": {"offset": offset, "rows": rows},
            },
            result_table_id=result_table_id,
            start=start,
            end=end,
        )

        return Response(
            data={"label_values": [i["label_value"] for i in results.get("list", {}) if i.get("label_value")]}
        )

    @action(methods=["GET"], detail=False, url_path="export")
    @user_visit_record
    def export(self, request: Request):
        serializer = ProfileQueryExportSerializer(data=request.data or request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        essentials = self.get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = self.enlarge_duration(
            validated_data["start"], validated_data["end"], offset=validated_data["offset"]
        )
        doris_converter = self.query(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            service_name=service_name,
            start=start,
            end=end,
            profile_id=validated_data.get("profile_id"),
            filter_labels=validated_data.get("filter_labels"),
            result_table_id=result_table_id,
            sample_type=validated_data["data_type"],
            converter=ConverterType.Profile,
            agg_method=validated_data["agg_method"],
            agg_interval=self.get_agg_interval(start, end),
        )

        # transfer data
        export_format = validated_data.get("export_format", DEFAULT_EXPORT_FORMAT)
        if export_format not in EXPORT_FORMAT_MAP:
            raise ValueError(f"({export_format}) format is currently not supported")
        now_str = timezone.localtime(timezone.now()).strftime("%Y-%m-%d-%H-%M-%S")
        file_name = PROFILE_EXPORT_FILE_NAME.format(
            app_name=app_name, data_type=validated_data["data_type"], time=now_str, format=export_format
        )

        if not doris_converter:
            compressed_data = b""
        else:
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
        ResourceRoute(
            "GET",
            ListApplicationServicesResource,
            endpoint="services",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute("POST", QueryProfileBarGraphResource, endpoint="services_trace_bar"),
        ResourceRoute(
            "GET",
            QueryServicesDetailResource,
            endpoint="services_detail",
            decorators=[
                user_visit_record,
            ],
        ),
    ]
