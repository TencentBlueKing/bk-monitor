import json

from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Q
from django.db.models.functions import Concat

from bk_monitor_base.metadata.models import BCSClusterInfo, DataSource, Space, SpaceDataSource
from bk_monitor_base.metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes
from bk_monitor_base.metadata.service.data_source import query_biz_plugin_data_id_list


class Command(BaseCommand):
    help = "query space detail"

    def add_arguments(self, parser):
        parser.add_argument("--space_uid", type=str, help="query space by uid, split by `,`")
        parser.add_argument("--id", type=str, help="query space detail by id(mysql id), split by `,`")
        parser.add_argument("--with_platform_data_id", action="store_true", help="query space with platform data id")

    def handle(self, *args, **options):
        with_platform_data_id = options.get("with_platform_data_id")
        space_list = self._refine_space(options)
        if not space_list:
            self.stdout.write("no space found")
            return
        space_dict, biz_space_dict, not_biz_space_dict, biz_id_list = {}, {}, {}, []
        for s in space_list:
            space_dict[(s["space_type_id"], s["space_id"])] = s
            if s["space_type_id"] == SpaceTypes.BKCC.value:
                biz_space_dict[(s["space_type_id"], s["space_id"])] = s
                biz_id_list.append(s["space_id"])
            else:
                not_biz_space_dict[(s["space_type_id"], s["space_id"])] = s

        # 获取已经移除的集群数据源 ID
        removed_cluster_data_id_list = self._query_removed_cluster_data_id_list()
        # 获取已经禁用的数据源 ID
        disabled_data_id_list = self._query_disabled_data_id_list()

        # 获取业务下的数据源及关联资源
        biz_space_data_source_dict, not_biz_space_data_source_dict = {}, {}
        if biz_space_dict:
            biz_space_data_source_dict = self._query_bkcc_space_data(
                biz_space_dict.keys(), removed_cluster_data_id_list, disabled_data_id_list
            )

        # 获取关联数据
        if not_biz_space_dict:
            not_biz_space_data_source_dict = self._query_not_bkcc_space_data(
                not_biz_space_dict.keys(), removed_cluster_data_id_list, disabled_data_id_list
            )

        # 获取业务下的插件
        biz_plugin_data_ids = query_biz_plugin_data_id_list(biz_id_list)

        # 获取空间类型数据
        space_type_data_ids = {}
        if with_platform_data_id:
            space_type_data_ids = self._query_platform_data_id_list()

        # 合并数据并追加平台 data_id
        for key, val in space_dict.items():
            if key[0] == SpaceTypes.BKCC.value:
                data_sources = biz_space_data_source_dict.get(key, {})
                _data_ids = biz_plugin_data_ids.get(key[1])
                if _data_ids:
                    data_sources["belong_space_data_id_list"].extend(_data_ids)
                data_sources["belong_space_data_id_total"] = len(data_sources["belong_space_data_id_list"])
                data_sources["platform_data_id_list"] = space_type_data_ids.get(key[0]) or []
            else:
                data_sources = not_biz_space_data_source_dict.get(key, [])
                data_sources["platform_data_id_list"] = space_type_data_ids.get(key[0]) or []
            val["data_sources"] = data_sources

        self.stdout.write(json.dumps(list(space_dict.values())))

    def _refine_space(self, options) -> list[dict]:
        space_uids = options.get("space_uid")
        ids = options.get("id")
        # 如果为空，则返回消息
        if not (space_uids or ids):
            self.stdout.write("params [space_uid] and [id] is null")
            return
        space_list = []
        if space_uids:
            space_list = self._query_by_space_uid_list(space_uids.split(","))
        if ids:
            space_list.extend(self._query_by_id_list(ids.split(",")))
        return space_list

    def _check_space_uid_list(self, space_uid_list: list) -> bool:
        error_uid_list = []
        for suid in space_uid_list:
            if SPACE_UID_HYPHEN not in suid:
                error_uid_list.append(suid)
        if error_uid_list:
            self.stderr.write(f"space_uid:{','.join(error_uid_list)} format error, expect to contains `__`")

    def _query_by_space_uid_list(self, space_uid_list) -> list:
        # 使用 annotate 过滤数据
        space_list = (
            Space.objects.annotate(space_uid=Concat("space_type_id", models.Value(SPACE_UID_HYPHEN), "space_id"))
            .filter(space_uid__in=space_uid_list)
            .values("space_uid", "id", "space_type_id", "space_id", "status")
        )
        return list(space_list)

    def _query_by_id_list(self, id_list: list) -> dict:
        space_list = (
            Space.objects.annotate(space_uid=Concat("space_type_id", models.Value(SPACE_UID_HYPHEN), "space_id"))
            .filter(id__in=id_list)
            .values("space_uid", "id", "space_type_id", "space_id", "status")
        )
        return list(space_list)

    def _query_bkcc_space_data(
        self, space_uid_list: list, removed_cluster_data_id_list: list, disabled_data_id_list: list
    ) -> tuple[dict, dict]:
        """获取业务空间关联的数据源 ID 和资源

        这里需要过滤业务下的集群资源
        """
        # 获取关联的 data id
        space_data_id_filter_q = Q()
        # space_uid_list 格式为 [(space_type_id, space_id), (space_type_id1, space_id1)]
        for s in space_uid_list:
            space_data_id_filter_q |= Q(space_type_id=s[0], space_id=s[1])

        return self._query_space_data_source(
            space_data_id_filter_q, removed_cluster_data_id_list, disabled_data_id_list
        )

    def _query_not_bkcc_space_data(
        self, space_uid_list: list, removed_cluster_data_id_list: list, disabled_data_id_list: list
    ) -> tuple[dict, dict]:
        # 获取关联的 data id
        filter_q = Q()
        # space_uid_list 格式为 [(space_type_id, space_id), (space_type_id1, space_id1)]
        for s in space_uid_list:
            filter_q |= Q(space_type_id=s[0], space_id=s[1])

        return self._query_space_data_source(filter_q, removed_cluster_data_id_list, disabled_data_id_list)

    def _query_space_data_source(
        self, filter_q: Q, removed_cluster_data_id_list: list, disabled_data_id_list: list
    ) -> dict:
        # 获取空间下的数据源 ID
        space_data_source = SpaceDataSource.objects.filter(filter_q)
        space_keys, belong_space_data_source_dict, authorized_space_data_source_dict = set(), {}, {}
        for sd in space_data_source:
            # 过滤掉已删除的集群数据源 ID 和已经禁用的数据源 ID
            if (sd.bk_data_id in removed_cluster_data_id_list) or (sd.bk_data_id in disabled_data_id_list):
                continue
            key = (sd.space_type_id, sd.space_id)
            space_keys.add(key)
            if sd.from_authorization:
                authorized_space_data_source_dict.setdefault(key, []).append(sd.bk_data_id)
            else:
                belong_space_data_source_dict.setdefault(key, []).append(sd.bk_data_id)

        # 合并数据
        space_data_source_dict = {}
        for key in space_keys:
            space_data_source_dict[key] = {"belong_space_data_id_list": belong_space_data_source_dict.get(key, [])}
            space_data_source_dict[key]["authorized_space_data_id_list"] = authorized_space_data_source_dict.get(
                key, []
            )
        return space_data_source_dict

    def _query_removed_cluster_data_id_list(self) -> list:
        """获取已删除的集群数据源 ID"""
        cluster_objs = BCSClusterInfo.objects.filter(
            status__in=[BCSClusterInfo.CLUSTER_STATUS_DELETED, BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED]
        ).values("K8sMetricDataID", "CustomMetricDataID", "K8sEventDataID", "CustomEventDataID")
        data_id_list = []
        for obj in cluster_objs:
            data_id_list.append(obj["K8sMetricDataID"])
            data_id_list.append(obj["CustomMetricDataID"])
            data_id_list.append(obj["K8sEventDataID"])
            data_id_list.append(obj["CustomEventDataID"])
        return data_id_list

    def _query_disabled_data_id_list(self) -> list:
        """获取已禁用的数据源 ID"""
        return list(DataSource.objects.filter(is_enable=False).values_list("bk_data_id", flat=True))

    def _query_platform_data_id_list(self) -> dict:
        """获取空间类型下数据源 ID"""
        ds_objs = DataSource.objects.filter(is_platform_data_id=True).values("bk_data_id", "space_type_id")
        space_type_data_ids = {}
        for obj in ds_objs:
            space_type_data_ids.setdefault(obj["space_type_id"], []).append(obj["bk_data_id"])
        return space_type_data_ids
