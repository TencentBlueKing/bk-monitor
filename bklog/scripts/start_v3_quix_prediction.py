"""在日志平台后端环境启动一个原索引的 Quix 预测。

从含 manage.py 的目录执行
    PYTHONPATH=. python /path/to/start_v3_quix_prediction.py --index-id 42

指定 --kafka-cluster-id 可在接流前选择聚类集群。BKFara 会校验原任务状态及新旧 Topic。
退出码 0 表示已收到启动回执，75 表示迁移材料尚未就绪，可用同一命令重试。
"""

import argparse
import json
import os
import sys


def start_prediction(index_id: int, *, kafka_cluster_id: int | None = None) -> dict:
    from django.conf import settings
    from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

    from apps.api import BkFaraApi
    from apps.log_clustering.models import ClusteringConfig
    from apps.log_search.models import LogIndexSet, Space

    if index_id < 1:
        raise ValueError("请指定原日志索引集的正整数 ID")
    if kafka_cluster_id is not None and (type(kafka_cluster_id) is not int or not 0 < kafka_cluster_id < 2**63):
        raise ValueError("请指定有效的 Kafka 集群编号")
    try:
        index = LogIndexSet.objects.get(index_set_id=index_id)
        # get_by_index_set_id 也会匹配派生的聚类索引，此处只使用 V3 原索引。
        legacy = ClusteringConfig.objects.get(index_set_id=index_id)
    except (ObjectDoesNotExist, MultipleObjectsReturned) as exc:
        raise ValueError(f"索引 {index_id} 未找到唯一的原索引和 V3 聚类配置") from exc
    if not legacy.access_finished or not legacy.model_output_rt:
        raise ValueError(f"索引 {index_id} 的 V3 聚类接入尚未完成或缺少原预测输出结果表")
    if legacy.collector_config_id is not None and legacy.collector_config_id != index.collector_config_id:
        raise ValueError(f"索引 {index_id} 的采集项与 V3 聚类配置不一致")

    tenant = Space.get_tenant_id(space_uid=index.space_uid, is_need_default=not settings.ENABLE_MULTI_TENANT_MODE)
    if not tenant or (settings.ENABLE_MULTI_TENANT_MODE and not index.space_uid):
        raise ValueError(f"索引 {index_id} 缺少所属空间的租户信息")
    source = {"index_id": str(index_id), "v3_source_scope": legacy.model_output_rt}
    key = f"bklog-v3-predict-{index_id}"
    if kafka_cluster_id is not None:
        source["kafka_cluster_id"] = kafka_cluster_id
        key = f"{key}-kafka-{kafka_cluster_id}"
    result = BkFaraApi.create_task(
        {**source, "expected_tenant_id": tenant, "Idempotency-Key": key},
        request_cookies=False,
    )
    if not isinstance(result, dict):
        raise ValueError(f"索引 {index_id} 收到无法识别的 BKFara 回执")
    if result.get("status") == "WAITING_FOR_SYNC" and result.get("reason"):
        return {**source, "status": result["status"], "reason": result["reason"]}
    if (
        result.get("status") != "ADOPTED"
        or result.get("tenant_id") != tenant
        or result.get("index_id") != source["index_id"]
        or result.get("v3_source_scope") != source["v3_source_scope"]
        or not result.get("task_id")
    ):
        raise ValueError(f"索引 {index_id} 未收到与原索引、租户和模型来源一致的启动回执")
    if kafka_cluster_id is not None and (
        type(result.get("kafka_cluster_id")) is not int or result["kafka_cluster_id"] != kafka_cluster_id
    ):
        raise ValueError(f"索引 {index_id} 未收到与指定集群 {kafka_cluster_id} 一致的启动回执")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="仅启动指定原日志索引的 Quix 预测")
    parser.add_argument("--index-id", type=int, required=True, help="原日志索引集 ID")
    parser.add_argument("--kafka-cluster-id", type=int, help="接流前使用的已登记聚类 Kafka 集群编号")
    args = parser.parse_args(argv)

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    django.setup()
    from apps.exceptions import ApiRequestError, ApiResultError

    try:
        result = start_prediction(args.index_id, kafka_cluster_id=args.kafka_cluster_id)
    except (ValueError, ApiRequestError, ApiResultError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 75 if result["status"] == "WAITING_FOR_SYNC" else 0


if __name__ == "__main__":
    sys.exit(main())
