"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.apps import AppConfig


class IamV4Config(AppConfig):
    name = "bkmonitor.iam.iam_v4"
    verbose_name = "IAM v4 Provider"

    def ready(self):
        # 注入 v4 codec 并显式触发 handler 注册（装饰器已在 import 时生效，
        # 这里只是保障 lazy import 场景下的确定性）。
        from .callback.services import service
        from .codec import V4NameCodec
        from .callback.handlers import register_all

        service.set_codec(V4NameCodec())
        register_all()
