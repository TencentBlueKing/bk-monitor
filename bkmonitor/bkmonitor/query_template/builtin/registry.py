"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from bkmonitor.models.query_template import QueryTemplate
from constants.query_template import GLOBAL_BIZ_ID

from .. import constants
from ..core import QueryTemplateWrapper
from .apm import APMQueryTemplateSet
from .k8s import K8SQueryTemplateSet

logger = logging.getLogger(__name__)

BUILTIN_QUERY_TEMPLATES: list = [K8SQueryTemplateSet, APMQueryTemplateSet]


def register_builtin_templates() -> None:
    """注册内置查询模版"""

    namespaces: list[str] = [builtin.NAMESPACE for builtin in BUILTIN_QUERY_TEMPLATES]
    if constants.Namespace.DEFAULT.value in namespaces:
        raise ValueError("不允许使用 DEFAULT 作为内置查询模板的命名空间")

    remote_templ_name_id_map: dict[str, int] = {
        templ["name"]: templ["id"]
        for templ in QueryTemplate.origin_objects.filter(bk_biz_id=GLOBAL_BIZ_ID, namespace__in=namespaces).values(
            "id", "name"
        )
    }

    to_be_created: list[QueryTemplate] = []
    to_be_updated: list[QueryTemplate] = []
    local_templ_names: set[str] = set()
    remote_templ_names: set[str] = set(remote_templ_name_id_map.keys())
    for builtin in BUILTIN_QUERY_TEMPLATES:
        for template in builtin.QUERY_TEMPLATES:
            template["namespace"] = builtin.NAMESPACE
            try:
                qtw: QueryTemplateWrapper = QueryTemplateWrapper.from_dict(template)
            except ValidationError as e:
                logger.error("[register_builtin_templates] invalid template: %s, error: %s", template["name"], e)
                return

            obj: QueryTemplate = QueryTemplate(is_deleted=False, **qtw.to_dict())
            if qtw.name in remote_templ_names:
                obj.update_time = timezone.now()
                obj.update_user = "system"
                obj.pk = remote_templ_name_id_map[qtw.name]
                to_be_updated.append(obj)
            else:
                obj.create_user = obj.update_user = "system"
                to_be_created.append(obj)

            local_templ_names.add(qtw.name)

    QueryTemplate.origin_objects.bulk_create(to_be_created, batch_size=500)
    QueryTemplate.origin_objects.bulk_update(
        to_be_updated,
        fields=[
            "alias",
            "description",
            "expression",
            "functions",
            "query_configs",
            "variables",
            "is_deleted",
            "update_time",
            "update_user",
        ],
        batch_size=500,
    )

    to_be_deleted: list[str] = list(remote_templ_names - local_templ_names)
    QueryTemplate.origin_objects.filter(bk_biz_id=GLOBAL_BIZ_ID, name__in=to_be_deleted).update(is_deleted=True)

    logger.info(
        "[register_builtin_templates] created=%s, updated=%s, deleted=%s",
        len(to_be_created),
        len(to_be_updated),
        len(to_be_deleted),
    )
