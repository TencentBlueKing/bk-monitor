from collections import defaultdict

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_search.constants import CollectorScenarioEnum
from apps.log_search.models import LogIndexSet, LogIndexSetData, AccessSourceConfig, Scenario
from apps.log_databus.models import CollectorConfig
from django.db.models import QuerySet

from bkm_space.utils import space_uid_to_bk_biz_id
from apps.log_search.handlers.index_set import IndexSetHandler


def fetch_log_collector_data(func):
    def inner(*args, **kwargs):
        result = func(*args, **kwargs)
        result_list = []
        for item in result:
            result_list.append(
                {
                    "table_id": item.get("table_id"),
                    "bk_data_id": item.get("bk_data_id"),
                    "collector_config_name": item.get("collector_config_name"),
                    "collector_config_id": item.get("collector_config_id"),
                    "table_id_prefix": item.get("table_id_prefix"),
                    "updated_by": item.get("updated_by"),
                    "custom_type": item.get("custom_type"),
                    "updated_at": item.get("updated_at"),
                    "index_set_id": item.get("index_set_id"),
                    "retention": item.get("retention"),
                    "is_active": item.get("is_active"),
                    "collector_scenario_name": item.get("collector_scenario_name"),
                    "storage_cluster_name": item.get("storage_cluster_name"),
                    "tags": item.get("tags"),
                    "category_name": item.get("category_name"),
                    "is_editable": item.get("is_editable"),
                    "scenario_name": item.get("scenario_name") if item.get("scenario_name") else "采集接入",
                }
            )
        return result_list

    return inner


class LogCollectorHandler:
    def __init__(self, space_uid):
        self.space_uid = space_uid
        self.bk_biz_id = space_uid_to_bk_biz_id(self.space_uid)

    def get_paginated_data(self, page, pagesize):
        """
        实现分页逻辑
        """
        collector_queryset = CollectorConfig.objects.filter(bk_biz_id=self.bk_biz_id)
        log_index_queryset = LogIndexSet.objects.filter(
            collector_config_id__isnull=True, space_uid=self.space_uid
        ).exclude(scenario_id=Scenario.LOG)

        total_collector_count = collector_queryset.count()
        total_log_index_count = log_index_queryset.count()
        total_count = total_collector_count + total_log_index_count

        result = {"collector_config": [], "log_index_set": [], "total": total_count}

        global_offset = (page - 1) * pagesize

        if global_offset < total_collector_count:
            # 获取 CollectorConfig 数据
            collector_end = min(global_offset + pagesize, total_collector_count)
            collector_data = collector_queryset[global_offset:collector_end]
            result["collector_config"] = collector_data

            # 如果还需要 LogIndexSet 数据
            if len(collector_data) < pagesize:
                log_index_needed = pagesize - len(collector_data)
                log_index_data = log_index_queryset[:log_index_needed]
                result["log_index_set"] = log_index_data

        else:
            # 完全在 LogIndexSet 范围内
            log_index_offset = global_offset - total_collector_count
            log_index_end = min(log_index_offset + pagesize, total_log_index_count)
            log_index_data = log_index_queryset[log_index_offset:log_index_end]
            result["log_index_set"] = log_index_data

        return result

    @fetch_log_collector_data
    def get_collector_config_info(self, collector_configs: QuerySet) -> list[dict]:
        collector_configs = collector_configs.values()
        # 添加采集场景名称
        for collector_config in collector_configs:
            collector_scenario_id = collector_config["collector_scenario_id"]
            collector_config["collector_scenario_name"] = CollectorScenarioEnum.get_choice_label(collector_scenario_id)
        collector_configs = CollectorHandler.add_cluster_info(collector_configs)
        collector_configs = CollectorHandler.add_tags_info(collector_configs)

        return collector_configs

    @fetch_log_collector_data
    def get_log_index_set_info(self, log_index_sets: QuerySet) -> list[dict]:
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

        log_index_set_data = LogIndexSetData.objects.filter(index_set_id__in=index_set_ids)

        log_index_set_data_mappings = defaultdict(list)
        for obj in log_index_set_data:
            log_index_set_data_mappings[obj.index_set_id].append(obj)

        result_list = []
        for obj in log_index_sets:
            _index_set_id = obj.index_set_id
            index_set_data = log_index_set_data_mappings[_index_set_id]
            source_id = obj.source_id
            indexes = [
                {
                    "index_id": data.index_id,
                    "index_set_id": _index_set_id,
                    "bk_biz_id": data.bk_biz_id,
                    "source_id": source_id,
                    "source_name": access_source_config_mappings.get(source_id, "--"),
                    "result_table_id": data.result_table_id,
                    "scenario_id": data.scenario_id,
                    "storage_cluster_id": data.storage_cluster_id,
                    "time_field": data.time_field,
                    "result_table_name": data.result_table_name,
                    "apply_status": data.apply_status,
                    "apply_status_name": data.get_apply_status_display(),
                }
                for data in index_set_data
            ]

            result_list.append(
                {
                    "index_set_id": obj.index_set_id,
                    "index_set_name": obj.index_set_name,
                    "indexes": indexes,
                    "updated_at": obj.updated_at,
                    "updated_by": obj.updated_by,
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
        return result_list

    def get_log_collectors(self, data):
        """获取日志采集信息"""
        paginated_data = self.get_paginated_data(data["page"], data["pagesize"])
        collector_configs = paginated_data["collector_config"]
        log_index_sets = paginated_data["log_index_set"]
        total = paginated_data["total"]
        combined_data = []
        if collector_configs:
            # 获取采集项内容
            collector_config_list = self.get_collector_config_info(collector_configs)
            combined_data.extend(collector_config_list)
        if log_index_sets:
            # 获取索引集内容
            log_index_set_list = self.get_log_index_set_info(log_index_sets)
            combined_data.extend(log_index_set_list)
        result = {
            "total": total,
            "list": combined_data,
        }
        return result
