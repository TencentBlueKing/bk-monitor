"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import IntegrityError, transaction

from bkmonitor.models import ApiAuthToken


def get_or_create_business_token(
    *, bk_tenant_id: str, bk_biz_id: int, token_type: str, operator: str
) -> tuple[ApiAuthToken, bool]:
    namespace = f"biz#{bk_biz_id}"
    database = ApiAuthToken.objects.db
    auth_token = ApiAuthToken.objects.filter(
        namespaces__contains=namespace,
        type=token_type,
        bk_tenant_id=bk_tenant_id,
    ).last()
    if auth_token:
        return auth_token, False

    try:
        with transaction.atomic(using=database):
            auth_token = ApiAuthToken.objects.create(
                name=f"{bk_biz_id}_{token_type}",
                type=token_type,
                namespaces=[namespace],
                bk_tenant_id=bk_tenant_id,
            )
            ApiAuthToken.origin_objects.filter(pk=auth_token.pk).update(create_user=operator)
            auth_token.create_user = operator
    except IntegrityError:
        auth_token = ApiAuthToken.objects.filter(
            namespaces__contains=namespace,
            type=token_type,
            bk_tenant_id=bk_tenant_id,
        ).last()
        if not auth_token:
            raise
        return auth_token, False

    return auth_token, True
