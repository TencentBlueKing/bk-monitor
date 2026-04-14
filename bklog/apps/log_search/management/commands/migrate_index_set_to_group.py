"""
按业务手动将索引集迁移为索引组

用法:
    # 迁移指定业务
    python manage.py migrate_index_set_to_group --bk_biz_id=2

    # 全量迁移所有业务
    python manage.py migrate_index_set_to_group --all

    # 回滚指定业务
    python manage.py migrate_index_set_to_group --bk_biz_id=2 --rollback

    # 回滚全量
    python manage.py migrate_index_set_to_group --all --rollback
"""

from django.core.management import BaseCommand

from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import IndexSetDataType
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from bkm_space.utils import bk_biz_id_to_space_uid


class Command(BaseCommand):
    help = "Migrate index sets to index groups"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bk_biz_id",
            type=str,
            required=False,
            default=None,
            help="Mutually exclusive with --all",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Migrate all biz. Mutually exclusive with --bk_biz_id",
        )
        parser.add_argument(
            "--rollback",
            action="store_true",
            default=False,
            help="Rollback mode: revert migrated index groups back to index sets",
        )

    def handle(self, *args, **options):
        bk_biz_id_str = options["bk_biz_id"]
        migrate_all = options["all"]
        rollback = options["rollback"]

        if not bk_biz_id_str and not migrate_all:
            self.stderr.write(self.style.ERROR("Error: please specify --bk_biz_id or --all"))
            return

        if bk_biz_id_str and migrate_all:
            self.stderr.write(self.style.ERROR("Error: --bk_biz_id and --all are mutually exclusive"))
            return

        if migrate_all:
            self.stdout.write(self.style.WARNING("Full migration mode: processing all biz"))
            space_uids = None
        else:
            try:
                bk_biz_id = int(bk_biz_id_str.strip())
            except ValueError:
                self.stderr.write(
                    self.style.ERROR("Error: invalid bk_biz_id, must be an integer (e.g. --bk_biz_id=-5)")
                )
                return

            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
            if not space_uid:
                self.stderr.write(
                    self.style.ERROR(f"Error: cannot convert bk_biz_id={bk_biz_id} to space_uid, biz may not exist")
                )
                return
            self.stdout.write(f"bk_biz_id={bk_biz_id} -> space_uid={space_uid}")
            space_uids = [space_uid]

        if rollback:
            self._rollback(space_uids)
        else:
            self._migrate(space_uids)

    def _get_index_set_queryset(self, space_uids, is_group):
        """获取索引集查询集，space_uids 为 None 时不按 space_uid 过滤（全量模式）"""
        qs = LogIndexSet.objects.filter(
            scenario_id=Scenario.LOG,
            collector_config_id__isnull=True,
            is_group=is_group,
        )
        if space_uids is not None:
            qs = qs.filter(space_uid__in=space_uids)
        return qs

    def _migrate(self, space_uids):
        """将符合条件的索引集转为索引组"""
        index_sets = self._get_index_set_queryset(space_uids, is_group=False)

        if not index_sets.exists():
            self.stdout.write(self.style.WARNING("No eligible index sets found, nothing to migrate"))
            return

        self.stdout.write(f"\nFound {index_sets.count()} index set(s) to migrate")

        # 建立映射：result_table_id -> CollectorConfig 对应的 index_set_id
        rt_id_to_index_set_id = dict(
            CollectorConfig.objects.filter(
                table_id__isnull=False,
                index_set_id__isnull=False,
            )
            .exclude(table_id="")
            .values_list("table_id", "index_set_id")
        )

        total_created = 0
        total_migrated = 0
        skip_count = 0

        for index_set in index_sets:
            log_index_data_list = list(LogIndexSetData.objects.filter(index_set_id=index_set.index_set_id))

            self.stdout.write(
                f"\nProcessing index_set_id={index_set.index_set_id}, "
                f"name={index_set.index_set_name}, space_uid={index_set.space_uid}"
            )

            to_create = []
            for index_data in log_index_data_list:
                # 通过 result_table_id 找到对应的采集项索引集ID
                mapped_index_set_id = rt_id_to_index_set_id.get(index_data.result_table_id)
                if not mapped_index_set_id:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  WARNING: no collector index set found for "
                            f"result_table_id={index_data.result_table_id}, skipped"
                        )
                    )
                    skip_count += 1
                    continue

                self.stdout.write(
                    f"  result_table_id={index_data.result_table_id} -> "
                    f"mapped to collector index_set_id={mapped_index_set_id}"
                )

                to_create.append(
                    LogIndexSetData(
                        index_set_id=index_set.index_set_id,
                        result_table_id=str(mapped_index_set_id),
                        scenario_id=index_data.scenario_id,
                        bk_biz_id=index_data.bk_biz_id,
                        type=IndexSetDataType.INDEX_SET.value,
                        apply_status="normal",
                    )
                )

            if to_create:
                LogIndexSetData.objects.bulk_create(to_create)
                total_created += len(to_create)

            index_set.is_group = True
            index_set.save(update_fields=["is_group"])
            total_migrated += 1
            self.stdout.write(self.style.SUCCESS(f"  Migrated: created {len(to_create)} record(s), set is_group=True"))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: migrated {total_migrated} index set(s), "
                f"created {total_created} LogIndexSetData record(s), "
                f"skipped {skip_count} unmapped record(s)"
            )
        )

    def _rollback(self, space_uids):
        """回滚已迁移的索引组为索引集"""
        index_sets = self._get_index_set_queryset(space_uids, is_group=True)

        if not index_sets.exists():
            self.stdout.write(self.style.WARNING("No migrated index groups found, nothing to rollback"))
            return

        self.stdout.write(f"\nFound {index_sets.count()} index group(s) to rollback")

        total_deleted = 0
        total_rollback = 0

        for index_set in index_sets:
            index_set_data_qs = LogIndexSetData.objects.filter(index_set_id=index_set.index_set_id, type="index_set")

            self.stdout.write(
                f"\nProcessing index_set_id={index_set.index_set_id}, "
                f"name={index_set.index_set_name}, space_uid={index_set.space_uid}"
            )

            deleted_count = index_set_data_qs.count()
            index_set_data_qs.delete()
            index_set.is_group = False
            index_set.save(update_fields=["is_group"])

            total_deleted += deleted_count
            total_rollback += 1
            self.stdout.write(
                self.style.SUCCESS(f"  Rolled back: deleted {deleted_count} record(s), set is_group=False")
            )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: rolled back {total_rollback} index group(s), deleted {total_deleted} LogIndexSetData record(s)"
            )
        )
