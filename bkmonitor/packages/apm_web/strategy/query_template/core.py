"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
from .local import LocalQueryTemplateSet
from bkmonitor.query_template.core import QueryTemplateWrapper


class BaseQueryTemplateWrapperFactory(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def get_wrapper(cls, bk_biz_id: int, name: str) -> QueryTemplateWrapper | None:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def get_wrappers(cls, keys: list[tuple[int, str]]) -> dict[tuple[int, str], "QueryTemplateWrapper"]:
        raise NotImplementedError


class LocalQueryTemplateWrapperFactory(BaseQueryTemplateWrapperFactory):
    _REGISTRY: dict[tuple[int, str], QueryTemplateWrapper] = {
        (template["bk_biz_id"], template["name"]): QueryTemplateWrapper.from_dict(
            {"namespace": LocalQueryTemplateSet.NAMESPACE, **template}
        )
        for template in LocalQueryTemplateSet.QUERY_TEMPLATES
    }

    @classmethod
    def get_wrapper(cls, bk_biz_id: int, name: str) -> QueryTemplateWrapper | None:
        return cls._REGISTRY.get((bk_biz_id, name))

    @classmethod
    def get_wrappers(cls, keys: list[tuple[int, str]]) -> dict[tuple[int, str], "QueryTemplateWrapper"]:
        wrappers: dict[tuple[int, str], QueryTemplateWrapper] = {}
        for key in keys:
            wrapper = cls._REGISTRY.get(key)
            if wrapper:
                wrappers[key] = wrapper
        return wrappers


class QueryTemplateWrapperFactory(BaseQueryTemplateWrapperFactory):
    _LOCAL_FACTORY: BaseQueryTemplateWrapperFactory = LocalQueryTemplateWrapperFactory

    @classmethod
    def get_wrapper(cls, bk_biz_id: int, name: str) -> QueryTemplateWrapper | None:
        qtw: QueryTemplateWrapper | None = cls._LOCAL_FACTORY.get_wrapper(bk_biz_id, name)
        if qtw:
            return qtw

        return QueryTemplateWrapper.from_unique_key(bk_biz_id, name)

    @classmethod
    def get_wrappers(cls, keys: list[tuple[int, str]]) -> dict[tuple[int, str], "QueryTemplateWrapper"]:
        wrappers: dict[tuple[int, str], QueryTemplateWrapper] = cls._LOCAL_FACTORY.get_wrappers(keys)

        miss_keys: set[tuple[int, str]] = set(keys) - set(wrappers.keys())
        if miss_keys:
            wrappers.update(QueryTemplateWrapper.from_unique_keys(list(miss_keys)))
        return wrappers
