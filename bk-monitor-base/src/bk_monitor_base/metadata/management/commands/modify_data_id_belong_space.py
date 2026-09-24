from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.models import DataSource, Space


class Command(BaseCommand):
    def handle(self, *args, **options):
        space_uid = options["space_uid"]
        data_ids = options["data_ids"]

        if not data_ids:
            self.stdout.write("data_ids can not be empty")
            return
        if space_uid:
            space_type_id, space_id = space_uid.split("__")
            try:
                space = Space.objects.get(space_id=space_id, space_type_id=space_type_id)
            except Space.DoesNotExist:
                self.stdout.write(f"can not find space {space_type_id}__{space_id}")
                return
            DataSource.objects.filter(bk_data_id__in=data_ids).update(space_uid=space.space_uid)
        else:
            DataSource.objects.filter(bk_data_id__in=data_ids).update(space_uid="")

        self.stdout.write(f"data_id's space_uid modified to {space_uid}")

    def add_arguments(self, parser):
        parser.add_argument("--space_uid", type=str, required=False, default="", help="空间UID")
        parser.add_argument("--data_ids", type=int, nargs="*", required=True, help="要修改的DataID")
