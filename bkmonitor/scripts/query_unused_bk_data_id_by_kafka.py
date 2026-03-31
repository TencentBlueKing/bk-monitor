"""
查询指定 Kafka 集群中无用的 bk_data_id 并输出到 CSV 文件。

使用方式：
1. 在 `python manage.py shell_plus` / `ipython shell` 中执行
2. 调用 query_unused_bk_data_id_by_kafka(domain_names=["127.0.0.1", "kafka.example.com"])

输出字段：
- data_id
- data_name
- etl_config
- topic
- 所属业务ID
- 关联的BCS/自定义指标/自定义事件

命中条件：
1. datasource 所属 mq_cluster_id 在指定 Kafka 集群内
2. BCSClusterInfo.status 为 DELETED/deleted 的管理 data_id
3. CustomEventGroup.origin_objects 中 is_deleted=True 的 data_id
4. CustomTSTable.origin_objects 中 is_deleted=True 的 data_id
5. etl_config=bk_flat_batch 且其关联 ResultTable.is_enable=False 的 data_id

输出文件：
- {output_file_prefix}_bkgse.csv
- {output_file_prefix}_bkdata.csv
"""

import csv
from collections import defaultdict

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from monitor_web.models import CustomEventGroup, CustomTSTable


def _parse_domain_names(raw_domain_names: list[str]) -> list[str]:
    """兼容两种输入形式：
    1. ["a.xx.com", "b.xx.com"]
    2. ["a.xx.com,b.xx.com"]
    同时去重并移除空白项。
    """
    domain_name_list = []
    seen: set[str] = set()
    for item in raw_domain_names:
        for name in item.split(","):
            name = name.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            domain_name_list.append(name)
    return domain_name_list


def _collect_candidate_data_sources(cluster_ids: list[int]):
    """按 mq_cluster_id 收集目标 Kafka 集群下的全部 datasource 及其 topic 信息。"""
    data_source_map = {
        item["bk_data_id"]: item
        for item in models.DataSource.objects.filter(mq_cluster_id__in=cluster_ids).values(
            "bk_data_id",
            "bk_tenant_id",
            "created_from",
            "data_name",
            "etl_config",
            "mq_cluster_id",
        )
    }

    topic_map = {
        item["bk_data_id"]: item["topic"]
        for item in models.KafkaTopicInfo.objects.filter(bk_data_id__in=data_source_map.keys()).values(
            "bk_data_id", "topic"
        )
    }

    return data_source_map, topic_map


def _match_deleted_bcs_clusters(candidate_ids, biz_ids_map, relation_map):
    """规则一：BCS 集群已删除时，四类管理 data_id 纳入候选清理对象。"""
    deleted_bcs_status = {
        models.BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
        models.BCSClusterInfo.CLUSTER_STATUS_DELETED,
    }
    bcs_data_id_fields = [
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
    ]

    for cluster in models.BCSClusterInfo.objects.filter(status__in=deleted_bcs_status).values(
        "cluster_id",
        "bk_biz_id",
        *bcs_data_id_fields,
    ):
        for field_name in bcs_data_id_fields:
            data_id = cluster[field_name]
            if data_id not in candidate_ids:
                continue
            biz_ids_map[data_id].add(cluster["bk_biz_id"])
            relation_map[data_id].add(f"BCS({cluster['cluster_id']}:{field_name})")


def _match_deleted_custom_event_groups(candidate_ids, biz_ids_map, relation_map):
    """规则二：自定义事件已软删除，但 bk_data_id 仍残留在 metadata。"""
    for group in CustomEventGroup.origin_objects.filter(is_deleted=True, bk_data_id__in=candidate_ids).values(
        "bk_data_id",
        "bk_biz_id",
        "name",
        "bk_event_group_id",
    ):
        biz_ids_map[group["bk_data_id"]].add(group["bk_biz_id"])
        relation_map[group["bk_data_id"]].add(f"自定义事件({group['name']}:{group['bk_event_group_id']})")


def _match_deleted_custom_ts_tables(candidate_ids, biz_ids_map, relation_map):
    """规则三：自定义指标已软删除，同样查询删除态记录。"""
    for table in CustomTSTable.origin_objects.filter(is_deleted=True, bk_data_id__in=candidate_ids).values(
        "bk_data_id",
        "bk_biz_id",
        "name",
        "time_series_group_id",
    ):
        biz_ids_map[table["bk_data_id"]].add(table["bk_biz_id"])
        relation_map[table["bk_data_id"]].add(f"自定义指标({table['name']}:{table['time_series_group_id']})")


def _match_disabled_flat_batch_result_tables(candidate_ids, data_source_map, biz_ids_map, relation_map):
    """规则四：bk_flat_batch 类型数据源关联的 ResultTable 已停用。"""
    flat_batch_data_sources = {
        data_id: data_source
        for data_id, data_source in data_source_map.items()
        if data_source["etl_config"] == "bk_flat_batch"
    }
    for dsrt in models.DataSourceResultTable.objects.filter(bk_data_id__in=flat_batch_data_sources.keys()).values(
        "bk_data_id",
        "bk_tenant_id",
        "table_id",
    ):
        data_source = flat_batch_data_sources.get(dsrt["bk_data_id"])
        if not data_source or data_source["bk_tenant_id"] != dsrt["bk_tenant_id"]:
            continue

        result_table = (
            models.ResultTable.objects.filter(
                table_id=dsrt["table_id"],
                bk_tenant_id=dsrt["bk_tenant_id"],
                is_enable=False,
            )
            .values("bk_biz_id")
            .first()
        )
        if not result_table:
            continue

        biz_ids_map[dsrt["bk_data_id"]].add(result_table["bk_biz_id"])
        relation_map[dsrt["bk_data_id"]].add(f"结果表已停用({dsrt['table_id']})")


def _write_csv_files(rows_by_created_from, output_file_prefix: str):
    """按 created_from 分别输出 CSV 文件。"""
    headers = ["data_id", "data_name", "etl_config", "topic", "所属业务ID", "关联的BCS/自定义指标/自定义事件"]

    for created_from, rows in rows_by_created_from.items():
        output_file = f"{output_file_prefix}_{created_from}.csv"
        with open(output_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"已输出 {len(rows)} 条记录到 {output_file}")


def query_unused_bk_data_id_by_kafka(
    domain_names: list[str],
    output_file_prefix: str = "unless_used_data_id",
):
    """查询指定 Kafka 集群中无用的 bk_data_id 并输出到 CSV。

    :param domain_names: Kafka 集群的 domain_name 列表，例如 ["127.0.0.1", "kafka.example.com"]。
    :param output_file_prefix: 输出文件名前缀，最终文件名为 {prefix}_bkgse.csv / {prefix}_bkdata.csv。
    """
    domain_names = _parse_domain_names(domain_names)
    if not domain_names:
        raise ValueError("请至少提供一个 domain_name")

    # 第一步：找出目标 Kafka 集群
    clusters = list(
        models.ClusterInfo.objects.filter(
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
            domain_name__in=domain_names,
        ).values("cluster_id", "domain_name")
    )
    if not clusters:
        raise ValueError(f"未查询到指定 Kafka 集群: {', '.join(domain_names)}")

    found_domain_names = {item["domain_name"] for item in clusters}
    missing_domain_names = [name for name in domain_names if name not in found_domain_names]
    if missing_domain_names:
        print(f"未命中的 Kafka 集群: {', '.join(missing_domain_names)}")

    # 第二步：收集候选 datasource
    cluster_ids = [item["cluster_id"] for item in clusters]
    data_source_map, topic_map = _collect_candidate_data_sources(cluster_ids)

    candidate_ids = set(data_source_map.keys())
    biz_ids_map: defaultdict[int, set] = defaultdict(set)
    relation_map: defaultdict[int, set] = defaultdict(set)

    # 第三步：逐条规则匹配
    _match_deleted_bcs_clusters(candidate_ids, biz_ids_map, relation_map)
    _match_deleted_custom_event_groups(candidate_ids, biz_ids_map, relation_map)
    _match_deleted_custom_ts_tables(candidate_ids, biz_ids_map, relation_map)
    _match_disabled_flat_batch_result_tables(candidate_ids, data_source_map, biz_ids_map, relation_map)

    # 第四步：汇总输出
    rows_by_created_from = {
        DataIdCreatedFromSystem.BKGSE.value: [],
        DataIdCreatedFromSystem.BKDATA.value: [],
    }
    for data_id in sorted(candidate_ids):
        relations = sorted(relation_map.get(data_id, set()))
        if not relations:
            continue

        data_source = data_source_map[data_id]
        biz_ids = sorted(biz_ids_map.get(data_id, set()))
        row = [
            str(data_id),
            data_source["data_name"],
            data_source["etl_config"],
            topic_map.get(data_id, ""),
            ",".join(str(biz_id) for biz_id in biz_ids),
            "; ".join(relations),
        ]

        created_from = data_source["created_from"]
        if created_from in rows_by_created_from:
            rows_by_created_from[created_from].append(row)
        else:
            rows_by_created_from[DataIdCreatedFromSystem.BKGSE.value].append(row)

    _write_csv_files(rows_by_created_from, output_file_prefix)
