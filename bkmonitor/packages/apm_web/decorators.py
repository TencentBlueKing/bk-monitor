"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import wraps

from apm_web.models import UserVisitRecord


def user_visit_record(func):
    """
    APM 用户访问记录装饰器

    Notice:
    - 仅限用于 APM 模块，如果其他模块也需要类似的能力，需要重新提取
    - 仅限放置在 基类为 core.drf_resource.viewsets.ResourceRouteResource 的 decorators 属性中
    """

    @wraps(func)
    def wrapper(obj, request, *args, **kwargs):
        bk_biz_id = request.biz_id
        username = request.user.username
        request_path = request.path_info
        app_name = request.data.get("app_name", "") or request.query_params.get("app_name", "")

        # 必须是访问了应用，才能算在请求记录里 (后续的统计需要关联应用的创建者)
        if app_name:
            try:
                UserVisitRecord.objects.create(
                    bk_biz_id=bk_biz_id,
                    app_name=app_name,
                    func_name=request_path,
                    created_by=username,
                )
            except Exception:  # pylint: disable=broad-except
                # 记录失败不能影响业务正常逻辑
                pass

        return func(obj, request, *args, **kwargs)

    return wrapper
