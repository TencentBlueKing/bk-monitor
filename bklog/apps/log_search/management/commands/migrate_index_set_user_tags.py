from django.core.management import BaseCommand, CommandError
from django.db import transaction

from apps.log_search.models import TAG_TYPE_USER, IndexSetTag, LogIndexSet
from bkm_space.utils import bk_biz_id_to_space_uid


class Command(BaseCommand):
    help = "Migrate user index-set tags to space scope"

    def add_arguments(self, parser):
        parser.add_argument("--space-uid", action="append", dest="space_uids", help="The space_uid to migrate.")
        parser.add_argument(
            "--bk-biz-id", action="append", dest="bk_biz_ids", type=int, help="The bk_biz_id to migrate."
        )
        parser.add_argument(
            "--all", action="store_true", default=False, help="Migrate all spaces that have index sets."
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            default=False,
            help="Only delete all unreferenced global user tags; do not migrate any space.",
        )
        parser.add_argument("--dry-run", action="store_true", default=False, help="Preview changes without writing.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cleanup = options["cleanup"]
        space_uids = self._get_space_uids(options)

        updated_index_sets = 0
        replaced_tag_refs = 0
        created_tags = 0

        self.stdout.write(f"Migrate space_uids={space_uids}, dry_run={dry_run}")

        with transaction.atomic():
            for space_uid in space_uids:
                result = self._migrate_space(space_uid)
                updated_index_sets += result["updated_index_sets"]
                replaced_tag_refs += result["replaced_tag_refs"]
                created_tags += result["created_tags"]

                self.stdout.write(
                    f"space_uid={space_uid}, index_sets={result['index_sets']}, "
                    f"updated={result['updated_index_sets']}, replaced={result['replaced_tag_refs']}, "
                    f"created={result['created_tags']}"
                )

            deleted_tags = self._delete_unreferenced_global_user_tags() if cleanup else 0

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(f"Updated index sets: {updated_index_sets}")
        self.stdout.write(f"Replaced user tag refs: {replaced_tag_refs}")
        self.stdout.write(f"Created user tags: {created_tags}")
        self.stdout.write(f"Deleted unreferenced global user tags: {deleted_tags}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run finished, no changes were written."))

    def _get_space_uids(self, options):
        space_uids = options["space_uids"] or []
        bk_biz_ids = options["bk_biz_ids"] or []
        migrate_all = options["all"]
        cleanup = options["cleanup"]

        mode_count = sum([bool(space_uids), bool(bk_biz_ids), migrate_all, cleanup])
        if mode_count != 1:
            raise CommandError("Please specify exactly one of --space-uid, --bk-biz-id, --all, or --cleanup.")

        if cleanup:
            return []

        if migrate_all:
            return list(
                LogIndexSet.objects.exclude(space_uid="")
                .order_by("space_uid")
                .values_list("space_uid", flat=True)
                .distinct()
            )

        if bk_biz_ids:
            space_uids = []
            for bk_biz_id in bk_biz_ids:
                space_uid = bk_biz_id_to_space_uid(bk_biz_id)
                if not space_uid:
                    raise CommandError(f"Cannot convert bk_biz_id={bk_biz_id} to space_uid.")
                space_uids.append(space_uid)

        if not all(space_uids):
            raise CommandError("space_uid cannot be empty.")
        return list(dict.fromkeys(space_uids))

    def _migrate_space(self, space_uid):
        index_sets = LogIndexSet.objects.filter(space_uid=space_uid)
        updated_index_sets = 0
        replaced_tag_refs = 0
        created_tags = 0

        for index_set in index_sets.iterator():
            old_tag_ids = [str(tag_id) for tag_id in index_set.tag_ids if tag_id]
            if not old_tag_ids:
                continue

            new_tag_ids = []
            changed = False

            for tag_id in old_tag_ids:
                tag = IndexSetTag.objects.filter(tag_id=tag_id, tag_type=TAG_TYPE_USER).first()
                if not tag or tag.space_uid == space_uid:
                    new_tag_ids.append(tag_id)
                    continue

                target_tag, created = IndexSetTag.objects.get_or_create(
                    space_uid=space_uid,
                    name=tag.name,
                    value=tag.value,
                    tag_type=TAG_TYPE_USER,
                    defaults={"color": tag.color},
                )

                new_tag_ids.append(str(target_tag.tag_id))
                changed = True
                replaced_tag_refs += 1
                if created:
                    created_tags += 1

            new_tag_ids = list(dict.fromkeys(new_tag_ids))
            if changed or new_tag_ids != old_tag_ids:
                updated_index_sets += 1
                index_set.tag_ids = new_tag_ids
                index_set.save(update_fields=["tag_ids"])

        return {
            "index_sets": index_sets.count(),
            "updated_index_sets": updated_index_sets,
            "replaced_tag_refs": replaced_tag_refs,
            "created_tags": created_tags,
        }

    def _delete_unreferenced_global_user_tags(self):
        referenced_tag_ids = set()
        # 软删除模型只重写了几个常用方法，这里需要手动过滤 is_deleted=False
        for tag_ids in LogIndexSet.objects.filter(is_deleted=False).values_list("tag_ids", flat=True).iterator():
            referenced_tag_ids.update(str(tag_id) for tag_id in tag_ids if tag_id)

        global_user_tag_ids = set(
            str(tag_id)
            for tag_id in IndexSetTag.objects.filter(tag_type=TAG_TYPE_USER, space_uid="").values_list(
                "tag_id", flat=True
            )
        )
        unreferenced_tag_ids = global_user_tag_ids - referenced_tag_ids
        if not unreferenced_tag_ids:
            return 0

        IndexSetTag.objects.filter(tag_id__in=[int(tag_id) for tag_id in unreferenced_tag_ids]).delete()
        return len(unreferenced_tag_ids)
