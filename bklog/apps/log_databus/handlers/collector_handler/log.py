from collections import defaultdict
from itertools import chain

import arrow
from django.core.paginator import Paginator
from django.db.models import F, Q, Value
from django.db.models.functions import Replace

from apps.api import TransferApi, BkDataMetaApi
from apps.log_databus.constants import (
    DEFAULT_LOG_COLLECTOR_ORDERING,
    STORAGE_CLUSTER_TYPE,
    CollectorSourceEnum,
)
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_search.constants import (
    CollectorScenarioEnum,
    CollectStatusEnum,
    IndexSetDataType,
    InnerTag,
    LogAccessTypeEnum,
)
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import (
    AccessSourceConfig,
    IndexSetTag,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    SpaceApi,
    TAG_TYPE_INNER,
)
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.utils.local import get_local_param
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import format_user_time_zone
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import space_uid_to_bk_biz_id


class LogCollectorHandler:
    def __init__(self, space_uid):
        self.space_uid = space_uid
        self.bk_biz_id = space_uid_to_bk_biz_id(self.space_uid)

        # related var
        self.space_type_id, _ = SpaceApi.parse_space_uid(self.space_uid)
        self._all_related_space_uids = None
        self._all_related_bk_biz_ids = None
        self._bk_biz_id_to_space_detail_map = None

    @property
    def all_related_space_uids(self) -> list[str]:
        if self._all_related_space_uids is None:
            self._all_related_space_uids = IndexSetHandler.get_all_related_space_uids(self.space_uid)
        return self._all_related_space_uids

    @property
    def all_related_bk_biz_ids(self) -> list[int]:
        if self._all_related_bk_biz_ids is None:
            self._all_related_bk_biz_ids = [
                space_uid_to_bk_biz_id(related_space_uid) for related_space_uid in self.all_related_space_uids
            ]
        return self._all_related_bk_biz_ids

    @property
    def bk_biz_id_to_space_detail_map(self) -> dict[int, dict]:
        if self._bk_biz_id_to_space_detail_map is None:
            all_space_objs = SpaceApi.batch_get_space_detail(set(self.all_related_space_uids))
            self._bk_biz_id_to_space_detail_map = {v.bk_biz_id: v.to_dict() for _, v in all_space_objs.items()}
        return self._bk_biz_id_to_space_detail_map

    def fetch_log_collector_data(self, result: list[dict], include_related_spaces: bool = False):
        result_list = []
        scenario_choices = dict(Scenario.CHOICES)
        for item in result:
            # 获取数据名
            index_set_name = item.get("index_set_name", "")
            table_id = item.get("table_id", "")
            table_id_prefix = item.get("table_id_prefix", "")
            if index_set_name:
                bk_data_name = item["bk_data_name"]
            elif table_id and table_id_prefix:
                bk_data_name = f"{table_id_prefix}{table_id}"
            else:
                bk_data_name = ""
            name_en = self.build_name_en(item.get("collector_config_name_en"), table_id)
            # 获取日志接入类型
            scenario_id = item.get("scenario_id")
            collector_scenario_id = item.get("collector_scenario_id", "")
            collector_config_name = item.get("collector_config_name", "")
            log_access_type = LogAccessTypeEnum.get_log_access_type(
                scenario_id=scenario_id,
                collector_scenario_id=collector_scenario_id,
                environment=item.get("environment", ""),
                container_collector_type=item.get("container_collector_type", ""),
            )

            related_space_info = {}

            if self.space_type_id == SpaceTypeEnum.BKCC.value and include_related_spaces:
                bk_biz_id = item.get("bk_biz_id")
                space_detail = self.bk_biz_id_to_space_detail_map.get(bk_biz_id) or {}
                space_uid = space_detail.get("space_uid")
                space_name = space_detail.get("space_name")
                is_related_space = bk_biz_id != self.bk_biz_id
                related_space_info = {
                    "bk_biz_id": bk_biz_id,
                    "space_uid": space_uid,
                    "space_name": space_name,
                    "is_related_space": is_related_space,
                }

            result_list.append(
                {
                    "table_id": item.get("table_id", ""),
                    "name_en": name_en,
                    "bk_data_id": item.get("bk_data_id", ""),
                    "name": collector_config_name if collector_config_name else index_set_name,
                    "collector_config_id": item.get("collector_config_id", ""),
                    "table_id_prefix": item.get("table_id_prefix", ""),
                    "bk_data_name": bk_data_name,
                    "updated_by": item.get("updated_by", ""),
                    "updated_at": item.get("updated_at", ""),
                    "created_by": item.get("created_by", ""),
                    "created_at": item.get("created_at", ""),
                    "custom_type": item.get("custom_type", ""),
                    "index_set_id": item.get("index_set_id", ""),
                    "retention": item.get("retention", ""),
                    "is_active": item.get("is_active", ""),
                    "collector_scenario_id": collector_scenario_id,
                    "collector_scenario_name": CollectorScenarioEnum.get_choice_label(collector_scenario_id),
                    "storage_cluster_id": item.get("storage_cluster_id", ""),
                    "storage_cluster_name": item.get("storage_cluster_name", ""),
                    "storage_display_name": item.get("storage_display_name", ""),
                    "tags": item.get("tags", ""),
                    "category_id": item.get("category_id", ""),
                    "category_name": item.get("category_name", ""),
                    # 采集项没有该字段，缺省即「不受此标记限制」；不可用空串，前端 !is_editable 会误判为不可编辑
                    "is_editable": item.get("is_editable", True),
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_choices.get(scenario_id, ""),
                    "status": item.get("status", ""),
                    "status_name": item.get("status_name", ""),
                    "environment": item.get("environment", ""),
                    "parent_index_sets": item.get("parent_index_sets", []),
                    "log_access_type": log_access_type,
                    "log_access_type_name": LogAccessTypeEnum.get_choice_label(log_access_type),
                    "container_collector_type": item.get("container_collector_type", ""),
                    "task_id_list": item.get("task_id_list", []),
                    "etl_config": item.get("etl_config", ""),
                    "collect_paths": item.get("params", {}).get("paths", []),
                    "is_search": item.get("is_search", True),
                    **related_space_info,
                }
            )
        return result_list

    @staticmethod
    def build_name_en(collector_config_name_en: str | None, table_id: str | None = "") -> str:
        """采集项英文名，历史数据缺失英文名时回退到结果表点号后的部分。"""
        return (collector_config_name_en or "") or (table_id or "").rpartition(".")[2]

    @staticmethod
    def normalize_searchable_text(value) -> str:
        """归一化待匹配文本，使结果表名的点号写法与下划线写法互相命中。"""
        return str(value or "").replace(".", "_").casefold()

    @classmethod
    def get_collector_table_fields(
        cls, table_id: str | None, collector_config_name_en: str | None = ""
    ) -> tuple[str, str]:
        """Convert the stored collector fields to the name_en / bk_data_name exposed by the collector list API."""
        return cls.build_name_en(collector_config_name_en, table_id), (table_id or "").replace(".", "_")

    @staticmethod
    def build_index_set_bk_data_name(result_table_ids) -> str:
        """Build the bk_data_name exposed by the collector list for an independent index set."""
        return ",".join([result_table_id for result_table_id in result_table_ids if result_table_id])

    @staticmethod
    def build_field_enum(values) -> list[dict]:
        """Build a stable, de-duplicated field-enum response."""
        enum_values = sorted({value for value in values if value not in (None, "")}, key=lambda value: str(value))
        return [{"key": value, "value": value} for value in enum_values]

    @staticmethod
    def _collector_identity_sort_key(item: dict) -> tuple:
        """Build a deterministic tie-breaker for mixed collector and index-set records."""
        collector_config_id = item.get("collector_config_id")
        if collector_config_id not in (None, ""):
            item_type = 0
            item_id = collector_config_id
        else:
            item_type = 1
            item_id = item.get("index_set_id")

        try:
            normalized_id = (0, int(item_id))
        except (TypeError, ValueError):
            normalized_id = (1, str(item_id or ""))
        return item_type, normalized_id

    @staticmethod
    def _name_character_sort_key(character: str, descending: bool) -> tuple[int, int]:
        """[A-Z][0-9][a-z]，[Z-A][9-0][z-a]"""
        if "A" <= character <= "Z":
            group, position = 0, ord(character) - ord("A")
        elif "0" <= character <= "9":
            group, position = 1, ord(character) - ord("0")
        elif "a" <= character <= "z":
            group, position = 2, ord(character) - ord("a")
        else:
            group, position = 3, ord(character)
        return group, -position if descending else position

    @classmethod
    def _name_sort_key(cls, item: dict, descending: bool) -> tuple:
        name = str(item.get("name") or "")
        character_keys = [cls._name_character_sort_key(character, descending) for character in name]
        character_keys.append((4, 0) if descending else (-1, 0))
        return not bool(name), tuple(character_keys), cls._collector_identity_sort_key(item)

    @classmethod
    def _field_sort_key(cls, item: dict, field: str, descending: bool) -> tuple:
        if field in {"daily_usage", "total_usage"}:
            value = (item.get("storage_usage") or {}).get(field)
        else:
            value = item.get(field)
        if value in (None, ""):
            return True, 0, cls._collector_identity_sort_key(item)

        try:
            if field in {"retention", "daily_usage", "total_usage"}:
                normalized_value = int(value)
            else:
                normalized_value = arrow.get(str(value)[:19], "YYYY-MM-DD HH:mm:ss").int_timestamp
        except (TypeError, ValueError, arrow.parser.ParserError):
            return True, 0, cls._collector_identity_sort_key(item)

        return False, -normalized_value if descending else normalized_value, cls._collector_identity_sort_key(item)

    @classmethod
    def sort_log_collectors(cls, data: list[dict], ordering: str = DEFAULT_LOG_COLLECTOR_ORDERING) -> list[dict]:
        """
        分页前排序
        """
        descending = ordering.startswith("-")
        field = ordering.removeprefix("-")

        if field == "name":
            return sorted(data, key=lambda item: cls._name_sort_key(item, descending))

        return sorted(data, key=lambda item: cls._field_sort_key(item, field, descending))

    def fill_storage_usage_info(self, data: list[dict]) -> list[dict]:
        """Fill storage usage fields for collector and independent-index-set records."""
        usage_fields = ("daily_count", "total_count", "daily_usage", "total_usage")
        index_set_ids = set()

        for item in data:
            item["storage_usage"] = {field: None for field in usage_fields}

            index_set_id = item.get("index_set_id")
            if index_set_id in (None, ""):
                continue

            try:
                index_set_ids.add(int(index_set_id))
            except (TypeError, ValueError):
                continue

        if not index_set_ids:
            return data

        index_set_ids_by_space_uid = defaultdict(list)
        index_set_space_info = LogIndexSet.objects.filter(index_set_id__in=index_set_ids).values_list(
            "index_set_id", "space_uid"
        )
        for index_set_id, space_uid in index_set_space_info:
            index_set_ids_by_space_uid[space_uid].append(index_set_id)

        usage_map = {}
        for space_uid, grouped_index_set_ids in index_set_ids_by_space_uid.items():
            bk_biz_id = self.bk_biz_id if space_uid == self.space_uid else space_uid_to_bk_biz_id(space_uid)
            usage_list = IndexSetHandler.get_storage_usage_info(bk_biz_id, grouped_index_set_ids)
            for usage in usage_list:
                try:
                    usage_map[int(usage["index_set_id"])] = usage
                except (KeyError, TypeError, ValueError):
                    continue

        for item in data:
            try:
                usage = usage_map.get(int(item.get("index_set_id")))
            except (TypeError, ValueError):
                usage = None

            if not usage:
                continue

            for field in usage_fields:
                item["storage_usage"][field] = usage.get(field)

        return data

    @classmethod
    def filter_by_queries(cls, data: list[dict], queries: list) -> list[dict]:
        """Filter records when every query matches at least one exposed searchable field."""
        normalized_queries = [
            cls.normalize_searchable_text(str(query).strip())
            for query in (queries or [])
            if query is not None and str(query).strip()
        ]
        if not normalized_queries:
            return data

        searchable_fields = ("name", "name_en", "bk_data_id", "table_id", "bk_data_name", "storage_display_name")
        return [
            item
            for item in data
            if all(
                any(query in cls.normalize_searchable_text(item.get(field)) for field in searchable_fields)
                for query in normalized_queries
            )
        ]

    @staticmethod
    def fuzzy_match_any(value, candidates: list) -> bool:
        """Return whether a value contains any candidate, ignoring case."""
        normalized_value = str(value or "").casefold()
        return any(str(candidate).casefold() in normalized_value for candidate in candidates)

    @staticmethod
    def get_collector_subscription_status(collector_id_list) -> dict[str, dict]:
        collector_status_mappings = {}
        result = CollectorHandler().get_subscription_status_by_list(collector_id_list)
        for item in result:
            collector_status_mappings[item["collector_id"]] = item
        return collector_status_mappings

    @staticmethod
    def filter_no_data(data: list[dict]) -> list[dict]:
        """过滤已被无数据巡检打标的索引集/采集项。"""
        no_data_tag_id = str(IndexSetTag.get_tag_id(InnerTag.NO_DATA.value, tag_type=TAG_TYPE_INNER))
        return [
            item
            for item in data
            if no_data_tag_id not in {str(tag.get("tag_id")) for tag in item.get("tags", []) if tag}
        ]

    @staticmethod
    def get_child_index_set_ids(parent_index_set_id: int) -> list:
        return list(
            LogIndexSetData.objects.filter(
                index_set_id=parent_index_set_id,
                type=IndexSetDataType.INDEX_SET.value,
            ).values_list("result_table_id", flat=True)
        )

    @staticmethod
    def fill_parent_index_sets_info(data):
        """
        补充归属索引集信息
        """

        # 查询索引集ID及其归属索引集ID
        index_set_ids = [item["index_set_id"] for item in data if item.get("index_set_id")]
        index_data = LogIndexSetData.objects.filter(
            type=IndexSetDataType.INDEX_SET.value,
            result_table_id__in=index_set_ids,
        ).values("index_set_id", "result_table_id")

        # 查询归属索引集信息
        index_group_ids = list({item["index_set_id"] for item in index_data if item.get("index_set_id")})
        index_group_list = LogIndexSet.objects.filter(index_set_id__in=index_group_ids, is_group=True).values(
            "index_set_id", "index_set_name"
        )
        index_group_map = {index_group["index_set_id"]: index_group for index_group in index_group_list}

        # 构建归属索引集映射
        parent_index_group_map = defaultdict(list)
        for item in index_data:
            parent_index_group = index_group_map.get(item["index_set_id"])
            if parent_index_group:
                parent_index_group_map[item["result_table_id"]].append(parent_index_group)

        # 添加归属索引集信息
        for item in data:
            item["parent_index_sets"] = parent_index_group_map.get(str(item["index_set_id"]), [])

    @staticmethod
    def fill_container_fields(data):
        """
        补充容器采集类型字段
        """
        collector_config_ids = [item["collector_config_id"] for item in data]
        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id__in=collector_config_ids)

        collector_type_mappings = {}
        for container_config in container_configs:
            collector_type_mappings[container_config.collector_config_id] = container_config

        for item in data:
            if container_config := collector_type_mappings.get(item["collector_config_id"]):
                item["container_collector_type"] = container_config.collector_type
                item["params"] = container_config.params

    @staticmethod
    def filter_data_by_access_types(data, log_access_type_list):
        """
        根据日志接入类型列表过滤数据
        """
        filtered_data = []
        for item in data:
            # 多个 log_access_type 之间是"或"的关系
            for log_access_type in log_access_type_list:
                _original_fields = LogAccessTypeEnum.get_original_fields(log_access_type)
                collector_scenario_id_list = _original_fields.get("collector_scenario_id_list", [])
                environment_list = _original_fields.get("environment_list", [])
                container_collector_type_list = _original_fields.get("container_collector_type_list", [])

                # 单个 log_access_type 里面的条件之间是"且"的关系
                if not (collector_scenario_id_list or environment_list or container_collector_type_list):
                    continue
                if collector_scenario_id_list and item["collector_scenario_id"] not in collector_scenario_id_list:
                    continue
                if environment_list and item["environment"] not in environment_list:
                    continue
                if (
                    container_collector_type_list
                    and item["container_collector_type"] not in container_collector_type_list
                ):
                    continue
                filtered_data.append(item)
                break

        return filtered_data

    def get_collector_config_info(
        self,
        keyword: str = None,
        parent_index_set_id: int = None,
        scenario_id_list: list = None,
        collector_config_name_list: list = None,
        name_en_list: list = None,
        bk_data_name_list: list = None,
        bk_data_id_list: list = None,
        collector_scenario_id_list: list = None,
        created_by_list: list = None,
        updated_by_list: list = None,
        storage_display_name_list: list = None,
        status_list: list = None,
        log_access_type_list: list = None,
        exclude_not_completed: bool = False,
        exclude_parent_index_set_id: int = None,
        include_related_spaces: bool = False,
        collector_source: list = None,
    ) -> list[dict]:
        """
         获取采集项信息
        :param keyword: 旧版单关键词搜索
        :param parent_index_set_id: 归属索引集ID
        :param scenario_id_list: 接入情景
        :param collector_config_name_list: 采集名称
        :param name_en_list: 数据名（采集项英文名）
        :param bk_data_name_list: 存储名
        :param bk_data_id_list: 数据ID
        :param collector_scenario_id_list: 日志类型
        :param created_by_list: 创建者
        :param updated_by_list: 创建者
        :param storage_display_name_list: 集群名
        :param status_list: 采集状态
        :param log_access_type_list: 日志接入类型
        :param exclude_not_completed: 是否排除未完成的采集项
        :param exclude_parent_index_set_id: 排除指定归属索引集下的采集项
        :param include_related_spaces: 是否包含关联空间中的采集项
        :param collector_source: 采集项来源
        """
        if scenario_id_list and Scenario.LOG not in scenario_id_list:
            # 非日志采集查询，直接返回
            return []

        # 采集插件通过 is_display 批量隐藏旗下采集项，且默认不可见，列表须与旧接口口径一致
        if self.space_type_id == SpaceTypeEnum.BKCC.value and include_related_spaces:
            query_bk_biz_ids = self.get_query_ids_by_collector_source(collector_source, is_bk_biz_id=True)
            qs = CollectorConfig.objects.filter(bk_biz_id__in=query_bk_biz_ids, is_display=True)
        else:
            qs = CollectorConfig.objects.filter(bk_biz_id=self.bk_biz_id, is_display=True)

        if exclude_not_completed:
            qs = qs.filter(table_id__isnull=False)

        if keyword or bk_data_name_list:
            qs = qs.alias(
                exposed_bk_data_name=Replace(
                    F("table_id"),
                    Value("."),
                    Value("_"),
                )
            )

        if keyword:
            keyword_filter = (
                Q(collector_config_name__icontains=keyword)
                | Q(collector_config_name_en__icontains=keyword)
                | Q(table_id__icontains=keyword)
                | Q(exposed_bk_data_name__icontains=keyword.replace(".", "_"))
            )
            if keyword.isdigit():
                keyword_filter |= Q(bk_data_id=int(keyword))
            qs = qs.filter(keyword_filter)

        # 先查询索引组下的索引集，再查询索引集对应的采集项
        if parent_index_set_id:
            index_set_id_list = self.get_child_index_set_ids(parent_index_set_id)
            if not index_set_id_list:
                return []
            collector_config_list = (
                LogIndexSet.objects.filter(
                    index_set_id__in=index_set_id_list,
                    collector_config_id__isnull=False,
                )
                .distinct()
                .values_list("collector_config_id", flat=True)
            )
            if not collector_config_list:
                return []
            qs = qs.filter(collector_config_id__in=collector_config_list)

        if exclude_parent_index_set_id:
            exclude_index_set_id_list = self.get_child_index_set_ids(exclude_parent_index_set_id)
            if exclude_index_set_id_list:
                exclude_collector_config_list = LogIndexSet.objects.filter(
                    index_set_id__in=exclude_index_set_id_list,
                    collector_config_id__isnull=False,
                ).values_list("collector_config_id", flat=True)
                qs = qs.exclude(collector_config_id__in=exclude_collector_config_list)

        if collector_config_name_list:
            query = Q()
            for name in collector_config_name_list:
                query |= Q(collector_config_name__icontains=name)
            qs = qs.filter(query)
        if collector_scenario_id_list:
            qs = qs.filter(collector_scenario_id__in=collector_scenario_id_list)
        if created_by_list:
            qs = qs.filter(created_by__in=created_by_list)
        if updated_by_list:
            qs = qs.filter(updated_by__in=updated_by_list)
        if bk_data_name_list:
            query = Q()
            for bk_data_name in bk_data_name_list:
                query |= Q(exposed_bk_data_name__icontains=str(bk_data_name).replace(".", "_"))
            qs = qs.filter(query)
        if bk_data_id_list:
            qs = qs.filter(bk_data_id__in=bk_data_id_list)

        collector_configs = qs.values()
        # Todo 时区处理逻辑太混乱，add_cluster_info 里面已经有时间处理逻辑，先在这里去掉时区
        timezone = get_local_param("time_zone")
        for item in collector_configs:
            item["created_at"] = arrow.get(item["created_at"]).to(timezone).format("YYYY-MM-DD HH:mm:ss")
            item["updated_at"] = arrow.get(item["updated_at"]).to(timezone).format("YYYY-MM-DD HH:mm:ss")

        # 英文名带回退逻辑，无法在 DB 侧表达，与展示保持同源以免出现「列表可见但搜不到」
        if name_en_list:
            collector_configs = [
                item
                for item in collector_configs
                if self.fuzzy_match_any(
                    self.build_name_en(item["collector_config_name_en"], item["table_id"]), name_en_list
                )
            ]

        collector_configs = CollectorHandler.add_cluster_info(collector_configs)
        self.fill_container_fields(collector_configs)

        if log_access_type_list:
            collector_configs = self.filter_data_by_access_types(collector_configs, log_access_type_list)

        # 根据 storage_cluster_name 和 container_collector_type 进行过滤
        tmp_result_list = []
        collector_id_list = []
        for collector_config in collector_configs:
            if storage_display_name_list and not self.fuzzy_match_any(
                collector_config["storage_display_name"], storage_display_name_list
            ):
                continue
            tmp_result_list.append(collector_config)
            collector_id_list.append(collector_config["collector_config_id"])

        # 获取采集状态信息并进行过滤（先过滤其他字段，尽量减少查询次数）
        result_list = []
        if status_list:
            collector_status_mappings = self.get_collector_subscription_status(collector_id_list)
            for item in tmp_result_list:
                original_status = collector_status_mappings.get(item["collector_config_id"], {}).get("status", "")
                new_status = CollectStatusEnum.get_collect_status(original_status)
                if new_status not in status_list:
                    continue
                result_list.append(item)
        else:
            result_list = tmp_result_list

        result_list = CollectorHandler.add_tags_info(result_list)
        return result_list

    def get_log_index_set_info(
        self,
        keyword: str = None,
        parent_index_set_id: int = None,
        scenario_id_list: list = None,
        index_set_name_list: list = None,
        result_table_id_list: list = None,
        created_by_list: list = None,
        updated_by_list: list = None,
        storage_display_name_list: list = None,
        log_access_type_list: list = None,
        exclude_parent_index_set_id: int = None,
        include_related_spaces: bool = False,
        collector_source: list = None,
    ) -> list[dict]:
        """
         获取索引集内容
        :param keyword: 旧版单关键词搜索
        :param parent_index_set_id: 归属索引集ID
        :param scenario_id_list: 接入情景
        :param index_set_name_list: 索引集名称
        :param result_table_id_list: 结果表ID
        :param created_by_list: 创建者
        :param updated_by_list: 创建者
        :param storage_display_name_list: 集群名
        :param log_access_type_list: 日志接入类型
        :param exclude_parent_index_set_id: 排除指定归属索引集下的索引集
        :param include_related_spaces: 是否包含关联空间中的采集项
        :param collector_source: 采集项来源
        """
        _scenario_id_list = []
        for log_access_type in log_access_type_list:
            _scenario_id_list.extend(LogAccessTypeEnum.get_original_fields(log_access_type)["scenario_id_list"])
            scenario_id_list.extend(_scenario_id_list)
        # 根据 log_access_type_list 过滤，但没有符合条件的数据类型，则返回空列表
        if log_access_type_list and not _scenario_id_list:
            return []

        qs = LogIndexSet.objects.filter(collector_config_id__isnull=True).exclude(scenario_id=Scenario.LOG)

        if self.space_type_id == SpaceTypeEnum.BKCC.value and include_related_spaces:
            query_space_uids = self.get_query_ids_by_collector_source(collector_source)
            log_index_sets = qs.filter(space_uid__in=query_space_uids)
        else:
            log_index_sets = qs.filter(space_uid=self.space_uid)

        if parent_index_set_id:
            index_set_id_list = self.get_child_index_set_ids(parent_index_set_id)
            if not index_set_id_list:
                return []
            log_index_sets = log_index_sets.filter(index_set_id__in=index_set_id_list)

        if exclude_parent_index_set_id:
            exclude_index_set_id_list = self.get_child_index_set_ids(exclude_parent_index_set_id)
            if exclude_index_set_id_list:
                log_index_sets = log_index_sets.exclude(index_set_id__in=exclude_index_set_id_list)

        if scenario_id_list:
            log_index_sets = log_index_sets.filter(scenario_id__in=scenario_id_list)

        if index_set_name_list:
            query = Q()
            for name in index_set_name_list:
                query |= Q(index_set_name__icontains=name)
            log_index_sets = log_index_sets.filter(query)

        if created_by_list:
            log_index_sets = log_index_sets.filter(created_by__in=created_by_list)
        if updated_by_list:
            log_index_sets = log_index_sets.filter(updated_by__in=updated_by_list)

        candidate_index_set_ids = list(log_index_sets.values_list("index_set_id", flat=True))
        index_set_data_objs = LogIndexSetData.objects.filter(index_set_id__in=candidate_index_set_ids).order_by(
            "-index_id"
        )

        index_set_data_objs_map = defaultdict(list)

        for index_set_data_obj in index_set_data_objs:
            index_set_data_objs_map[index_set_data_obj.index_set_id].append(index_set_data_obj)

        if result_table_id_list:
            requested_result_table_id_list = {
                self.normalize_searchable_text(result_table) for result_table in result_table_id_list
            }
            matched_index_set_ids = []
            for index_set_id, index_set_data_objs in index_set_data_objs_map.items():
                index_set_result_table_id = self.normalize_searchable_text(
                    self.build_index_set_bk_data_name(
                        [index_set_data_obj.result_table_id for index_set_data_obj in index_set_data_objs]
                    )
                )
                for requested_result_table_id in requested_result_table_id_list:
                    if requested_result_table_id in index_set_result_table_id:
                        matched_index_set_ids.append(index_set_id)

            log_index_sets = log_index_sets.filter(index_set_id__in=matched_index_set_ids)

        if keyword:
            normalized_keyword = self.normalize_searchable_text(keyword)
            keyword_index_set_ids = [
                index_set_id
                for index_set_id, index_set_data_objs in index_set_data_objs_map.items()
                if normalized_keyword
                in self.normalize_searchable_text(
                    self.build_index_set_bk_data_name(
                        [index_set_data_obj.result_table_id for index_set_data_obj in index_set_data_objs]
                    )
                )
            ]
            log_index_sets = log_index_sets.filter(
                Q(index_set_name__icontains=keyword) | Q(index_set_id__in=keyword_index_set_ids)
            )

        index_set_ids = []
        source_ids = []
        for obj in log_index_sets:
            index_set_ids.append(obj.index_set_id)
            source_ids.append(obj.source_id)

        access_source_config = AccessSourceConfig.objects.filter(source_id__in=source_ids).values(
            "source_id", "source_name"
        )
        access_source_config_mappings = {}
        for item in access_source_config:
            access_source_config_mappings[item["source_id"]] = item["source_name"]

        time_zone = get_local_param("time_zone")
        result_list = []
        for obj in log_index_sets:
            _index_set_id = obj.index_set_id
            index_set_data = index_set_data_objs_map[_index_set_id]
            source_id = obj.source_id
            indexes = []
            bk_data_name_list = []
            for data in index_set_data:
                result_table_id = data.result_table_id
                indexes.append(
                    {
                        "index_id": data.index_id,
                        "index_set_id": _index_set_id,
                        "bk_biz_id": data.bk_biz_id,
                        "source_id": source_id,
                        "source_name": access_source_config_mappings.get(source_id, "--"),
                        "result_table_id": result_table_id,
                        "scenario_id": data.scenario_id,
                        "storage_cluster_id": data.storage_cluster_id,
                        "time_field": data.time_field,
                        "result_table_name": data.result_table_name,
                        "apply_status": data.apply_status,
                        "apply_status_name": data.get_apply_status_display(),
                    }
                )
                if result_table_id:
                    bk_data_name_list.append(result_table_id)

            result_list.append(
                {
                    "index_set_id": obj.index_set_id,
                    "index_set_name": obj.index_set_name,
                    "indexes": indexes,
                    "bk_data_name": ",".join(bk_data_name_list),
                    "updated_at": format_user_time_zone(obj.updated_at, time_zone),
                    "updated_by": obj.updated_by,
                    "created_at": format_user_time_zone(obj.created_at, time_zone),
                    "created_by": obj.created_by,
                    "tag_ids": obj.tag_ids,
                    "category_id": obj.category_id,
                    "scenario_id": obj.scenario_id,
                    "storage_cluster_id": obj.storage_cluster_id,
                    "space_uid": obj.space_uid,
                    "time_field": obj.time_field,
                    "is_editable": obj.is_editable,
                    "is_active": obj.is_active,
                }
            )
        result_list = IndexSetHandler.post_list(result_list)
        if storage_display_name_list:
            result_list = list(
                filter(
                    lambda x: self.fuzzy_match_any(x.get("storage_display_name"), storage_display_name_list),
                    result_list,
                )
            )
        return result_list

    def get_log_collectors(self, data):
        """获取日志采集信息"""
        keyword = data.get("keyword")
        conditions = data.get("conditions", [])
        include_related_spaces = data.get("include_related_spaces", False)
        scenario_id_list = []
        name_list = []
        bk_data_name_list = []
        name_en_list = []
        bk_data_id_list = []
        collector_scenario_id_list = []
        created_by_list = []
        updated_by_list = []
        status_list = []
        storage_display_name_list = []
        log_access_type_list = []
        tag_id_list = []
        collector_source = []
        query_list = []
        for item in conditions:
            if item["key"] == "scenario_id":
                scenario_id_list = item["value"]
            elif item["key"] == "name":
                name_list = item["value"]
            elif item["key"] == "bk_data_name":
                bk_data_name_list = item["value"]
            elif item["key"] == "name_en":
                name_en_list = item["value"]
            elif item["key"] == "bk_data_id":
                bk_data_id_list = item["value"]
            elif item["key"] == "collector_scenario_id":
                collector_scenario_id_list = item["value"]
            elif item["key"] == "created_by":
                created_by_list = item["value"]
            elif item["key"] == "updated_by":
                updated_by_list = item["value"]
            elif item["key"] == "status":
                status_list = item["value"]
            elif item["key"] == "storage_display_name":
                storage_display_name_list = item["value"]
            elif item["key"] == "log_access_type":
                log_access_type_list = item["value"]
            elif item["key"] == "tags":
                tag_id_list = [int(v) for v in item["value"]]
            elif item["key"] == "collector_source":
                collector_source = item["value"]
            elif item["key"] == "query":
                query_list = item["value"]

        # 获取采集项信息
        collector_configs = self.get_collector_config_info(
            keyword=keyword,
            parent_index_set_id=data.get("parent_index_set_id"),
            scenario_id_list=scenario_id_list,
            collector_config_name_list=name_list,
            name_en_list=name_en_list,
            bk_data_name_list=bk_data_name_list,
            bk_data_id_list=bk_data_id_list,
            collector_scenario_id_list=collector_scenario_id_list,
            created_by_list=created_by_list,
            updated_by_list=updated_by_list,
            storage_display_name_list=storage_display_name_list,
            status_list=status_list,
            log_access_type_list=log_access_type_list,
            exclude_not_completed=data.get("exclude_not_completed", False),
            exclude_parent_index_set_id=data.get("exclude_parent_index_set_id"),
            include_related_spaces=include_related_spaces,
            collector_source=collector_source,
        )

        lists_to_check = [
            collector_scenario_id_list,
            status_list,
            name_en_list,
            bk_data_id_list,
        ]
        if any(chain.from_iterable(lists_to_check)):
            # 如果存在对采集名称、存储名、日志类型、采集状态不为空的查询,直接返回
            log_index_sets = []
        else:
            # 获取索引集信息
            log_index_sets = self.get_log_index_set_info(
                keyword=keyword,
                parent_index_set_id=data.get("parent_index_set_id"),
                scenario_id_list=scenario_id_list,
                index_set_name_list=name_list,
                result_table_id_list=bk_data_name_list,
                created_by_list=created_by_list,
                updated_by_list=updated_by_list,
                storage_display_name_list=storage_display_name_list,
                log_access_type_list=log_access_type_list,
                exclude_parent_index_set_id=data.get("exclude_parent_index_set_id"),
                include_related_spaces=include_related_spaces,
                collector_source=collector_source,
            )

        combined_data = collector_configs + log_index_sets
        self.fill_parent_index_sets_info(combined_data)
        combined_data = self.fetch_log_collector_data(
            result=combined_data, include_related_spaces=include_related_spaces
        )
        combined_data = self.filter_by_queries(combined_data, query_list)
        if data.get("exclude_not_data", False):
            combined_data = self.filter_no_data(combined_data)
        # 按标签过滤
        if tag_id_list:
            combined_data = [
                item for item in combined_data if any(tag.get("tag_id") in tag_id_list for tag in item.get("tags", []))
            ]
        ordering = data.get("ordering") or DEFAULT_LOG_COLLECTOR_ORDERING
        if ordering.removeprefix("-") in {"daily_usage", "total_usage"}:
            combined_data = self.fill_storage_usage_info(combined_data)
        combined_data = self.sort_log_collectors(combined_data, ordering)
        # 分页
        paginator = Paginator(combined_data, data["pagesize"])
        page_obj = paginator.get_page(data["page"])
        # 获取当前页的记录，以列表形式返回
        current_page_data = list(page_obj)
        result = {
            "total": paginator.count,
            "list": current_page_data,
        }
        return result

    def get_collector_count(self):
        """获取采集项总数"""
        collector_count = CollectorConfig.objects.filter(bk_biz_id=self.bk_biz_id, is_display=True).count()
        index_set_count = (
            LogIndexSet.objects.filter(collector_config_id__isnull=True, space_uid=self.space_uid)
            .exclude(scenario_id=Scenario.LOG)
            .count()
        )
        return collector_count + index_set_count

    def get_bkdata_cluster_names(self) -> set:
        """
        获取bkdata集群名
        """
        # 查询当前业务下bkdata的索引
        index_set_ids = LogIndexSet.objects.filter(space_uid=self.space_uid, scenario_id=Scenario.BKDATA).values_list(
            "index_set_id", flat=True
        )
        result_tables = (
            LogIndexSetData.objects.filter(index_set_id__in=index_set_ids)
            .values_list("result_table_id", flat=True)
            .distinct()
        )

        multi_execute_func = MultiExecuteFunc()
        for rt_id in result_tables:
            multi_execute_func.append(
                result_key=rt_id, func=BkDataMetaApi.result_tables.storages, params={"result_table_id": rt_id}
            )
        result = multi_execute_func.run()

        bkdata_cluster_names = set()
        for cluster_info in result.values():
            es_info = cluster_info.get("es")
            if not es_info:
                continue
            bkdata_cluster_names.add(es_info["storage_cluster"]["cluster_name"])
        return bkdata_cluster_names

    def get_metadata_cluster_names(self) -> set:
        params = {"cluster_type": STORAGE_CLUSTER_TYPE}
        cluster_info = TransferApi.get_cluster_info(params)
        metadata_cluster_names = set()
        for cluster in cluster_info:
            if StorageHandler().can_visible(
                self.bk_biz_id,
                cluster["cluster_config"].get("custom_option"),
                cluster["cluster_config"]["registered_system"],
            ):
                if display_name := cluster["cluster_config"].get("display_name"):
                    metadata_cluster_names.add(display_name)
        return metadata_cluster_names

    def get_collector_field_enums(self, include_related_spaces: bool = False):
        """
        获取采集项字段枚举值
        :param include_related_spaces: 是否包含关联空间中的采集项
        :return: 包含创建人和更新人枚举值的字典
        """
        # 枚举须与列表同源，否则筛选项里会出现列表中不存在的采集项
        if self.space_type_id == SpaceTypeEnum.BKCC.value and include_related_spaces:
            query_collector_condition = {"bk_biz_id__in": self.all_related_bk_biz_ids, "is_display": True}
            query_index_set_condition = {
                "collector_config_id__isnull": True,
                "space_uid__in": self.all_related_space_uids,
            }
        else:
            query_collector_condition = {"bk_biz_id": self.bk_biz_id, "is_display": True}
            query_index_set_condition = {"collector_config_id__isnull": True, "space_uid": self.space_uid}

        collector_fields = list(
            CollectorConfig.objects.filter(**query_collector_condition).values(
                "collector_config_name",
                "collector_config_name_en",
                "table_id",
                "bk_data_id",
                "created_by",
                "updated_by",
            )
        )

        # 获取索引集的创建人和更新人枚举
        index_set_fields = list(
            LogIndexSet.objects.filter(**query_index_set_condition)
            .exclude(scenario_id=Scenario.LOG)
            .values("index_set_id", "index_set_name", "created_by", "updated_by")
        )

        index_set_ids = [item["index_set_id"] for item in index_set_fields]

        result_table_ids_map = defaultdict(list)

        for index_set_data in LogIndexSetData.objects.filter(index_set_id__in=index_set_ids).order_by("-index_id"):
            if index_set_data.result_table_id:
                result_table_ids_map[index_set_data.index_set_id].append(index_set_data.result_table_id)

        name_ens = []
        bk_data_names = []

        for item in collector_fields:
            name_en, bk_data_name = self.get_collector_table_fields(item["table_id"], item["collector_config_name_en"])
            name_ens.append(name_en)
            bk_data_names.append(bk_data_name)

        bk_data_names.extend(
            [self.build_index_set_bk_data_name(result_table_ids_map[item["index_set_id"]]) for item in index_set_fields]
        )

        # 合并
        name_enums = [item["collector_config_name"] for item in collector_fields]
        name_enums.extend(item["index_set_name"] for item in index_set_fields)
        created_by_enums = [item["created_by"] for item in collector_fields]
        created_by_enums.extend(item["created_by"] for item in index_set_fields)
        updated_by_enums = [item["updated_by"] for item in collector_fields]
        updated_by_enums.extend(item["updated_by"] for item in index_set_fields)

        # 过滤空值并转换为字典格式
        name_dict = self.build_field_enum(name_enums)
        created_by_dict = self.build_field_enum(created_by_enums)
        updated_by_dict = self.build_field_enum(updated_by_enums)
        # 获取集群名枚举
        cluster_names = self.get_metadata_cluster_names() | self.get_bkdata_cluster_names()
        cluster_name_dict = self.build_field_enum(cluster_names)

        return {
            "name": name_dict,
            "bk_data_id": self.build_field_enum(item["bk_data_id"] for item in collector_fields),
            "name_en": self.build_field_enum(name_ens),
            "bk_data_name": self.build_field_enum(bk_data_names),
            "storage_display_name": cluster_name_dict,
            "created_by": created_by_dict,
            "updated_by": updated_by_dict,
        }

    @staticmethod
    def get_collector_status(collector_id_list):
        original_status_list = CollectorHandler().get_subscription_status_by_list(collector_id_list)
        result = []
        for item in original_status_list:
            original_status = item.get("status")
            new_status = CollectStatusEnum.get_collect_status(original_status)
            result.append(
                {
                    "collector_id": item["collector_id"],
                    "status": new_status,
                    "status_name": CollectStatusEnum.get_choice_label(new_status),
                }
            )
        return result

    def get_query_ids_by_collector_source(self, collector_source, is_bk_biz_id=False):
        if not collector_source:
            query_ids = self.all_related_bk_biz_ids if is_bk_biz_id else self.all_related_space_uids
        else:
            query_ids = []
            if is_bk_biz_id:
                other_ids = [bk_biz_id for bk_biz_id in self.all_related_bk_biz_ids if bk_biz_id != self.bk_biz_id]
            else:
                other_ids = [space_uid for space_uid in self.all_related_space_uids if space_uid != self.space_uid]

            collector_source = set(collector_source)

            if CollectorSourceEnum.CURRENT_SPACE.value in collector_source:
                query_ids.append(self.bk_biz_id if is_bk_biz_id else self.space_uid)
            if CollectorSourceEnum.RELATED_SPACE.value in collector_source:
                query_ids.extend(other_ids)

        return query_ids
