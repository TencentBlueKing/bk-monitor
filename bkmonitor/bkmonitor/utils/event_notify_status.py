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


from itertools import product


class NotifyStatus(object):
    STATUS_ENUM = ("SUCCESS", "SHIELDED", "PARTIAL_SUCCESS", "FAILED")

    @staticmethod
    def get(status_list=None):
        if not status_list:
            ret_status = 0
        else:
            ori_status = "{SUCCESS}{SHIELDED}{PARTIAL_SUCCESS}{FAILED}"
            status_map = {}
            for status in NotifyStatus.STATUS_ENUM:
                if status in status_list:
                    status_map[status] = "1"
                else:
                    status_map[status] = "0"
            ret_status = ori_status.format(**status_map)
        return int(ret_status)


class NotifyStatusResult(object):
    # {SUCCESS}{SHIELD}{PARTIAL_SUCCESS}{FAILED}
    @staticmethod
    def get_query_conditions(status_list):
        result = []
        for input_status in status_list:
            result.extend(getattr(NotifyStatusResult, input_status.lower())())
        return set(result)

    @staticmethod
    def success():
        success_nums = []
        for i in list(product(["0", "1"], repeat=3)):
            num_list = list(i)
            num_list.insert(0, "1")
            success_nums.append(int("".join(num_list)))
        return success_nums

    @staticmethod
    def failed():
        failed_nums = []
        for i in list(product(["0", "1"], repeat=3)):
            num_list = list(i)
            num_list.insert(3, "1")
            failed_nums.append(int("".join(num_list)))
        return failed_nums

    @staticmethod
    def shielded():
        shield_nums = []
        for i in list(product(["0", "1"], repeat=3)):
            num_list = list(i)
            num_list.insert(1, "1")
            shield_nums.append(int("".join(num_list)))
        return shield_nums

    @staticmethod
    def partial_success():
        shield_nums = []
        for i in list(product(["0", "1"], repeat=3)):
            num_list = list(i)
            num_list.insert(2, "1")
            shield_nums.append(int("".join(num_list)))
        return shield_nums
