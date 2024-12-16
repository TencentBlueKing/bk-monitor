# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from calendars.constants import ItemFreq


class RepeatSerializer(serializers.DictField):
    """
    日历事项-重复事项配置
    """

    freq = serializers.ChoiceField(label="重复频率", choices=["day", "week", "month", "year"])
    interval = serializers.IntegerField(label="重复频率", min_value=1)
    until = serializers.IntegerField(label="重复结束时间", allow_null=True)
    every = serializers.ListField(label="重复区间")
    exclude_date = serializers.ListField(label="排除事项日期")

    def run_validation(self, data=empty):
        """
        判断重复区间是否符合
        freq：day=>every:[]
        freq: week=>every:[0-6]
        freq: month=>every:[1-31]
        freq: year=>every:[1-12]
        """
        value = super(RepeatSerializer, self).run_validation(data)
        if not value:
            return value
        freq = value["freq"]
        every = value["every"]
        every.sort()

        def check_every(freq, every, every_range):
            for need_check_data in every:
                if need_check_data not in every_range:
                    raise ValidationError(
                        _("当重复频率为{}时，重复区间里的值应该在{}-{}之间").format(freq, every_range[0], every_range[-1])
                    )

        if freq == ItemFreq.DAY and every != []:
            raise ValidationError(_("当重复频率为day时，重复区间必须为[]"))
        elif freq == ItemFreq.WEEK:
            check_every(freq, every, [i for i in range(7)])
        elif freq == ItemFreq.MONTH:
            check_every(freq, every, [i for i in range(1, 32)])
        else:
            check_every(freq, every, [i for i in range(1, 13)])
        return value
