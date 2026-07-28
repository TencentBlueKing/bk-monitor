from django.db import migrations


TAG_TYPE_USER = "user"


def migrate_index_set_user_tags(apps, schema_editor):
    IndexSetTag = apps.get_model("log_search", "IndexSetTag")
    LogIndexSet = apps.get_model("log_search", "LogIndexSet")

    user_tags = list(
        IndexSetTag.objects.filter(tag_type=TAG_TYPE_USER).values("tag_id", "space_uid", "name", "value", "color")
    )
    user_tags_by_id = {str(tag["tag_id"]): tag for tag in user_tags}

    index_sets = LogIndexSet.objects.filter(is_deleted=False).exclude(space_uid="")
    target_tag_id_map = {}
    index_sets_to_update = []
    for index_set in index_sets.iterator(chunk_size=500):
        old_tag_ids = [str(tag_id) for tag_id in index_set.tag_ids if tag_id]
        if not old_tag_ids:
            continue

        new_tag_ids = []
        changed = False
        for tag_id in old_tag_ids:
            tag = user_tags_by_id.get(tag_id)
            if not tag or tag["space_uid"] == index_set.space_uid:
                new_tag_ids.append(tag_id)
                continue

            space_and_source_tag_id = (index_set.space_uid, tag_id)
            target_tag_id = target_tag_id_map.get(space_and_source_tag_id)
            if target_tag_id is None:
                target_tag, _ = IndexSetTag.objects.get_or_create(
                    space_uid=index_set.space_uid,
                    name=tag["name"],
                    value=tag["value"],
                    tag_type=TAG_TYPE_USER,
                    defaults={"color": tag["color"]},
                )
                target_tag_id = str(target_tag.tag_id)
                target_tag_id_map[space_and_source_tag_id] = target_tag_id

            new_tag_ids.append(target_tag_id)
            changed = True

        # 同一个索引集可能引用多个最终映射到同一空间标签的全局标签，
        # 在保持原有顺序的同时去除重复引用。
        new_tag_ids = list(dict.fromkeys(new_tag_ids))
        if changed or new_tag_ids != old_tag_ids:
            index_set.tag_ids = new_tag_ids
            index_sets_to_update.append(index_set)

    # 预期数据量不会过万，直接放到内存之后批量更新
    if index_sets_to_update:
        LogIndexSet.objects.bulk_update(index_sets_to_update, ["tag_ids"], batch_size=500)

    referenced_tag_ids = set()
    active_index_sets = LogIndexSet.objects.filter(is_deleted=False).values_list("tag_ids", flat=True)
    for tag_ids in active_index_sets.iterator(chunk_size=500):
        referenced_tag_ids.update(str(tag_id) for tag_id in tag_ids if tag_id)

    global_user_tag_ids = set(
        str(tag_id)
        for tag_id in IndexSetTag.objects.filter(tag_type=TAG_TYPE_USER, space_uid="").values_list("tag_id", flat=True)
    )
    unreferenced_tag_ids = global_user_tag_ids - referenced_tag_ids
    if unreferenced_tag_ids:
        IndexSetTag.objects.filter(tag_id__in=[int(tag_id) for tag_id in unreferenced_tag_ids]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0098_migrate_doris_tag_to_inner"),
    ]

    operations = [
        migrations.RunPython(migrate_index_set_user_tags, migrations.RunPython.noop),
    ]
