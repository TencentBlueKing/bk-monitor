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
import datetime
import json
import logging
import re

import arrow
import curator
import elasticsearch
import elasticsearch5
import elasticsearch6
from django.conf import settings
from elasticsearch_dsl import Search

from bkmonitor.utils.elasticsearch.curator import IndexList

logger = logging.getLogger(__name__)


class ILM:
    ES_REMOVE_TYPE_VERSION = 7

    def __init__(
        self,
        index_name: str,
        index_body: dict,
        es_client,
        es_version: int = 7,
        date_format: str = "%Y%m%d",
        slice_gap: int = 120,
        slice_size: int = 500,
        retention: int = 30,
        enable: bool = True,
        warm_phase_days: int = 0,
        warm_phase_settings: dict = None,
        use_template: bool = False,
        reindex_enabled: bool = False,
        reindex_query: dict = None,
    ):
        self.index_name = index_name
        self.index_body = index_body
        self.es_version = es_version
        self.es_client = es_client
        self.date_format = date_format
        self.slice_gap = slice_gap
        self.slice_size = slice_size
        self.retention = retention
        self.enable = enable
        self.warm_phase_days = warm_phase_days
        self.warm_phase_settings = warm_phase_settings
        self.use_template = use_template
        self.reindex_enabled = reindex_enabled
        self.reindex_query = reindex_query

    def get_client(self):
        return self.es_client

    def search_format(self):
        return f"{self.index_name}_*"

    @property
    def index_re(self):
        """获取这个存储的正则匹配内容"""
        pattern = r"{}_(?P<datetime>\d+)_(?P<index>\d+)".format(self.index_name)
        return re.compile(pattern)

    def index_exist(self):
        """
        判断该index是否已经存在
        :return: True | False
        """
        es_client = self.get_client()
        stat_info_list = es_client.indices.stats(self.search_format())
        if stat_info_list["indices"]:
            logger.debug("index_name->[%s] found index list->[%s]", self.index_name, str(stat_info_list))
            return True
        logger.debug("index_name->[%s] no index", self.index_name)
        return False

    def current_index_info(self):
        """
        返回当前使用的最新index相关的信息
        :return: {
            "datetime_object": max_datetime_object,
            "index": 0,
            "size": 123123,  # index大小，单位byte
        }
        """
        es_client = self.get_client()
        # stats格式为：{
        #   "indices": {
        #       "${index_name}": {
        #           "total": {
        #               "store": {
        #                   "size_in_bytes": 1000
        #               }
        #           }
        #       }
        #   }
        # }
        stat_info_list = es_client.indices.stats(self.search_format())

        # 1.1 判断获取最新的index
        datetime_index_list = []
        for stat_index_name in list(stat_info_list["indices"].keys()):

            re_result = self.index_re.match(stat_index_name)
            if re_result is None:
                # 去掉一个整体index的计数
                logger.warning("index->[%s] is not match re, maybe something go wrong?", stat_index_name)
                continue

            # 获取实际的count及时间对象
            current_index = int(re_result.group("index"))
            current_datetime_str = re_result.group("datetime")

            current_datetime_object = datetime.datetime.strptime(current_datetime_str, self.date_format)

            datetime_index_list.append((current_datetime_object, current_index))

        # 如果datetime_index_list为空，说明没找到任何可用的index
        if not datetime_index_list:
            logger.info("index->[%s] has no index now, will raise a fake not found error", self.index_name)
            raise elasticsearch5.NotFoundError(self.index_name)

        datetime_index_list.sort(reverse=True)
        max_datetime_object, max_index = datetime_index_list[0]

        return {
            "datetime_object": max_datetime_object,
            "index": max_index,
            "size": stat_info_list["indices"][f"{self.make_index_name(max_datetime_object, max_index)}"]["primaries"][
                "store"
            ]["size_in_bytes"],
        }

    def make_index_name(self, datetime_object, index):
        """根据传入的时间和index，创建返回一个index名"""
        return f"{self.index_name}_{datetime_object.strftime(self.date_format)}_{index}"

    def create_or_update_aliases(self, ahead_time=1440):
        """
        更新alias，如果有已存在的alias，则将其指向最新的index，并根据ahead_time前向预留一定的alias
        """
        es_client = self.get_client()
        current_index_info = self.current_index_info()
        last_index_name = self.make_index_name(current_index_info["datetime_object"], current_index_info["index"])

        now_datetime_object = datetime.datetime.utcnow()

        now_gap = 0
        index_name = self.index_name

        created_alias = []

        while now_gap <= ahead_time:

            round_time = now_datetime_object + datetime.timedelta(minutes=now_gap)
            round_time_str = round_time.strftime(self.date_format)

            try:
                round_alias_name = f"write_{round_time_str}_{index_name}"
                round_read_alias_name = f"{index_name}_{round_time_str}_read"

                # 3.1 判断这个别名是否有指向旧的index，如果存在则需要解除
                try:
                    # 此处是非通配的别名，所以会有NotFound的异常
                    index_list = es_client.indices.get_alias(name=round_alias_name).keys()

                    # 排除已经指向最新index的alias
                    delete_list = []
                    for alias_index in index_list:
                        if alias_index != last_index_name:
                            delete_list.append(alias_index)

                    logger.debug(
                        "index_name->[%s] found alias_name->[%s] is relay with index->[%s] all will be deleted.",
                        self.index_name,
                        round_alias_name,
                        delete_list,
                    )
                except (elasticsearch5.NotFoundError, elasticsearch6.NotFoundError, elasticsearch.NotFoundError):
                    # 可能是在创建未来的alias，所以不一定会有别名关联的index
                    logger.debug(
                        "index_name->[%s] alias_name->[%s] found not index relay, will not delete any thing.",
                        self.index_name,
                        round_alias_name,
                    )
                    delete_list = []

                # 3.2 需要将循环中的别名都指向了最新的index
                es_client.indices.update_aliases(
                    body={
                        "actions": [
                            {"add": {"index": last_index_name, "alias": round_alias_name}},
                            {"add": {"index": last_index_name, "alias": round_read_alias_name}},
                        ]
                    }
                )

                created_alias.append(round_alias_name)
                created_alias.append(round_read_alias_name)

                logger.info(
                    "index_name->[%s] now has index->[%s] and alias->[%s | %s]",
                    self.index_name,
                    last_index_name,
                    round_alias_name,
                    round_read_alias_name,
                )

                # 只有当index相关列表不为空的时候，才会进行别名关联清理
                if len(delete_list) != 0:
                    index_list_str = ",".join(delete_list)
                    es_client.indices.delete_alias(index=index_list_str, name=round_alias_name)
                    logger.info(
                        "index_name->[%s] index->[%s] alias->[%s] relations now had delete.",
                        self.index_name,
                        delete_list,
                        round_alias_name,
                    )

            finally:
                logger.info("all operations for index->[{}] gap->[{}] now is done.".format(self.index_name, now_gap))
                now_gap += self.slice_gap

        return {
            "last_index_name": last_index_name,
            "created_alias": created_alias,
        }

    def create_index_and_aliases(self, ahead_time=1440):
        new_index_name = self.create_index()
        aliases = self.create_or_update_aliases(ahead_time)
        return new_index_name, aliases

    def update_index_and_aliases(self, ahead_time=1440):
        new_index_name, old_index_name = self.update_index()
        aliases = self.create_or_update_aliases(ahead_time)

        if new_index_name and old_index_name:
            self.reindex(new_index_name, old_index_name)

        return new_index_name, aliases

    def is_index_enable(self):
        """判断index是否启用中"""
        return self.enable

    def create_index(self):
        """
        创建全新的index序列，以及指向它的全新alias
        """
        if not self.is_index_enable():
            return False

        now_datetime_object = datetime.datetime.utcnow()
        es_client = self.get_client()
        new_index_name = self.make_index_name(now_datetime_object, 0)
        # 创建index
        if self.use_template:
            # 如果使用了索引模板，创建索引时无需传body
            es_client.indices.create(index=new_index_name, params={"request_timeout": 30})
        else:
            es_client.indices.create(index=new_index_name, body=self.index_body, params={"request_timeout": 30})
        logger.info("index_name->[%s] has created new index->[%s]", self.index_name, new_index_name)
        return new_index_name

    def update_index(self):
        """
        判断index是否需要分裂，并提前建立index别名的功能
        此处仍然保留每个小时创建新的索引，主要是为了在发生异常的时候，可以降低影响的索引范围（最多一个小时）
        :return: 二元组 new_index_name, old_index_name
        """
        if not self.is_index_enable():
            return None, None

        now_datetime_object = datetime.datetime.utcnow()

        # 0. 获取客户端
        es_client = self.get_client()

        # 1. 获取当前最新的index
        try:
            current_index_info = self.current_index_info()
            last_index_name = self.make_index_name(current_index_info["datetime_object"], current_index_info["index"])
            index_size_in_byte = current_index_info["size"]

        except (elasticsearch5.NotFoundError, elasticsearch6.NotFoundError, elasticsearch.NotFoundError):
            logger.warning(
                "attention! index_name->[%s] can not found any index to update,will do create function", self.index_name
            )
            return self.create_index(), None

        # 1.1 兼容旧任务，将不合理的超前index清理掉
        # 如果最新时间超前了，要对应处理一下,通常发生在旧任务应用新的es代码过程中
        # 循环处理，以应对预留时间被手动加长,导致超前index有多个的场景
        while now_datetime_object < current_index_info["datetime_object"]:
            logger.warning(
                "index_name->[%s] delete index->[%s] because it has ahead time", self.index_name, last_index_name
            )
            es_client.indices.delete(index=last_index_name)
            # 重新获取最新的index，这里没做防护，默认存在超前的index，就一定存在不超前的可用index
            current_index_info = self.current_index_info()
            last_index_name = self.make_index_name(current_index_info["datetime_object"], current_index_info["index"])

        # 2. 判断index是否需要分割
        # 如果是小于分割大小的，不必进行处理
        should_create = False
        if index_size_in_byte / 1024.0 / 1024.0 / 1024.0 > self.slice_size:
            logger.info(
                "index_name->[%s] index->[%s] current_size->[%s] is larger than slice size->[%s], "
                "create new index slice",
                self.index_name,
                last_index_name,
                index_size_in_byte,
                self.slice_size,
            )
            should_create = True

        # 当不需要创建的时候, 需要判断mapping是否修改
        if not should_create:

            is_same_mapping, should_create = self.is_mapping_same(last_index_name)

            # mapping一致地情况，直接返回
            if is_same_mapping:
                logger.info(
                    "index_name->[%s] index->[%s] everything is ok, nothing to do",
                    self.index_name,
                    last_index_name,
                )
                return None, last_index_name

            # mapping不一致并且仅新增字段地时候，直接修改mapping
            if not should_create:
                logger.info(
                    "index_name->[%s] index->[%s] mapping is not the same, will reset the mapping",
                    self.index_name,
                    last_index_name,
                )
                es_client.indices.put_mapping(
                    index=last_index_name, body={"properties": self.get_database_properties()}
                )
                return None, last_index_name

        #  其他情况，直接创建新索引
        logger.info(
            "index_name->[%s] index->[%s] mapping is not the same, will create the new",
            self.index_name,
            last_index_name,
        )

        new_index = 0
        # 判断日期是否当前的时期或时间
        if now_datetime_object.strftime(self.date_format) == current_index_info["datetime_object"].strftime(
            self.date_format
        ):

            # 如果当前index并没有写入过数据(count==0),则对其进行删除重建操作即可
            if es_client.count(index=last_index_name).get("count", 0) == 0:
                new_index = current_index_info["index"]
                es_client.indices.delete(index=last_index_name)
                logger.info(
                    "index_name->[%s] has index->[%s] which has not data, will be deleted for new index create.",
                    self.index_name,
                    last_index_name,
                )
            # 否则原来的index不动，新增一个index，并把alias指向过去
            else:
                new_index = current_index_info["index"] + 1
                logger.info(
                    "index_name->[%s] index->[%s] has data, so new index will create", self.index_name, new_index
                )

        # 但凡涉及到index新增，都使用v2版本的格式
        new_index_name = self.make_index_name(now_datetime_object, new_index)
        logger.info("index_name->[%s] will create new index->[%s]", self.index_name, new_index_name)

        # 2.1 创建新的index
        if self.use_template:
            # 如果使用了索引模板，创建索引时无需传body
            es_client.indices.create(index=new_index_name, params={"request_timeout": 30})
        else:
            es_client.indices.create(index=new_index_name, body=self.index_body, params={"request_timeout": 30})
        logger.info("index_name->[%s] new index_name->[%s] is created now", self.index_name, new_index_name)

        return new_index_name, last_index_name

    @property
    def write_alias_re(self):
        """获取写入别名的正则匹配"""
        pattern = r"write_(?P<datetime>\d+)_{}".format(self.index_name)
        return re.compile(pattern)

    @property
    def old_write_alias_re(self):
        """获取旧版写入别名的正则匹配"""
        pattern = r"{}_(?P<datetime>\d+)_write".format(self.index_name)
        return re.compile(pattern)

    @property
    def read_alias_re(self):
        """获取读取别名的正则匹配"""
        pattern = r"{}_(?P<datetime>\d+)_read".format(self.index_name)
        return re.compile(pattern)

    def get_alias_datetime_str(self, alias_name):
        # 判断是否是需要的格式
        # write_xxx
        alias_write_re = self.write_alias_re
        # xxx_read
        alias_read_re = self.read_alias_re
        # xxx_write
        old_write_alias_re = self.old_write_alias_re

        # 匹配并获取时间字符串
        write_result = alias_write_re.match(alias_name)
        if write_result is not None:
            return write_result.group("datetime")
        read_result = alias_read_re.match(alias_name)
        if read_result is not None:
            return read_result.group("datetime")
        old_write_result = old_write_alias_re.match(alias_name)
        if old_write_result is not None:
            return old_write_result.group("datetime")
        return ""

    def group_expired_alias(self, alias_list, expired_days):
        """
        将每个索引的别名进行分组，分为已过期和未过期
        :param alias_list: 别名列表，格式
        {
            "2_bkmonitor_event_1500498_20200603_0":{
                "aliases":{
                    "2_bkmonitor_event_1500498_20200603_write":{},
                    "write_20200603_2_bkmonitor_event_1500498":{}
                }
            }
        }
        :param expired_days: 过期时间，单位天
        :return: 格式
        {
            "2_bkmonitor_event_1500498_20200603_0": {
                "expired_alias": ["write_20200603_2_bkmonitor_event_1500498"],
                "not_expired_alias: ["write_20200602_2_bkmonitor_event_1500498"],
            }
        }
        """
        logger.info("index_name->[%s] filtering expired alias before %s days.", self.index_name, expired_days)

        expired_datetime_point = datetime.datetime.utcnow() - datetime.timedelta(days=expired_days)

        filter_result = {}

        for index_name, alias_info in alias_list.items():

            expired_alias = []
            not_expired_alias = []

            # 遍历所有的alias是否需要删除
            for alias_name in alias_info["aliases"]:

                logger.info("going to process index_name->[%s] ", self.index_name)

                # 判断这个alias是否命中正则，是否需要删除的范围内
                datetime_str = self.get_alias_datetime_str(alias_name)

                if not datetime_str:
                    # 匹配不上时间字符串的情况，一般是因为用户自行创建了别名
                    if settings.ES_RETAIN_INVALID_ALIAS:
                        # 保留不合法的别名，将该别名视为未过期
                        not_expired_alias.append(alias_name)
                        logger.info(
                            "index_name->[%s] index->[%s] got alias_name->[%s] " "not match datetime str, retain it.",
                            self.index_name,
                            index_name,
                            alias_name,
                        )
                    else:
                        # 不保留不合法的别名，将该别名视为已过期
                        expired_alias.append(alias_name)
                        logger.info(
                            "index_name->[%s] index->[%s] got alias_name->[%s] not match datetime str, remove it.",
                            self.index_name,
                            index_name,
                            alias_name,
                        )
                    continue

                try:
                    index_datetime_object = datetime.datetime.strptime(datetime_str, self.date_format)
                except ValueError:
                    logger.error(
                        "index_name->[%s] got index->[%s] with datetime_str->[%s] which is not match date_format->"
                        "[%s], something go wrong?",
                        self.index_name,
                        index_name,
                        datetime_str,
                        self.date_format,
                    )
                    continue

                # 检查当前别名是否过期
                logger.info("%s %s", index_datetime_object, expired_datetime_point)
                if index_datetime_object > expired_datetime_point:
                    logger.info(
                        "index_name->[%s] got alias->[%s] for index->[%s] is not expired.",
                        self.index_name,
                        alias_name,
                        index_name,
                    )
                    not_expired_alias.append(alias_name)
                else:
                    logger.info(
                        "index_name->[%s] got alias->[%s] for index->[%s] is expired.",
                        self.index_name,
                        alias_name,
                        index_name,
                    )
                    expired_alias.append(alias_name)

            filter_result[index_name] = {
                "expired_alias": expired_alias,
                "not_expired_alias": not_expired_alias,
            }

        return filter_result

    def clean_index(self):
        """
        清理过期的写入别名及index的操作，如果发现某个index已经没有写入别名，那么将会清理该index
        :return: int(清理的index个数) | raise Exception
        """
        # 获取所有的写入别名
        es_client = self.get_client()

        alias_list = es_client.indices.get_alias(index=f"*{self.index_name}_*_*")

        filter_result = self.group_expired_alias(alias_list, self.retention)

        deleted_index = []
        deleted_alias = {}

        for index_name, alias_info in filter_result.items():
            if not alias_info["not_expired_alias"]:
                # 如果已经不存在未过期的别名，则将索引删除
                logger.info(
                    "index_name->[%s] has not alias need to keep, will delete the index->[%s].",
                    self.index_name,
                    index_name,
                )
                es_client.indices.delete(index=index_name)
                deleted_index.append(index_name)
                logger.warning("index_name->[%s] index->[%s] is deleted now.", self.index_name, index_name)
                continue

            elif alias_info["expired_alias"]:
                # 如果存在已过期的别名，则将别名删除
                logger.info(
                    "index_name->[%s] delete_alias_list->[%s] is not empty will delete the alias.",
                    self.index_name,
                    alias_info["expired_alias"],
                )
                es_client.indices.delete_alias(index=index_name, name=",".join(alias_info["expired_alias"]))
                deleted_alias[index_name] = alias_info["expired_alias"]
                logger.warning(
                    "index_name->[%s] delete_alias_list->[%s] is deleted.", self.index_name, alias_info["expired_alias"]
                )

            logger.info("index_name->[%s] index->[%s] is process done.", self.index_name, index_name)

        logger.info("index_name->[%s] is process done.", self.index_name)

        return {
            "deleted_index": deleted_index,
            "deleted_alias": deleted_alias,
        }

    def get_database_properties(self):
        # 判断字段列表是否一致的: _type在ES7.x版本后取消
        if self.es_version < self.ES_REMOVE_TYPE_VERSION:
            es_properties = self.index_body["mappings"][self.index_name]["properties"]
        else:
            es_properties = self.index_body["mappings"]["properties"]
        return es_properties

    def is_mapping_same(self, index_name):
        """
        判断一个index的mapping和数据库当前记录的配置是否一致
        :param index_name: 当前的时间字符串
        :return: {
            # 是否需要创建新的索引
            "should_create": True | False,
            # 新的索引名
            "index": "index_name",
            # 新索引对应的写别名
            "write_alias": "write_alias"
        }
        """
        es_client = self.get_client()
        should_create = True

        # 判断最后一个index的配置是否和数据库的一致，如果不是，表示需要重建
        try:
            es_mappings = es_client.indices.get_mapping(index=index_name)[index_name]["mappings"]
            if es_mappings.get(self.index_name):
                current_mapping = es_mappings[self.index_name]["properties"]
            else:
                current_mapping = es_mappings["properties"]

        except (KeyError, elasticsearch5.NotFoundError, elasticsearch6.NotFoundError, elasticsearch.NotFoundError):
            logger.info("index_name->[{}] is not exists, will think the mapping is not same.".format(index_name))
            return False, should_create

        # 判断字段列表是否一致的: _type在ES7.x版本后取消
        es_properties = self.get_database_properties()

        database_field_list = list(es_properties.keys())
        current_field_list = list(current_mapping.keys())

        # 实际 mapping 比模型定义的 mapping 多一些字段也没关系，不处理
        field_diff_set = set(database_field_list) - set(current_field_list)

        # 遍历判断字段的内容是否完全一致
        for field_name, database_config in list(es_properties.items()):
            if field_name in field_diff_set:
                # 多出来的字段，不需要考虑
                continue

            current_config = current_mapping[field_name]
            # 判断具体的内容是否一致，只要以下这些字段
            for field_config in ["type", "include_in_all", "doc_values", "format", "properties", "fields"]:
                database_value = database_config.get(field_config, None)
                current_value = current_config.get(field_config, None)

                if field_config == "type" and current_value is None:
                    logger.info(
                        "index_name->[{}] index->[{}] field->[{}] config->[{}] database->[{}] es config is None, "
                        "so nothing will do.".format(
                            self.index_name, index_name, field_name, field_config, database_value
                        )
                    )
                    continue

                if database_value != current_value:
                    logger.info(
                        "index_name->[{}] index->[{}] field->[{}] config->[{}] database->[{}] es->[{}] is "
                        "not the same, ".format(
                            self.index_name, index_name, field_name, field_config, database_value, current_value
                        )
                    )
                    return False, should_create

        should_create = False
        if field_diff_set:
            return False, should_create

        logger.debug("index_name->[{}] index->[{}] field config same.".format(self.index_name, index_name))
        return True, should_create

    def reallocate_index(self):
        """
        重新分配索引所在的节点
        """
        if self.warm_phase_days <= 0:
            logger.info("index_name->[%s] warm_phase_days is not set, skip.", self.index_name)
            return

        warm_phase_settings = self.warm_phase_settings
        allocation_attr_name = warm_phase_settings["allocation_attr_name"]
        allocation_attr_value = warm_phase_settings["allocation_attr_value"]
        allocation_type = warm_phase_settings["allocation_type"]

        es_client = self.get_client()

        # 获取索引对应的别名
        alias_list = es_client.indices.get_alias(index=f"*{self.index_name}_*_*")

        filter_result = self.group_expired_alias(alias_list, self.warm_phase_days)

        # 如果存在未过期的别名，那说明这个索引仍在被写入，不能把它切换到冷节点
        reallocate_index_list = [
            index_name for index_name, alias in filter_result.items() if not alias["not_expired_alias"]
        ]

        # 如果没有过期的索引，则返回
        if not reallocate_index_list:
            logger.info(
                "index_name->[%s] no index should be allocated, skip.",
                self.index_name,
            )
            return

        ilo = IndexList(es_client, index_names=reallocate_index_list)
        # 过滤掉已经被 allocate 过的 index
        ilo.filter_allocated(key=allocation_attr_name, value=allocation_attr_value, allocation_type=allocation_type)

        # 过滤后索引为空，则返回
        if not ilo.indices:
            logger.info(
                "index_name->[%s] no index should be allocated, skip.",
                self.index_name,
            )
            return

        logger.info(
            "index_name->[%s] ready to reallocate with settings: days(%s), name(%s), value(%s), type(%s), "
            "for index_list: %s",
            self.index_name,
            self.warm_phase_days,
            allocation_attr_name,
            allocation_attr_value,
            allocation_type,
            ilo.indices,
        )

        try:
            # 执行 allocation 动作
            allocation = curator.Allocation(
                ilo=ilo,
                key=allocation_attr_name,
                value=allocation_attr_value,
                allocation_type=allocation_type,
            )
            allocation.do_action()
        except curator.NoIndices:
            # 过滤后索引列表为空，则返回
            if not ilo.indices:
                logger.info(
                    "index_name->[%s] no index should be allocated, skip.",
                    self.index_name,
                )
                return
        except Exception as e:
            logger.exception("index_name->[%s] error occurred when allocate: %s", self.index_name, e)
        else:
            logger.info("index_name->[%s] index->[%s] allocate success!", self.index_name, ilo.indices)

    def reindex(self, new_index_name, old_index_name, request_timeout=300, delete_old_docs=True):
        if not self.reindex_enabled:
            # 未开启索引重建，不操作
            return

        if not new_index_name or not old_index_name:
            # 索引名称为空，不操作
            return

        if new_index_name == old_index_name:
            # 索引名称相同，不操作
            return

        re_result = self.index_re.match(new_index_name)
        if re_result is None:
            # 去掉一个整体index的计数
            logger.warning("index->[%s] is not match re, maybe something go wrong?", new_index_name)
            return

        current_datetime_str = re_result.group("datetime")

        current_datetime_object = datetime.datetime.strptime(current_datetime_str, self.date_format)
        start_ts = int(arrow.get(current_datetime_object).timestamp)

        search = Search().from_dict(self.reindex_query or {}).filter("range", create_time={"gte": start_ts})
        search_dsl = search.to_dict()

        reindex_params = {
            "conflicts": "proceed",
            "source": {
                "index": old_index_name,
                "query": search_dsl["query"],
            },
            "dest": {
                "index": new_index_name,
                "op_type": "create",
            },
        }

        logger.info("reindex [%s]->[%s] with params: %s", old_index_name, new_index_name, json.dumps(reindex_params))

        try:
            reindex_result = self.es_client.reindex(reindex_params, params={"request_timeout": request_timeout})
        except Exception as e:
            logger.exception("reindex [%s]->[%s] call reindex failed: %s", old_index_name, new_index_name, e)
            return

        print("reindex [{}]->[{}] reindex result: {}".format(old_index_name, new_index_name, reindex_result))
        logger.info("reindex [%s]->[%s] reindex result: %s", old_index_name, new_index_name, reindex_result)

        if not delete_old_docs:
            return

        try:
            delete_result = self.es_client.delete_by_query(
                old_index_name, search_dsl, params={"request_timeout": request_timeout}
            )
        except Exception as e:
            logger.exception("reindex [%s]->[%s] call delete_by_query failed: %s", old_index_name, new_index_name, e)
            return

        print("reindex [{}]->[{}] delete old document result: {}".format(old_index_name, new_index_name, delete_result))
        logger.info("reindex [%s]->[%s] delete old document result: %s", old_index_name, new_index_name, delete_result)
