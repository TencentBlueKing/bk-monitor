"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dateutil import parser
from rest_framework.exceptions import PermissionDenied

from apps.constants import ApiTokenAuthType
from apps.log_commons.models import ApiAuthToken
from apps.log_search.constants import OperatorEnum
from apps.log_unifyquery.constants import ADVANCED_OP_MAP
from bkm_space.utils import bk_biz_id_to_space_uid


def transform_advanced_addition(addition: dict):
    origin_operator = addition["operator"]
    field = addition["field"]
    value = addition["value"]

    op = ADVANCED_OP_MAP.get(origin_operator, {}).get("operator", "eq")
    condition = ADVANCED_OP_MAP.get(origin_operator, {}).get("condition", "or")
    is_wildcard = ADVANCED_OP_MAP.get(origin_operator, {}).get("is_wildcard", False)

    if origin_operator in [OperatorEnum.IS_TRUE["operator"], OperatorEnum.IS_FALSE["operator"]]:
        value = ["true" if origin_operator == OperatorEnum.IS_TRUE["operator"] else "false"]
    elif origin_operator in [OperatorEnum.EXISTS["operator"], OperatorEnum.NOT_EXISTS["operator"]]:
        value = [""]
    else:
        value = value if isinstance(value, list) else value.split(",")
        if op == ADVANCED_OP_MAP.get(origin_operator, {}).get("operator", "contains") and origin_operator == "=~":
            for index, item in enumerate(value):
                if item.startswith("*"):
                    item = item[1:]
                if item.endswith("*"):
                    item = item[:-1]
                value[index] = item

    if condition == "or":
        field_list = [{"field_name": field, "op": op, "value": value, "is_wildcard": is_wildcard}]
        condition_list = []
    else:
        field_list = [{"field_name": field, "op": op, "value": [v], "is_wildcard": is_wildcard} for v in value]
        condition_list = [condition] * (len(value) - 1)

    return field_list, condition_list


def deal_time_format(start_time, end_time):
    """
    处理时间戳信息
    """
    if isinstance(start_time, int) and isinstance(end_time, int):
        return start_time, end_time

    dt1 = parser.parse(start_time)
    dt2 = parser.parse(end_time)
    start_time = int(dt1.timestamp() * 1000)
    end_time = int(dt2.timestamp() * 1000)
    return start_time, end_time


def verify_unify_query_token(request, auth_info):
    """
    验证统一查询接口的 token 是否存在以及是否过期
    """
    # 获取并验证参数
    bk_biz_id = request.data.get("bk_biz_id")
    if not bk_biz_id:
        raise PermissionDenied("bk_biz_id is required")

    space_uid = bk_biz_id_to_space_uid(bk_biz_id)
    if not space_uid:
        raise PermissionDenied(f"Unable to get valid space_uid from bk_biz_id {bk_biz_id}")

    # 查询 token 表，根据 space_uid 和 app_code 查找对应的 token
    token_obj = ApiAuthToken.objects.filter(
        type=ApiTokenAuthType.UNIFY_QUERY.value,
        space_uid=space_uid,
        params__contains={"app_code": auth_info["bk_app_code"]},
    ).first()

    if not token_obj or token_obj.is_expired():
        raise PermissionDenied("Token not found or expired")
