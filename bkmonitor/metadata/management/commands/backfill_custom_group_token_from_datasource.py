"""
将 proxy/JSON 自定义上报分组的 DataSource.token 回填到 CustomGroupBase.token。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from metadata.models.custom_report.event import EventGroup
from metadata.models.custom_report.log import LogGroup
from metadata.models.custom_report.time_series import TimeSeriesGroup
from metadata.models.data_source import DataSource
from monitor_web.models.custom_report import CustomTSTable


class Command(BaseCommand):
    help = "Backfill CustomGroupBase.token from DataSource.token for proxy/json custom report groups."

    def add_arguments(self, parser):
        parser.add_argument("--bk-data-id", type=int, default=None, help="指定数据 ID，仅回填单个自定义分组")
        parser.add_argument("--bk-tenant-id", type=str, default=None, help="指定租户 ID")
        parser.add_argument("--dry-run", action="store_true", help="只打印将要回填的数据，不实际写库")

    def handle(self, *args, **options):
        bk_data_id = options["bk_data_id"]
        bk_tenant_id = options["bk_tenant_id"]
        dry_run = options["dry_run"]

        data_source_qs = DataSource.objects.exclude(token="")
        if bk_data_id is not None:
            data_source_qs = data_source_qs.filter(bk_data_id=bk_data_id)
        if bk_tenant_id is not None:
            data_source_qs = data_source_qs.filter(bk_tenant_id=bk_tenant_id)

        data_source_token_map = {
            (item["bk_data_id"], item["bk_tenant_id"]): item["token"]
            for item in data_source_qs.values("bk_data_id", "bk_tenant_id", "token")
        }
        if not data_source_token_map:
            self.stdout.write(self.style.WARNING("No available DataSource.token found."))
            return

        event_count = self.backfill_model(EventGroup, data_source_token_map, dry_run)
        log_count = self.backfill_model(LogGroup, data_source_token_map, dry_run)
        time_series_count = self.backfill_json_time_series(data_source_token_map, dry_run)

        action = "Would backfill" if dry_run else "Backfilled"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} custom group token: event_count={event_count}, log_count={log_count}, "
                f"time_series_count={time_series_count}"
            )
        )

    def backfill_model(self, model, data_source_token_map: dict[tuple[int, str], str], dry_run: bool) -> int:
        groups = []
        qs = model.objects.filter(token="", bk_data_id__in=[key[0] for key in data_source_token_map.keys()])
        for group in qs:
            token = data_source_token_map.get((group.bk_data_id, group.bk_tenant_id))
            if not token:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skip {model.__name__}: group_id={group.custom_group_id}, "
                        f"bk_data_id={group.bk_data_id}, bk_tenant_id={group.bk_tenant_id}, reason=empty_token"
                    )
                )
                continue
            group.token = token
            groups.append(group)

        if groups and not dry_run:
            with transaction.atomic():
                model.objects.bulk_update(groups, ["token"])
        return len(groups)

    def backfill_json_time_series(self, data_source_token_map: dict[tuple[int, str], str], dry_run: bool) -> int:
        groups = []
        json_group_ids = set(
            CustomTSTable.objects.filter(protocol="json").values_list("time_series_group_id", flat=True)
        )
        qs = TimeSeriesGroup.objects.filter(
            token="",
            time_series_group_id__in=json_group_ids,
            bk_data_id__in=[key[0] for key in data_source_token_map.keys()],
        )
        for group in qs:
            token = data_source_token_map.get((group.bk_data_id, group.bk_tenant_id))
            if not token:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skip TimeSeriesGroup: group_id={group.custom_group_id}, "
                        f"bk_data_id={group.bk_data_id}, bk_tenant_id={group.bk_tenant_id}, reason=empty_token"
                    )
                )
                continue
            group.token = token
            groups.append(group)

        if groups and not dry_run:
            with transaction.atomic():
                TimeSeriesGroup.objects.bulk_update(groups, ["token"])
        return len(groups)
