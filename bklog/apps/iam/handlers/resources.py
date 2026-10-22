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

import abc

from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from iam import Resource

from apps.iam.exceptions import ResourceNotExistError
from bkm_space.utils import space_uid_to_bk_biz_id


class ResourceMeta(metaclass=abc.ABCMeta):
    """
    资源定义
    """

    system_id: str = ""
    id: str = ""
    name: str = ""
    selection_mode: str = ""
    related_instance_selections: list = ""

    @classmethod
    def to_json(cls):
        return {
            "system_id": cls.system_id,
            "id": cls.id,
            "selection_mode": cls.selection_mode,
            "related_instance_selections": cls.related_instance_selections,
        }

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        attribute = attribute or {}
        # 补充路径信息
        if "space_uid" in attribute:
            bk_biz_id = space_uid_to_bk_biz_id(attribute["space_uid"])
            attribute.update({"_bk_iam_path_": f"/{Business.id},{bk_biz_id}/"})
        elif "bk_biz_id" in attribute:
            attribute.update({"_bk_iam_path_": "/{},{}/".format(Business.id, attribute["bk_biz_id"])})
        return Resource(cls.system_id, cls.id, str(instance_id), attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建资源实例（带实例名称）可由子类重载
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        return cls.create_simple_instance(instance_id, attribute)


class Business(ResourceMeta):
    """
    CMDB业务
    """

    system_id = "bk_monitorv3"
    id = "space"
    name = gettext_lazy("空间")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "space_list"}]

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        from apps.iam.views.resources import SpaceResourceProvider

        metadata = SpaceResourceProvider.get_instance_attributes(instance_id)
        attribute = attribute or {}
        attribute.update(metadata)
        return Resource(cls.system_id, cls.id, metadata["id"], attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = cls.create_simple_instance(instance_id, attribute)
        return resource


class Collection(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "collection"
    name = gettext_lazy("采集项")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "collection_list_v2"}]

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        from apps.iam.views.resources import CollectionResourceProvider

        resource = super().create_simple_instance(instance_id, attribute)
        if not resource.attribute:
            resource.attribute = CollectionResourceProvider.get_instance_attributes(instance_id)
        return resource


class EsSource(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "es_source"
    name = gettext_lazy("ES源")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "es_source_list_v2"}]

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        from apps.iam.views.resources import EsSourceResourceProvider

        resource = super().create_simple_instance(instance_id, attribute)
        if not resource.attribute:
            resource.attribute = EsSourceResourceProvider.get_instance_attributes(instance_id)
        return resource


class Indices(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "indices"
    name = gettext_lazy("索引集")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "indices_list_v2"}]

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        from apps.iam.views.resources import IndicesResourceProvider

        resource = super().create_simple_instance(instance_id, attribute)
        if not resource.attribute:
            resource.attribute = IndicesResourceProvider.get_instance_attributes(instance_id)
        return resource


class ResourceEnum:
    """
    资源类型枚举
    """

    BUSINESS = Business
    COLLECTION = Collection
    ES_SOURCE = EsSource
    INDICES = Indices


_all_resources = {resource.id: resource for resource in ResourceEnum.__dict__.values() if hasattr(resource, "id")}


def get_resource_by_id(resource_id: str) -> ResourceMeta:
    """
    根据资源ID获取资源
    """
    if resource_id not in _all_resources:
        raise ResourceNotExistError(_("资源ID不存在：{resource_id}").format(resource_id=resource_id))

    return _all_resources[resource_id]
