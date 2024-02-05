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

from django.utils.translation import ugettext_lazy as _
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apm_web.models import Application, ProfileUploadRecord
from apm_web.profile.converter import get_converter_by_input_type
from apm_web.profile.diagrams import get_diagrammer
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource import api

from .converter import generate_profile_id
from .doris.converter import DorisConverter
from .doris.querier import APIParams, APIType, Query
from .handler import CollectorHandler
from .serializers import (
    ProfileQuerySerializer,
    ProfileUploadRecordSLZ,
    ProfileUploadSerializer,
)

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

    def query(self, request: Request):
        """查询 profiling 数据"""
        serializer = ProfileQuerySerializer(data=request.query_params)
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

        extra_params = {}
        profile_id = validated_data["profile_id"]
        if profile_id:
            extra_params["label_filter"] = {"profile_id": profile_id}
        profile_type = validated_data["profile_type"]
        # 查询 BK Doris 数据
        q = Query(
            api_type=APIType.QUERY_SAMPLE,
            api_params=APIParams(
                biz_id=bk_biz_id, app=app_name, type=profile_type, start=start, end=end, **extra_params
            ),
            result_table_id=application_info["profiling_config"]["result_table_id"],
        )

        r = q.execute()
        if r is None:
            raise ValueError(_("未查询到有效数据"))

        # 直接将 profiling 数据转换成火焰图格式
        c = DorisConverter()
        p = c.convert(r)
        if p is None:
            raise ValueError(_("无法转换 profiling 数据"))

        return Response(data=get_diagrammer(validated_data["diagram_type"]).draw(c))

    def upload(self, request: Request):
        """上传 profiling 文件"""
        uploaded = request.FILES.get("file")
        if not uploaded:
            raise ValueError(_("上传文件为空"))

        # 0. prepare uploaded file
        uploaded = uploaded.read()
        md5 = hashlib.md5(uploaded).hexdigest()
        if ProfileUploadRecord.objects.filter(file_md5=md5).exists():
            raise ValueError(_("相同文件已上传"))

        # 1. got target application
        serializer = ProfileUploadSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # 2. convert file to Profile object
        profile_id = generate_profile_id()
        file_type = validated_data["file_type"]
        c = get_converter_by_input_type(file_type)(preset_profile_id=profile_id)
        try:
            p = c.convert(uploaded)
        except Exception:  # pylint: disable=broad-except
            logger.exception("convert profiling data failed")
            p = None
        if p is None:
            raise ValueError(_("无法转换 profiling 数据"))

        # 3. send data to collector
        try:
            CollectorHandler.send(p)
        except Exception:  # pylint: disable=broad-except
            logger.exception("save profiling data to doris failed")
            raise ValueError(_("保存 profiling 数据失败"))

        # 4. record it if everything is ok
        record = ProfileUploadRecord.objects.create(
            bk_biz_id=validated_data["bk_biz_id"],
            file_md5=md5,
            file_type=file_type,
            profile_id=profile_id,
            operator=request.user.username,
        )

        return Response(data=ProfileUploadRecordSLZ(record).data)
