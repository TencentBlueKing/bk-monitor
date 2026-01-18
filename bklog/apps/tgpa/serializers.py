"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.tgpa.constants import TGPA_REPORT_ORDER_FIELDS


class GetCountInfoSerializer(serializers.Serializer):
    """
    获取客户端日志数量信息
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))


class CreateTGPATaskSerializer(serializers.Serializer):
    """
    创建客户端日志捞取任务
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    task_name = serializers.CharField(label=_("任务名称"))
    openid = serializers.CharField(label=_("openid"))
    log_path = serializers.CharField(label=_("客户端日志路径"))
    platform = serializers.CharField(label=_("客户端类型"), required=False)
    start_time = serializers.DateTimeField(label=_("文件修改时间范围起始时间"), required=False)
    end_time = serializers.DateTimeField(label=_("文件修改时间范围结束时间"), required=False)
    max_file_num = serializers.IntegerField(label=_("最大捞取文件数"), required=False)
    scene = serializers.IntegerField(label=_("任务阶段"), required=False)
    frequency = serializers.CharField(label=_("触发频率"), required=False)
    trigger_duration = serializers.IntegerField(label=_("持续触发时间(s)"), required=False)
    comment = serializers.CharField(label=_("备注"), required=False, allow_blank=True)


class GetTGPATaskListSerializer(serializers.Serializer):
    """
    获取客户端日志捞取任务列表
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    status = serializers.CharField(label=_("任务状态"), required=False, allow_null=True)
    scene = serializers.CharField(label=_("任务阶段"), required=False, allow_null=True)
    created_by = serializers.CharField(label=_("创建人"), required=False, allow_null=True)
    ordering = serializers.CharField(label=_("排序字段"), required=False, allow_null=True, allow_blank=True)
    keyword = serializers.CharField(label=_("关键字"), required=False, allow_null=True, allow_blank=True)
    page = serializers.IntegerField(label=_("页码"), default=1)
    pagesize = serializers.IntegerField(label=_("分页大小"), default=10)


class GetDownloadUrlSerializer(serializers.Serializer):
    """
    获取客户端日志捞取任务文件下载链接
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    id = serializers.IntegerField(label=_("任务ID"))


class GetUsernameListSerializer(serializers.Serializer):
    """
    获取用户名列表
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))


class GetIndexSetIdSerializer(serializers.Serializer):
    """
    获取客户端日志索引集ID
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))


class GetReportListSerializer(serializers.Serializer):
    """
    获取客户端日志上报文件列表
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    keyword = serializers.CharField(label=_("关键字"), required=False, allow_null=True, allow_blank=True)
    start_time = serializers.IntegerField(label=_("开始时间"), required=False, allow_null=True)
    end_time = serializers.IntegerField(label=_("结束时间"), required=False, allow_null=True)
    order_field = serializers.ChoiceField(label=_("排序字段"), required=False, choices=TGPA_REPORT_ORDER_FIELDS)
    order_type = serializers.ChoiceField(label=_("排序类型"), required=False, choices=["ASC", "DESC"])
    page = serializers.IntegerField(label=_("页码"), default=1)
    pagesize = serializers.IntegerField(label=_("分页大小"), default=10)


class SyncReportSerializer(serializers.Serializer):
    """
    同步客户端日志上报文件
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    openid_list = serializers.ListField(
        label=_("openid列表"), child=serializers.CharField(), required=False, allow_null=True, allow_empty=True
    )
    file_name_list = serializers.ListField(
        label=_("文件名列表"), child=serializers.CharField(), required=False, allow_null=True, allow_empty=True
    )
    start_time = serializers.IntegerField(label=_("开始时间"), required=False, allow_null=True)
    end_time = serializers.IntegerField(label=_("结束时间"), required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("openid_list") and not attrs.get("file_name_list"):
            raise serializers.ValidationError(_("openid_list 和 file_name_list 不能同时为空"))
        return attrs


class GetFileStatusSerializer(serializers.Serializer):
    """
    获取文件状态
    """

    file_name_list = serializers.ListField(label=_("文件名列表"), child=serializers.CharField())


class RetrieveSyncRecordSerializer(serializers.Serializer):
    """
    获取同步记录详情
    """

    record_id = serializers.IntegerField(label=_("同步记录ID"))
