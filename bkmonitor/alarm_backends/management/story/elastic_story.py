# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import sys

import elasticsearch5
from django.utils.functional import cached_property

from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    StepController,
    register_step,
    register_story,
)
from bkmonitor.documents import ALL_DOCUMENTS
from bkmonitor.utils.cache import InstanceCache
from metadata.models import EventGroup
from metadata.models.result_table import ResultTable
from metadata.models.storage import ClusterInfo, ESStorage


class ElasticEntry(StepController):
    def _check(self):
        return "-es" in sys.argv


es_controller = ElasticEntry()


@register_story()
class ElasticSearchStory(BaseStory):
    name = "ElasticSearch Healthz Check"


class ESStatusDown(Problem):
    def position(self):
        self.story.warning("确认ES集群是否可用")


class ClusterRed(Problem):
    def position(self):
        self.story.warning(
            "red: 未在集群中分配特定的shard，yellow: 表示已分配主shard，但未分配副本。" "index级别状态为由最坏的shard状态控制。群集状态由最差的index状态控制。"
        )


class IndexRed(Problem):
    def position(self):
        red = self.context.get("red_indices", [])
        yellow = self.context.get("yellow_indices", [])
        msg = ""
        if red:
            suffix = "" if len(red) <= 10 else "等{}".format(len(red))
            msg += f"red: {red[:10]}{suffix}"
        if yellow:
            suffix = "" if len(yellow) <= 10 else "等{}".format(len(yellow))
            msg += f"yellow: {yellow[:10]}{suffix}"
        self.story.warning(msg)


class InvalidIndexWithNoAlias(Problem):
    def position(self):
        no_alias_index_list = self.context.get("no_alias_index_list")
        self.story.warning("同步索引失败结果表: {}, 需要排查监控后台日志[kernel_metadata.log]确认同步失败原因".format(no_alias_index_list))


class TodayAliasNotFound(Problem):
    def position(self):
        self.story.warning("可能是索引轮转周期任务未成功执行，需要排查监控后台日志[kernel_metadata.log]确认原因")


class InvalidWriteIndex(Problem):
    def position(self):
        self.story.warning("数据在写入之前未能正确创建索引，需要删除该索引并将write_*开头的索引设置为不允许自动创建")


cache = InstanceCache()


@register_step(ElasticSearchStory)
class ElasticSearchStatusCheck(CheckStep):
    name = "check es status"
    controller = es_controller

    @cached_property
    def _cache(self):
        return cache

    def iter_cluster_healthz(self):
        for _id in ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_ES, version__gte="7").values_list(
            "cluster_id", flat=True
        ):
            healthz = self._cache.get(_id)
            if healthz is None:
                continue
            yield _id, healthz

    def es_client(self, cluster_id):
        if isinstance(cluster_id, ClusterInfo):
            cluster_info = cluster_id
        else:
            cluster_info = ClusterInfo.objects.get(cluster_id=cluster_id)

        connection_info = {
            "hosts": ["{}:{}".format(cluster_info.domain_name, cluster_info.port)],
            "verify_certs": cluster_info.is_ssl_verify,
            "use_ssl": cluster_info.is_ssl_verify,
        }
        if cluster_info.username is not None and cluster_info.password is not None:
            connection_info["http_auth"] = (cluster_info.username, cluster_info.password)
        return elasticsearch5.Elasticsearch(**connection_info)

    def check(self):
        p_list = []
        for cluster_info in ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_ES, version__gte="7"):
            healthz = self._cache.get(cluster_info.cluster_id)
            # 近期检测过，直接跳过
            if healthz:
                continue

            # 检测es可用性，并缓存下来
            api_url = f"http://{cluster_info.domain_name}:{cluster_info.port}"
            try:
                es_client = self.es_client(cluster_info)
                healthz = es_client.cluster.health()
            except Exception as e:
                info = "集群: {} 连接失败: {}:{}: {}".format(
                    cluster_info.cluster_name, cluster_info.domain_name, cluster_info.port, e
                )
                p_list.append(ESStatusDown(info, self.story, api_url=api_url, ex=e))
                continue
            else:
                status = healthz["status"]
                info = "集群: {}({}) 状态: {}:{}: {}!".format(
                    cluster_info.cluster_name,
                    healthz['cluster_name'],
                    cluster_info.domain_name,
                    cluster_info.port,
                    status,
                )
                if status == "green":
                    action = self.story.info
                else:
                    action = self.story.warning
                    p_list.append(ClusterRed(info, self.story))
                action(info)
                # 缓存10s
                self._cache.set(cluster_info.cluster_id, healthz, seconds=10)
        if p_list:
            return p_list


@register_step(ElasticSearchStory)
class IndexStatus(ElasticSearchStatusCheck):
    name = "check index status"

    def check(self):
        super(IndexStatus, self).check()
        p_list = []
        for cluster_id, healthz in self.iter_cluster_healthz():
            cluster_name = healthz["cluster_name"]
            active_shards = healthz["active_shards"]
            active_shards_percent_as_number = healthz["active_shards_percent_as_number"]
            info = (
                f"{cluster_name} active_shards: {active_shards},"
                f" active_shards_percent_as_number: {active_shards_percent_as_number}%"
            )
            if active_shards_percent_as_number == 100:
                self.story.info(info)
                continue
            else:
                self.story.warning(info)
            es_client = self.es_client(cluster_id)
            red_indices = [
                index["index"] for index in es_client.cat.indices(params={"health": "red", "format": "json"})
            ]
            yellow_indices = [
                index["index"] for index in es_client.cat.indices(params={"health": "yellow", "format": "json"})
            ]
            p_list.append(
                IndexRed(
                    "集群: {} 索引状态异常: red: 共{}; yellow: 共{}".format(cluster_name, len(red_indices), len(yellow_indices)),
                    self.story,
                    red_indices=red_indices,
                    yellow_indices=yellow_indices,
                )
            )

        if p_list:
            return p_list


@register_step(ElasticSearchStory)
class AliasCheck(ElasticSearchStatusCheck):
    name = "check invalid index with no alias"

    def check(self):
        p_list = []
        for cluster_id, healthz in self.iter_cluster_healthz():
            cluster_name = healthz["cluster_name"]
            alias_json = self.es_client(cluster_id).cat.aliases(params={"format": "json"})
            alias_index_list = {alias["alias"] for alias in alias_json}
            indices = ESStorage.objects.filter(storage_cluster_id=cluster_id)
            # 有效的索引： 1. EventGroup还有效， 2. ResultTable还有效
            active_table_ids = set(
                EventGroup.objects.filter(is_enable=True, is_delete=False).values_list("table_id", flat=True)
            )
            active_table_ids &= {i.index_name for i in indices}
            table_ids = ResultTable.objects.filter(
                table_id__in=active_table_ids, is_deleted=False, is_enable=True
            ).values_list("table_id", flat=True)

            no_alias_index_list = [
                table_id for table_id in table_ids if not list(filter(lambda i: table_id in i, alias_index_list))
            ]
            if no_alias_index_list:
                p = InvalidIndexWithNoAlias(
                    "集群: {} 索引同步异常: 共{}个结果表".format(cluster_name, len(no_alias_index_list)),
                    self.story,
                    no_alias_index_list=no_alias_index_list,
                )
                p_list.append(p)

        if p_list:
            return p_list


@register_step(ElasticSearchStory)
class FtaIndicesCheck(CheckStep):
    name = "check fta indices status"
    controller = StepController()

    def check(self):
        p_list = []

        for document_cls in ALL_DOCUMENTS:
            doc_name = document_cls.__name__.replace("Document", "")
            client = document_cls._index._get_connection()

            write_index_name = document_cls()._get_index()
            read_index_name = document_cls.build_index_name_by_time()[0]

            write_indices = [alias["index"] for alias in client.cat.aliases(write_index_name, format="json")]
            read_indices = [alias["index"] for alias in client.cat.aliases(read_index_name, format="json")]

            if (
                write_indices
                and read_indices
                and len(write_indices) == 1
                and len(read_indices) >= 1
                and write_indices[0] in read_indices
            ):
                self.story.info(f"[{doc_name}] check today alias [passed]: write{write_indices}, read{read_indices}")
            else:
                self.story.warning(f"[{doc_name}] check today alias [failed]: write{write_indices}, read{read_indices}")
                p = TodayAliasNotFound("[{}]无法根据当前别名获取正确的物理索引".format(doc_name), self.story)
                p_list.append(p)
                continue

            current_index = write_indices[0]

            index_info = client.cat.indices(current_index, format="json")[0]

            index_message = (
                f"[{doc_name}] current index: doc_count[{index_info['docs.count']}], "
                f"size[{index_info['pri.store.size']}], status[{index_info['health']}]"
            )

            if index_info["health"] != "green":
                self.story.warning(index_message)
                p_list.append(ClusterRed("[{}]当前索引状态异常: {}".format(doc_name, index_info['health']), self.story))
            else:
                self.story.info(index_message)

            all_indices = client.cat.indices(f"*{document_cls.Index.name}*", format="json", bytes="mb")

            invalid_write_indices = [index["index"] for index in all_indices if index["index"].startswith("write")]
            yellow_indices = [index for index in all_indices if index["health"] == "yellow"]
            red_indices = [index for index in all_indices if index["health"] == "red"]
            all_doc_count = sum(int(index["docs.count"]) for index in all_indices)
            total_size = sum(int(index["pri.store.size"]) for index in all_indices)

            all_indices_message = (
                f"[{doc_name}] all indices: total[{len(all_indices)}] "
                f"invalid[{len(invalid_write_indices)}] yellow[{len(yellow_indices)}] "
                f"red[{len(red_indices)}] doc_count[{all_doc_count}] size[{total_size}mb]"
            )

            if invalid_write_indices:
                p_list.append(
                    InvalidWriteIndex("[{}]发现不合法的写入索引: {}".format(doc_name, invalid_write_indices), self.story)
                )
                self.story.warning(all_indices_message)
            elif yellow_indices or red_indices:
                p_list.append(
                    ClusterRed(
                        "[{}]整体索引状态异常: yellow: 共{}; red: 共{}".format(doc_name, len(yellow_indices), len(red_indices)),
                        self.story,
                    )
                )
                self.story.warning(all_indices_message)
            else:
                self.story.info(all_indices_message)

        if p_list:
            return p_list
