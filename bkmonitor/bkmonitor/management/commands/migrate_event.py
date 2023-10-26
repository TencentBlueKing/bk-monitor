# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand

from bkmonitor.documents import AlertDocument
from bkmonitor.models import Event
from constants.alert import EventStatus


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("-d", "--days", default=30, help="Data of param(days) ago will be migrated")
        parser.add_argument("-s", "--size", default=100, help="Data size stored at one time, less than 1000")

    def handle(self, days, size, **kwargs):
        days = int(days)
        size = int(size)
        size = 1000 if size > 1000 else size
        create_time = datetime.now(tz=timezone.utc) - timedelta(days=days)
        print("start to migrate events data from  {} to now".format(create_time.strftime("%Y-%m-%d %H:%M:%S")))
        events = Event.objects.filter(
            status__in=[EventStatus.CLOSED, EventStatus.RECOVERED], create_time__gte=create_time
        ).order_by("-create_time")
        total_count = events.count()
        failed_count = 0

        ilm = AlertDocument.get_lifecycle_manager()
        index_info = ilm.current_index_info()
        last_index_name = ilm.make_index_name(index_info["datetime_object"], index_info["index"])
        existed_write_alias = []
        succeed_count = 0
        for index in range(0, total_count, size):
            new_alerts = []
            for event in events[index : index + size]:
                try:
                    new_dimensions = []
                    try:
                        origin_strategy = event.origin_strategy
                    except Exception:
                        origin_strategy = event.origin_config
                    dimension_dict = event.origin_alarm["data"]["dimensions"]
                    for key, dimension in event.origin_alarm["dimension_translation"].items():
                        if key == "bk_topo_node":
                            continue
                        new_dimension = {
                            "key": key,
                            "value": dimension.get("value", ""),
                            "display_key": dimension.get("display_name", key),
                            "display_value": dimension.get("display_value", dimension.get("value", "")),
                        }
                        new_dimensions.append(new_dimension)
                    try:
                        metric_id = origin_strategy["items"][0]["query_configs"][0]["metric_id"]
                    except Exception:  # noqa
                        print(f"failed get metric id for event({event.id})")
                        metric_id = ""

                    target_type = (event.target_key.split("|")[0] if event.target_key else "other_rt",)

                    alert_event = {
                        "bk_biz_id": event.bk_biz_id,
                        "data_type": "event",
                        "target_type": target_type,
                        "target": "",
                        "category": origin_strategy.get("scenario", "other_rt"),
                        "description": event.anomaly_message,
                        "tags": new_dimensions,
                        "metric": [metric_id],
                        "plugin_id": "bkmonitor",
                    }
                    alert_event.update(dimension_dict)
                    new_alert = AlertDocument(
                        **{
                            # 创建时间
                            "create_time": int(event.create_time.timestamp()),
                            # 开始时间
                            "begin_time": int(event.begin_time.timestamp()),
                            # 结束时间
                            "end_time": int(event.end_time.timestamp()),
                            # 最近异常时间
                            "latest_time": int(event.end_time.timestamp()),
                            # 第一次异常时间
                            "first_anomaly_time": int(event.begin_time.timestamp()),
                            # 延续时常
                            "duration": int(event.end_time.timestamp()) - int(event.begin_time.timestamp()),
                            # 告警级别
                            "severity": event.level,
                            # 业务ID
                            "bk_biz_id": event.bk_biz_id,
                            # 策略ID
                            "strategy_id": event.strategy_id,
                            # 状态
                            "status": event.status,
                            # 是否处理
                            "is_handled": bool(event.notify_status),
                            # 告警名称
                            "alert_name": origin_strategy.get("name", ""),
                            # 其他信息，包含origin_alarm和策略快照
                            "extra_info": {"origin_alarm": event.origin_alarm, "strategy": origin_strategy},
                            # 告警ID
                            "id": "{}{}".format(int(event.create_time.timestamp()), event.id),
                            # 是否已确认
                            "is_ack": event.is_ack,
                            # 是否屏蔽
                            "is_shielded": event.is_shielded,
                            # 维度
                            "dimensions": new_dimensions,
                            # 去重信息
                            "dedupe_md5": event.event_id,
                            # 告警最近异常点部分信息
                            "event": alert_event,
                            "seq_id": event.id,
                        }
                    )
                    alias_time_str = event.create_time.strftime(ilm.date_format)
                    write_alias_name = f"write_{alias_time_str}_{ilm.index_name}"
                    read_alias_name = f"{ilm.index_name}_{alias_time_str}_read"
                    if write_alias_name not in existed_write_alias:
                        # 不存在的写别名，需要重新创建
                        try:
                            index_list = ilm.es_client.indices.get_alias(name=write_alias_name).keys()
                            print(f"existed index {write_alias_name} for index_list", index_list)
                        except Exception:
                            index_list = []
                        if not index_list:
                            ilm.es_client.indices.update_aliases(
                                body={
                                    "actions": [
                                        {"add": {"index": last_index_name, "alias": write_alias_name}},
                                        {"add": {"index": last_index_name, "alias": read_alias_name}},
                                    ]
                                }
                            )
                            print(f"create write index {write_alias_name} to index f{last_index_name}")
                        existed_write_alias.append(write_alias_name)
                    new_alerts.append(new_alert)
                except Exception as error:
                    failed_count += 1
                    print(f"migrate event data  partial failed, {str(error)}")

            try:
                AlertDocument.bulk_create(new_alerts, action="upsert")
                succeed_count += len(new_alerts)
            except Exception as error:
                failed_count += len(new_alerts)
                print(f"save alert data partial failed, {str(error)[:1000]}")
        print(
            f"end to migrate events data total_count({total_count}),"
            f" succeed_count({succeed_count}) failed_count({failed_count})，"
            f" create alias f{existed_write_alias}, real index f{last_index_name}"
        )
