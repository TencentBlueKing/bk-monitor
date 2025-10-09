"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
UNIFYQUERY 模块，调用接口汇总
"""

from django.utils.translation import gettext_lazy as _  # noqa

from apps.api.base import DataAPI  # noqa
from apps.api.modules.utils import add_esb_info_before_request, biz_to_tenant_getter  # noqa
from apps.utils.local import get_request
from bkm_space.utils import bk_biz_id_to_space_uid
from config.domains import UNIFYQUERY_APIGATEWAY_ROOT  # noqa


def add_unify_query_header_before(params):
    params = add_esb_info_before_request(params)
    if params.get("bk_biz_id"):
        space_uid = bk_biz_id_to_space_uid(params["bk_biz_id"])
        if space_uid:
            params["X-Bk-Scope-Space-Uid"] = space_uid
    else:
        params["X-Bk-Scope-Skip-Space"] = "skip"

    try:
        username = get_request().user.username
    except Exception:  # pylint: disable=broad-except
        username = ""

    if username:
        params["Bk-Query-Source"] = f"username:{username}"
    else:
        params["Bk-Query-Source"] = "backend"

    return params


def add_data_after_request(response_data):
    result = response_data.pop("result", True)
    data = {"data": response_data, "result": result}
    return data


class _UnifyQueryApi:
    MODULE = _("UNIFYQUERY模块")

    HEADER_KEYS = ["X-Bk-Scope-Skip-Space", "X-Bk-Scope-Space-Uid", "Bk-Query-Source"]

    def __init__(self):
        self.query_ts = DataAPI(
            method="POST",
            url=UNIFYQUERY_APIGATEWAY_ROOT + "query/ts/",
            module=self.MODULE,
            description="时序型检索",
            after_request=add_data_after_request,
            header_keys=self.HEADER_KEYS,
            before_request=add_unify_query_header_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.query_ts_reference = DataAPI(
            method="POST",
            url=UNIFYQUERY_APIGATEWAY_ROOT + "query/ts/reference/",
            module=self.MODULE,
            description="非时序型检索",
            after_request=add_data_after_request,
            header_keys=self.HEADER_KEYS,
            before_request=add_unify_query_header_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.query_ts_raw = DataAPI(
            method="POST",
            url=UNIFYQUERY_APIGATEWAY_ROOT + "query/ts/raw/",
            module=self.MODULE,
            description="时序型检索原始日志",
            after_request=add_data_after_request,
            header_keys=self.HEADER_KEYS,
            before_request=add_unify_query_header_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.query_ts_raw_with_scroll = DataAPI(
            method="POST",
            url=UNIFYQUERY_APIGATEWAY_ROOT + "query/ts/raw_with_scroll/",
            module=self.MODULE,
            description="滚动检索原始数据",
            after_request=add_data_after_request,
            header_keys=self.HEADER_KEYS,
            before_request=add_unify_query_header_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
        self.query_field_map = DataAPI(
            method="POST",
            url=UNIFYQUERY_APIGATEWAY_ROOT + "query/ts/info/field_map/",
            module=self.MODULE,
            description="获取字段列表",
            after_request=add_data_after_request,
            header_keys=self.HEADER_KEYS,
            before_request=add_unify_query_header_before,
            bk_tenant_id=biz_to_tenant_getter(),
        )
