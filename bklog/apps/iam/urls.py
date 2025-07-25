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

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.conf.urls import include
from django.urls import re_path
from rest_framework import routers

from apps.iam import Permission
from apps.iam.views import meta
from apps.iam.views.resources import (
    CollectionResourceProvider,
    EsSourceResourceProvider,
    IndicesResourceProvider,
)

from apps.iam.views import resources

dispatcher = resources.ResourceApiDispatcher(
    Permission.get_iam_client(settings.DEFAULT_TENANT_ID), settings.BK_IAM_SYSTEM_ID
)
dispatcher.register("collection", CollectionResourceProvider())
dispatcher.register("es_source", EsSourceResourceProvider())
dispatcher.register("indices", IndicesResourceProvider())


router = routers.DefaultRouter(trailing_slash=True)

router.register(r"meta", meta.MetaViewSet, basename="meta")


urlpatterns = [re_path(r"^", include(router.urls)), re_path(r"^resource/$", dispatcher.as_view([login_exempt]))]
