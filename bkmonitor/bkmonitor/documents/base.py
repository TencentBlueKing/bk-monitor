# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import arrow
from django.conf import settings
from django.db import models
from django_elasticsearch_dsl import Document
from elasticsearch_dsl import Date as BaseDate
from elasticsearch_dsl import MetaField

from bkmonitor.utils.elasticsearch.ilm import ILM


class BulkActionType:
    CREATE = "create"
    INDEX = "index"
    UPDATE = "update"
    DELETE = "delete"
    UPSERT = "upsert"


class BaseDocument(Document):
    INDEX_TIME_FORMAT = "%Y%m%d"
    DATE_FORMAT = "epoch_second"
    ES_REQUEST_TIMEOUT = 30  # ES 请求超时，默认30s
    ES_BULK_MAX_RETRIES = 3  # ES 批量写入最大重试次数

    # 索引轮转时，是否需要将部分数据转移至新索引（避免数据重复）
    REINDEX_ENABLED = False
    REINDEX_QUERY = None

    class Meta:
        dynamic = MetaField("false")

    class Django:
        # django_elasticsearch_dsl 要求必须绑定一个model才能使用 Document
        # 于是就假装绑定了一个，但实际上啥都不干
        model = models.Model

        # Ignore auto updating of Elasticsearch when a model is saved or deleted:
        ignore_signals = True

        # Don't perform an index refresh after every update (overrides global setting):
        auto_refresh = False

    def get_index_time(self):
        # 索引时间
        # 由于索引是根据时间拆分的，因此需要有一个时间字段判断存放到哪个索引
        raise NotImplementedError

    @classmethod
    def get_write_index_name(cls, index_name, date_str):
        return f"write_{date_str}_{index_name}"

    @classmethod
    def get_read_index_name(cls, index_name, date_str):
        return f"{index_name}_{date_str}_read"

    def _get_index(self, index=None, required=True):
        index_name = index
        if index is None:
            index_name = getattr(self._index, "_name", None)

        try:
            index_time = self.get_index_time()
            time_obj = arrow.get(index_time)
        except Exception:
            # 如果时间解析失败了，也不要紧，用当前的时间去生成索引
            time_obj = arrow.now()
        date_str = time_obj.strftime(self.INDEX_TIME_FORMAT)

        return self.get_write_index_name(index_name, date_str)

    def save(self, using=None, index=None, validate=False, skip_empty=True, **kwargs):
        # 注意：这里默认不进行校验，因为 elasticsearch-py 这个库对秒级 timestamp 的清洗有问题
        # 会无脑对 timestamp 除以 1000，所以跳过校验
        # 若需要打开校验，请慎重，请保证传进来的 timestamp 是一个毫秒级的时间戳
        if hasattr(self, "id"):
            # 需要在 Document 初始化时传入 id 参数，如果不给，则由ES自动生成
            self.meta["id"] = getattr(self, "id")
        return super(BaseDocument, self).save(using, index, validate, skip_empty, **kwargs)

    @classmethod
    def _format_index_by_day(cls, start_time, end_time):
        index_name = cls._index._name
        index = []

        if (end_time - start_time).days > 15:
            # 如果差距大于15天，就不枚举了，直接按月通配符
            return [cls.get_read_index_name(index_name, f"{start_time.strftime('%Y%m')}*")]

        current_time = start_time
        while current_time < end_time:
            index.append(cls.get_read_index_name(index_name, current_time.strftime("%Y%m%d")))
            current_time = current_time.replace(days=1)
        return index

    @classmethod
    def build_index_name_by_time(cls, start_time=None, end_time=None, days=0):
        """
        根据起止时间构建索引列表
        """
        index_name = cls._index._name

        # 如果没有提供索引，则根据开始和结束时间去生成索引列表
        if not start_time:
            start_time = arrow.now().replace(days=-days).floor("day")
        else:
            start_time = arrow.get(start_time).floor("day")
        if not end_time:
            end_time = arrow.now().ceil("day")
        else:
            end_time = arrow.get(end_time).ceil("day")

        index = []

        if start_time.year == end_time.year and start_time.month == end_time.month:
            # 当开始和结束时间是同一个月，从头到尾遍历一遍即可，每一天都是一个索引
            return cls._format_index_by_day(start_time, end_time)

        # 当开始和结束时间不在同一个月，那么
        # 1. 将开始月遍历一遍
        index.extend(cls._format_index_by_day(start_time, start_time.ceil("month")))

        # 2. 中间的每一个月遍历一遍，每个月对应一个索引
        current_time = start_time.floor("month").replace(months=1)
        current_end_time = end_time.ceil("month").replace(months=-1)
        while current_time < current_end_time:
            index.append(cls.get_read_index_name(index_name, f"{current_time.strftime('%Y%m')}*"))
            current_time = current_time.replace(months=1)

        # 3. 将结束月遍历一遍
        index.extend(cls._format_index_by_day(end_time.floor("month"), end_time))

        return index

    @classmethod
    def build_all_indices_read_index_name(cls):
        return f"{cls.Index.name}_*_read"

    @classmethod
    def search(cls, using=None, index=None, start_time=None, end_time=None, days=0, all_indices=False):
        if index:
            # 如果提供了特定的索引，则直接用它来查询
            return super().search(using=using, index=index).params(ignore_unavailable=True)
        if all_indices:
            return (
                super()
                .search(using=using, index=cls.build_all_indices_read_index_name())
                .params(ignore_unavailable=True)
            )
        index = cls.build_index_name_by_time(start_time, end_time, days)
        return super().search(using=using, index=index).params(ignore_unavailable=True)

    def prepare_action(self, action=BulkActionType.CREATE):
        data = {
            "_op_type": action,
            "_index": self._get_index(),
        }

        if hasattr(self, "id"):
            # 需要在 Document 初始化时传入 id 参数，如果不给，则由ES自动生成
            data["_id"] = getattr(self, "id")

        if action == BulkActionType.UPDATE:
            # update 参数需要特殊处理
            # 参考：https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html#bulk-update
            data["doc"] = self.to_dict()
        elif action == BulkActionType.UPSERT:
            # 如果存在，就增量更新；如果不存在，就直接插入
            # 参考：https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-update.html#doc_as_upsert
            data["_op_type"] = BulkActionType.UPDATE
            data["doc"] = self.to_dict()
            data["doc_as_upsert"] = True
        else:
            data["_source"] = self.to_dict() if action != BulkActionType.DELETE else None
        return data

    @classmethod
    def bulk_create(cls, documents, parallel=False, action=BulkActionType.CREATE, **kwargs):
        actions = []
        for doc in documents:
            actions.append(doc.prepare_action(action))
        params = dict(actions=actions, request_timeout=cls.ES_REQUEST_TIMEOUT, **kwargs)
        if parallel:
            return cls().parallel_bulk(**params)
        return cls().bulk(max_retries=cls.ES_BULK_MAX_RETRIES, **params)

    @classmethod
    def get_lifecycle_manager(cls):
        return ILM(
            index_name=cls.Index.name,
            index_body=cls._index.to_dict(),
            es_client=cls._index._get_connection(),
            slice_size=settings.FTA_ES_SLICE_SIZE or 50,
            retention=settings.FTA_ES_RETENTION or 365,
            slice_gap=1440,  # 创建索引的步长，1天
            date_format=cls.INDEX_TIME_FORMAT,  # 索引的日期格式
            use_template=True,
            reindex_enabled=cls.REINDEX_ENABLED,
            reindex_query=cls.REINDEX_QUERY,
        )

    @classmethod
    def upsert_template(cls):
        """
        更新索引模板
        """
        index_template = cls._index.as_template(template_name=cls.Index.name, pattern=f"{cls.Index.name}_*", order=100)
        index_template.save()

    @classmethod
    def rollover(cls):
        """
        索引轮转
        """
        ilm = cls.get_lifecycle_manager()

        cls.upsert_template()

        if ilm.index_exist():
            return ilm.update_index_and_aliases()

        return ilm.create_index_and_aliases()

    @classmethod
    def clear_expired_index(cls):
        """
        清理过期索引
        """
        ilm = cls.get_lifecycle_manager()
        return ilm.clean_index()


class Date(BaseDate):
    """
    重新封装的日期字段
    """

    def _deserialize(self, data):
        # 注意：这里默认不进行校验，因为 elasticsearch-py 这个库对秒级 timestamp 的清洗有问题
        # 会无脑对 timestamp 除以 1000，所以跳过校验
        return data
