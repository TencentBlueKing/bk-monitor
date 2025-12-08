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

from rest_framework import serializers


class CreateTGPATaskSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    task_name = serializers.CharField(label="任务名称")
    openid = serializers.CharField(label="openid")
    log_path = serializers.CharField(label="客户端日志路径")
    platform = serializers.CharField(label="客户端类型", required=False)
    start_time = serializers.DateTimeField(label="文件修改时间范围起始时间", required=False)
    end_time = serializers.DateTimeField(label="文件修改时间范围结束时间", required=False)
    max_file_num = serializers.IntegerField(label="最大捞取文件数", required=False)
    scene = serializers.IntegerField(label="任务阶段", required=False)
    frequency = serializers.CharField(label="触发频率", required=False)
    trigger_duration = serializers.IntegerField(label="持续触发时间(s)", required=False)
    comment = serializers.CharField(label="备注", required=False, allow_blank=True)


class GetTGPATaskListSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")


class GetDownloadUrlSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    id = serializers.IntegerField(label="数据库主键")
