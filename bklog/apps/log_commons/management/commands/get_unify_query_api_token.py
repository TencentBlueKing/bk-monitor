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

from datetime import datetime

from django.core.management import BaseCommand
from django.utils import timezone

from apps.constants import ApiTokenAuthType
from apps.log_commons.models import ApiAuthToken
from bkm_space.utils import bk_biz_id_to_space_uid


class Command(BaseCommand):
    help = "Get or create an API auth token of UnifyQuery type"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bk_biz_id", type=int, default=None, help="Business ID, mutually exclusive with --space_uid"
        )
        parser.add_argument(
            "--space_uid", type=str, default=None, help="Space UID, mutually exclusive with --bk_biz_id"
        )
        parser.add_argument("--app_code", type=str, required=True, help="Application code (bk_app_code)")
        parser.add_argument(
            "--expire_time",
            type=str,
            default=None,
            help="Expire time, format: YYYY-MM-DD HH:MM:SS, never expires if not set",
        )

    def handle(self, **options):
        bk_biz_id = options.get("bk_biz_id")
        space_uid = options.get("space_uid")
        app_code = options.get("app_code")
        expire_time_str = options.get("expire_time")

        if not bk_biz_id and not space_uid:
            self.stderr.write(self.style.ERROR("Either --bk_biz_id or --space_uid must be specified"))
            return

        if bk_biz_id and not space_uid:
            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
            if not space_uid:
                self.stderr.write(self.style.ERROR(f"Failed to resolve space_uid from bk_biz_id={bk_biz_id}"))
                return

        expire_time = None
        if expire_time_str:
            try:
                expire_time = timezone.make_aware(datetime.strptime(expire_time_str, "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                self.stderr.write(
                    self.style.ERROR(f"Invalid expire time format: {expire_time_str}, expected YYYY-MM-DD HH:MM:SS")
                )
                return

        token_obj = ApiAuthToken.objects.filter(
            type=ApiTokenAuthType.UNIFY_QUERY.value,
            space_uid=space_uid,
            params__contains={"app_code": app_code},
        ).first()

        if token_obj:
            if token_obj.is_expired():
                old_expire_time = token_obj.expire_time
                token_obj.expire_time = expire_time
                token_obj.save(update_fields=["expire_time"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Existing token was expired (old expire time: {old_expire_time}), expire time updated:"
                    )
                )
                self._print_token_info(token_obj)
                return
            else:
                self.stdout.write(self.style.SUCCESS("Found existing valid token:"))
                self._print_token_info(token_obj)
                return

        token_obj = ApiAuthToken.objects.create(
            type=ApiTokenAuthType.UNIFY_QUERY.value,
            space_uid=space_uid,
            params={"app_code": app_code},
            expire_time=expire_time,
        )
        self.stdout.write(self.style.SUCCESS("Successfully created new token:"))
        self._print_token_info(token_obj)

    def _print_token_info(self, token_obj):
        """输出token信息"""
        self.stdout.write(f"  Token:       {token_obj.token}")
        self.stdout.write(f"  Space UID:   {token_obj.space_uid}")
        self.stdout.write(f"  Type:        {token_obj.type}")
        self.stdout.write(f"  Params:      {token_obj.params}")
        self.stdout.write(f"  Expire Time: {token_obj.expire_time or 'Never'}")
        self.stdout.write(f"  Created At:  {token_obj.created_at}")
        self.stdout.write(f"  Created By:  {token_obj.created_by}")
