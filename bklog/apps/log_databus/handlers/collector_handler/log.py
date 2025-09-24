from collections import defaultdict
from itertools import chain

from django.core.paginator import Paginator
from django.db.models import Q

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_search.constants import CollectorScenarioEnum
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, AccessSourceConfig, Scenario
from apps.log_databus.models import CollectorConfig
from bkm_space.utils import space_uid_to_bk_biz_id


class LogCollectorHandler:
    def __init__(self, space_uid):
        self.space_uid = space_uid
        self.bk_biz_id = space_uid_to_bk_biz_id(self.space_uid)

    @staticmethod
    def fetch_log_collector_data(result: list[dict]):
        result_list = []
        scenario_choices = dict(Scenario.CHOICES)
        for item in result:
            scenario_id = item.get("scenario_id", Scenario.LOG)
            collector_scenario_id = item.get("collector_scenario_id", "")
            collector_config_name = item.get("collector_config_name", "")
            index_set_name = item.get("index_set_name", "")
            table_id = item.get("table_id", "")
            table_id_prefix = item.get("table_id_prefix", "")
            if index_set_name:
                bk_data_name = item["bk_data_name"]
            elif table_id and table_id_prefix:
                bk_data_name = f"{table_id_prefix}{table_id}"
            else:
                bk_data_name = ""
            result_list.append(
                {
                    "table_id": item.get("table_id", ""),
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
                    "storage_cluster_name": item.get("storage_cluster_name", ""),
                    "tags": item.get("tags", ""),
                    "category_id": item.get("category_id", ""),
                    "category_name": item.get("category_name", ""),
                    "is_editable": item.get("is_editable", ""),
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_choices.get(scenario_id, ""),
                    "status_name": item.get("status_name", ""),
                }
            )
        return result_list

    @staticmethod
    def get_collector_subscription_status(collector_id_list) -> dict[str, dict]:
        collector_status_mappings = {}
        result = CollectorHandler().get_subscription_status_by_list(collector_id_list)
        for item in result:
            collector_status_mappings[item["collector_id"]] = item
        return collector_status_mappings

    def get_collector_config_info(
        self,
        scenario_id_list: list = None,
        collector_config_name_list: list = None,
        table_id_list: list = None,
        collector_scenario_id_list: list = None,
        created_by_list: list = None,
        updated_by_list: list = None,
        storage_cluster_name_list: list = None,
        status_name_list: list = None,
    ) -> list[dict]:
        """
         获取采集项信息
        :param scenario_id_list: 接入情景
        :param collector_config_name_list: 采集名称
        :param table_id_list: 结果表ID
        :param collector_scenario_id_list: 日志类型
        :param created_by_list: 创建者
        :param updated_by_list: 创建者
        :param storage_cluster_name_list: 集群名
        :param status_name_list: 采集状态
        """
        if scenario_id_list and Scenario.LOG not in scenario_id_list:
            # 非日志采集查询，直接返回
            return []
        qs = CollectorConfig.objects.filter(bk_biz_id=self.bk_biz_id)
        if collector_config_name_list:
            qs = qs.filter(collector_config_name__in=collector_config_name_list)
        if collector_scenario_id_list:
            qs = qs.filter(collector_scenario_id__in=collector_scenario_id_list)
        if created_by_list:
            qs = qs.filter(created_by__in=created_by_list)
        if updated_by_list:
            qs = qs.filter(updated_by__in=updated_by_list)
        if table_id_list:
            # 存储名查询，忽略前缀
            query = Q()
            for table_id in table_id_list:
                query |= Q(table_id__endswith=table_id)
            qs = qs.filter(query)

        collector_configs = qs.values()
        collector_configs = CollectorHandler.add_cluster_info(collector_configs)

        tmp_result_list = []
        collector_id_list = []
        # 添加collector_scenario_name采集场景名称. 如果storage_cluster_name存在则进行过滤
        for collector_config in collector_configs:
            if storage_cluster_name_list and collector_config["storage_cluster_name"] not in storage_cluster_name_list:
                continue
            tmp_result_list.append(collector_config)
            collector_id_list.append(collector_config["collector_config_id"])

        # 获取采集状态信息
        collector_status_mappings = self.get_collector_subscription_status(
            collector_id_list,
        )
        result_list = []
        # 添加status_name采集状态, 如果status_name存在则进行过滤
        for item in tmp_result_list:
            status_name = collector_status_mappings.get(item["collector_config_id"], {}).get("status_name", "")
            if status_name_list and status_name not in status_name_list:
                continue
            item["status_name"] = status_name
            result_list.append(item)
        result_list = CollectorHandler.add_tags_info(result_list)
        return result_list

    def get_log_index_set_info(
        self,
        scenario_id_list: list = None,
        index_set_name_list: list = None,
        result_table_id_list: list = None,
        created_by_list: list = None,
        updated_by_list: list = None,
        storage_cluster_name_list: list = None,
    ) -> list[dict]:
        """
         获取索引集内容
        :param scenario_id_list: 接入情景
        :param index_set_name_list: 索引集名名称
        :param result_table_id_list: 结果表ID
        :param created_by_list: 创建者
        :param updated_by_list: 创建者
        :param storage_cluster_name_list: 集群名
        """
        log_index_sets = LogIndexSet.objects.filter(collector_config_id__isnull=True, space_uid=self.space_uid).exclude(
            scenario_id=Scenario.LOG
        )
        if scenario_id_list:
            log_index_sets = log_index_sets.filter(scenario_id__in=scenario_id_list)
        if index_set_name_list:
            log_index_sets = log_index_sets.filter(index_set_name__in=index_set_name_list)
        if created_by_list:
            log_index_sets = log_index_sets.filter(created_at__in=created_by_list)
        if updated_by_list:
            log_index_sets = log_index_sets.filter(updated_by__in=updated_by_list)

        log_index_set_data = LogIndexSetData.objects.all()
        if result_table_id_list:
            log_index_set_data = log_index_set_data.filter(result_table_id__in=result_table_id_list)
        index_set_id_list = []
        log_index_set_data_mappings = defaultdict(list)
        for obj in log_index_set_data:
            log_index_set_data_mappings[obj.index_set_id].append(obj)
            index_set_id_list.append(obj.index_set_id)

        if result_table_id_list:
            log_index_sets = log_index_sets.filter(index_set_id__in=index_set_id_list)

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

        result_list = []
        for obj in log_index_sets:
            _index_set_id = obj.index_set_id
            index_set_data = log_index_set_data_mappings[_index_set_id]
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
        if storage_cluster_name_list:
            result_list = list(filter(lambda x: x["storage_cluster_name"] in storage_cluster_name_list, result_list))
        return result_list

    def get_log_collectors(self, data):
        """获取日志采集信息"""
        conditions = data.get("conditions", [])
        scenario_id_list = []
        name_list = []
        bk_data_name_list = []
        collector_scenario_id_list = []
        created_at_list = []
        updated_by_list = []
        status_name_list = []
        storage_cluster_name_list = []
        for item in conditions:
            if item["key"] == "scenario_id":
                scenario_id_list = item["value"]
            elif item["key"] == "name":
                name_list = item["value"]
            elif item["key"] == "bk_data_name":
                bk_data_name_list = item["value"]
            elif item["key"] == "collector_scenario_id":
                collector_scenario_id_list = item["value"]
            elif item["key"] == "created_at":
                created_at_list = item["value"]
            elif item["key"] == "updated_by":
                updated_by_list = item["value"]
            elif item["key"] == "status_name":
                status_name_list = item["value"]
            elif item["key"] == "storage_cluster_name":
                storage_cluster_name_list = item["value"]

        # 获取采集项信息
        collector_configs = self.get_collector_config_info(
            scenario_id_list=scenario_id_list,
            collector_config_name_list=name_list,
            table_id_list=bk_data_name_list,
            collector_scenario_id_list=collector_scenario_id_list,
            created_by_list=created_at_list,
            updated_by_list=updated_by_list,
            storage_cluster_name_list=storage_cluster_name_list,
            status_name_list=status_name_list,
        )

        lists_to_check = [
            collector_scenario_id_list,
            status_name_list,
        ]
        if any(chain.from_iterable(lists_to_check)):
            # 如果存在对采集名称、存储名、日志类型、采集状态不为空的查询,直接返回
            log_index_sets = []
        else:
            # 获取索引集信息
            log_index_sets = self.get_log_index_set_info(
                scenario_id_list=scenario_id_list,
                index_set_name_list=name_list,
                result_table_id_list=bk_data_name_list,
                created_by_list=created_at_list,
                updated_by_list=updated_by_list,
                storage_cluster_name_list=storage_cluster_name_list,
            )

        combined_data = collector_configs + log_index_sets
        combined_data = self.fetch_log_collector_data(combined_data)
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
