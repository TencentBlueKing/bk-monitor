# -*- coding: utf-8 -*-
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
from collections import defaultdict

from django.utils.translation import gettext as _

from apps.log_clustering.exceptions import (
    DuplicateNameException,
    RegexTemplateNotExistException,
    RegexTemplateReferencedException,
)
from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs
from apps.log_clustering.models import ClusteringConfig, RegexTemplate
from apps.log_search.models import LogIndexSet


class RegexTemplateHandler(object):
    def list_templates(self, space_uid):
        # 空间是否有模板
        templates = RegexTemplate.objects.filter(space_uid=space_uid)
        if not templates.exists():
            instance, created = RegexTemplate.objects.get_or_create(
                space_uid=space_uid,
                template_name=_("系统默认"),
                predefined_varibles=OnlineTaskTrainingArgs.PREDEFINED_VARIBLES,
            )
            return [
                {
                    "id": instance.id,
                    "space_uid": instance.space_uid,
                    "template_name": instance.template_name,
                    "predefined_varibles": instance.predefined_varibles,
                    "related_index_set_list": [],
                }
            ]
        # 存在，返回列表
        data = templates.values("id", "space_uid", "template_name", "predefined_varibles")
        template_ids = [rt["id"] for rt in data]
        config_data = list(
            ClusteringConfig.objects.filter(regex_template_id__in=template_ids).values(
                "index_set_id", "regex_template_id"
            )
        )
        index_set_ids = [config["index_set_id"] for config in config_data]
        related_index_sets = list(
            LogIndexSet.objects.filter(index_set_id__in=index_set_ids).values("index_set_id", "index_set_name")
        )
        related_index_set_dict = {index_set["index_set_id"]: index_set for index_set in related_index_sets}

        # 引用该模板的 索引集id列表
        # 创建一个映射，从 regex_template_id 到 index_set_id 的列表
        template_to_index_set = defaultdict(list)
        for config in config_data:
            if config["regex_template_id"] not in template_to_index_set:
                template_to_index_set[config["regex_template_id"]] = []
            template_to_index_set[config["regex_template_id"]].append(config["index_set_id"])

        # 为每个 rt 添加 related_index_set_list
        for rt in data:
            index_set_ids = template_to_index_set.get(rt["id"], [])
            rt["related_index_set_list"] = [
                related_index_set_dict[index_set_id]
                for index_set_id in index_set_ids
                if index_set_id in related_index_set_dict
            ]
        return list(data)

    def create_template(self, space_uid, template_name):
        instance, created = RegexTemplate.objects.get_or_create(space_uid=space_uid, template_name=template_name)
        if not created:
            raise DuplicateNameException(DuplicateNameException.MESSAGE.format(name=template_name))
        instance.predefined_varibles = OnlineTaskTrainingArgs.PREDEFINED_VARIBLES
        instance.save()
        return {
            "id": instance.id,
            "space_uid": instance.space_uid,
            "template_name": instance.template_name,
            "predefined_varibles": instance.predefined_varibles,
            "related_index_set_list": [],
        }

    def update_template(self, template_id, template_name):
        instance = RegexTemplate.objects.filter(id=template_id).first()
        if not instance:
            raise RegexTemplateNotExistException(
                RegexTemplateNotExistException.MESSAGE.format(regex_template_id=template_id)
            )
        duplicate_name_template = RegexTemplate.objects.exclude(id=template_id).filter(
            space_uid=instance.space_uid, template_name=template_name
        )
        if duplicate_name_template.exists():
            raise DuplicateNameException(DuplicateNameException.MESSAGE.format(name=template_name))
        instance.template_name = template_name
        instance.save()
        return {"id": instance.id, "space_uid": instance.space_uid, "template_name": instance.template_name}

    def delete_template(self, template_id):
        instance = RegexTemplate.objects.filter(id=template_id).first()
        if not instance:
            raise RegexTemplateNotExistException(
                RegexTemplateNotExistException.MESSAGE.format(regex_template_id=template_id)
            )
        index_set_ids = list(
            ClusteringConfig.objects.filter(regex_template_id=instance.id).values_list("index_set_id", flat=True)
        )
        # 有关联的索引集
        if LogIndexSet.objects.filter(index_set_id__in=index_set_ids).exists():
            raise RegexTemplateReferencedException(
                RegexTemplateReferencedException.MESSAGE.format(regex_template_id=template_id)
            )
        instance.delete()
        return
